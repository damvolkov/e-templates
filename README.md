# e-api

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
| Runtime | `fastapi[standard]`, `pydantic`, `msgspec`, `structlog` |

##### LAYOUT #####

```
src/e_api/          # all modules live here: core/logger.py, core/settings.py, ...
tests/unit/         # mirrors src, import-mode=importlib
scripts/            # init.py (scaffold), gen_ref_pages.py (docs)
docs/               # site landing; reference/ auto-generated from sources
```

##### USAGE #####

```bash
make init <name>    # rename template → your project (asks name if omitted)
make install        # uv sync + prek hooks
make check          # lint + type + arch + test
make run            # python -m e_api
make docs           # serve docs at http://localhost:8000
make up             # docker compose up
```

`make` alone lists every target.
