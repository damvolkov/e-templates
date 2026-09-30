# Changelog de auditoría — api + common

Auditoría read-only de `systems/api` y `systems/core` contra la doctrina `AGENTS.md` (20 headlines) y los skills cargados. `ruff check` y `ty check` pasan limpios en ambos paquetes — las infracciones son de doctrina, no de lint. La divergencia `api/src/core/* ↔ core/src/e_core/core/*` es **únicamente** el rewrite `e_core.core → core` / `e_core.ops → ops` producido por el `sed` del Makefile; el resto es byte-idéntico.

---

## systems/core/src/e_core/core/settings/\_\_init\_\_.py

- **[COMM] settings/\_\_init\_\_.py:1-60** — `tax-py-naming` r1 (`__init__.py` is never created; holds a docstring or that hook and nothing else) — el archivo contiene composición dinámica (`msgspec.defstruct`), monkey-patch de `Settings.load`, instanciación eager del singleton y lógica de discovery. Excede "un hook y nada más".
  ```python
  Settings: Any = msgspec.defstruct("Settings", list(_SCOPES.items()), bases=(BaseSettings,), frozen=True, kw_only=True)
  Settings.load = classmethod(_load)  # type: ignore[method-assign]
  settings: Any = _load(Settings)
  ```
  **Fix**: extraer la composición a `settings/compose.py` (módulo normal) y dejar en `__init__.py` solo el re-export de `settings`. El `FileFinder` ya salta `__init__`, así que el discovery no lo necesita. — **MAYOR**

- **[COMM] settings/\_\_init\_\_.py:52** — `lang-py-typing` + `AGENTS` r13 — `_load(cls: type, **overrides: dict[str, Any]) -> Any` está mal tipado: `**overrides: dict[str, Any]` declara que *cada valor* es `dict[str, Any]`, pero el cuerpo hace `overrides.pop(scope, {})`. Inconsistente con `Crypto.load(cls, **overrides: Any) -> Self` (crypto.py:221). El `Any` de retorno oculta el tipo real `Settings`.
  ```python
  def _load(cls: type, **overrides: dict[str, Any]) -> Any:
      parts = {scope: sub.load(**overrides.pop(scope, {})) for scope, sub in _SCOPES.items()}
  ```
  **Fix**: `def _load(cls: type[Self], **overrides: Any) -> Self`, alineado con el patrón de `Crypto.load`. — **MAYOR**

- **[COMM] settings/\_\_init\_\_.py:59** — `proj-py-layout` + `AGENTS` r11 ("Nothing loads at import") — `settings: Any = _load(Settings)` se ejecuta al importar el módulo: lee env, secrets y `.env` en momento de import, con efectos secundarios globales que dificultan el test aislado.
  **Fix**: exponer `Settings` (el tipo) y una función `load()` explícita; el singleton vive en el lifespan o en un módulo `runtime.py` aparte, no en el body del paquete. — **MAYOR**

## systems/core/src/e_core/core/crypto.py

- **[COMM] core/crypto.py:358** — `tax-py-naming` r6 — `# ── runtime type checking (silent fallback if beartype not installed) ──` es un separador informal con guiones Unicode.
  **Fix**: `##### RUNTIME TYPE CHECKING #####`. — **MENOR**

- **[COMM] core/crypto.py:359-373** — `AGENTS` r11/r10 + `tax` r4 — el bloque `try: import beartype as _bt / except ImportError: pass / else: def _wrap... _wrap(Crypto)` es **código muerto**: `beartype>=0.22.9` está en `pyproject.toml`, siempre instalado. Además `_wrap` es un helper módulo-level fuera de un utility module.
  **Fix**: `Crypto = beartype.beartype(Crypto)` en module level, o `@beartype.beartype` como decorator. — **MAYOR**

- **[COMM] core/crypto.py:56** — `para-py-dispatch` r5 — `ENC_KEY_SIZES: dict[str, int]` usa `.value` (strings crudos) como claves en un mapping de selección; acceso `ENC_KEY_SIZES[settings.enc.value]` (línea 107).
  **Fix**: `ENC_KEY_SIZES: Final[Mapping[TokenEnc, int]] = MappingProxyType({TokenEnc.A128GCM: 16, TokenEnc.A256GCM: 32})` y acceso `ENC_KEY_SIZES[settings.enc]`. — **MAYOR**

- **[COMM] core/crypto.py:57-62** — `para-py-dispatch` r5 — `JOSE_KEY_TYPES: dict[str, Literal[...]]` mapea prefijos de alg (strings crudos) a tipos de key.
  **Fix**: `class AlgPrefix(StrEnum)` + `Final[Mapping[AlgPrefix, ...]]`, extrayendo el prefijo con `AlgPrefix(alg.value[:2])`. — **MENOR**

