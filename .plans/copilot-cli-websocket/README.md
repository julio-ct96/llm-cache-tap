# Copilot CLI por WebSocket: índice

Objetivo: reconocer la inferencia Responses WebSocket que usa Copilot CLI y mostrar cada petición en el inspector con modelo, tokens, caché y coste por las tablas existentes. Mantener sin cambios el comportamiento HTTP, los datos del usuario y el replay histórico.

**Fase 1 terminada; fase 2 en ejecución.** La captura común ya está extraída; se está incorporando el soporte WebSocket.

## Acuerdo de ejecución

- Ejecutores: subagentes GPT-6 Luna (high), uno por tarea.
- El usuario pidió commit y push por tarea; los hace el orquestador, después de las verificaciones, nunca los subagentes.
- Punto de partida acordado: checkout actual sobre `60c3b39`, conservando fuera de los commits del plan los seis ficheros con trabajo previo. Sus huellas y la del golden están en `base-ejecucion.json`.
- El plan se versiona en un commit separado antes de empezar. No se descartan ni incluyen cambios ajenos, no se hace stash y no se fuerza ningún push.
- La fase 2 fue autorizada tras cerrar la fase 1. Al cerrar cada fase se para y se espera confirmación antes de la siguiente.

## Hallazgo que determina el cambio

Copilot CLI 1.0.105 no envió esa inferencia como POST: abrió GET `/responses` con upgrade 101 y envió `response.create` por WebSocket. `/auto` solo enruta y devuelve un token de sesión, por lo que añadirlo al filtro sería incorrecto y peligroso para la privacidad.

La prueba adicional de identificación fue un único `hola` en modo `efficiency`; seleccionó GPT-6 Luna y reportó 0,06 créditos. La evidencia de forma, los contratos y los límites están en [protocolo.md](protocolo.md). [caso.json](caso.json) es un fixture artificial, no una captura cruda.

## Cómo se ejecuta

- Una tarea por ejecutor; lee [reglas.md](reglas.md), su tarea y las secciones de protocolo que cite. Del índice solo necesita su fila y los estados de dependencias.
- Solo se inicia cuando todas las dependencias están terminadas. No se lanzan tareas que comparten ficheros en paralelo.
- Estados: `pendiente` · `en curso` · `terminada sin commit` · `terminada con commit` · `bloqueada`.
- Al terminar cada fase se para y se espera confirmación.
- No se hacen commits automáticamente. La comprobación de pago final es optativa y no bloquea la entrega offline.

## Tareas

| ID | Tarea | Fichero | Depende de | Estado | Notas |
| --- | --- | --- | --- | --- | --- |
| 1.01 | Red de seguridad HTTP y caso Responses | [1.01](fase-1/1.01-red-seguridad.md) | — | terminada con commit | CHECK: 301 Python y 20 JS; golden y cambios previos intactos |
| 1.02 | Extraer el alta compartida | [1.02](fase-1/1.02-alta-compartida.md) | 1.01 | terminada con commit | CHECK y golden OK; retorno corregido a int tras revisión |
| 1.03 | Extraer el ciclo de captura | [1.03](fase-1/1.03-ciclo-captura.md) | 1.02 | terminada con commit | CHECK --full OK; formato corregido tras revisión; golden intacto |
| 2.01 | Decoder y proyección sin sobre | [2.01](fase-2/2.01-decodificacion.md) | 1.03 | terminada con commit | CHECK: 309 Python y 20 JS; proyección sin sobre; golden intacto |
| 2.02 | Contrato del transporte e idempotencia | [2.02](fase-2/2.02-contrato-transporte.md) | 2.01 | terminada con commit | Auditado; fixture/pipeline reales; CHECK: 318 Python y 20 JS; golden intacto |
| 2.03 | Sesión secuencial: camino correcto | [2.03](fase-2/2.03-sesion-secuencial.md) | 2.02 | terminada con commit | Auditado; correlación y privacidad del fixture OK; CHECK: 324 Python y 20 JS; sin hooks |
| 2.04 | Errores, límites y desincronización | [2.04](fase-2/2.04-errores-y-limites.md) | 2.03 | terminada con commit | Auditada: error sin ID y fallo de log corregidos; CHECK: 339 Python y 20 JS; golden intacto |
| 2.05 | Cablear hooks mitmproxy | [2.05](fase-2/2.05-hooks-mitmproxy.md) | 2.04 | terminada con commit | Auditado: fixture acordado, host/ruta y no-mutación; CHECK: 349 Python y 20 JS; golden intacto |
| 2.06 | API y panel con tráfico sintético | [2.06](fase-2/2.06-api-y-panel.md) | 2.05 | pendiente | Chrome sin cuota; no cambia ui/ |
| 3.01 | Runner real opt-in y económico | [3.01](fase-3/3.01-smoke-economico.md) | 2.06 | pendiente | Prepararlo no llama al modelo |
| 3.02 | Documentar soporte y límites | [3.02](fase-3/3.02-documentacion.md) | 2.06 | pendiente | Conserva los cambios ajenos de AGENTS.md |
| 3.03 | Una comprobación real barata | [3.03](fase-3/3.03-verificacion-real.md) | 3.01 | pendiente | Optativa; requiere autorización vigente y acceso; nunca reintenta |

