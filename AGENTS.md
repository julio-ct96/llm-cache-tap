# llm-cache-tap

## Qué es

Addon de mitmproxy que captura las llamadas a LLM que pasan por el proxy (panel local en `http://127.0.0.1:8900`).
Muestra si cada una acertó la caché de prompts y, si no, por qué.

## Mapa

| Fichero | Qué contiene |
| --- | --- |
| `tap.py` | Entrada del addon: hooks de mitmproxy y cableado de los módulos |
| `cachetap/__init__.py` | Marca el paquete interno del addon |
| `cachetap/config.py` | Rutas, puertos y límites (TTL, MAX) |
| `cachetap/record.py` | Contrato del registro de una petición y ayudas para exponerlo |
| `cachetap/request_body.py` | Decodifica y valida cuerpos JSON antes de inspeccionarlos |
| `cachetap/segments.py` | Trocea la petición en segmentos cacheables, los huella y los compara |
| `cachetap/linking.py` | Empareja una petición con la anterior de su conversación |
| `cachetap/verdict.py` | Calcula el veredicto de caché (HIT, PARTIAL, MISS...) y las notas que lo explican |
| `cachetap/response_body.py` | Lee el uso y el texto generado del cuerpo de la respuesta, JSON o SSE |
| `cachetap/store.py` | Registros en memoria, suscriptores del panel y el jsonl |
| `cachetap/dashboard.py` | Servidor HTTP del panel: estáticos de `ui/`, API de registros y stream en vivo |
| `cachetap/providers/__init__.py` | Despacho por proveedor (`PROVIDERS`): vida de la caché, límites y formato del mensaje |
| `cachetap/providers/base.py` | Lo común a los proveedores: leer la versión del nombre del modelo |
| `cachetap/providers/anthropic.py` | Reglas de Claude: TTL de la caché y prefijo mínimo cacheable |
| `cachetap/providers/openai.py` | Reglas de OpenAI: TTL de la caché y prefijo mínimo cacheable |
| `ui/index.html` | Estructura del panel; el orden de sus `<link>` es la cascada del CSS |
| `ui/app.js` | Entrada del panel: cablea eventos y arranca la conexión |
| `ui/state.js` | Estado compartido del panel |
| `ui/format.js` | Utilidades de formato y escape de HTML |
| `ui/prefs.js` | Preferencias guardadas en localStorage |
| `ui/parts.js` | Fragmentos de HTML reutilizables (badge, barra de reparto) |
| `ui/cache-timer.js` | Temporizador de vida de la caché de cada petición |
| `ui/list.js` | Lista de peticiones con filtros y contadores |
| `ui/detail.js` | Panel de detalle de una petición |
| `ui/stream.js` | Conexión en vivo (SSE) con el backend |
| `ui/events.js` | Validación de eventos SSE recibidos |
| `ui/status.js` | Mensajes accesibles de error/estado de operaciones |
| `ui/help.js` | Diálogo de ayuda pintado desde la referencia de TTL y mínimos |
| `ui/json-tree.js` | Visor de JSON plegable |
| `ui/css/` | `tokens`, `base`, `header`, `layout`, `tables`, `parts`, `detail`, `json-tree`, `help`, `responsive` (el orden de los `<link>` es la cascada) |
| `start.sh`, `via.sh` | Arrancan proxy y panel; lanzan un comando a través del proxy |
| `.agents/skills/plan-small-tasks/` | Skill para escribir y ejecutar planes por tareas pequeñas, como el de `.plans/` |
| `tests/replay/` | Escenario sintético (`scenario`, `steps_*`, `builders`, `flows`, `adapter`), `golden.json` y `serve.py` |
| `tests/test_*.py` | Un test por módulo, más `test_replay`, `test_dependencies` y `test_ui_assets` |
| `tests/ui/unit/` | Tests JS puros con `node:test` |
| `scripts/check.py` | Runner local: Ruff, mypy, unittest, JS y UI opcional |
| `requirements-dev.txt`, `requirements-ci.txt` | Dependencias de herramientas y entorno de CI |
| `.github/workflows/check.yml` | Workflow en GitHub Actions; Python 3.12, Node 24 y Chrome |

## Dónde tocar

| Para… | Abre |
| --- | --- |
| cambiar el TTL o el mínimo cacheable de un modelo | el fichero de su proveedor en `cachetap/providers/` y su test |
| añadir un proveedor | un fichero nuevo en `cachetap/providers/` con la misma interfaz que `anthropic.py`, y añadirlo a `PROVIDERS` |
| cambiar cuándo es HIT, MISS o PARTIAL | `cachetap/verdict.py` |
| cambiar cómo se empareja una petición con la anterior | `cachetap/linking.py` |
| añadir un campo al registro | `cachetap/record.py`, el hook de `tap.py` que lo rellena y `tests/replay/golden.json` |
| añadir una columna a la lista | `ui/list.js`, `ui/index.html` y `ui/css/tables.css` |
| cambiar el panel de detalle | `ui/detail.js` y `ui/css/detail.css` |
| añadir un endpoint | `cachetap/dashboard.py` |