## systems/core/src/e_core/core/logger.py

- **[COMM] core/logger.py:146** — `tax-py-naming` r6 — mismo comentario informal que crypto.py. **Fix**: `##### RUNTIME TYPE CHECKING #####`. — **MENOR**

- **[COMM] core/logger.py:147-159** — `AGENTS` r10/r11 — bloque beartype fallback idéntico al de crypto.py: código muerto + `_wrap` helper módulo-level. **Fix**: `ELogger = beartype.beartype(ELogger)`. — **MAYOR**

- **[COMM] core/logger.py:162-163** — `proj-py-layout` + `AGENTS` r11 — `setup(env=st.app.app_env); logger = structlog.get_logger()` en el body del módulo: reconfigura structlog (efecto global) y materializa el singleton al importar.
  **Fix**: exponer `setup` perezosa o invocarla desde el lifespan; `logger` vía función/getter. — **MAYOR**

- **[COMM] core/logger.py:66-68** — `tax-py-naming` r4 — `encode_json` es helper módulo-level en un módulo que no es utility. **Fix**: mover a `serializers.py` o `@staticmethod` de `ELogger`. — **MENOR**

- **[COMM] core/logger.py:111** — `tax-py-naming` r4 — `setup()` es función módulo-level con efecto secundario global. **Fix**: método de una clase `LoggerBootstrap` o wiring en el lifespan. — **MENOR**

## systems/core/src/e_core/ops/tui.py

- **[COMM] ops/tui.py:28-229** — `tax-py-naming` r4 — siete funciones privadas módulo-level (`_font`, `_glyphs`, `_cells`, `_layout`, `_bitmap`, `_compact`, `_pick`) sirven exclusivamente a `HeaderTui`; son helpers de clase fugados al módulo.
  **Fix**: `@staticmethod` de `HeaderTui` o `ops/tui/_bitmap.py` como utility interno. — **MAYOR**

- **[COMM] ops/tui.py:280-282** — `tax-py-naming` r3 — `_max_rows` sirve a `_lines` (privado), no a un público; la cadena de nombrado se rompe.
  **Fix**: `_render_max_rows` o consolidar en `_render_lines`. — **MENOR**

- **[COMM] ops/tui.py:125-134, 163-175** — `para-py-iteration` + `AGENTS` r7 — `_glyphs` y `_bitmap` usan `for` anidados con `if`/`break`/`else` y mutación imperativa.
  **Fix**: `return [next((f[ch] for f in fonts if ch in f), BLANK) for ch in text]`. — **MENOR**

- **[COMM] ops/tui.py:219-229** — `para-py-iteration` — `_pick` usa `while` con mutación secuencial (búsqueda lineal, n ≤ 40, legítima pero reescribible). **Fix**: comprehension + `next`, o cota analítica. — **MENOR**

- **[COMM] ops/tui.py:281-282** — `para-py-dispatch` r6 — `isinstance` único reescribible como match sobre `int() | float()`. — **MENOR**

## systems/core/src/e_core/core/settings/base.py

- **[COMM] core/settings/base.py:6,61** — `AGENTS` r16 — `cls.read(os.environ)` lee el entorno crudo. Encapsulado en el loader, pero la regla literal lo proscribe.
  **Fix**: `Mapping[str, str]` tipado e inyectable. — **MENOR** (diseño custom msgspec+e-serde deliberado; espíritu cumplido, literal no)

- **[COMM] core/settings/base.py:114-122** — `para-py-dispatch` r6 — `merge` usa dos `isinstance` para decidir rama.
  **Fix**: `match (base.get(key), value): case (dict() as b, Mapping() as v): ...`. — **MENOR**

- **[COMM] core/settings/base.py:107-112** — `AGENTS` r7 — `reduce(lambda node, part: node.setdefault(part, {}), ...)` — lambda en reduce (PEP 8 desaconseja). **Fix**: `def` nombrada `_dig`. — **MENOR**

## systems/api/src/e_api/adapters/sqlite.py

- **[APLI] adapters/sqlite.py:28** — `conc-py-async` r1/r5 — `self._path.parent.mkdir(...)` es I/O síncrono dentro de la corutina `connect`.
  **Fix**: `await anyio.to_thread.run_sync(...)`. — **MAYOR**

## systems/api/src/e_api/adapters/base.py

- **[APLI] adapters/base.py:15,38** — `arch-py-hexagonal` — `BaseAdapter(ABC)` + `abstractmethod` en vez de Protocol para el puerto que consumen `deps.py` y routers.
  **Fix**: `StorePort(Protocol)`; `StoreAdapter` como implementación. — **MENOR**