## Qué se puede lanzar a la vez

- Las fases 1 y 2 son cadenas: las extracciones comparten tap/capture y la incorporación del transporte comparte websocket y sus tests.
- Tras confirmar el cierre de fase 2, 3.01 y 3.02 pueden ir en paralelo: no comparten ficheros de trabajo. Cada una modifica solo su propia fila del índice.
- 3.03 puede ejecutarse cuando 3.01 esté terminada, aunque la documentación siga pendiente: no edita código. Un bloqueo de autenticación o cuota no impide acabar 3.02 ni entregar el soporte offline.

## Estructura final de la implementación

| Ruta | Contenido |
| --- | --- |
| `cachetap/capture.py` (nuevo) | Ciclo común extraído de tap, sin objetos mitmproxy |
| `cachetap/websocket.py` (nuevo) | Decoder/proyección Responses y Session secuencial |
| `tap.py` | Hooks HTTP existentes y hooks WebSocket finos |
| `cachetap/record.py`, `cachetap/verdict.py` | Campos exclusivos del transporte y prudencia ante contexto incremental |
| `tests/fixtures/copilot_responses_ws.json` (nuevo) | Caso sintético sin secretos reales |
| `tests/test_capture_regression.py` (nuevo) | Oráculo HTTP y análisis existente |
| `tests/test_capture.py` (nuevo) | Timestamps, metadatos, contexto parcial e idempotencia de captura |
| `tests/test_websocket.py` (nuevo) | Decoder, sesión, errores, límites y coste una sola vez |
| `tests/test_websocket_hooks.py` (nuevo) | Hooks con objetos reales de mitmproxy y helper play_fixture |
| `tests/test_websocket_dashboard.py` (nuevo) | API/SSE del registro capturado |
| `tests/ui/check.mjs` | C34 para representar el registro en la UI actual |
| `scripts/check_copilot.py`, `tests/test_check_copilot.py` (nuevos) | Smoke opt-in y pruebas de runner sin cuota |
| `tests/test_dependencies.py`, `pyproject.toml` | Registrar los nuevos módulos y su tipado |
| `tests/test_flows.py`, `tests/test_record.py`, `tests/test_verdict.py` | Targets tras extracción y cobertura de contratos |
| `README.md`, `AGENTS.md` | Soporte, alcance y comandos |

## Decisiones ya tomadas

- Añadir soporte nativo de WebSocket, no forzar al CLI a cambiar de transporte ni desactivar TLS.
- Reutilizar normalización OpenAI, veredictos y precios actuales; no copiar cálculo de coste dentro de los hooks WebSocket.
- No crear proveedor Copilot ni añadir `/auto` a `LLM_PATHS`; no guardar su session_token ni cabeceras embebidas.
- Mantener HTTP sin nuevos defaults y no regenerar golden: el escenario antiguo no contiene inferencias WebSocket.
- Primer alcance: Responses WebSocket en hosts Copilot, peticiones secuenciales. Contexto incremental se muestra con N/A, no se reconstruye un prefijo supuesto.
- En errores ambiguos se deja de inspeccionar esa conexión sin tocar los bytes del cliente. Una conexión nueva vuelve a ser inspeccionable.
- Los límites son del inspector; no prometen acotar el historial de mitmproxy ni el RSS.
- La interfaz existente ya acepta registros parciales y status 101. Se añade cobertura, no diseño ni CSS.
- Los tests de regresión deben ir antes que las extracciones. La prueba real queda aparte y nunca se incorpora a CHECK o CI.
- Fallos/funciones que no se arreglan: Antigravity, Gemini nativo, otros hosts WebSocket, multiplexación simultánea, reconstrucción de previous_response_id y descuentos/créditos de Auto frente a precios de tabla.
- Advertencia ya observada de Node sobre MODULE_TYPELESS_PACKAGE_JSON: no forma parte de este trabajo; todas las comprobaciones pasaron a pesar de ella.

## Estado comprobado al escribir

- `venv/bin/python scripts/check.py` y `venv/bin/python scripts/check.py --full`: pasaron; 296 tests Python, 20 tests JS y lista completa de Chrome.
- Replay histórico: 44 registros, 131 eventos, 44 cuerpos y 43 líneas de log; golden verificado, no actualizado.
- El payload de uso capturado ya lo entienden los lectores actuales: falta transporte, no una tabla nueva de tokens. `check_plan.py` vuelve a comprobar los resultados sobre el código real sin red externa.
- Había modificaciones previas en `AGENTS.md`, `cachetap/prices/openai.py`, `tests/test_dashboard.py`, `tests/test_prices.py`, `tests/test_prices_copilot.py` y `tests/test_prices_openai.py`. No son parte del plan y no se descartan ni corrigen.

## Validar el plan

Desde la raíz: `venv/bin/python .plans/copilot-cli-websocket/check_plan.py`.

Salida esperada: `Plan OK: 12 tareas; enlaces, dependencias y caso verificado`.
