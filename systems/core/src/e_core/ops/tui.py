"""ops/tui: HeaderTui — the agnostic retro masthead for any Textual app.

Usage, in any app:

    from ops.tui import HeaderTui

    yield HeaderTui()                        # E-TEMPLATES / eager (sub at 1/4 the title scale)
    yield HeaderTui("mi app", "beta")        # MI APP / beta  (main always uppercase)
    yield HeaderTui("X", "", color="#ff8800", max_height=12, sub_scale=1)

Scales to the available width and height in integer steps, never overflows the terminal,
and falls back to a framed compact line when not even the minimum scale fits."""

from functools import lru_cache

from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

##### DEFAULTS #####
COLOR: str = "#0277bd"  # dark sky blue: letters and frame
MAX_SCALE: int = 40
MIN_WIDTH: int = 5
SUB_RATIO: int = 4  # the sub line is drawn at a quarter of the title scale: a tagline, not a second logo

##### FONTS #####
UPPER_SPEC: str = """
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
"""
LOWER_SPEC: str = """
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
"""
UPPER: dict[str, tuple[str, ...]] = {
    key: tuple(rows.split("/")) for item in UPPER_SPEC.split("\n") if item for key, rows in [item.split(" ", 1)]
}
UPPER[" "] = ("..",) * 5
UPPER["/"] = ("..#", "..#", ".#.", "#..", "#..")
LOWER: dict[str, tuple[str, ...]] = {
    key: tuple(rows.split("/")) for item in LOWER_SPEC.split("\n") if item for key, rows in [item.split(" ", 1)]
}

BLANK: tuple[str, ...] = ("..",) * 5
HALF: dict[tuple[bool, bool], str] = {
    (False, False): " ",
    (True, False): "▀",
    (False, True): "▄",
    (True, True): "█",
}