- **[APLI] adapters/base.py:52-54** — `para-py-iteration` + `AGENTS` r3 — `keys() -> list[str]` materializa (`fetchall` en sqlite; `KEYS` en redis).
  **Fix**: `AsyncIterator[str]`; sqlite `async for row in cursor`; redis `scan_iter` (SCAN, no KEYS). — **MAYOR**

## systems/api/src/e_api/adapters/http.py

- **[APLI] adapters/http.py:56,62** — `lang-py-typing` — `get/post -> Any`; el contrato del puerto pierde tipo.
  **Fix**: `-> object` o genérico `T` con decode `as_: type[T]` (msgspec). — **MENOR**

- **[APLI] adapters/http.py:53** — `tax-py-naming` r6 — comentario `#` libre → forma `###`. — **NIT**

## systems/api/src/e_api/api/deps.py

- **[APLI] api/deps.py:60-75** — `tax-py-naming` r4 — `load_record`/`to_user` son helpers compartidos en un módulo de links DI; no son links ni dispatch.
  **Fix**: mover a `models/user.py` (`@staticmethod`) o `services/user.py`. — **MENOR**

- **[APLI] api/deps.py:46** — `lang-py-typing` — `claims: dict[str, Any]` sin acotar. **Fix**: alias `ClaimValue`. — **NIT**

## systems/api/src/e_api/api/security.py

- **[APLI] api/security.py:25** — `tax-py-naming` r4 — `bearer_claims` helper módulo-level fuera de utility/dispatch. **Fix**: `_guard_bearer_claims` o submódulo. — **MENOR**

- **[APLI] api/security.py:21** — `para-py-dispatch` r5 — string crudo `"bearerAuth"` en `SECURITY`. **Fix**: `StrEnum` alineado con `BEARER_SCHEME`. — **NIT**

## systems/api/src/e_api/api/middlewares.py

- **[APLI] api/middlewares.py:55** — `tax-py-naming` r6 — `#` libre → `###`. — **NIT**
- **[APLI] api/middlewares.py:53** — `proj-py-layout` r11 — default `settings: ApiSettings = st.api` se congela en momento de import. **Fix**: `None` + fallback en cuerpo. — **NIT**
- **[APLI] api/middlewares.py:63** — `lang-py-typing` — `tuple[type, ...]` es `type[Any]`. **Fix**: tipo paramétrico o `Final`. — **NIT**

## systems/api/src/e_api/main.py

- **[APLI] main.py:35** — `proj-py-layout` — `version="0.1.0"` hardcodeado; la versión vive en `pyproject.toml`. **Fix**: `importlib.metadata.version("e-api")`. — **NIT**

## systems/api/src/e_api/\_\_main\_\_.py

- **[APLI] \_\_main\_\_.py:15** — `proj-py-layout` — `reload=True` hardcodeado. **Fix**: derivar de `st.app.app_env`. — **NIT**

## systems/api/src/e_api/api/router/health.py

- **[APLI] router/health.py:18** — `AGENTS` r9 — acceso a `oauth._registry` (privado de authlib). **Fix**: wrapper público en `deps.oauth`. — **MENOR**

## systems/api/src/e_api/api/router/user.py

- **[APLI] router/user.py:88-94** — `para-py-dispatch` r5 — claves string crudas en `GRAPH_DEPS`/`READ_DEPS`/`OAUTH_DEPS`; un typo rompe wiring en runtime. **Fix**: `class DepKey(StrEnum)`. — **MENOR**

## systems/api/src/e_api/models/user.py

- **[APLI] models/user.py:55** — `tax-py-naming` r6 — `#` libre → `###`. — **NIT**

## systems/core/src/e_core/core/settings/app.py

- **[COMM] settings/app.py:9** — `arch-py-adt` — `app_env: str = "dev"` siendo string crudo cuando `logger.py` define `Env(StrEnum)`. Un typo (`APP_ENV=deV`) revienta en runtime.
  **Fix**: `app_env: Env = Env.DEV` con validación en decode; mover `Env` a `settings/app.py`. — **MENOR**

## systems/core/src/e_core/core/settings/api.py

- **[COMM] settings/api.py:8** — `para-py-dispatch` r5 — `DEFAULT_METHODS: list[str]` verbos HTTP crudos. **Fix**: `StrEnum`. — **NIT**

## systems/core/src/e_core/core/state.py

- **[COMM] core/state.py:18** — `lang-py-typing` — `MutableMapping[str, Any]`; `Any` es decisión de diseño, no necesidad. **Fix**: `MutableMapping[str, object]` (consumers ya castean). — **NIT**

## systems/api/tests/unit/e_api/conftest.py

- **[APLI] conftest.py:7-8** — `proj-py-layout` + `AGENTS` r16 — `os.environ.setdefault(...)` *antes* de los imports; side-effect → import, no reentrante.
  **Fix**: env setup en `tests/conftest.py` raíz o fixture autouse session-scoped; separar bloque de imports. — **MENOR**

