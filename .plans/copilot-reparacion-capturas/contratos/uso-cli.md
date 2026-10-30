# Contrato de uso del CLI Copilot

## Fuentes

- [Usage and billing metrics — Copilot SDK](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing#accumulated-ai-credit-and-token-totals), sección **Accumulated AI credit and token totals** (documentación oficial vigente consultada el 2026-10-30). Identifica `session.usage.getMetrics` como acumulado de sesión e indica que su resultado `UsageGetMetricsResult` y los tipos SDK generados son la referencia completa. Describe `modelMetrics` como desglose por modelo y `totalNanoAiu` como coste de sesión en nano-AI units. Limitación: no documenta el formato de un fichero temporal de uso del CLI ni que ese fichero sea una serialización directa de este RPC.
- [Tipos generados de eventos y uso del Copilot SDK](https://github.com/github/copilot-sdk/blob/e22b95e6ead5e1de7e9a68d3087b8d28dc5f364a/nodejs/src/generated/session-events.ts#L3552-L3706), `UsageGetMetricsResult` y `UsageMetricsModelMetric` (generado desde `session-events.schema.json`). Fuente fijada al [commit público e22b95e6ead5e1de7e9a68d3087b8d28dc5f364a](https://github.com/github/copilot-sdk/commit/e22b95e6ead5e1de7e9a68d3087b8d28dc5f364a) del repositorio SDK, fechado `2026-10-28T17:51:00Z` y consultado el 2026-10-30. En ese esquema `modelMetrics` es un mapa por modelo; `requests` y `usage` son requeridos; `tokenDetails` y `usage.reasoningTokens` son opcionales; las cuatro cuentas de tokens principales son `number`; cada detalle presente lleva `tokenCount: number`. El mapa de `tokenDetails` acepta nombres de clave de runtime, no enumera `cache_write` como campo obligatorio. Limitación: los tipos generados describen la superficie SDK/RPC, no demuestran por sí solos el contrato del fichero temporal leído por el smoke runner.
- [Versión CLI fijada por el SDK](https://github.com/github/copilot-sdk/blob/e22b95e6ead5e1de7e9a68d3087b8d28dc5f364a/nodejs/src/cliVersion.ts#L1), en el mismo commit del SDK consultado el 2026-10-30, identifica `1.0.105-1`. Los endpoints públicos de GitHub para [ref del tag v1.0.105](https://api.github.com/repos/github/copilot-cli/git/ref/tags/v1.0.105) y [ref del tag v1.0.105-1](https://api.github.com/repos/github/copilot-cli/git/ref/tags/v1.0.105-1) devuelven ambos `object.type=commit` y `object.sha=8f18becc073481aeab76c83bc38d6db8c3d6c85a`. Esto verifica solamente que las dos refs públicas apuntan al mismo objeto commit del repositorio `copilot-cli`; no demuestra identidad de activos/binarios ni equivalencia del runtime empaquetado. Tampoco expone el serializador del fichero temporal.
- [Streaming session events — Copilot SDK](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/streaming-events#assistantusage), sección `assistant.usage`, documenta campos de uso **por llamada** y señala contadores opcionales. Se usa solo para distinguir esa señal efímera del RPC acumulado: no es evidencia del JSON temporal.

## Esquema demostrado

La superficie pública de `session.usage.getMetrics` demuestra un resultado acumulado de sesión, no un registro por llamada:

| Ruta | Forma y unidad documentadas | Opcionalidad / semántica demostrada |
| --- | --- | --- |
| `modelMetrics` | Objeto/mapa cuyas claves son identificadores de modelo; valores `UsageMetricsModelMetric` | Requerido en `UsageGetMetricsResult`; agrupa contadores acumulados por modelo. |
| `modelMetrics[modelo].requests.count` | `number`, número de peticiones API de ese modelo | Requerido en la métrica por modelo. |
| `modelMetrics[modelo].requests.cost` | `number`, coste de premium request con multiplicador aplicado | Requerido en la métrica por modelo; no es un recuento de tokens. |
| `modelMetrics[modelo].usage.inputTokens` | `number` de tokens de entrada acumulados | Requerido en el tipo generado. |
| `modelMetrics[modelo].usage.outputTokens` | `number` de tokens de salida acumulados | Requerido en el tipo generado. |
| `modelMetrics[modelo].usage.cacheReadTokens` | `number` de tokens acumulados leídos de la caché | Requerido en el tipo generado. |
| `modelMetrics[modelo].usage.cacheWriteTokens` | `number` de tokens acumulados escritos en la caché | Requerido en el tipo generado. |
| `modelMetrics[modelo].usage.reasoningTokens` | `number` de tokens de salida usados para razonamiento | Opcional en el tipo generado. |
| `modelMetrics[modelo].tokenDetails` | Mapa opcional de claves de tipo token a objetos `{tokenCount: number}` | El tipo permite omitir el mapa y no enumera nombres fijos ni exige una clave `cache_write`. Para cada detalle presente, `tokenCount` es requerido. |
| `totalNanoAiu` | `number`, coste acumulado de sesión en nano-AI units | Opcional en `UsageGetMetricsResult`; no se convierte aquí a créditos o moneda. |

Las definiciones generadas expresan contadores como `number`; no establecen por sí solas una regla adicional de entero ni admiten `null`. El esquema público tampoco determina si el JSON del fichero temporal elimina campos opcionales, transforma nombres o conserva mirrors.

## Rechazo observado

El validador local actual exige los cinco contadores `usage.*` y el objeto `tokenDetails` con las cuatro claves que inspecciona; `_decode_token_count` exige `tokenCount`. Los tests nuevos fijan, usando entradas **sintéticas** basadas en el constructor `cli_usage` de `tests/test_check_copilot.py`, que:

- la entrada sintética válida se acepta y conserva los contadores;
- quitar `usage.reasoningTokens` produce `RunnerError`;
- quitar `tokenDetails.cache_write` produce `RunnerError`;
- quitar el objeto `tokenDetails` entero produce `RunnerError`;
- `agentMetrics` y `providerModelMetrics` mirrors no añaden solicitudes al conteo de `modelMetrics`.

Estos resultados caracterizan el lector y los fixtures; no son muestras Gemini/Grok ni demuestran qué campo faltó en los dos rechazos históricos.

## Ausencias y contradicciones

La sección **Uso CLI: límite de la evidencia** de `evidencia.md` indica que los JSON originales de Google/xAI fueron rechazados y eliminados: solo quedó `invalid_schema`, no el campo concreto ni el JSON. **El campo rechazado en las dos pruebas históricas no se conservó.** Los contadores HTTP del panel y los mirrors no reconstruyen el temporal; los tres casos sintéticos tampoco atribuyen el fallo histórico.

El esquema SDK/RPC vigente muestra una diferencia observable con la rigidez del lector local (`reasoningTokens` y `tokenDetails` son opcionales allí). No es una contradicción resuelta: la documentación pública consultada no demuestra que el fichero temporal del CLI tenga exactamente el mismo productor, proyección o contrato que `UsageGetMetricsResult`. Tampoco prueba si `cache_write` debe aparecer en ese fichero.

## Decisión

**status: insuficiente; approved: false.** Sin estimar, se puede registrar como demostrado para el RPC SDK que `reasoningTokens` y el objeto `tokenDetails` pueden omitirse, y que un detalle individual no tiene una clave fija obligatoria en el tipo generado. No se puede transferir esa opcionalidad al fichero temporal consumido por `read_cli_usage`, ni identificar el campo causal de Gemini/Grok. Se conserva el lector estricto: no añadir defaults ni relajar campos en esta tarea. La tarea 2.02 requiere una fuente/versionado que describa el fichero temporal exacto antes de proponer una modificación.
