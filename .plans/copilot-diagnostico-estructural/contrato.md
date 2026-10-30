# Contrato mínimo

## 1. Igualdad simbólica de IDs

Los casos sintéticos existentes `other_same` (`created=A, in_progress=B, completed=B`) y `other_different` (`created=A, in_progress=B, completed=C`) terminan hoy con las mismas acciones. A/B/C son IDs artificiales, no tráfico observado.

- Añadir solo `WebSocketDiagnosticStep.id_symbol`, opcional, entero exacto 1–32.
- Un mapa temporal por `_ActiveCapture` asigna ordinales consecutivos a un máximo de 32 IDs de servidor distintos; iguales repiten ordinal. No usar hashes ni reciclar ordinales.
- Sin ID o ante una identidad nueva una vez saturado, omitir `id_symbol`. Un `unknown` compartido está prohibido; identidades conocidas retienen su ordinal.
- Limpiar todo el mapa en éxito/fallo/límite/close/clear/eviction/cleanup. El único dato persistido es el ordinal en `ws_diagnostic` de fallo/detail.
- A-B-B da `1,2,2`; A-B-C da `1,2,3`, sin cambios de acciones/estado/atribución. Esto prueba igualdad entre IDs de eventos, **no** propiedad respecto del create.
- No tocar `stream_id`, `project_event`, campos del wire, lista de eventos, lógica de terminales, reglas de matching ni proyección.

## 2. `invalid_schema`

El módulo actual usa `RunnerError` y `main` imprime `ERROR: …`; no contiene una clasificación `invalid_schema` propia. En el límite de salida de error estructurado, conservar literalmente el código `invalid_schema` que reconoce el runner/orquestador y emitir una sola línea JSON compacta en stderr: `{ "error": "invalid_schema", "diagnostic": {"path": ..., "expected": ..., "actual": ...} }`. Si no hay diagnóstico allowlisted, omitir `diagnostic`. Otros `RunnerError` mantienen su salida actual. No incluir mensaje dinámico, JSON crudo, claves de modelo, nombres de modelo o valores externos. Paths usan `[*]` y son cerrados.

| `path` permitido | `expected` |
| --- | --- |
| `modelMetrics`, `modelMetrics[*]`, `modelMetrics[*].requests`, `modelMetrics[*].usage`, `modelMetrics[*].tokenDetails`, y `modelMetrics[*].tokenDetails.{input,cache_read,cache_write,output}` | `object` (en `modelMetrics[*]` también `model_identifier`) |
| `modelMetrics[*].requests.count`, `modelMetrics[*].usage.{inputTokens,outputTokens,cacheReadTokens,cacheWriteTokens,reasoningTokens}`, `modelMetrics[*].tokenDetails.*.tokenCount`, `totalNanoAiu` | `non_negative_integer` |
| `modelMetrics[*].requests.cost` | `finite_non_negative_number` |

`actual` solo puede ser `missing`, `null`, `boolean`, `number`, `string`, `array`, `object`, `negative_number`, `non_finite_number` o `invalid_identifier`. Sin clasificación allowlisted, omitir el diagnóstico y conservar `invalid_schema`.

Durante las tareas diagnósticas 1.01–1.03 se mantuvo el decoder igual de estricto. Después de las cinco llamadas, la única excepción aprobada es la receta 1.05 de `contrato-uso-observado.md`, sin defaults. No inferir el fichero desde el SDK ni atribuir los rechazos históricos. El flujo de `run_real` no cambia. Para el JSON de fallo WS, aceptar `id_symbol` solo como entero exacto 1–32 en paso de servidor; formas inválidas siguen la política de diagnóstico inválido existente.

## 3. Epistemología y operativa real

- Hechos Argon aportados por el usuario: promoción oficial `2/.10/10` y `Default/Not applicable`; `cache_write` es cantidad en Billing reports, su tarifa sigue sin acreditarse. No extrapolar OpenAI/Anthropic a Google. `cost_missing` y `approved=false` permanecen.
- El inventario de solo lectura indica PID `73039`, puertos `8899/8900`, checkout original (`ORIGINAL`, ruta local no publicada); snapshot de 25 filas/4 WS; API detail conserva `ws_diagnostic`, API body conserva cuerpos, JSONL light excluye diagnóstico/output. No consultar esas fuentes en tareas offline.
- Original `main` `697f091` detrás de `a41417d`, sin overlap protegido; fast-forward-only solo tras backup y diff. No hacerlo en esta fase.
- El cierre admite insuficiencia y no habilita reparación de precio, reglas o protocolo.