- **[APLI] conftest.py:44** — `lang-py-typing` — `def created_user(client) -> dict:` sin parametrizar. **Fix**: `dict[str, Any]` o TypedDict. — **NIT**

## systems/core/tests/unit/e_core/ops/test_tui.py

- **[COMM] test_tui.py:5** — `test-py-tdd` — importa siete privados (`_art, _cells, _compact, _glyphs, _layout, _pick`) para testear implementación, no comportamiento.
  **Fix**: testear `HeaderTui.render()`/`get_content_height()` sobre inputs controlados; cubre lo mismo sin acoplamiento. — **MAYOR**

## systems/api/tests/unit/test_ci_contract.py

- **[APLI] test_ci_contract.py:27-33** — `para-py-iteration` — `entries = {}` + `for` + mutación, llamado dos veces sin memoizar. **Fix**: dict comprehension + `lru_cache`. — **NIT**

---

## Diferencia idéntica verificada (sin nonconformity)

`diff` confirma que `systems/api/src/core/*`, `ops/file.py` y todos los `settings/*.py` son **byte-idénticos** a `systems/core/src/e_core/core/*` salvo el rewrite de imports. **No hay divergencia semántica oculta.** El drift-check (`make core-check`) valida congruencia del propio sed, no validez semántica del transform.

---

## Resumen

| Severidad | Count |
|---|---|
| CRÍTICA | 0 |
| MAYOR | 11 |
| MENOR | 14 |
| NIT | 11 |

| Regla / skill | Infracciones |
|---|---|
| `tax-py-naming` r4 (helpers módulo-level fuera de utility) | 6 |
| `tax-py-naming` r6 (comentarios: solo 3 formas) | 7 |
| `tax-py-naming` r1 (`__init__.py` sin lógica) | 1 |
| `AGENTS` r11 (Nothing loads at import) | 3 |
| `AGENTS` r10/r11 (código muerto beartype fallback) | 2 |
| `para-py-dispatch` r5 (StrEnum keys, no string crudo) | 5 |
| `para-py-dispatch` r6 (isinstance chains) | 2 |
| `para-py-iteration` (lazy, no imperativo) | 4 |
| `conc-py-async` r1/r5 (loop bloqueado) | 1 |
| `arch-py-hexagonal` (Protocol over ABC) | 1 |
| `lang-py-typing` (Any gratuito / firmas flojas) | 6 |
| `test-py-tdd` (tests de implementación) | 1 |
| `AGENTS` r16 (`os.environ`) | 1 |

## Fixes estructurales (deduplicación core → e_core)

1. `e-core` **no** está declarado como dependencia en `systems/api/pyproject.toml` — línea 10 lo dice: *"shared core materialized from systems/core"*. El API copia `core/` y `ops/` en build-time vía `make core` (sed + cp).
2. Divergencia real: solo el rewrite de imports. Ninguna semántica.
3. ¿Importar `e_core` en vez de copiar? Trade-off de template, no bug: la materialización permite congelar versión por sistema. Pero el `sed -i 's/e_core\.core\b/core/g'` es **frágil** (regex sobre código, no transform estructural).

**Plan A — emigrar a dependencia**: 1) `e-core` como dep path/workspace en `systems/api/pyproject.toml`; 2) borrar `make core`/`core-check` y `src/core/`, `src/ops/`; 3) reescribir imports `from core.* → from e_core.core.*` (global, trivial: ya son absolutos, cero `from .`); 4) actualizar hatch `packages`, isort `known-first-party`, `tach.toml`; 5) reescribir imports en tests. Estimación: 1-2 h mecánica + 1 h tach/coverage. Riesgo bajo.

**Plan B — mantener materialización, endurecerla**: reemplazar el `sed` por transform AST con `libcst` (`scripts/rewrite_core.py`) que renombre import nodes de forma estructural. Sin cambio de modelo, elimina la fragilidad.

## Lo que ya cumple

1. Imports absolutos desde la raíz, **cero `from .`** en todo `src/` (API y core); `ruff` con `ban-relative-imports = "all"` lo garantiza.
2. Dispatch por match-case y StrEnum en el core crítico: `Crypto.verify_token`, `FileFinder._select`, `State.__getattr__`, `Status.from_latency`. `if/elif` prácticamente ausente.
3. `AsyncExitStack` y context managers: lifespan abre cada adapter en su stack y cierra en orden inverso. Ciclo de vida determinista.
4. Contratos msgspec `frozen=True`, `kw_only=True` en el borde; `Password`/`Secret` son newtypes con `__repr__`/`__str__` redactados.
5. Off-thread donde duele: argon2/bcrypt y el walk de imports vía `anyio.to_thread`; `TaskGroup` real en stress tests.
