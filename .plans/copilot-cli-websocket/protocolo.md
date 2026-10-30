# Contrato y evidencia verificada

## Evidencia del 30 de octubre de 2026

Se probó Copilot CLI 1.0.105 desde un directorio vacío, con `hola`, modelo `auto` y perfil `efficiency`. La segunda prueba real reportó GPT-6 Luna y 0,06 créditos. No se persistieron cuerpos crudos ni credenciales: solo formas anonimizadas y contadores. El cliente recibió su respuesta correctamente.

| Tramo observado | Función | Decisión |
| --- | --- | --- |
| GET `/models` | Catálogo | No crear registro |
| POST `/auto` | Selección; su respuesta contiene `session_token` | No inspeccionar ni retener su cuerpo |
| GET `/responses`, respuesta HTTP 101 | Apertura de WebSocket | No crear registro de inferencia por el handshake |
| Mensaje cliente `type=response.create` | Petición real; `model`, `input`, `tools`, `reasoning` en la raíz | Un registro por mensaje aceptado |
| Mensaje servidor `response.created` | `response.id` y modelo | Identificar la respuesta activa |
| Mensaje servidor `response.output_text.delta` | `delta` de texto | Texto visible y TTFT |
| Mensaje servidor `response.completed` | `response.usage` | Finalizar una sola vez |

Los mensajes cliente y servidor pueden contener un objeto raíz `headers`. Es parte del sobre del protocolo: no debe llegar al cuerpo retenido, al JSONL, a `raw_usage` ni a las notas. Tampoco se retienen `copilot_quota_snapshots`, `copilot_usage`, IDs de interacción ni `encrypted_content` o contenido de razonamiento de los eventos servidor. El contenido de input que envía el cliente sigue siendo el cuerpo de inferencia retenible en memoria: no se reescribe su contexto.

El paquete npm localizado en otra instalación era 0.0.365, no el binario probado. No se usa como descripción de 1.0.105.

## Caso sintético reproducible

`caso.json` contiene texto y IDs artificiales, la forma del protocolo observado y los contadores de la segunda prueba. No es una captura cruda. La primera tarea lo copiará a `tests/fixtures/copilot_responses_ws.json`; los tests no dependerán de `.plans`.

| Valor | Resultado comprobado con los lectores y tarifas actuales |
| --- | --- |
| Modelo | `gpt-6-luna` |
| Uso normalizado | `input_total=13293`, `read=9004`, `write=4286`, `uncached=3`, `output=36`, `reasoning=21` |
| Texto sintético | `Hola mundo` |
| Segmentos de la petición normalizada | `msg0:system`, `msg1:user` |
| Primera llamada con ese uso | `PARTIAL`; no hay petición anterior con la que comparar |
| TTL | 1800 segundos, fuente predeterminada de GPT-5.6 y posteriores |
| Tarifa del host observado | Copilot |
| Coste según tablas actuales | `usd=0.00064409`, `no_cache_usd=0.0013473`, `saved_usd=0.00070321` |

El coste por tablas no se compara con el cargo exacto del CLI: Auto puede aplicar descuentos. Este plan no cambia facturación ni consume `copilot_usage` para sustituir precios.

## Destino y dependencias

| Módulo | Responsabilidad | Imports internos permitidos |
| --- | --- | --- |
| `cachetap/capture.py` | Alta, reserva, buffer, finalización, error y log de una captura; sin mitmproxy | `config`, `record`, `segments`, `linking`, `providers`, `response_body`, `verdict`, `cost`, `store` |
| `cachetap/websocket.py` | Decodificación/proyección Responses y estado de una conexión; sin mitmproxy | `config`, `record`, `request_body`, `capture`, `store` |
| `tap.py` | Frontera mitmproxy: HTTP existente y hooks WebSocket | Usa los módulos anteriores con prefijo; ningún módulo importa `tap` |

No se añade un proveedor «Copilot»: el modelo sigue siendo OpenAI y la tarifa la decide el host. No se cambia `response_body.py`: se convierte cada evento permitido a una línea SSE interna para reutilizar sus lectores existentes.

## API común de captura

La tarea 1.02 crea `begin`; 1.03 completa el resto. Los argumentos opcionales nuevos de esta tabla se incorporan en 2.02, no durante las extracciones mecánicas.

