# Diagnóstico de Responses WebSocket: índice

Objetivo: hacer observable por qué el inspector termina con «peticiones solapadas» o «conexión cerrada antes de completar», sin modificar la correlación ni guardar contenido. La reparación del protocolo se decide después de obtener evidencia suficiente.

**Ejecución autorizada de las cinco tareas con Luna (2026-10-30).** La autorización de ejecutar todo el plan cubre ambas fases; se audita y resume cada cierre sin repetir la petición de permiso. No autoriza llamadas reales ni reparación del protocolo. Evidencia y límites en [evidencia.md](evidencia.md); contrato en [contrato.md](contrato.md).

## Ejecución

- Se conserva el acuerdo anterior: un subagente Luna high por tarea; el orquestador audita código y tests antes de aceptar, hacer commit y push por tarea.
- Antes de ejecutar, versionar este plan por separado sin incluir los ocho ficheros ya modificados; sus huellas, la del golden y la del fixture original están en base-ejecucion.json.
- Los agentes leen reglas.md, su tarea y las secciones citadas del contrato; del índice solo su fila y dependencias.
- Estados: `pendiente`, `en curso`, `terminada sin commit`, `terminada con commit`, `bloqueada`.
- Al cerrar una fase, auditar y resumir antes de continuar con la autorización global del usuario. No enviar prompts ni ejecutar --run-real en ninguna tarea.
- El inspector del usuario sigue activo en el checkout original. Antes de 1.02 el orquestador debe acordar el aislamiento del desarrollo; no se recarga ni se pierde su estado por iniciativa del agente.

## Tareas

| ID | Tarea | Fichero | Depende de | Estado | Notas |
| --- | --- | --- | --- | --- | --- |
| 1.01 | Red de seguridad del diagnóstico | [1.01](fase-1/1.01-red-seguridad.md) | — | terminada con commit | Auditada: siete casos; CHECK 372 Python/20 JS; invariantes OK |
| 1.02 | Traza estructural acotada | [1.02](fase-1/1.02-traza-acotada.md) | 1.01 | terminada con commit | Auditada y corregida: deltas, generate y limpieza; FULL e invariantes OK |
| 1.03 | Fallos saneados del runner | [1.03](fase-1/1.03-errores-runner.md) | 1.01 | terminada con commit | Auditada: diagnóstico validado; bloqueo transitorio resuelto; FULL y RUNNER OK |
| 2.01 | Integración hooks/API/runner | [2.01](fase-2/2.01-integracion.md) | 1.02, 1.03 | pendiente | Tras auditar el cierre de fase 1; autorización global |
| 2.02 | Informe y puerta de decisión | [2.02](fase-2/2.02-informe.md) | 2.01 | pendiente | No declara reparado el WebSocket real |

## Paralelismo

- 1.01 va primero; fija el comportamiento existente.
- 1.02 y 1.03 pueden ejecutarse en paralelo después de 1.01: no comparten ficheros de trabajo. Cada agente solo cambia su propia fila del índice. El contrato común ya está decidido.
- Fase 2 es una cadena, cubierta por la autorización global después de revisar fase 1.

## Estructura final

| Ruta | Resultado |
| --- | --- |
| `cachetap/record.py`, `cachetap/websocket.py` | Diagnóstico opcional de fallos, acotado y sin contenido |
| `scripts/check_copilot.py` | Mismo smoke, errores con categorías y metadatos validados |
| `tests/fixtures/copilot_ws_diagnosis.json` (nuevo) | Siete secuencias artificiales y resultados actuales |
| `tests/test_websocket_diagnosis.py` (nuevo) | Matriz, privacidad, límites y limpieza |
| Tests existentes de record, runner, hooks y dashboard | Contratos y pipeline completos |
| `resultado.md` (nuevo al ejecutar 2.02) | Evidencia y decisión posterior, sin prometer una reparación |

## Decisiones y exclusiones

- No afirmar solapamiento real solo por la nota: varios caminos sintéticos ya producen el mismo error.
- Mantener una captura activa por conexión y la protección ante ambigüedad; no implementar multiplexación a ciegas.
- Observar generate=false sin cambiar su semántica; no es una causa real demostrada.
- Retener como máximo 32 pasos de control por captura y contador saturado de eventos omitidos, no eventos crudos ni IDs. Exponer la copia solo en detalle de un fallo, no SSE/JSONL.
- Los nuevos campos son solo WebSocket y opcionales. No cambia HTTP, coste, linking, límites de captura ni golden.
- Fuera: resolver Auto, Antigravity, Gemini nativo, otros hosts, reconstrucción incremental, UI, tarifas y otra prueba real.
- El plan anterior sigue bloqueado en 3.03. Este diagnóstico no lo cierra ni cambia sus informes pendientes.

## Estado comprobado al escribir

- Base `ac0dc07`; FULL pasó con 370 Python, 20 JS y C34, más mypy explícito del runner y READY sin red.
- Snapshot observado: 23 registros, 20 HTTP done y 3 WebSocket error; dos notas de solapamiento y una de cierre prematuro. Los recuentos son históricos, no aserciones de una API viva.
- Hay ocho ficheros modificados previos a este plan. No se descartan ni incluyen en sus commits.

## Validación del plan

Desde la raíz: `venv/bin/python .plans/copilot-websocket-diagnostico/check_plan.py`.

Salida: `Plan OK: 5 tareas; 7 casos offline; invariantes preservadas`.
