# Validación por cliente de 2.01

**Estado (2026-11-18):** los tres clientes de IA tienen al menos una captura útil validada en Chrome. Primera ronda: el usuario autorizó una invocación por cliente con `hola` o `holi`, sin reintentos; OpenCode falló y se paró. Segunda ronda: el usuario pidió probar todos los clientes con varios modelos, una invocación por modelo y sin reintentos (detalle abajo).

Primera ronda: el usuario autorizó una invocación por cliente de IA con `hola` o `holi`, sin reintentos. Tras comprobar que el entorno temporal no tenía cuenta, el usuario pidió continuar con la cuenta habitual de OpenCode. Se mantuvo la autenticación habitual, se arrancó un servidor propio solo para heredar el proxy y se deshabilitaron herramientas, plugins externos y MCP para la prueba. No se exportaron ni copiaron credenciales. Solo se invocó OpenCode: se detuvo la prueba antes de Claude Code y Copilot CLI, tal como exige el plan ante un fallo.

| Cliente | Versión | Perfil/modelo | Transporte | Filas `done` con uso | Lectura y veredicto | Chrome: oscuro/claro × escritorio/estrecho | Cargo | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Copilot CLI | 1.0.112 | Cuenta habitual; `gpt-6-luna`, `low` | Responses WebSocket (`101`) | 1 | 0/13799 · 0,0 % · `COLD` | 4/4 | CLI: 0,17 AI Credits; panel: $0,0017318 (coinciden) | pasó |
| Copilot CLI | 1.0.112 | Cuenta habitual; `claude-haiku-5.5` | HTTPS `/v1/messages` | 1 | 16928/23694 · 71,4 % · `PARTIAL` | 4/4 | CLI: 0,11 AI Credits; panel: sin precio | pasó |
| Claude Code | 2.1.327 | Login de Claude; `claude-haiku-5-5` | HTTPS `/v1/messages` | 1 | 649/3090 · 21,0 % · `PARTIAL` | 4/4 | No informado; panel: sin precio | pasó |
| Claude Code | 2.1.327 | Login de Claude; `claude-sonnet-5-5` | HTTPS `/v1/messages` | 1 | 649/2227 · 29,1 % · `PARTIAL` | 4/4 | No informado; panel: $0,0066978 | pasó |
| OpenCode | 2.3.2 | Cuenta habitual Copilot; `claude-haiku-5.5` | HTTPS `/v1/messages` | 1 | 0/1214 · 0,0 % · `COLD` | 4/4 | No informado; panel: sin precio | pasó |
| OpenCode | 2.3.2 | Cuenta habitual Copilot; `gemini-3.8-flash` | HTTPS `/chat/completions` | 1 | 0/591 · 0,0 % · `N/A` (bajo el mínimo cacheable) | 4/4 | No informado; panel: $0,0005745 | pasó |
| OpenCode | 2.3.2 | Cuenta habitual Copilot; `gpt-6-luna` | HTTPS `/responses` | 0 | Fila `error`/`ERR` con HTTP 200, sin `usage`; el CLI sí respondió y salió con 0 | No aplica | No informado | anomalía del inspector (ver abajo) |
| OpenCode (1.ª ronda) | 2.3.2 | Cuenta habitual Copilot; `gpt-5.4-nano` | HTTPS `/responses` | 0 | Tres filas sin uso: `N/A`, «Lectura de caché: sin datos» | 12/12 para las tres filas sin uso | No informado | HTTP 400 del proveedor |
| Node `fetch` | 24.14.1 | Sin cuenta; mock `gpt-4o-mini` | HTTPS Chat Completions vía proxy | 1 (`#1`) | 9500/10000 · 95,0 % verde · `HIT` | 4/4 | Sin proveedor facturable | pasó |
| Python `requests` | 2.34.2 | Sin cuenta; mock `gpt-4o-mini` | HTTPS Chat Completions vía proxy | 1 (`#2`) | 9500/10000 · 95,0 % verde · `HIT` | 4/4 | Sin proveedor facturable | pasó |
| Python `httpx` | 0.28.1 | Sin cuenta; mock `gpt-4o-mini` | HTTPS Chat Completions vía proxy | 1 (`#3`) | 9500/10000 · 95,0 % verde · `HIT` | 4/4 | Sin proveedor facturable | pasó |
| `curl` | 8.7.1 | Sin cuenta; mock `gpt-4o-mini` | HTTPS Chat Completions vía proxy | 1 (`#4`) | 9500/10000 · 95,0 % verde · `HIT` | 4/4 | Sin proveedor facturable | pasó |