| Función | Entrada / salida fijadas |
| --- | --- |
| `begin(req, text, host, path, request_bytes, started_at)` | Objeto ya validado, cuerpo retenible, host/ruta, bytes originales y timestamp opcional; devuelve el ID. En 2.02 admite keywords `transport=None`, `context_partial=False` |
| `start(rid, status, response_headers, request_end, response_start)` | Cabeceras de respuesta ya filtradas; devuelve `StreamState` y publica `streaming` |
| `feed(rid, state, data)` | Devuelve el mismo objeto bytes. En 2.02 admite keyword `at=None` para el timestamp del mensaje WebSocket |
| `limit(rid, state, reason)` | Vacía chunks y libera reserva; marca el mismo `CaptureLimit` existente; idempotente |
| `finish(rid, state, status, request_end, logger)` | Lectores, veredicto, coste, total y log; limpieza en finally. En 2.02 admite keyword `ended_at=None` |
| `fail(rid, state, message)` | `state` admite None; conserva el comportamiento actual de error HTTP. En 2.02 admite keyword `ended_at=None` |

`StreamState` conserva `chunks`, `first`, `bytes`, `limited`, `reserved`. En 2.02 añade `closed` para impedir doble finalización/coste/log. Los valores temporales por defecto siguen usando `time.time`, como hoy. El logger de `finish` lo pasa el llamador: los avisos HTTP siguen siendo de `tap`.

## Decodificación Responses WebSocket

| API de `websocket.py` | Contrato |
| --- | --- |
| `decode_client(content)` | Bytes UTF-8 estrictos, objeto JSON `type=response.create`; devuelve objeto validado por `request_body.parse`, o None para otro tipo válido. JSON inválido, raíz inválida, forma inválida o tamaño excesivo: ValueError con motivo fijo sin datos externos |
| `decode_server(content)` | Bytes UTF-8 estrictos y objeto con `type` texto; devuelve el objeto decodificado o ValueError fijo. Nunca se persiste ni se añade ese objeto completo a un buffer |
| `project_event(event)` | Objeto mínimo de la tabla siguiente, o None. Valida las formas de los campos que consume; nunca copia `headers` ni campos ajenos |

La petición normalizada conserva únicamente estas claves raíz cuando existen: `model`, `input`, `instructions`, `tools`, `reasoning`, `reasoning_effort`, `tool_choice`, `parallel_tool_calls`, `max_output_tokens`, `prompt_cache_options`, `prompt_cache_retention`, `previous_response_id`, `stream`, `text`, `store`, `include`. No elimina campos dentro de mensajes o esquemas de tools. `previous_response_id` solo admite texto o null. La presencia de texto no vacío activa `context_partial`.

| Tipo servidor | Proyección retenible |
| --- | --- |
| `response.created`, `response.in_progress` | `type` y `response` con `id`/`model` si son texto; sin más propiedades |
| `response.output_text.delta` | `type`, `delta` texto y `response_id` opcional de texto |
| `response.completed` | `type`, `response` con `id`, `model` y `usage` objeto si existen; sin copiar output ni sobre |
| `response.failed`, `response.incomplete`, `error` | Solo `type` y, si existe, `response.id` texto; mensaje de error local fijo |
| Otros tipos válidos, incluidos deltas de razonamiento y tools | None; no se retienen ni cuentan como texto/TTFT |

No se guarda el ID de respuesta en el registro público. El estado de la conexión puede conservar el ID activo y el último terminado para correlacionar y descartar duplicados, nunca un historial creciente.

## Estado por conexión y límites

`Session` ofrece `client(content, at)`, `server(content, at)` y `close(at=None)`. Su constructor recibe `host`, `path` y `logger`. No recibe objetos mitmproxy. Una conexión admite peticiones secuenciales; no se promete multiplexación simultánea.

Los mensajes locales están fijados para no dejar decisiones de privacidad al ejecutor:

| Situación | Nota o aviso literal |
| --- | --- |
| `response.failed` | `respuesta WebSocket fallida` |
| `response.incomplete` | `respuesta WebSocket incompleta` |
| `error` | `error del protocolo WebSocket` |
| Cierre con petición activa | `conexión WebSocket cerrada antes de completar la respuesta` |
| Create solapado | `captura WebSocket interrumpida: peticiones solapadas` |
| JSON/UTF-8 servidor inválido o binario activo | `evento WebSocket no inspeccionable` |
| Petición cliente inválida o excesiva | Aviso `Petición WebSocket no inspeccionable`, sin interpolar el payload ni la excepción |
| Bug inesperado durante una captura | Limpiar con `error interno al inspeccionar WebSocket` y propagar la excepción original |

