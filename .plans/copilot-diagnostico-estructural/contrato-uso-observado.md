# Compatibilidad CLI: contrato acotado aprobado por el orquestador

## Evidencia nueva

La campaña autorizada de cinco saludos a esfuerzo low terminó con cinco respuestas correctas, una petición CLI reportada por sesión y una fila del modelo solicitado por ventana. No hubo retries del harness. Son observaciones actuales, no recuperación de los temporales históricos.

| Modelo/familia | Diagnóstico estricto observado | Campos relevantes conservados por proyección |
| --- | --- | --- |
| Gemini 4 Argon / Google | `modelMetrics[*].usage.reasoningTokens`, esperado entero no negativo, `missing` | Contadores de input/output/read/write presentes y válidos; write explícito 0. TokenDetails input/read/write/output presentes. |
| Grok 4.7 / xAI | `modelMetrics[*].tokenDetails.cache_write`, esperado objeto, `missing` | `usage.cacheWriteTokens=0` explícito; reasoningTokens entero válido; input/read/output details presentes. |

El SDK oficial fijado en la investigación anterior también marca reasoningTokens opcional y tokenDetails como mapa opcional. Aquí no se infiere el fichero desde ese SDK: el fichero actual se leyó realmente y su presencia/tipo se conservó antes de limpiar temporales. No se conserva el JSON bruto ni se afirma que estas fueran las causas de las sesiones históricas.

## Decisión aprobada y límites

- Permitir ausencia de `usage.reasoningTokens`, sin rellenarlo con 0 y sin perder su validación si está presente. No participa en la comparación de input/output/caché ni autoriza precio.
- Permitir ausencia exclusiva de `tokenDetails.cache_write` SOLO cuando `usage.cacheWriteTokens` ya fue validado y vale exactamente 0. No crear un detalle ficticio de cero; omitir la clave. En la comparación con inspector, la ausencia solo es compatible con write explícito 0 en ambos contadores; si es distinto, falta o es inválido, falla cerrado.
- Mantener requeridos y validados el resto de contadores/objetos. `null`, bool, negativos o formas incorrectas presentes siguen rechazados. El objeto tokenDetails completo continúa requerido. Sin cambios de atribución, procesos, prompts, retries, precio o coste.
- Las nuevas pruebas usan fixtures sintéticas con la forma observada, no se presentan como replays de JSON bruto perdido. No hace falta otra llamada pagada para validar esta transformación del lector.
- `status=acreditado-acotado`, `approved=true` SOLO para esta receta 1.05. No desbloquea las reservas genéricas anteriores ni reparación de WebSocket/precios. Las dos sesiones WS nuevas muestran A-B-C, lo cual todavía no establece propiedad de los IDs.
