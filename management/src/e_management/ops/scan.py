"""ops.scan: the dynamic survey of the common tree — areas and units discovered by FileFinder, the import graph read from the AST, and the units the system itself pins.

Everything here is computed from the live sources: drop a new module into any area and it appears
in the wizard and the exporter with no code change anywhere.
"""

import ast
import importlib
import pkgutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from msgspec import Struct

from ops.file import FileFinder, Kind

if TYPE_CHECKING:
    from e_management.models.manifest import Common


##### TYPES #####
class Unit(Struct, frozen=True, kw_only=True):
    """One exportable piece of one area: a module file or a whole package, plus its test mates."""

    area: str
    name: str
    package: bool
    source: str  # repo-relative path of the module file or package directory
    tests: tuple[tuple[str, str], ...] = ()  # (repo-relative source, project-relative destination)

    @property
    def key(self) -> str:
        return f"{self.area}/{self.name}"

    @property
    def export(self) -> str:
        """Project-relative destination of the unit itself."""
        return f"src/{self.area}/{self.name}" + ("" if self.package else ".py")

    @property
    def files(self) -> tuple[str, ...]:
        """Every project-relative path this unit owns: itself plus its tests."""
        return (self.export, *(dest for _, dest in self.tests))


class Survey(Struct, frozen=True, kw_only=True):
    """The discovered truth of one common tree: units per area, the dependents graph, and the pinned units."""

    root: str
    package: str
    areas: tuple[tuple[str, tuple[Unit, ...]], ...]
    required: frozenset[str]
    dependents: tuple[tuple[str, frozenset[str]], ...]
    conftests: tuple[tuple[str, str, str], ...] = ()  # (area, repo-relative source, destination)

    def units(self, area: str) -> tuple[Unit, ...]:
        return dict(self.areas)[area]

    def area_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.areas)

    def all_units(self) -> tuple[Unit, ...]:
        return tuple(unit for _, units in self.areas for unit in units)

    def unit(self, key: str) -> Unit:
        return next(u for u in self.all_units() if u.key == key)

    def strip(self) -> tuple[tuple[str, str], ...]:
        """The rules that drop the common package prefix from sources: e_core.core → core."""
        return tuple((f"{self.package}.{area}", area) for area in self.area_names())

    def cascade(self, drop: frozenset[str]) -> frozenset[str]:
        """The full drop set after cascading through dependents; raises when a required unit would fall."""
        edges = dict(self.dependents)
        full, stack = set(drop), list(drop)
        while stack:
            for dependent in edges.get(stack.pop(), ()):
                if dependent not in full:
                    full.add(dependent)
                    stack.append(dependent)
        if pinned := full & self.required:
            msg = f"the system itself imports {', '.join(sorted(pinned))} — it cannot be dropped"
            raise ValueError(msg)
        return frozenset(full)


##### LOGIC #####
def _refs(dotted: str, package: str, areas: frozenset[str]) -> set[str]:
    parts = dotted.split(".")
    match parts:
        case [area, unit] if area in areas:
            return {f"{area}/{unit}"}
        case [first, area, unit, *_] if first == package and area in areas:
            return {f"{area}/{unit}"}
        case _:
            return set()


def _imports(text: str, package: str, areas: frozenset[str]) -> set[str]:
    """Every ``area/unit`` an AST actually imports — attribute chains like ``state.adapters.sqlite`` never count."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(text)):
        match node:
            case ast.ImportFrom(module=str(module), names=names) if module:
                found |= {
                    ref
                    for dotted in (module, *(f"{module}.{alias.name}" for alias in names))
                    for ref in _refs(dotted, package, areas)
                }
            case ast.Import(names=names):
                found |= {ref for alias in names for ref in _refs(alias.name, package, areas)}
    return found


def _unit_files(base: Path, modules: list[str], packages: list[str]) -> dict[str, Path]:
    return {name: base / f"{name}.py" for name in modules} | {name: base / name for name in packages}


def _body(path: Path) -> str:
    return "\n".join(p.read_text() for p in ([path] if path.is_file() else sorted(path.rglob("*.py"))))


def _unit_tests(root: Path, tests_area: Path, name: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(p.relative_to(root)), f"tests/unit/{tests_area.name}/{p.name}")
        for p in sorted(tests_area.glob(f"test_{name}*.py"))
    )


def _edges(
    bodies: dict[str, str], keys: frozenset[str], package: str, areas: frozenset[str]
) -> tuple[tuple[str, frozenset[str]], ...]:
    edges: dict[str, set[str]] = {key: set() for key in keys}
    for key, body in bodies.items():
        edges_from = {ref for ref in _imports(body, package, areas) if ref in edges and ref != key}
        for ref in edges_from:
            edges[ref].add(key)
    return tuple((key, frozenset(deps)) for key, deps in edges.items())


def survey(root: Path, common: Common, system_sources: tuple[Path, ...]) -> Survey:
    """Discover every area/unit of the common package, its test mates, and what the system pins."""
    package_root = root / common.root / "src"
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    package = importlib.import_module(common.package)
    tests_root = root / common.root / "tests" / "unit" / common.package

    areas: list[tuple[str, tuple[Unit, ...]]] = []
    bodies: dict[str, str] = {}
    imports: dict[str, set[str]] = {}
    conftests: set[tuple[str, str, str]] = set()
    area_names = {p.name for p in Path(next(iter(package.__path__))).iterdir() if p.is_dir() and any(p.glob("*.py"))}
    for area in sorted(area_names):
        mod = importlib.import_module(f"{common.package}.{area}")
        modules = sorted(FileFinder(f"{common.package}.{area}").discover(Kind.MODULES))
        packages = sorted(m.name for m in pkgutil.iter_modules(mod.__path__) if m.ispkg)
        tests_dir = tests_root / area
        units: list[Unit] = []
        for name, path in _unit_files(package_root / common.package / area, modules, packages).items():
            key = f"{area}/{name}"
            bodies[key] = _body(path)
            imports[key] = {r for r in _imports(bodies[key], common.package, frozenset(area_names)) if r != key}
            if key not in set(common.skip):
                units.append(
                    Unit(
                        area=area,
                        name=name,
                        package=path.is_dir(),
                        source=str(path.relative_to(root)),
                        tests=_unit_tests(root, tests_dir, name),
                    )
                )
                if (tests_dir / "conftest.py").is_file():
                    conftests.add(
                        (area, str((tests_dir / "conftest.py").relative_to(root)), f"tests/unit/{area}/conftest.py")
                    )
        areas.append((area, tuple(units)))

    keys = frozenset(bodies)
    areas_seen = frozenset(name for name, _ in areas)
    pinned = {
        ref
        for base in system_sources
        for path in sorted(base.rglob("*.py"))
        for ref in _imports(path.read_text(), common.package, areas_seen)
    } & keys
    return Survey(
        root=common.root,
        package=common.package,
        areas=tuple(areas),
        required=_forward(pinned, imports),
        dependents=_edges(bodies, keys, common.package, areas_seen),
        conftests=tuple(sorted(conftests, key=lambda c: c[0])),
    )


def _forward(seed: set[str], imports: dict[str, set[str]]) -> frozenset[str]:
    """A unit is required when the system imports it, or imports something that imports it — transitively."""
    out, stack = set(seed), list(seed)
    while stack:
        for dep in imports.get(stack.pop(), ()):
            if dep not in out:
                out.add(dep)
                stack.append(dep)
    return frozenset(out)
