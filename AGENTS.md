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
| `ui/app.js` | Lista, filtros, detalle y conexión en vivo (SSE) |
| `ui/json-tree.js` | Visor de JSON plegable |
| `ui/app.css`, `ui/tokens.css` | Estilos y variables de diseño |
| `start.sh` | Crea el venv si falta y arranca proxy (8899) y panel (8900) |
| `via.sh` | Lanza un comando a través del proxy |

No se versionan: `ca/` (claves del proxy), `data/` (métricas capturadas), `venv/`.

## Comandos

- Arrancar: `./start.sh`
- Lanzar un cliente por el proxy: `./via.sh <comando>`
- Tests: `venv/bin/python -m unittest discover -s tests -t . -q`
- Panel de prueba sin proxy (puerto 8901): `venv/bin/python tests/replay/serve.py`

## Refactorización en curso

El backend ya está partido en módulos; falta el frontend (`ui/app.js` y `ui/app.css`). El plan vive en `.plans/arquitectura-localidad/`:

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
