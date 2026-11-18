# Validación por cliente: resultado parcial de 2.01

El usuario autorizó una invocación por cliente de IA con `hola` o `holi`, sin reintentos. Tras comprobar que el entorno temporal no tenía cuenta, el usuario pidió continuar con la cuenta habitual de OpenCode. Se mantuvo la autenticación habitual, se arrancó un servidor propio solo para heredar el proxy y se deshabilitaron herramientas, plugins externos y MCP para la prueba. No se exportaron ni copiaron credenciales. Solo se invocó OpenCode: se detuvo la prueba antes de Claude Code y Copilot CLI, tal como exige el plan ante un fallo.

| Cliente | Versión | Perfil/modelo | Transporte | Filas `done` con uso | Lectura y veredicto | Chrome: oscuro/claro × escritorio/estrecho | Cargo | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Copilot CLI | 1.0.112 | No invocado; previsto `gpt-6-luna`, `low` | No observado | — | — | No ejecutado | No hubo llamada | bloqueada: parada tras OpenCode |
| Claude Code | 2.1.327 | Se confirmó inicio de sesión de Claude; no se invocó el modelo | No observado | — | — | No ejecutado | No hubo llamada | bloqueada: parada tras OpenCode |
| OpenCode | 2.3.2 | Cuenta habitual Copilot; modelo solicitado `github-copilot/gpt-5.4-nano` | HTTPS `/responses` vía proxy | 0 | Tres filas sin uso: `N/A`, «Lectura de caché: sin datos» | 12/12 para las tres filas sin uso | No informado | bloqueada: HTTP 400 del proveedor; dos peticiones adicionales bloqueadas localmente |
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
