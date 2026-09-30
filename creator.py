"""HeaderLogo: cabecera retro (años 90) para Textual.

Uso dentro de cualquier app Textual:

    from header_logo import HeaderLogo

    yield HeaderLogo()                      # E-TEMPLATES / eager
    yield HeaderLogo("mi app", "beta")      # MI APP / beta   (main siempre en mayúsculas)
    yield HeaderLogo("X", "", color="#ff8800", max_height=12)

Se adapta al ancho (y al alto) disponible: escala en pasos enteros, nunca se
sale de la terminal y, si ni siquiera cabe la versión mínima, cae a una
versión compacta de texto con marco.
"""
from __future__ import annotations

import argparse
import asyncio
from functools import lru_cache

from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Header, Static

COLOR = "#0277bd"  # azul celeste oscuro (letras y borde)
MAX_SCALE = 40


# ── Tipografías bitmap (# = píxel activo, 5 filas de alto) ───────────────
def _font(spec: str) -> dict[str, tuple[str, ...]]:
    out = {}
    for item in filter(None, spec.split("\n")):
        key, rows = item.split(" ", 1)
        out[key] = tuple(rows.split("/"))
    return out


UPPER = _font("""
A .#./#.#/###/#.#/#.#
B ##./#.#/##./#.#/##.
C .##/#../#../#../.##
D ##./#.#/#.#/#.#/##.
E ###/#../###/#../###
F ###/#../##./#../#..
G .##/#../#.#/#.#/.##
H #.#/#.#/###/#.#/#.#
I ###/.#./.#./.#./###
J ..#/..#/..#/#.#/.#.
K #.#/#.#/##./#.#/#.#
L #../#../#../#../###
M #...#/##.##/#.#.#/#...#/#...#
N #..#/##.#/#.##/#..#/#..#
O ###/#.#/#.#/#.#/###
P ###/#.#/###/#../#..
Q ###/#.#/#.#/###/..#
R ##./#.#/##./#.#/#.#
S ###/#../###/..#/###
T ###/.#./.#./.#./.#.
U #.#/#.#/#.#/#.#/###
V #.#/#.#/#.#/#.#/.#.
W #...#/#...#/#.#.#/##.##/#...#
X #.#/#.#/.#./#.#/#.#
Y #.#/#.#/.#./.#./.#.
Z ###/..#/.#./#../###
0 ###/#.#/#.#/#.#/###
1 .#./##./.#./.#./###
2 ###/..#/###/#../###
3 ###/..#/###/..#/###
4 #.#/#.#/###/..#/..#
5 ###/#../###/..#/###
6 ###/#../###/#.#/###
7 ###/..#/..#/.#./.#.
8 ###/#.#/###/#.#/###
9 ###/#.#/###/..#/###
- .../.../###/.../...
. .../.../.../.../.#.
! .#./.#./.#./.../.#.
: .../.#./.../.#./...
+ .../.#./###/.#./...
""")
UPPER[" "] = ("..",) * 5
UPPER["/"] = ("..#", "..#", ".#.", "#..", "#..")

LOWER = _font("""
a .##./...#/.###/#..#/.###
b #.../###./#..#/#..#/###.
c .###/#.../#.../#.../.###
d ...#/.###/#..#/#..#/.###
e .##./#..#/####/#.../.###
f .###/#.../###./#.../#...
g .###/#..#/.###/...#/###.
h #.../#.../###./#..#/#..#
i .#./.../.#./.#./.#.
j ..#/.../..#/#.#/.#.
k #..#/#.#./##../#.#./#..#
l ##./.#./.#./.#./###
m #...#/##.##/#.#.#/#...#/#...#
n ###./#..#/#..#/#..#/#..#
o .##./#..#/#..#/#..#/.##.
p ###./#..#/###./#.../#...
q .###/#..#/.###/...#/...#
r #.##/##../#.../#.../#...
s .###/#.../.##./...#/###.
t .#./###/.#./.#./.##
u #..#/#..#/#..#/#..#/.###
v #..#/#..#/#..#/.##./..#.
w #...#/#...#/#.#.#/##.##/#...#
x #..#/#..#/.##./#..#/#..#
y #..#/#..#/.###/...#/###.
z ####/...#/.##./#.../####
""")