Los cuatro clientes de script fueron procesos reales contra un servidor HTTPS local simulado, no replays ni llamadas a proveedores. El control directo devolvió HTTP 200 y no creó fila; cada llamada a través del proxy creó una sola fila. Se validó TLS en ambos tramos con CAs independientes de prueba. `requests` y `httpx` se instalaron en un entorno temporal, sin cambiar el del proyecto. El coste estimado por el panel sobre tokens sintéticos no representa un cargo.

Comandos ejecutados con el proxy aislado en marcha; los manifiestos y puertos eran temporales:

```sh
TAP_UI_PORT=57852 TAP_DEBUG_PORT=57877 node tests/ui/check.mjs --inspect-cache-read /private/var/folders/g6/rb0r99js4qn4mx1_g2gr40280000gr/T/opencode/cache-read-real.2qUhXf/Node.json
TAP_UI_PORT=57852 TAP_DEBUG_PORT=57966 node tests/ui/check.mjs --inspect-cache-read /private/var/folders/g6/rb0r99js4qn4mx1_g2gr40280000gr/T/opencode/cache-read-real.2qUhXf/requests.json
TAP_UI_PORT=57852 TAP_DEBUG_PORT=58036 node tests/ui/check.mjs --inspect-cache-read /private/var/folders/g6/rb0r99js4qn4mx1_g2gr40280000gr/T/opencode/cache-read-real.2qUhXf/httpx.json
TAP_UI_PORT=57852 TAP_DEBUG_PORT=58108 node tests/ui/check.mjs --inspect-cache-read /private/var/folders/g6/rb0r99js4qn4mx1_g2gr40280000gr/T/opencode/cache-read-real.2qUhXf/curl.json
```

Los cuatro comandos emitieron `ok   CACHE-READ-VISUAL: 4 combinaciones`. `venv/bin/python scripts/check.py --full` también pasó (423 pruebas Python, 24 JavaScript y C35 con 32 combinaciones de replay). No se da por cerrada la fase 2.

## Intento autenticado de OpenCode

El catálogo de la cuenta listaba `github-copilot/gpt-5.4-nano`, pero la única petición enviada al proveedor respondió HTTP 400; el CLI informó de que el modelo solicitado no estaba disponible y terminó con código 1. En esa misma invocación el CLI intentó dos peticiones adicionales (`gpt-6-luna` y `gpt-5.4-nano`), a las que el proxy de prueba devolvió HTTP 403 local para impedir enviarlas al proveedor. No se hizo otra invocación ni se eligió un sustituto. La API marcó las tres filas `done` (captura terminada, no éxito HTTP) y ninguna trajo `usage`. La comprobación visual verifica únicamente ese estado sin datos, no una captura útil de inferencia.

```sh
TAP_UI_PORT=58909 TAP_DEBUG_PORT=58941 node tests/ui/check.mjs --inspect-cache-read /private/var/folders/g6/rb0r99js4qn4mx1_g2gr40280000gr/T/opencode/cache-read-paid.kaIPjX/opencode/manifest.json
```

El comando emitió `ok   CACHE-READ-VISUAL: 12 combinaciones`.

## Segunda ronda autenticada (2026-11-18)

Siete invocaciones, una por modelo, con `hola` (`holi` en Copilot CLI) y sin reintentos. Cada una usó su propio proxy, panel, JSONL y workspace temporales en puertos efímeros (nunca 8899/8900), con la CA existente solo para el proceso cliente. Un addon de prueba dejaba pasar **una sola** llamada de inferencia con el modelo pedido y respondía 403 local a cualquier otra. En las siete se dejó pasar exactamente una y no se bloqueó ninguna.

