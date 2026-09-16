# e-api

e-stack service template: **uv · ruff · ty · tach · prek · pytest · properdocs · docker**.

## Quickstart

```bash
make install    # uv sync + git hooks
make check      # lint + types + architecture + tests
make run        # python -m e_api
make docs       # serve this site at http://localhost:8000
```

## Layout

All modules live under `src/e_api/`, layered by [tach](https://tach.dev):

| Module | Layer | Purpose |
|---|---|---|
| [`e_api.core.logger`](reference/e_api/core/logger.md) | core | Structured logging: JSON in prod, ordered plain text in dev |
| [`e_api.core.settings`](reference/e_api/core/settings.md) | core | Typed, frozen, layered config on msgspec |

Reference pages below are generated automatically from the sources: drop a new module under `src/` and it appears here on the next build.
