# Validación por cliente: resultado parcial de 2.01

El usuario autorizó una invocación por cliente de IA con `hola` o `holi`, sin reintentos. **No se lanzó ninguna invocación de IA**: la instancia privada de OpenCode, con configuración, directorio y estado temporales, devolvió una lista vacía en `auth list --standalone`; no se exportaron ni copiaron credenciales. La puerta de ejecución del plan impide iniciar las llamadas de cuota hasta completar esa comprobación previa. No se validó ningún binario de IA autenticado.

| Cliente | Versión | Perfil/modelo | Transporte | Filas `done` con uso | Lectura y veredicto | Chrome: oscuro/claro × escritorio/estrecho | Cargo | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Copilot CLI | 1.0.112 | No invocado; previsto `gpt-6-luna`, `low` | No observado | — | — | No ejecutado | No hubo llamada | bloqueada: puerta de ejecución |
| Claude Code | 2.1.327 | Se confirmó inicio de sesión de Claude; no se invocó el modelo | No observado | — | — | No ejecutado | No hubo llamada | bloqueada: puerta de ejecución |
| OpenCode | 2.3.2 | Instancia privada sin cuenta conectada; ningún modelo invocado | No observado | — | — | No ejecutado | No hubo llamada | bloqueada: falta autenticación en el entorno aislado |
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
