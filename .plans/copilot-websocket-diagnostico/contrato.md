# Contrato del diagnóstico, no de una reparación

## 1. Alcance

El resultado es saber qué ramas recorrió el inspector antes de un fallo, sin cambiar esas ramas. Las notas actuales no distinguen la causa real. La secuencia de control de las capturas antiguas no se puede recuperar desde sus registros.

No se implementan multiplexación, precalentamiento, reconocimiento de nuevos terminales ni cambios de Auto. `generate=false` es una hipótesis sintética para comprobar la pérdida de metadatos, no un comportamiento observado en estas capturas reales.

## 2. Contratos y destino

No se crea un módulo nuevo. `record.py` conserva su independencia; `websocket.py` usa sus imports actuales; el runner sigue siendo autónomo y valida el JSON de la API en su frontera.

| Ruta | Cambio decidido |
| --- | --- |
| `cachetap/record.py` | Aliases y TypedDict de diagnóstico; campo opcional `ws_diagnostic`; añadirlo al final de `HEAVY` |
| `cachetap/websocket.py` | Metadatos de decodificación internos y anillo local de control de cada captura; sin cambiar las decisiones de Session |
| `scripts/check_copilot.py` | Formateador de fallo con JSON reconstruido y validado; sin cambiar argumentos, cuota, éxito ni limpieza |
| Tests | Casos actuales, contrato, límites, privacidad, hooks y API |

### Tipos de `record.py`

Estos límites son decisiones de diseño nuevas, no resultados del tráfico observado.

| Nombre | Forma cerrada |
| --- | --- |
| `WebSocketDirection` | `client`, `server`, `local` |
| `WebSocketControlEvent` | `response.create`, `response.created`, `response.in_progress`, `response.completed`, `response.failed`, `response.incomplete`, `error`, `invalid`, `close`, `uninspectable` |
| `WebSocketAction` | `start`, `observe`, `ignore_no_id`, `ignore_other_id`, `ignore_previous`, `finish`, `fail`, `overlap` |
| `WebSocketIdRelation` | `missing`, `last`, `unbound`, `active`, `other` |
| `WebSocketGenerate` | `absent`, `true`, `false`, `invalid` |
| `WebSocketDiagnosticStep` | Requeridas: `direction`, `event`, `action`, `identified` booleano, `id_relation`. Opcionales solo para create: `generate`, `incremental` booleano |
| `WebSocketDiagnostic` | Requeridas: `events` lista de pasos, `truncated` booleano, `omitted_server_events` entero entre 0 y 255 |
| `Record.ws_diagnostic` | `NotRequired[WebSocketDiagnostic]`; ausente en HTTP y capturas correctas |

`HEAVY` pasa a ser la tupla actual seguida de `ws_diagnostic`. El diagnóstico se ve en `record.public` y `GET /api/record/<id>`; no viaja en `record.light`, SSE, snapshot ni JSONL. No se modifica la UI ni se añade un endpoint.

## 3. Captura de metadatos

### Decodificación cliente

Extrae el cuerpo actual de `decode_client` a `_decode_client_message`. Su resultado es una dataclass privada `_ClientMessage` con `request` (`JsonObject | None`) y `generate` (`WebSocketGenerate`). La función pública `decode_client(content)` devuelve solo `request` y conserva exactamente su contrato y excepciones.

Clasifica `generate` mientras el JSON ya decodificado está en la frontera: clave ausente → `absent`; booleano exacto True/False → `true`/`false`; cualquier otra forma → `invalid`. No conviertas 0/1 a booleanos, no guardes el valor original y no lo añadas a la petición normalizada. Esa clasificación no acepta/rechaza mensajes ni cambia el número de registros.

`Session.client` usa el resultado interno una sola vez, sin volver a decodificar. `incremental` indica exclusivamente que `previous_response_id` validado es una cadena no vacía, sin conservarla en el diagnóstico.

### Memoria y ciclo

- Añade a `_ActiveCapture` un deque de pasos con máximo 32, un flag `truncated` y un contador `omitted_server_events` saturado en 255. Son privados y por captura; no crees historia de conexión ni mapas de IDs adicionales.
- Guarda únicamente los eventos de control de la tabla. Los deltas de texto, tools, razonamiento y tipos desconocidos no crean pasos; incrementan el contador saturado al observarlos mientras hay captura activa. No copies sus tipos desconocidos ni su contenido.
- Un paso usa el estado anterior a procesar ese evento. `identified` indica si ya existe `active.response_id`.
- Relación de ID, en este orden: sin ID proyectado → `missing`; igual al último terminal → `last`; activa aún sin ID → `unbound`; igual al activo → `active`; resto → `other`. No se guarda ningún ID, hash, longitud ni alias.
- El primer create se anota `start` después de crear la captura, con `identified=false`, relación `missing` y sus dos campos opcionales.
- Un create válido con captura activa se anota `overlap`, incluyendo sus dos campos opcionales, antes de fallar. Un tipo cliente ignorado no añade paso. Un cliente inválido activo anota `invalid`/`fail`, sin valores externos.
- En servidor anota, en la rama que ya existe, `ignore_previous`, `ignore_other_id`, `ignore_no_id`, `observe`, `finish` o `fail`. `response.created` aceptado es `observe`; un terminal correcto es `finish`. No uses el diagnóstico para elegir la rama. Los límites de bytes se siguen comprobando antes de decodificar.
- Un error de decodificación/proyección se representa como servidor `invalid`/`fail`. `close` y `uninspectable` locales con activa usan `fail`. No añadas pasos cuando no hay captura o la conexión está deshabilitada.
- Al perder el paso más antiguo del deque, fija `truncated=true`. Nunca una lista que crezca sin límite.

