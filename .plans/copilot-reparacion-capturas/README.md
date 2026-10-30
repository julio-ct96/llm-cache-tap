# Reparación de capturas Copilot: índice

Objetivo: corregir las falsas capturas WebSocket fallidas, admitir uso CLI válido y cubrir la tarifa Copilot ausente, sin mezclar respuestas, inventar contadores/precios ni alterar el tráfico.

**Estado: fase 1 autorizada con Luna; preparando ejecución aislada.** Las fichas de reparación de fase 2 son **reservas bloqueadas**, no instrucciones para que Luna invente la solución: faltan una regla de IDs demostrada, el esquema pertinente de uso y la tarifa oficial. Deben sustituirse por recetas cerradas tras la evidencia y la confirmación de la fase siguiente. La activación necesita permiso posterior independiente.

## Cómo se ejecuta

- Un subagente Luna por tarea, con auditoría del orquestador y commit/push separado por tarea aprobada. El plan se publica separado antes de empezar cuando se autorice su ejecución; nunca se incluyen los ocho cambios previos.
- El ejecutor lee `reglas.md`, su tarea y las secciones que esta cite. Consulta solo su fila y dependencias del índice. No lee otras tareas para deducir instrucciones.
- Solo se lanzan tareas pendientes con dependencias terminadas con commit. Una ficha bloqueada no se ejecuta. Estados: `pendiente`, `en curso`, `terminada sin commit`, `terminada con commit`, `bloqueada`.
- Desarrollo en checkout separado del inspector vivo. Al terminar cada fase: auditoría, resumen y confirmación del usuario antes de continuar.
- Investigación pública de fuentes sin inferencias. Cero pruebas pagadas nuevas y cero reintentos automáticos.

## Tareas

| ID | Tarea | Fichero | Depende de | Estado | Notas |
| --- | --- | --- | --- | --- | --- |
| 1.01 | Red de seguridad WebSocket | [1.01](fase-1/1.01-regresiones-websocket.md) | — | terminada con commit | Seis secuencias auditadas; acumulados y coste comprobados explícitamente; ninguna reparación de producción |
| 1.02 | Contrato seguro de correlación | [1.02](fase-1/1.02-contrato-ids.md) | 1.01 | pendiente | Puede concluir evidencia insuficiente; no debilita la correlación |
| 1.03 | Contrato y seguridad del uso CLI | [1.03](fase-1/1.03-contrato-uso-cli.md) | — | terminada con commit | Cinco tests sintéticos auditados y fuentes SDK ancladas; el formato del temporal y la causa histórica siguen sin acreditarse |
| 1.04 | Fuente oficial para Argon | [1.04](fase-1/1.04-verificar-tarifa.md) | — | terminada con commit | Tarifas promocionales y tier de contexto auditados al 2026-10-30; escritura no acreditada, approved=false y cost_missing conservados |
| 2.01 | Reparación WebSocket | [2.01](fase-2/2.01-correlacion-websocket.md) | 1.02 | bloqueada | Falta contrato aprobado y sustitución de la reserva por una receta exacta |
| 2.02 | Compatibilidad del lector de uso | [2.02](fase-2/2.02-validacion-uso-cli.md) | 1.03 | bloqueada | Falta esquema probado y receta exacta; no defaults inventados |
| 2.03 | Fila Copilot de Argon | [2.03](fase-2/2.03-precio-argon.md) | 1.04 | bloqueada | Sin cifras oficiales verificadas se conserva cost_missing |
| 3.01 | Integración y resultado offline | [3.01](fase-3/3.01-integracion.md) | 2.01 | pendiente | Incluye 2.02/2.03 solo si ya están aprobadas; deja explícitos sus bloqueos |
| 4.01 | Respaldo y activación controlada | [4.01](fase-4/4.01-respaldo-activacion.md) | 3.01 | bloqueada | Permiso independiente y receta de respaldo/servicio del momento; ninguna inferencia incluida |

## Qué puede ir en paralelo

- 1.01, 1.03 y 1.04 no comparten ficheros de trabajo. Cada agente actualiza solo su fila del índice; el orquestador integra las filas sin perder cambios.
- 1.02 sigue a 1.01; puede coincidir con las otras investigaciones pendientes.
- Tras la auditoría y reescritura de fichas, 2.01, 2.02 y 2.03 podrán ir en paralelo solo si sus listas cerradas siguen sin compartir ficheros. Ninguna se desbloquea automáticamente por terminar su investigación.
- Una tarifa o esquema CLI sin fuente no bloquea investigar/reparar WebSocket. La integración admite alcance parcial y no etiqueta todo el plan como terminado. Activación y nuevas llamadas reales nunca se deducen de ese resultado.

## Estructura final prevista

| Ruta | Contenido |
| --- | --- |
| Este plan: reglas, evidencia, contratos y resultado | Hechos, decisiones de puertas, tareas y auditoría |
| `check_plan.py`, `base-ejecucion.json`, `casos.json` | Verificador del plan, diez huellas protegidas y seis secuencias de base |
| `tests/test_websocket_repair.py`, `tests/fixtures/copilot_ws_repair.json` | Regresiones sin depender de datos privados o de `.plans` |
| `tests/test_copilot_usage_contract.py` | Contrato estricto actual y variantes demostradas futuras |
| `cachetap/websocket.py` | Solo la regla de correlación acreditada, tras desbloquear 2.01 |
| `scripts/check_copilot.py` | Solo variantes acreditadas del uso CLI, tras desbloquear 2.02 |
| `cachetap/prices/copilot.py`, `cachetap/prices/__init__.py`, `tests/test_prices_argon.py` | Solo tarifa acreditada de Argon y revisión, tras desbloquear 2.03 |
| `tests/test_websocket_repair_dashboard.py` | Integración de la regla aprobada por hooks, detalle, SSE y JSONL |

## Decisiones tomadas y alcance excluido

- Las cinco respuestas fueron correctas, pero dos capturas ERR no se arreglan cambiando modelos. Los terminales ignorados son el fallo observable; su vínculo de identidad no está demostrado.
- No se acepta cualquier completed, no se retiran protecciones por solapamiento, no hay multiplexación ciega ni reconstrucción incremental.
- No se publican cuerpos, credenciales, IDs reales ni hashes de IDs. La evidencia original queda local; su verificación es optativa y no entra en CI.
- No se inventan los campos CLI perdidos ni tarifas; no se confunde compatibilidad de esquema con confirmación de la causa histórica.
- Fuera: Auto/routing, modelos Nano auxiliares, ampliar proveedores directos, UI, TTL, refactorizaciones generales y reparación retroactiva de registros. La prueba histórica 3.03 sigue fallida/bloqueada; no se reetiqueta por estos tests.
- Sin permiso independiente no se recarga ni reinicia el inspector, y no se envían llamadas pagadas para resolver las incógnitas.

## Comprobación reproducible

Ejecuta `venv/bin/python .plans/copilot-reparacion-capturas/check_plan.py --baseline --evidence` desde la raíz. Comprueba índice/ficheros/dependencias, huellas, la base sintética y los 16 ficheros locales; no usa el panel ni proveedores. En otro checkout sin evidencia local, omite `--evidence`. Tras una reparación aprobada, omite también `--baseline`, que caracteriza el comportamiento anterior.
