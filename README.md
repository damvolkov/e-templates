# e-app

[![CI](https://img.shields.io/github/actions/workflow/status/damvolkov/e-app/ci.yml?label=test)](https://github.com/damvolkov/e-app/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/damvolkov/e-app?color=166b7e)](https://github.com/damvolkov/e-app/releases)
[![PyPI](https://img.shields.io/pypi/v/e-app?color=166b7e)](https://pypi.org/project/e-app/)
[![Python](https://img.shields.io/pypi/pyversions/e-app)](https://pypi.org/project/e-app/)
[![License](https://img.shields.io/pypi/l/e-app?color=166b7e)](LICENSE)

Generic **e-stack** service template: FastAPI + Pydantic on uv, Rust-backed tooling end to end.
Clone, run `make init <name>`, and every file, folder, and config is renamed deterministically to your project.

##### STACK #####

| Concern | Tool |
|---|---|
| Env + deps + lock | `uv` (dependency groups, `exclude-newer`) |
| Lint + format | `ruff` |
| Types | `ty` (static) |
| Architecture | `tach` (layered imports: api → pipelines → adapters → core) |
| Hooks | `prek` + gitleaks |
| Tests | `pytest` (asyncio, cov ≥90%, xdist, randomly, timeout, benchmark) + `hypothesis`, `polyfactory`, `inline-snapshot` |
| Docs | `mkdocs-material` + `mkdocstrings`, built with `properdocs` (API pages generated from `src/`) |
| Release | git-tag versions (`uv-dynamic-versioning`) · one dispatch: tag → GitHub release → sdist/wheel → PyPI/ghcr, gated per repo |
| Runtime | `fastapi[standard]`, `pydantic`, `msgspec`, `structlog` |

##### LAYOUT #####

```
src/e_app/          # all modules live here: core/logger.py, core/settings.py, ...
tests/unit/         # mirrors src, import-mode=importlib; includes the CI-gate contract test
scripts/            # init.py (scaffold), gen_ref_pages.py (docs)
docs/               # site landing + release guide; reference/ auto-generated from sources
.github/            # ci.yml · release.yml · dependabot.yml · ci.vars.example (gate manifest)
Dockerfile          # two-stage: builder (uv) + deploy (python-slim, non-root)
compose.yml         # single e-app service, :8000
```

##### USAGE #####

```bash
make init <name>    # rename template → your project (asks name if omitted)
make install        # uv sync + prek hooks
make check          # lint + type + arch + test
make run            # python -m e_app
make docs           # serve docs at http://localhost:8000
make up             # docker compose up
make release minor  # cut a release: tag → GitHub release → artifacts (see docs/release.md)
make ci-vars        # list the optional CI/CD gates
```

`make` alone lists every target.

##### CI/CD #####

`ci.yml` is the non-negotiable floor every project gets on day one: ruff · ty · tach ·
validate-pyproject · zizmor, pytest × {ubuntu, macos, windows} with the ≥90% coverage
gate, and a strict docs build on every PR. Pages deploy and publishing (`release.yml`:
tag → GitHub release → sdist/wheel → PyPI/ghcr) are **inert gates** — off until a repo
declares itself, one `gh variable set` per surface. The gate manifest is
`.github/ci.vars.example`, enforced against the workflows by `tests/unit/test_ci_contract.py`
(undocumented, dead or enabled-by-default gates fail CI). Full operator guide:
[docs → Releasing](https://damvolkov.github.io/e-app/release/).