## Comandos

- Arrancar el proxy y el panel: `./start.sh`; cliente a través del proxy: `./via.sh <comando>`.
- El hook `load` arranca el panel y anuncia su URL mediante `logger.info`; el nivel de log se configura en mitmproxy (`start.sh` usa `termlog_verbosity=warn`).
- Tests: `venv/bin/python -m unittest discover -s tests -t . -q`.
- Panel de prueba sin proxy: `venv/bin/python tests/replay/serve.py` (puerto 8901).
- Comprobación de la interfaz en un Chrome sin ventana: `node tests/ui/check.mjs --full`.
- Comprobación unificada: `venv/bin/python scripts/check.py`; añade `--full` para ejecutar también Chrome. Requiere Node 24 y el entorno `venv/`; `--full` requiere Chrome/Chromium. Para preparar herramientas, `venv/bin/python -m pip install -r requirements-dev.txt`; `requirements-ci.txt` incluye mitmproxy y esas herramientas.
- Suite Python: 229 tests con el comando anterior de unittest; suite JS: `node --test tests/ui/unit/*.test.mjs` (11 tests). `node tests/ui/benchmark.mjs` mide informativamente 30/300/3000 registros, sin umbral de aprobación.

## Contratos y límites

- `cachetap/record.py` define los contratos `TypedDict` del registro y eventos; `Record` se completa por fases (solo `id` es obligatorio) y usa `Literal` para estados/veredictos cerrados. `GET /api/record/<id>` entrega el registro sin claves internas; la lista/SSE omite campos pesados. `GET /api/body/<id>` entrega el cuerpo retenido. `GET /api/reference` sirve TTL/mínimos, `GET /events` emite snapshot y eventos, y `POST /api/clear` limpia.
- `cachetap/request_body.py` es la frontera de entrada JSON: JSON mal formado da objeto vacío para compatibilidad; raíz u opciones con formas inválidas producen `ValueError`, se registran como petición no inspeccionable y no se inspeccionan.
- Límites del inspector: 300 registros, 4 MiB por petición inspeccionable, 64 MiB de cuerpos retenidos medidos en UTF-8, 8 MiB por buffer de respuesta, 16 capturas simultáneas y 512 eventos pendientes por cliente. No limitan buffers previos de mitmproxy ni la memoria/RSS total. Los bytes de respuesta siempre siguen hacia el cliente; una respuesta con captura limitada acaba en `N/A`. Cliente SSE lento: la cola se reemplaza por una señal de desconexión y el navegador reconecta para recibir un snapshot.

## Reglas

- Los módulos de `cachetap` se importan como módulo y se usan con prefijo (`config.MAX`), para poder sustituirlos en los tests.
- Usa nombres del dominio y transformaciones pequeñas; valida datos externos en la frontera antes de procesarlos. Haz explícitas las mutaciones y los efectos (filesystem, red, logs).
- Cuenta tamaños de texto en bytes UTF-8 cuando el límite sea de almacenamiento; captura excepciones específicas y deja que errores inesperados sean visibles.
- Las funciones de estado de `store` se llaman con `store.LOCK` adquirido por el llamador. No hagas I/O, esperas de cola, logging ni escritura HTTP dentro del lock; `append_log` se ejecuta fuera.
- Conserva y actualiza los `TypedDict`/aliases del contrato cuando cambie un registro o evento. No añadas defaults a todos los registros si un campo solo aplica en algunos casos.
- En UI, `id` identifica controles; usa `data-id` y `data-act` para datos/acciones de filas. Escapa según el contexto de salida; usa `textContent` para texto y no interpoles datos externos como HTML.
- Prueba comportamiento y límites observables con casos sintéticos. Mide antes de optimizar; benchmarks informativos no se convierten en umbrales frágiles.
- Quién puede importar a quién está fijado en `tests/test_dependencies.py`; un módulo nuevo debe añadirse a su tabla.
- `tests/replay/golden.json` fija el comportamiento completo: el plan de buenas prácticas corrigió en 2.01 las cinco apariciones de `n_msgs` del registro 30 de 17 a 1; el golden actual conserva esa corrección. En cambios futuros solo se regenera con `TAP_UPDATE_GOLDEN=1` si el cambio está aprobado y se revisa su diff.
- mitmproxy recarga al guardar `tap.py`; tras cambiar un fichero de `cachetap/`, guarda también `tap.py` (o `touch tap.py`).
- Los tests nunca escriben en `data/requests.jsonl` ni usan los puertos 8899 y 8900.
- El frontend no tiene build ni dependencias: módulos ES cargados tal cual.
- No se versionan `ca/` (clave privada del proxy), `data/` (métricas capturadas) ni `venv/`.