BLANK = ("..",) * 5
HALF = {(False, False): " ", (True, False): "▀", (False, True): "▄", (True, True): "█"}


def _glyphs(text: str, *fonts: dict) -> list[tuple[str, ...]]:
    out = []
    for ch in text:
        for font in fonts:
            if ch in font:
                out.append(font[ch])
                break
        else:
            out.append(BLANK)
    return out


def _cells(glyphs: list) -> int:
    """Ancho en 'píxeles' de una fila de glifos (1 columna de separación entre ellos)."""
    return sum(len(g[0]) for g in glyphs) + max(len(glyphs) - 1, 0)


def _layout(tcells: int, scells: int, tc: int) -> tuple[int, int, int, int, int, int]:
    """(celda_sub, borde, padding, hueco, ancho, alto) en píxeles para la escala `tc`.

    Trazo del sub == borde; el título es ~1.5x más grueso; padding proporcional.
    """
    tw = tcells * tc
    ec = max(1, round(tc * 2 / 3))
    if scells:
        ec = max(1, min(ec, tw // scells))  # el sub nunca es más ancho que el título
    bt, pad = ec, 2 * tc
    inner = max(tw, scells * ec)
    gap = 2 * tc if scells else 0
    sh = 5 * ec if scells else 0
    width = inner + 2 * (pad + bt)
    height = 5 * tc + gap + sh + 2 * (pad + bt)
    return ec, bt, pad, gap, width, height + height % 2


def _bitmap(glyphs: list, cell: int) -> list[list[bool]]:
    grid = [[False] * (_cells(glyphs) * cell) for _ in range(5 * cell)]
    x0 = 0
    for g in glyphs:
        for r, line in enumerate(g):
            for c, ch in enumerate(line):
                if ch == "#":
                    for dy in range(cell):
                        row = grid[r * cell + dy]
                        for dx in range(cell):
                            row[(x0 + c) * cell + dx] = True
        x0 += len(g[0]) + 1
    return grid


@lru_cache(maxsize=64)
def _art(main: str, sub: str, tc: int) -> tuple[str, ...]:
    """Logo completo (marco + título + sub) como filas de texto con medios bloques."""
    tg, sg = _glyphs(main, UPPER), _glyphs(sub, LOWER, UPPER)
    ec, bt, pad, gap, width, height = _layout(_cells(tg), _cells(sg), tc)
    title = _bitmap(tg, tc)
    subbmp = _bitmap(sg, ec) if sg else []
    th, sh = len(title), len(subbmp)

    canvas = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            if x < bt or x >= width - bt or y < bt or y >= height - bt:
                canvas[y][x] = True

    def blit(src: list[list[bool]], ox: int, oy: int) -> None:
        for y, row in enumerate(src):
            for x, on in enumerate(row):
                if on:
                    canvas[oy + y][ox + x] = True

    area = height - 2 * (pad + bt)
    oy = bt + pad + (area - (th + gap + sh)) // 2
    blit(title, (width - len(title[0])) // 2, oy)
    if subbmp:
        blit(subbmp, (width - len(subbmp[0])) // 2, oy + th + gap)

    return tuple(
        "".join(HALF[(canvas[y][x], canvas[y + 1][x])] for x in range(width))
        for y in range(0, height, 2)
    )


def _compact(main: str, sub: str, width: int) -> tuple[str, ...]:
    """Versión mínima (texto con marco) para cuando no cabe ni la escala 1."""
    if width < 5:
        return (main[: max(width, 0)],)
    inner = width - 4
    rows = ["█" * width]
    rows += [f"█ {t[:inner].center(inner)} █" for t in (main, sub) if t]
    rows.append("█" * width)
    return tuple(rows)


def _pick(tcells: int, scells: int, avail_w: int, max_rows: int) -> int | None:
    """Mayor escala entera que cabe en ancho y alto; None si no cabe ni la 1."""
    if _layout(tcells, scells, 1)[4] > avail_w:
        return None
    tc = 1
    while tc < MAX_SCALE:
        *_, w, h = _layout(tcells, scells, tc + 1)
        if w > avail_w or h // 2 > max_rows:
            break
        tc += 1
    return tc


class HeaderLogo(Widget):
    """Logo retro escalable.

    Args:
        main: texto principal (se muestra siempre en MAYÚSCULAS).
        sub: texto pequeño de abajo (por defecto "eager"; "" para ocultarlo).
        color: color de letras y borde.
        max_height: tope de alto. Un float (0-1) es fracción del alto de la
            terminal; un int son filas. Sólo limita el crecimiento: la escala
            mínima se mantiene siempre que quepa en ancho.
    """

    DEFAULT_CSS = """
    HeaderLogo {
        width: 100%;
        height: auto;
        background: black;
    }
    """

    main = reactive("E-TEMPLATES", layout=True)
    sub = reactive("eager", layout=True)

    def __init__(
        self,
        main: str = "E-TEMPLATES",
        sub: str = "eager",
        *,
        color: str = COLOR,
        max_height: int | float = 0.6,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.logo_color = color
        self.max_height = max_height
        self.main = main
        self.sub = sub

    def validate_main(self, value: str) -> str:
        return value.upper()

    # -- tamaño ----------------------------------------------------------
    def _max_rows(self) -> int:
        m = self.max_height
        return int(m) if isinstance(m, int) else max(1, int(self.app.size.height * m))

    def _lines(self, width: int) -> tuple[str, ...]:
        tcells = _cells(_glyphs(self.main, UPPER))
        scells = _cells(_glyphs(self.sub, LOWER, UPPER))
        tc = _pick(tcells, scells, width, self._max_rows())
        if tc is None:
            return _compact(self.main, self.sub, width)
        return _art(self.main, self.sub, tc)

    def get_content_height(self, container, viewport, width: int) -> int:
        return len(self._lines(width))

    # -- dibujo ----------------------------------------------------------
    def render(self) -> Text:
        width = self.size.width
        lines = self._lines(width)
        left = " " * max(0, (width - len(lines[0])) // 2)
        return Text(
            "\n".join(left + line for line in lines),
            style=Style(color=self.logo_color),
            no_wrap=True,
            overflow="crop",
        )


# ── Demo ─────────────────────────────────────────────────────────────────
class RetroApp(App):
    """Aplicación de prueba en Textual con cabecera retro."""

    CSS = """
    Screen { background: black; }
    HeaderLogo { margin: 1 0; }
    #contenido { padding: 2; color: #888888; text-align: center; }
    """

    def __init__(self, main: str = "E-TEMPLATES", sub: str = "eager") -> None:
        super().__init__()
        self.logo_main, self.logo_sub = main, sub

    def compose(self) -> ComposeResult:
        yield Header()
        yield HeaderLogo(self.logo_main, self.logo_sub)
        yield Container(
            Static("Presiona [b]Q[/b] para salir de la aplicacion."),
            id="contenido",
        )
        yield Footer()


async def _shot(app: App, size: tuple[int, int], out: str) -> None:
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        print(app.save_screenshot(out))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Cabecera retro con logo escalable.")
    cli.add_argument("main", nargs="?", default="E-TEMPLATES", help="texto principal (se pasa a mayúsculas)")
    cli.add_argument("--sub", default="eager", help="texto pequeño inferior (def: eager)")
    cli.add_argument("--screenshot", metavar="PATH", help="render headless y exportar SVG")
    cli.add_argument("--size", default="120x32", help="anchoxalto del render headless (def: 120x32)")
    args = cli.parse_args()
    app = RetroApp(args.main, args.sub)
    if args.screenshot:
        asyncio.run(_shot(app, tuple(map(int, args.size.split("x"))), args.screenshot))
    else:
        app.run()