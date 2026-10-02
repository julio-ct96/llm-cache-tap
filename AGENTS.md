# llm-cache-tap

Addon de mitmproxy que captura las llamadas a LLM que pasan por el proxy y muestra en un panel local
(`http://127.0.0.1:8900`) si cada una acertó la caché de prompts y, si no, por qué.

## Mapa

| Fichero | Qué contiene |
| --- | --- |
| `tap.py` | Entrada del addon: solo los hooks de mitmproxy y el cableado |
| `cachetap/` | Backend por módulos: `config`, `record` (contrato del registro), `segments`, `linking`, `verdict`, `response_body`, `store`, `dashboard` |
| `cachetap/providers/` | Lo que cambia por proveedor: `anthropic.py`, `openai.py`, y el despacho en `__init__.py` |
| `tests/` | Un `test_*.py` por módulo; `tests/replay/` tiene el escenario sintético y `golden.json` |
| `ui/index.html` | Estructura del panel y diálogo de ayuda |
| `ui/app.js` | Entrada del panel: cablea eventos y arranca la conexión |
| `ui/list.js`, `ui/detail.js`, `ui/stream.js` | Lista con filtros y contadores; panel de detalle; conexión en vivo (SSE) |
| `ui/state.js`, `ui/format.js`, `ui/prefs.js`, `ui/parts.js`, `ui/cache-timer.js` | Estado compartido, formato, preferencias, fragmentos de HTML y temporizador de caché |
| `ui/json-tree.js` | Visor de JSON plegable |
| `ui/css/` | Una hoja por zona: `tokens`, `base`, `header`, `layout`, `tables`, `parts`, `detail`, `json-tree`, `help`, `responsive`. El orden de los `<link>` de `index.html` es la cascada |
| `start.sh` | Crea el venv si falta y arranca proxy (8899) y panel (8900) |
| `via.sh` | Lanza un comando a través del proxy |

No se versionan: `ca/` (claves del proxy), `data/` (métricas capturadas), `venv/`.

## Comandos

- Arrancar: `./start.sh`
- Lanzar un cliente por el proxy: `./via.sh <comando>`
- Tests: `venv/bin/python -m unittest discover -s tests -t . -q`
- Panel de prueba sin proxy (puerto 8901): `venv/bin/python tests/replay/serve.py`
- Comprobación de la interfaz en un Chrome sin ventana: `node tests/ui/check.mjs --full`

## Refactorización en curso

El backend y el frontend ya están partidos en módulos; falta la fase 4 (ayuda con fuente única y este mapa definitivo). El plan vive en `.plans/arquitectura-localidad/`:

- `README.md`: índice de tareas con sus dependencias y su estado.
- `reglas.md`: reglas comunes para ejecutar cualquier tarea.
- `fase-N/`: un fichero por tarea.

Para ejecutar una tarea, lee `reglas.md` y el fichero de esa tarea; no hace falta leer el resto.
Este fichero se reescribe con el mapa definitivo en la tarea 4.03.

## Reglas

- Sin dependencias nuevas: backend con la librería estándar de Python; frontend sin build.
- mitmproxy recarga `tap.py` al guardarlo; lo capturado en memoria se pierde en cada recarga.
- Las cabeceras de la petición nunca se leen ni se guardan: ahí va el token de autenticación.
- Comentarios y nombres en inglés; textos de la interfaz en castellano.
