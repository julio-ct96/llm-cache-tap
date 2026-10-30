# Resultado del diagnóstico offline

## Hechos reales

La evidencia histórica de `.plans/copilot-websocket-diagnostico/evidencia.md`, recogida antes de esta tarea mediante snapshot y detalle del inspector, registró 23 entradas: 20 HTTP en `done` y 3 WebSocket en `error`, con estado HTTP `101` y veredicto `ERR`. Dos notas indicaban solapamiento y una cierre antes de completar. Es una fotografía previa, no un recuento actual; en esta tarea no se volvió a consultar el panel ni sus cuerpos.

Las tres entradas WebSocket no tenían `usage` validado. No permiten inferir tokens, coste ni llamadas facturadas. El mensaje de Auto routing informado entonces es un bloqueo de selección/enrutamiento separado: por sí solo no demuestra un fallo de transporte, caché o inspección.

## Matriz offline

El fixture `tests/fixtures/copilot_ws_diagnosis.json` fija siete secuencias sintéticas. `tests/test_websocket_diagnosis.py` verifica que se conservan los estados, veredictos, notas, reservas y estado de deshabilitación esperados; ahora el diagnóstico diferencia las ramas de control sin decidirlas ni alterar el comportamiento anterior.

| Caso sintético | Distinción que aporta el diagnóstico | Resultado anterior conservado |
| --- | --- | --- |
| `sequential` | No hay error que diagnosticar; no se publica el campo en éxito | `done` seguido de `streaming`, `PARTIAL` y sin deshabilitar la conexión |
| `create_before_created` | Segundo `response.create` → `overlap` antes de recibir `created` | Error por solapamiento |
| `created_then_create` | `response.created` observado; segundo create → `overlap` | Error por solapamiento |
| `completed_without_created` | `completed` se ignora por falta de ID asociado; segundo create → `overlap` | Error por solapamiento |
| `mismatched_completed` | Terminal de otro ID → `ignore_other_id`; segundo create → `overlap` | Error por solapamiento |
| `generate_false_then_create` | Registra `generate=false` como clasificación cerrada; segundo create → `overlap` | Error por solapamiento; `generate` no cambia la normalización ni crea una rama nueva |
| `close_before_completed` | Cierre local → `fail` | Error de cierre, no de solapamiento |

Los siete casos prueban estas ramas con datos sintéticos. No prueban cuál recorrieron las tres capturas antiguas. En particular, el caso `generate=false` es una hipótesis de diagnóstico, no evidencia de precalentamiento de Copilot.

## Privacidad y límites

- El registro conserva solo una proyección acotada de eventos de control, acciones y relaciones categóricas; clasifica `generate` e `incremental` sin guardar sus valores originales/IDs. Tipos de eventos de servidor omitidos solo incrementan un contador saturado.
- El anillo tiene un máximo de 32 pasos y marca truncamiento. No retiene contenido, deltas, razonamiento, cabeceras, IDs, hashes ni tipos desconocidos.
- Los tests de integración comprueban que el diagnóstico aparece en el detalle de la API y en la salida de fallo saneada del runner, pero no en SSE/snapshot, JSONL ni cuerpo retenido. La proyección del runner reconstruye claves y enums permitidos, limita las notas examinadas y acota el JSON a 8192 bytes.
- Los tests usan estado/log temporal y servidores de prueba locales. No se modificaron datos reales, `tests/replay/golden.json`, la tarifa ni los ocho cambios previos preservados. La comprobación de las diez huellas SHA-256 incluye además el fixture original. No se enviaron prompts, no se invocó `--run-real`, no se consultaron proveedores ni se leyó el panel vivo.

## Verificaciones

Todas las comprobaciones ejecutadas en este checkout terminaron con código 0:

| Comando | Resultado observado |
| --- | --- |
| `venv/bin/python scripts/check.py` | `all checks passed`; 392 tests Python y 20 tests JS |
| `venv/bin/python scripts/check.py --full` | `all checks passed`; 392 tests Python, 20 JS y Chrome completo incluida C34. No aparecieron advertencias en esta ejecución |
| `venv/bin/python -m mypy scripts/check_copilot.py` | `Success: no issues found in 1 source file` |
| `venv/bin/python -m ruff check scripts/check_copilot.py tests/test_check_copilot.py` | `All checks passed!` |
| `venv/bin/python -m ruff format --check scripts/check_copilot.py tests/test_check_copilot.py` | `2 files already formatted` |
| `venv/bin/python .plans/copilot-websocket-diagnostico/check_plan.py` | `Plan OK: 5 tareas; 7 casos offline; invariantes preservadas` |
| `venv/bin/python scripts/check_copilot.py` | `READY: no model calls; use --run-real` |

La salida del runner sin opciones fue solo la indicación de espera; no inició una llamada. `check_plan.py` verificó las diez huellas de `base-ejecucion.json` y los siete casos offline. Tras escribir este informe, la revisión de alcance confirmó que solo cambiaron este resultado y la fila 2.02; `git diff --check` pasó sin salida.

**Evidencia independiente proporcionada por el orquestador, no repetida como verificación de esta tarea:** después de auditar 2.01 en `c2e04dd`, un `git archive` limpio sin los ocho cambios previos pasó FULL con código 0 (391 Python, 20 JS, C34, sin `ResourceWarning`) y mypy explícito con código 0. En este checkout con los cambios previos preservados, FULL da 392 Python, 20 JS y C34. La diferencia es un test de precios preexistente excluido de los commits del diagnóstico, no un test de diagnóstico omitido.

**Incidencias de auditoría previas, comunicadas por el orquestador y no reproducidas aquí:** en 1.02 se corrigieron pasos de control que incluían deltas ignorados, una tabla `generate` con el flag equivocado y la limpieza tras éxito; en 1.03 se resolvió un bloqueo transitorio de formato durante paralelismo sin cambios ajenos; en 2.01 se sustituyó un opcode no disponible por el helper `is_text` y se cerró explícitamente `HTTPResponse` SSE, eliminando los `ResourceWarning` en la ejecución FULL final. Son incidencias resueltas del trabajo offline; la causa real de las capturas sigue indeterminada.

## Incertidumbres

causa real indeterminada

Los registros históricos no incluyen secuencia de control suficiente para distinguir solapamiento real, terminal no reconocido u otro patrón. Ningún test sintético reconstruye las tres capturas antiguas. No se demuestra que WebSocket esté arreglado ni se atribuye el error anterior de 3.03 a la misma causa sin datos. Auto sigue siendo un bloqueo separado, sin prueba de un fallo de transporte o caché.

## Siguiente decisión

Sin ejecutar una corrección ni una llamada en esta tarea, la puerta posterior es: revisar trazas estructurales disponibles y autorizadas; si alguna sustenta una rama, preparar y revisar un fixture mínimo; decidir si corresponde una corrección y redactar un plan separado antes de implementarla. Solo si la evidencia lo exige y se autoriza explícitamente una comprobación real, limitarla a una única llamada con `hola` y un modelo económico, sin reintentos. Auto continúa como bloqueo separado. Pasar las pruebas sintéticas no demuestra que el WebSocket real funcione.