| Entrada / situación | Efecto exigido |
| --- | --- |
| Cliente `response.create` válido y sin petición activa | `begin` y `start`; `status=101`, `resp_headers={}`, sin `hdr_s`; el origen temporal es el timestamp de ese mensaje, no el handshake |
| Registro WebSocket | Campo opcional `transport="websocket"`; ausente en HTTP |
| Petición con `previous_response_id` no vacío | Campo opcional `context_partial=True`; no enlazar con previas y dejar `_msgs=[]` para que ninguna posterior se enlace con ella. Con usage: N/A y nota `contexto incremental WebSocket: no se dispone del prefijo completo`; puede tener coste conocido, nunca `lost_usd` |
| Primer delta de texto | `first=at`; no usar el razonamiento para TTFT |
| Delta de texto vacío | No adelantar TTFT; no añadir al buffer un evento que solo dispararía el marcador sin texto |
| `response.created` | Asociar ID. Un ID diferente del activo no puede finalizar la petición actual |
| `response.completed` correspondiente | `finish` una vez, soltar estado activo; permitir otra petición en esa conexión |
| Terminal duplicado / evento sin petición activa | Ignorar; no crear filas ni sumar coste |
| Terminal con ID del último ya terminado | Ignorar, incluso si ya llegó otra petición cliente |
| `response.failed`, `response.incomplete`, `error`, cierre con petición activa | `fail`, estado error/ERR y nota local fija; sin inventar usage/coste de una respuesta incompleta |
| Segundo create mientras sigue activa la primera | Fallar la activa con nota de solapamiento y deshabilitar inspección de esa conexión hasta su cierre. No asignar eventos ambiguos a una segunda fila |
| JSON o UTF-8 servidor inválido durante una captura, o mensaje binario durante ella | Fallar con nota de evento no inspeccionable y deshabilitar esa conexión. Mensajes ajenos sin captura activa no crean filas |
| Petición cliente inválida o excesiva | No crear fila; deshabilitar la conexión para no atribuir su respuesta a otra petición; aviso fijo sin contenido |
| Respuesta supera bytes permitidos | `limit(...,"response_size")`, `finish` en N/A inmediatamente y deshabilitar inspección de esa conexión; el tráfico continúa |
| Reserva simultánea agotada | Finalizar de inmediato como N/A con `active_captures`, deshabilitar esa conexión; no reservar memoria de respuesta |

Los errores de transporte anteriores usan mensajes locales fijos, no el cuerpo de error, close_reason ni cabeceras externas. Después de un fallo ambiguo se prefiere dejar de inspeccionar esa conexión a producir diagnósticos falsos; reconectar crea una sesión nueva.

Aplica `MAX_REQUEST_BYTES` al tamaño del mensaje cliente antes de decodificar. En servidor lleva un contador de bytes originales por petición y comprueba el límite antes de decodificar; el buffer común limita por separado los bytes SSE retenidos. Cualquiera de los dos desbordamientos limita la captura. Esto evita que anonimizar eventos reduzca artificialmente el tamaño medido. No se retienen listas de eventos aparte del buffer común.

Los 16 slots son compartidos por HTTP y WebSocket. El alta WebSocket reserva antes de acumular mensajes. Cada finalización, error, cierre y `done` debe soltar reserva/buffers. Tras expulsión o clear, se detecta la ausencia del registro en el siguiente mensaje o cierre y se libera sin resucitarlo; no se cambia store.clear ni el comportamiento histórico de HTTP. No se limita el historial previo de mensajes que mantiene mitmproxy ni el RSS total.

## Frontera mitmproxy

Solo activar para GET con respuesta 101, host `githubcopilot.com` o subdominio con frontera de punto, y ruta normalizada `/responses` o `/v1/responses`. Ignorar query y barra final solo para comparar, como en HTTP. No ampliar `_is_llm` ni añadir `/auto` a `LLM_PATHS`.

`tap.py` mantiene `SOCKETS`, un diccionario de sesiones por `flow.id`, sin guardar mensajes en él. `websocket_start` registra sesión; `websocket_message` procesa exclusivamente el último mensaje ensamblado y usa `message.timestamp`, `from_client`, `is_text`, `content`; `websocket_end` cierra y retira sesión. Si está dropped o injected, no lo cuenta. `error` cierra también la sesión de ese flow. `done` cierra y vacía las sesiones antes de parar el panel; conserva la limpieza HTTP existente.

Mitmproxy ya ensambla frames fragmentados en un `WebSocketMessage` de bytes: no implementar ensamblador propio, no modificar los mensajes y no duplicar la inferencia como un registro HTTP.