### Publicación y limpieza

En `_fail_active`, antes de `capture.fail`, adjunta una copia independiente del diagnóstico al registro existente, bajo `store.LOCK`, solo si el estado no está committed. No publiques por separado: `capture.fail` ya publica el error. No resucites registros borrados o expulsados.

`_release` elimina el anillo local y los contadores después de copiar, sin modificar la copia del registro. Éxito y finalización por límites no añaden el campo público y liberan el anillo. Los fallos inesperados de `_guard` siguen propagándose; no modifiques el resultado ya committed ni intentes convertir una excepción inesperada en éxito.

Cerrar dos veces, duplicar terminales o enviar mensajes tras deshabilitar no cambia el diagnóstico publicado, no crea filas y no duplica coste. No se añade I/O al ciclo de Session.

## 4. Fallos saneados del runner

Conserva el prefijo `the WebSocket record did not complete successfully` y añade `; diagnostic=` seguido de JSON compacto ASCII generado por `format_record_failure`. No interpolar el registro, notas, excepción, modelo, IDs o salida del CLI.

`format_record_failure` es puro, recibe el objeto de registro ya comprobado por ID y devuelve el JSON con estas únicas claves:

| Clave | Validación / sustitución |
| --- | --- |
| `transport` | `websocket` o `http`; ausente se considera `http`, valor desconocido → `unknown` |
| `status` | Entero exacto 100–599; cualquier otra forma → null |
| `state` | `pending`, `streaming`, `done`, `error`; otra forma → `unknown` |
| `verdict` | `HIT`, `PARTIAL`, `MISS`, `COLD`, `N/A`, `ERR`; otra forma → `unknown` |
| `reason` | Código cerrado de la tabla inferior; otra nota o forma → `unknown` |
| `ws_diagnostic` | Reconstrucción validada del contrato 2, o null si falta o tiene forma inválida |

| Nota exacta ya presente en código | Código de `reason` |
| --- | --- |
| captura WebSocket interrumpida: peticiones solapadas | `overlap` |
| conexión WebSocket cerrada antes de completar la respuesta | `closed_before_completed` |
| respuesta WebSocket fallida | `response_failed` |
| respuesta WebSocket incompleta | `response_incomplete` |
| error del protocolo WebSocket | `protocol_error` |
| evento WebSocket no inspeccionable | `uninspectable` |
| error interno al inspeccionar WebSocket | `internal_error` |
| captura incompleta: límite de tamaño de respuesta | `response_size_limit` |
| captura incompleta: límite de respuestas simultáneas | `active_capture_limit` |

Para `reason`, examina como máximo las primeras ocho notas si es una lista, en orden; elige el primer texto exactamente reconocido, sin imprimir ningún otro. El código nombra el fallo del inspector, no prueba la causa del protocolo.

Valida cada paso contra los enums, booleanos exactos y claves requeridas. Los campos opcionales solo son válidos en `response.create`. Si hay más de 32 pasos, contador no entero 0–255, enum desconocido o forma inválida, todo `ws_diagnostic` se representa null. No recortes una secuencia y la presentes como completa. Descarta claves ajenas al reconstruir.

La cadena JSON no supera 8192 bytes UTF-8. Si excepcionalmente los supera, sustituye solo `ws_diagnostic` por null y conserva el resto saneado. No se escriben ficheros de diagnóstico ni se conservan los temporales para depurar.

Errores de ID distinto, JSON inválido y esquemas de usage siguen sus errores actuales; no se debilita ninguna validación para obtener un resultado verde. `READY`, resumen de éxito, `COLD`, limpieza, una sola invocación y ausencia de reintentos permanecen iguales.

## 5. Qué se puede concluir

| Evidencia | Conclusión permitida |
| --- | --- |
| Dos creates con activa, sin secuencia de control | El inspector activó su protección; causa real indeterminada |
| Completed ignorado por no tener created reconocido | Esa es la rama del inspector; no demuestra que esa variante haya ocurrido en el tráfico real |
| Create con generate=false en un test | Hipótesis sintética; no demuestra precalentamiento de Copilot |
| Traza real futura válida | Puede motivar un fixture nuevo y un plan de corrección, tras revisión |
| Error de Auto | Problema de enrutamiento separado; no demuestra un fallo de transporte ni de caché |

No se autorizan llamadas reales en este plan. Si solo se dispone de las capturas actuales, el informe final debe decir `causa real indeterminada` y no prometer la reparación.