##### TYPES #####
class HeaderTui(Widget):
    """The agnostic retro masthead: a scalable block logo over a frame, on black.

    Args:
        main: the headline text, always rendered uppercase.
        sub: the small line beneath (default "eager"; empty hides it).
        color: the stroke color of letters and frame.
        max_height: growth cap only - a float (0-1) is a fraction of the terminal height,
            an int is rows. The smallest scale is always kept if it fits the width.
        sub_scale: pixel cell of the small line; None keeps the automatic title/SUB_RATIO.
    """

    DEFAULT_CSS = """
    HeaderTui {
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
        sub_scale: int | None = None,
        name: str | None = None,
        id: str | None = None,  # noqa: A002 — textual's widget contract
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.logo_color = color
        self.max_height = max_height
        self.sub_scale = sub_scale
        self.main = main
        self.sub = sub

    ############################################################

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_cells(glyphs: list[tuple[str, ...]]) -> int:
        """Width in pixels of a glyph row: one column of separation between glyphs."""
        return sum(len(glyph[0]) for glyph in glyphs) + max(len(glyphs) - 1, 0)

    @staticmethod
    def _common_glyphs(text: str, *fonts: dict[str, tuple[str, ...]]) -> list[tuple[str, ...]]:
        """Rows per character, from the first font that knows it; unknown characters fall back to BLANK."""
        return [next((font[ch] for font in fonts if ch in font), BLANK) for ch in text]

    @staticmethod
    def _common_layout(
        tcells: int, scells: int, tc: int, sub_tc: int | None = None
    ) -> tuple[int, int, int, int, int, int]:
        """(sub-cell, border, padding, gap, width, height) in pixels at title scale `tc`.

        `sub_tc` forces the sub scale; otherwise it is title scale / SUB_RATIO (at least 1).
        The border tracks the sub stroke; padding proportional."""
        tw = tcells * tc
        ec = max(1, tc // SUB_RATIO) if sub_tc is None else max(1, sub_tc)
        match scells:
            ### the sub never outgrows the title width.
            case int() if scells and ec * scells > tw:
                ec = max(1, tw // scells)
            case _:
                pass
        bt, pad = ec, 2 * tc
        inner = max(tw, scells * ec)
        gap = 2 * tc if scells else 0
        sh = 5 * ec if scells else 0
        width = inner + 2 * (pad + bt)
        height = 5 * tc + gap + sh + 2 * (pad + bt)
        return ec, bt, pad, gap, width, height + height % 2

    @staticmethod
    def _common_bitmap(glyphs: list[tuple[str, ...]], cell: int) -> list[list[bool]]:
        """Pixel grid at scale `cell`: every glyph row followed by a blank separator, stretched on both axes."""
        lines = [[on for glyph in glyphs for ch in (*glyph[row], ".") for on in [ch == "#"] * cell] for row in range(5)]
        return [line[: HeaderTui._common_cells(glyphs) * cell] for line in lines for _ in range(cell)]

    @staticmethod
    def _common_compact(main: str, sub: str, width: int) -> tuple[str, ...]:
        """The minimum version (framed plain text) for when not even scale 1 fits."""
        match width < MIN_WIDTH:
            case True:
                return (main[: max(width, 0)],)
            case _:
                return (
                    "█" * width,
                    *(f"█ {text[: width - 4].center(width - 4)} █" for text in (main, sub) if text),
                    "█" * width,
                )

    @staticmethod
    def _common_pick(tcells: int, scells: int, avail_w: int, max_rows: int, sub_tc: int | None = None) -> int | None:
        """The largest integer title scale that fits width and height; None when scale 1 does not fit the width."""
        match next(
            (
                tc
                for tc in range(MAX_SCALE, 0, -1)
                if (fit := HeaderTui._common_layout(tcells, scells, tc, sub_tc))[4] <= avail_w
                and fit[5] // 2 <= max_rows
            ),
            None,
        ):
            case int() as scale:
                return scale
            ### the smallest scale is always kept when it fits the width, even if it overgrows the height.
            case _:
                return 1 if HeaderTui._common_layout(tcells, scells, 1, sub_tc)[4] <= avail_w else None

    @staticmethod
    @lru_cache(maxsize=64)
    def _common_art(main: str, sub: str, tc: int, sub_tc: int | None = None) -> tuple[str, ...]:
        """The full logo (frame + title + sub) as half-block text rows."""
        tg, sg = HeaderTui._common_glyphs(main, UPPER), HeaderTui._common_glyphs(sub, LOWER, UPPER)
        ec, bt, pad, gap, width, height = HeaderTui._common_layout(
            HeaderTui._common_cells(tg), HeaderTui._common_cells(sg), tc, sub_tc
        )
        title = HeaderTui._common_bitmap(tg, tc)
        subbmp = HeaderTui._common_bitmap(sg, ec) if sg else []
        th, sh = len(title), len(subbmp)
        canvas = [
            [x < bt or x >= width - bt or y < bt or y >= height - bt for x in range(width)] for y in range(height)
        ]

        def _blit(src: list[list[bool]], ox: int, oy: int) -> None:
            for y, row in enumerate(src):
                for x, on in enumerate(row):
                    match on:
                        case True:
                            canvas[oy + y][ox + x] = True
                        case _:
                            pass

        area = height - 2 * (pad + bt)
        oy = bt + pad + (area - (th + gap + sh)) // 2
        _blit(title, (width - len(title[0])) // 2, oy)
        ### an empty sub blits nothing: the offset guard is the ternary, the call stays unconditional.
        _blit(subbmp, (width - len(subbmp[0]) if subbmp else 0) // 2, oy + th + gap)

        return tuple("".join(HALF[(canvas[y][x], canvas[y + 1][x])] for x in range(width)) for y in range(0, height, 2))

    def _common_max_rows(self) -> int:
        """Row cap from `max_height`: an int is rows, a float a fraction of the terminal height."""
        match self.max_height:
            case int() as rows:
                return rows
            case ratio:
                return max(1, int(self.app.size.height * ratio))

    def _common_lines(self, width: int) -> tuple[str, ...]:
        """Every half-block row of the masthead at this width: the one source for render and height."""
        tg = HeaderTui._common_glyphs(self.main, UPPER)
        sg = HeaderTui._common_glyphs(self.sub, LOWER, UPPER)
        tc = HeaderTui._common_pick(
            HeaderTui._common_cells(tg), HeaderTui._common_cells(sg), width, self._common_max_rows(), self.sub_scale
        )
        match tc:
            case None:
                return HeaderTui._common_compact(self.main, self.sub, width)
            case scale:
                return HeaderTui._common_art(self.main, self.sub, scale, self.sub_scale)

    ############################################################

    ##### PUBLIC #####

    def validate_main(self, value: str) -> str:
        return value.upper()

    def get_content_height(self, container, viewport, width: int) -> int:  # noqa: ARG002 — textual's sizing contract
        return len(self._common_lines(width))

    def render(self) -> Text:
        width = self.size.width
        lines = self._common_lines(width)
        left = " " * max(0, (width - len(lines[0])) // 2)
        return Text(
            "\n".join(left + line for line in lines),
            style=Style(color=self.logo_color),
            no_wrap=True,
            overflow="crop",
        )