- **OpenCode:** `opencode run --standalone --archived --title prueba -m github-copilot/<modelo> hola`, con `XDG_CONFIG_HOME` temporal. La config contenía solo `plugin: []`, `mcp: {}`, `tools: {"*": false}` y `permission: {"*": "deny"}`, y `opencode debug config` confirmó que no se cargaba la config global. La cuenta habitual siguió en su directorio de datos, sin copiar credenciales. `--standalone` levanta un servidor propio que hereda el proxy; sin él, el servicio de fondo llamaría al proveedor sin pasar por el inspector. `--title` evita la llamada de título.
- **Claude Code:** `claude -p --safe-mode --tools "" --strict-mcp-config --no-session-persistence --model <modelo> hola`. `--safe-mode` desactiva hooks, plugins, MCP, skills y CLAUDE.md, y conserva el login.
- **Copilot CLI:** los flags de aislamiento de `run_real` con `--model=<modelo>`, `--reasoning-effort=low` (solo `gpt-6-luna`) y `--usage-output-file`. Se ejecutó desde un proceso normal, no desde la terminal de Orca, y autenticó sin problema. Los tokens de `usage` del panel coinciden exactamente con `modelMetrics` del CLI en ambos modelos.
- Cada fila útil se verificó con el panel aislado aún en marcha. El manifiesto tenía `id`, `verdict`, `label`, `high` e `incremental`. `label` y `high` salieron del `usage` de la API con `pct` de `ui/format.js`, no del DOM. Los siete paneles usaron este comando, y los seis con fila `done` emitieron `ok   CACHE-READ-VISUAL: 4 combinaciones`:

```sh
TAP_UI_PORT=<puerto del panel aislado> TAP_DEBUG_PORT=<puerto CDP libre> node tests/ui/check.mjs --inspect-cache-read <manifiesto.json>
```

### Anomalía: OpenCode + `gpt-6-luna` por HTTP `/responses`

OpenCode recibió la respuesta completa y salió con código 0. Aun así, el inspector dejó la fila en `state=error`, `verdict=ERR` y `status=200`, sin `usage`.

**Causa reproducida sin cuota (2026-11-18).** Se probó un mock local de Responses SSE detrás del proxy aislado, con OpenCode 2.3.2 real (`@ai-sdk/openai`, host ficticio redirigido por el proxy):

| Cliente | El servidor cierra el stream | Fila |
| --- | --- | --- |
| `curl`, lee hasta EOF | al instante | `done`, con `usage` |
| Socket que cierra tras `response.completed` | 2 s después | `error`/`ERR`, HTTP 200, sin `usage`, nota «Client disconnected.» |
| OpenCode | al instante | `done`, con `usage` |
| OpenCode | 3 s después | `error`/`ERR`, HTTP 200, sin `usage`, nota «Client disconnected.» (el CLI salió a los 0,78 s) |

OpenCode da la respuesta por terminada al recibir `response.completed` y sale sin esperar al final del cuerpo. Si el servidor tarda en cerrar el stream, mitmproxy dispara `error` («Client disconnected.») antes de `response`. Entonces `capture.fail` publica `ERR` y descarta los bytes ya capturados, `usage` incluido. La fila real tiene la misma huella. No se guardó su nota exacta, así que que Copilot tarde en cerrar `/responses` es una inferencia, no una observación. Los demás formatos no fallaron porque su servidor cerró a tiempo.

Arreglo propuesto, fuera del alcance de 2.01: si el error de flujo llega cuando lo capturado ya contiene el evento terminal con `usage` (`response.completed`, `message_stop`, `[DONE]`), terminar la captura como `done`. Sería en `cachetap/capture.py`, junto con el hook `error` de `tap.py`, con un test sintético de desconexión tardía.

### Precios ausentes observados

`claude-haiku-5-5` no tiene precio en la lista de Anthropic, y `claude-haiku-5.5` tampoco en la tarifa de Copilot. El panel lo muestra correctamente como `cost_missing` y no estima nada. Actualizar `cachetap/prices/` es otra tarea.
