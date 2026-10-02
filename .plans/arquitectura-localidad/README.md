# Arquitectura por localidad: índice

Objetivo: que un agente resuelva cada cambio leyendo pocos ficheros pequeños. Se parte `tap.py`, `ui/app.js` y
`ui/app.css` por motivo de cambio, sin alterar el comportamiento, y se añaden tests.

## Cómo se ejecuta

- Una tarea = un agente. Cada agente lee `reglas.md` y el fichero de su tarea, nada más.
- Una tarea se puede lanzar cuando todas las de «Depende de» están terminadas. Las que cumplen eso a la vez se pueden lanzar en paralelo.
- Estados: `pendiente` · `en curso` · `terminada sin commit` · `terminada con commit` · `bloqueada`.
- Al cerrar cada fase se para y se espera la confirmación del usuario.

## Tareas

| ID | Tarea | Fichero | Depende de | Estado | Notas |
| --- | --- | --- | --- | --- | --- |
| 0.01 | Commit de partida (solo por orden del usuario) | — | — | terminada con commit | 12 commits, de `80cba76` a `6d78e21` |
| 1.01 | Flujos falsos y adaptador | `fase-1/1.01-flujos-y-adaptador.md` | — | terminada con commit | |
| 1.02 | Constructores de peticiones y respuestas | `fase-1/1.02-constructores.md` | — | terminada con commit | |
| 1.03 | Ejecutor del escenario | `fase-1/1.03-ejecutor.md` | 1.01, 1.02 | terminada con commit | |
| 1.04 | Pasos de Anthropic | `fase-1/1.04-pasos-anthropic.md` | 1.03 | terminada con commit | |
| 1.05 | Pasos de OpenAI | `fase-1/1.05-pasos-openai.md` | 1.03 | terminada con commit | |
| 1.06 | Pasos varios | `fase-1/1.06-pasos-varios.md` | 1.03 | terminada con commit | |
| 1.07 | Golden | `fase-1/1.07-golden.md` | 1.04, 1.05, 1.06 | terminada con commit | golden generado por el usuario; sha1 `3270ea7c` |
| 1.08 | Test de expulsión | `fase-1/1.08-expulsion.md` | 1.03 | terminada con commit | |
| 1.09 | Test del panel HTTP | `fase-1/1.09-panel-http.md` | 1.03 | terminada con commit | |
| 1.10 | Servidor de prueba | `fase-1/1.10-servidor-de-prueba.md` | 1.07 | terminada con commit | |
| 2.01 | Paquete y recarga en caliente | `fase-2/2.01-paquete-y-recarga.md` | 1.07, 1.08, 1.09 | terminada con commit | |
| 2.02 | `config.py` | `fase-2/2.02-config.md` | 2.01 | terminada con commit | |
| 2.03 | `record.py` | `fase-2/2.03-record.md` | 2.02 | terminada con commit | |
| 2.04 | `segments.py` | `fase-2/2.04-segments.md` | 2.03 | terminada con commit | |
| 2.05 | `providers/base.py` | `fase-2/2.05-providers-base.md` | 2.04 | terminada con commit | |
| 2.06 | Anthropic: reglas por modelo | `fase-2/2.06-anthropic-modelo.md` | 2.05 | terminada con commit | |
| 2.07 | OpenAI: reglas por modelo | `fase-2/2.07-openai-modelo.md` | 2.06 | terminada con commit | |
| 2.08 | Despacho por modelo | `fase-2/2.08-despacho-modelo.md` | 2.07 | pendiente | |
| 2.09 | Esfuerzo, usage y primer token | `fase-2/2.09-formato-mensaje.md` | 2.08 | pendiente | |
| 2.10 | `response_body.py` | `fase-2/2.10-response.md` | 2.09 | pendiente | |
| 2.11 | `linking.py` | `fase-2/2.11-linking.md` | 2.10 | pendiente | |
| 2.12 | `verdict.py` | `fase-2/2.12-verdict.md` | 2.11 | pendiente | |
| 2.13 | `store.py` | `fase-2/2.13-store.md` | 2.12 | pendiente | |
| 2.14 | `dashboard.py` | `fase-2/2.14-dashboard.md` | 2.13 | pendiente | |
| 2.15 | Cierre del backend | `fase-2/2.15-cierre-backend.md` | 2.14 | pendiente | |
| 3.00 | Test de recursos de la interfaz | `fase-3/3.00-test-recursos-ui.md` | — | terminada con commit | |
| 3.01 | JS: `format.js` y `prefs.js` | `fase-3/3.01-js-format-prefs.md` | 3.00, 1.10, 2.15 | pendiente | |
| 3.02 | JS: `state.js` | `fase-3/3.02-js-state.md` | 3.01 | pendiente | |
| 3.03 | JS: `parts.js` y `cache-timer.js` | `fase-3/3.03-js-parts-timer.md` | 3.02 | pendiente | |
| 3.04 | JS: `list.js` | `fase-3/3.04-js-list.md` | 3.03 | pendiente | |
| 3.05 | JS: `detail.js` | `fase-3/3.05-js-detail.md` | 3.04 | pendiente | |
| 3.06 | JS: `stream.js` y cierre de `app.js` | `fase-3/3.06-js-stream.md` | 3.05 | pendiente | |
| 3.07 | CSS: copiar por secciones | `fase-3/3.07-css-particion.md` | — | terminada con commit | |
| 3.08 | CSS: cambiar a los ficheros nuevos | `fase-3/3.08-css-cambio.md` | 3.00, 3.06, 3.07 | pendiente | |
| 4.01 | Referencia de TTL y mínimos en el backend | `fase-4/4.01-referencia-backend.md` | 2.15, 3.08 | pendiente | |
| 4.02 | Ayuda pintada desde la referencia | `fase-4/4.02-ayuda-frontend.md` | 4.01, 3.08 | pendiente | |
| 4.03 | `AGENTS.md` | `fase-4/4.03-agents-md.md` | 4.02 | pendiente | |
| 4.04 | Verificación con el proxy real (con el usuario) | `fase-4/4.04-verificacion-real.md` | 4.03 | pendiente | |

