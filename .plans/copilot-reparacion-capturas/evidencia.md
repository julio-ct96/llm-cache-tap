# Base comprobada para la reparación

Fecha: 2026-10-30. HEAD: `b6c0b56`. Hay ocho ficheros modificados previamente; se protegen por huella y no forman parte del encargo. No se hicieron llamadas de inferencia para redactar este plan.

## Hechos de las cinco pruebas guardadas

Las pruebas se hicieron por GitHub Copilot, no por las API directas de cada fabricante. Todas usaron esfuerzo observado `low`, un saludo literal y un proceso CLI que terminó con código 0. No hubo reintentos de peticiones pagadas.

| Registro local histórico | Modelo | Prompt | Transporte | Captura | Uso CLI validado |
| --- | --- | --- | --- | --- | --- |
| 21 | `gpt-6.1-terra` | `hola` | WebSocket | error/ERR | Sí; una petición a ese modelo |
| 22 | `claude-opus-5.5` | `que tal` | HTTP | done/COLD | Sí |
| 23 | `gemini-4-argon` | `buenas` | HTTP | done/COLD, sin precio Copilot | No: `invalid_schema` |
| 24 | `grok-4.7` | `hola` | HTTP | done/PARTIAL | No: `invalid_schema` |
| 25 | `mai-code-1.1-flash` | `que tal` | WebSocket | error/ERR | Sí; una petición a ese modelo |

Los números de registro son referencias a la evidencia histórica, no IDs de respuesta del proveedor ni expectativas para futuros tests. No apareció ningún registro Nano nuevo durante estas ventanas. La clasificación auxiliar anterior y Auto no se reparan aquí.

La evidencia íntegra permanece local e ignorada por Git en `data/model-checks/20261030-194813-low-dt3k5lzg/`. El manifiesto cubre 16 ficheros y sus huellas se verificaron. El plan solo publica hechos estructurales y huellas de integridad, no cuerpos ni eventos crudos.

## WebSocket: qué sabemos y qué no

Terra y MAI tienen esta secuencia de control sin truncar:

| Paso | Decisión actual | Relación con ID activo |
| --- | --- | --- |
| Cliente `response.create` | start | missing |
| Servidor `response.created` | observe | unbound |
| Servidor `response.in_progress` | ignore_other_id | other |
| Servidor `response.completed` | ignore_other_id | other |
| Cierre local | fail | missing |

Los contadores de eventos omitidos son 14 y 15. Esos eventos no se pueden reconstruir. El diagnóstico no retiene IDs, hashes ni relaciones entre dos IDs alternativos.

Por tanto, el diagnóstico es compatible tanto con `created=A, in_progress=B, completed=B` como con `created=A, in_progress=B, completed=C`. Esos ejemplos usan IDs artificiales, son contraejemplos sintéticos, **no** mensajes recuperados del tráfico real. `casos.json` y BASELINE comprueban que hoy producen exactamente el mismo diagnóstico.

Está probado que un terminal se ignoró y que el cliente obtuvo su saludo. No está probado qué campo une las dos identidades ni qué transición se puede aceptar sin atribuir otra respuesta. No se autoriza sustituir la igualdad estricta por «aceptar B porque apareció antes en in_progress».

## Uso CLI: límite de la evidencia

`scripts/check_copilot.py::_model_metrics` exige los cinco contadores de `usage` y las cuatro categorías de `tokenDetails`; `compare_usage` cruza contadores, modelo y una única petición. La salida original de Google/xAI fue rechazada y eliminada por el harness temporal. Se conserva `invalid_schema`, **no** el campo concreto ni el JSON original.

Los contadores HTTP del panel no permiten reconstruir ese JSON. Que el lector rechace campos sintéticos ausentes demuestra su rigidez, no demuestra cuál faltó en Gemini/Grok. No se declara resuelto hasta verificar el contrato pertinente o recuperar evidencia ya existente sin enviar otra petición.

Además, `decode_completed_record` solo admite WebSocket/101. El plan no lo amplía a HTTP por conveniencia ni presenta los tres éxitos HTTP como validación del runner de Auto.

## Precios

`prices.lookup("api.githubcopilot.com", "gemini-4-argon")` devuelve `("Copilot", None)` en esta base. Terra, Opus, Grok y MAI ya tienen entrada en la tarifa. Solo está demostrado que falta la de Argon entre estos cinco modelos.

El catálogo OpenCode no es una fuente suficiente de facturación Copilot. La tabla que se añada deberá tener fuente oficial de GitHub, unidad, vigencia, caché y niveles de contexto verificados. Si no se encuentra, se conserva `cost_missing`; nunca se rellena con precio de otro Gemini ni con cero.

## Verificaciones al preparar

- FULL: `all checks passed`; 392 tests Python, 20 JS y Chrome completo incluida C34. Son recuentos de esta base con cambios previos del usuario, no umbrales futuros.
- RUNNER-TYPES: sin incidencias.
- Runner sin opciones: `READY: no model calls; use --run-real`.
- Integridad local: 16 ficheros originales verificados contra su manifiesto.
- BASELINE: seis secuencias WebSocket y tres variantes CLI sintéticas; caracteriza el estado anterior a reparar, no una confirmación del protocolo real.
- Verificador del plan: Ruff y formato aprobados; las tres puertas rechazan ejecución sin aprobación. Pruebas negativas sobre copias temporales rechazaron desbloqueo sin permiso, dependencia inexistente, receta sin redactar y fichero de tarea ausente.

## Decisión de planificación

La fase 1 es ejecutable tras autorización. Fase 2 contiene reservas explícitamente bloqueadas: el orquestador capaz debe convertirlas en recetas cerradas tras auditar los contratos de fase 1. No se delega a Luna inventar la regla, el esquema ni las tarifas. Fase 3 verifica y fase 4 requiere permiso independiente para preservar y activar el inspector vivo. Una rama bloqueada no impide investigar las otras.
