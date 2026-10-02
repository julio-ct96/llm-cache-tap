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
| `ui/help.js` | Diálogo de ayuda pintado desde la referencia de TTL y mínimos |
| `ui/json-tree.js` | Visor de JSON plegable |
| `ui/css/` | `tokens`, `base`, `header`, `layout`, `tables`, `parts`, `detail`, `json-tree`, `help`, `responsive` (el orden de los `<link>` es la cascada) |
| `start.sh`, `via.sh` | Arrancan proxy y panel; lanzan un comando a través del proxy |
| `tests/replay/` | Escenario sintético (`scenario`, `steps_*`, `builders`, `flows`, `adapter`), `golden.json` y `serve.py` |
| `tests/test_*.py` | Un test por módulo, más `test_replay`, `test_dependencies` y `test_ui_assets` |

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
- Tests: `venv/bin/python -m unittest discover -s tests -t . -q`.
- Panel de prueba sin proxy: `venv/bin/python tests/replay/serve.py` (puerto 8901).
- Comprobación de la interfaz en un Chrome sin ventana: `node tests/ui/check.mjs --full`.

## Reglas

- Los módulos de `cachetap` se importan como módulo y se usan con prefijo (`config.MAX`), para poder sustituirlos en los tests.
- Quién puede importar a quién está fijado en `tests/test_dependencies.py`; un módulo nuevo debe añadirse a su tabla.
- `tests/replay/golden.json` fija el comportamiento completo: solo se regenera con `TAP_UPDATE_GOLDEN=1` si el cambio es intencionado, y se revisa su diff.
- mitmproxy recarga al guardar `tap.py`; tras cambiar un fichero de `cachetap/`, guarda también `tap.py` (o `touch tap.py`).
- Los tests nunca escriben en `data/requests.jsonl` ni usan los puertos 8899 y 8900.
- El frontend no tiene build ni dependencias: módulos ES cargados tal cual.
- No se versionan `ca/` (clave privada del proxy), `data/` (métricas capturadas) ni `venv/`.