## Qué se puede lanzar a la vez

- Arranque: 1.01, 1.02, 3.00 y 3.07.
- Tras 1.03: 1.04, 1.05, 1.06, 1.08 y 1.09.
- La fase 2 es una cadena: cada tarea edita `tap.py`.
- Las tareas 3.01 a 3.06 son una cadena: cada una edita `ui/app.js`.
- La fase 4 es una cadena.

## Estructura final

```
tap.py                  hooks de mitmproxy y cableado
cachetap/
  config.py             rutas, puertos, TTL, MAX
  record.py             contrato del registro
  providers/            base.py, anthropic.py, openai.py, __init__.py (despacho)
  segments.py           trocear la petición, hash, diff
  linking.py            emparejar con la petición anterior
  verdict.py            HIT / PARTIAL / MISS / COLD / N/A
  response_body.py      usage y texto del cuerpo de la respuesta
  store.py              estado en memoria, suscriptores, jsonl
  dashboard.py          servidor HTTP del panel
ui/
  app.js  state.js  format.js  prefs.js  parts.js  cache-timer.js  list.js  detail.js  stream.js  help.js  json-tree.js
  css/    tokens  base  header  layout  tables  parts  detail  json-tree  help  responsive
tests/
  replay/               escenario sintético y golden
  test_*.py             uno por módulo
AGENTS.md
```

## Decisiones ya tomadas

- La entrada sigue siendo `tap.py`; `start.sh` no cambia. El paquete se llama `cachetap` porque un paquete `tap/` taparía a `tap.py`.
- Tests con `unittest`, sin instalar nada.
- El mapa para agentes es `AGENTS.md`, no `CLAUDE.md`. Ya existe con el estado actual; la tarea 4.03 lo reescribe con la estructura final.
- Fallos conocidos que **no** se arreglan: una línea SSE cuyo JSON no es un objeto hace fallar `_output_text`;
  `claude-3-5-haiku-*` no se reconoce como Haiku 3.5 y se queda en 1024.
- Copia del estado inicial: carpeta `backup-llm-cache-tap` del scratchpad de la sesión que creó el plan (no sobrevive a un reinicio).
