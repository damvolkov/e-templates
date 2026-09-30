# e-management

Internal tool of the e-templates repository: a deterministic engine (registry → plan → scaffold)
with a plain CLI today and a Textual wizard as the next skin. Generates ready-to-work boilerplates
from `systems/` and reports materialized drift. Not published: no CI, no Docker, no release path.

##### USAGE #####

```bash
make install                  # uv sync
make drift                    # are systems/* in sync with their material sources?
make plan T=api N=myapp      # the ordered generation actions, as JSON
make gen T=api N=myapp DEST=../myapp OFF=websockets
uv run python -m e_management --help
```

##### LAYOUT #####

```
data/templates.yml          # the registry: materials, pieces (optional parts), finalize prunes
src/e_management/cli/       # verbs, console-free; __main__ registers and renders
src/e_management/adapters/  # IO ports: registry file, filesystem scaffold
src/e_management/core/      # domain: blueprint (validation+composition), plan (actions as values), errors
src/e_management/ops/       # pure utilities: guarded whole-word rewrite
```
