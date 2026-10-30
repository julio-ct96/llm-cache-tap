# Resultado: real terminado y lector reparado; WebSocket pendiente

## Entregado

| Área | Resultado |
| --- | --- |
| Diagnóstico WebSocket | Igualdad de IDs mediante ordinales acotados, sin guardar valores/hashes ni modificar matching; limpieza y exclusiones de privacidad probadas. Commit `ed32f17`. |
| Diagnóstico CLI | Error de schema con campo/tipos cerrados y sin datos externos. Commit `9b16ea9`. |
| Integración | Hooks, detalle y sanitizador conservan ordinales; no llegan a SSE, snapshot, body ni JSONL. Commit `bda6d3d`. |
| Pruebas reales | Cinco saludos low, cinco respuestas correctas, una petición CLI reportada por sesión y una fila por ventana; cero retries del harness. Resultado publicado en `71f1c64`. |
| Compatibilidad CLI | Ausencia de reasoningTokens aceptada sin default; cache_write detail ausente solo con write explícito 0. Presentes inválidos, cantidades positivas sin detalle y discrepancias siguen fallando. Commit `71268cb`. |

## Estado real observado antes de reparar el lector

- Terra y MAI respondieron correctamente pero sus capturas WS terminaron ERR: created, in_progress y completed llevan tres identidades diferentes (`1,2,3`), sin truncado. No se modifican atribución ni estado para aparentar éxito.
- Opus completó HTTP y su uso validó. Gemini y Grok completaron HTTP, pero el lector estricto rechazó respectivamente reasoningTokens ausente y detalle cache_write ausente con contador write explícito 0.
- Las respuestas y solicitudes sintéticas, proyecciones y diagnósticos están conservados en evidencia local ignorada, con hashes. No se guardaron eventos CLI, uso bruto ni cuerpos privados en la evidencia estructural. Hay backups privados completos antes y después.

## Validación de la reparación

- 45 tests del lector, FULL 413 Python + 20 JS + Chrome; export limpio FULL 412 Python + 20 JS + Chrome, además de mypy y Ruff. Diferencia de un test debida a cambios previos del usuario, no a omisiones de esta entrega.
- Cinco reconstrucciones offline derivadas de la proyección conservada: lector anterior reproduce ambos rechazos, nuevo lector acepta las cinco formas y preserva los contadores. Son fixtures reconstruidas con coste sintético, no replay de ficheros brutos ni verificación de facturación. No se enviaron otras llamadas pagadas después de las cinco autorizadas.
- ORIGINAL actualizado por fast-forward; una recarga nativa para activar diagnóstico, ninguna segunda recarga para el lector. PID/puertos conservados. Memoria anterior exportada, no reimportada al panel; cinco filas nuevas siguen disponibles y respaldadas.
- Los ocho cambios previos, las diez huellas protegidas y los dieciséis ficheros de evidencia anterior permanecen intactos. Nada privado se añadió a Git.

## Qué no está resuelto

1. **Correlación WebSocket:** A-B-C descarta una solución basada en aceptar el segundo ID, pero no establece propiedad del terminal respecto del create. Se mantienen mismatch, duplicate-terminal, overlap y ambigüedad. No hay reparación segura de captura todavía.
2. **Precio Argon:** la promoción input/cached-input/output es oficial, pero la semántica/tarifa de escritura de caché no se acredita. `cost_missing` permanece; no se implementa una tarifa por analogía.
3. **Historia y alcance:** las muestras nuevas no recuperan los temporales antiguos; Auto/routing sigue separado y no pasa por los éxitos de modelos explícitos. La ausencia de retry del harness y el contador reportado no prueban una política interna del CLI.

La fase termina aquí. Cualquier ampliación de protocolo/correlación requiere evidencia y receta nuevas; no se ocultan los dos ERR ni se gasta más cuota para repetir los mismos saludos.
