"""cli.commands: the tool's verbs, free of any console — __main__ registers and renders what these return."""

from typing import TYPE_CHECKING

from e_management.adapters.manifest import ManifestReader
from e_management.adapters.scaffold import Scaffold
from e_management.core.blueprint import Blueprint
from e_management.ops.scan import survey as scan

if TYPE_CHECKING:
    from pathlib import Path

    from e_management.core.plan import Plan
    from e_management.models.manifest import Manifest
    from e_management.ops.scan import Survey


def registry(file: Path) -> Manifest:
    """The validated template registry."""
    return ManifestReader(file).load()


def survey(root: Path, spec: Manifest, template: str) -> Survey | None:
    """The live common survey of one template — None when it declares no common tree."""
    spec_t = spec.templates[template]
    if spec_t.common is None:
        return None
    return scan(root, spec_t.common, (root / spec_t.source / "src" / spec_t.package,))


def blueprint(root: Path, spec: Manifest, template: str, name: str) -> Blueprint:
    """The domain view of a template for a concrete name, wired with its dynamic common survey."""
    return Blueprint(spec.templates[template], name, survey(root, spec, template))


def plan(
    root: Path,
    spec: Manifest,
    template: str,
    name: str,
    *,
    off: frozenset[str] = frozenset(),
    drop: frozenset[str] = frozenset(),
) -> Plan:
    """The ordered actions for ``template`` under the new ``name``, without touching the filesystem."""
    return blueprint(root, spec, template, name).plan(off, drop)


def gen(
    root: Path,
    spec: Manifest,
    template: str,
    name: str,
    dest: Path,
    *,
    off: frozenset[str] = frozenset(),
    drop: frozenset[str] = frozenset(),
) -> Path:
    """Materializes and generates the project, returning its path. Raises on any invalid selection."""
    return Scaffold(root).apply(plan(root, spec, template, name, off=off, drop=drop), dest)


def drift(root: Path, spec: Manifest) -> dict[str, list[str]]:
    """Per template: the material files its system holds that no longer match the sources."""
    return {name: Scaffold(root).drift(template) for name, template in spec.templates.items()}
