# Contratos comunes del destino

Este fichero contiene decisiones compartidas; cada tarea señala qué sección necesita.

## Límites

Son valores nuevos de política, no resultados medidos ni garantías sobre el RSS total del proceso.

| Constante en `config.py` | Valor | Política |
| --- | --- | --- |
| `MAX` | 300, existente | Máximo de registros retenidos |
| `MAX_REQUEST_BYTES` | 4 × 1024 × 1024 | Peticiones mayores se dejan pasar y no se inspeccionan |
| `MAX_BODY_BYTES` | 64 × 1024 × 1024 | Presupuesto de cuerpos UTF-8 retenidos; expulsión FIFO de registros y cuerpos juntos |
| `MAX_RESPONSE_BYTES` | 8 × 1024 × 1024 | Retención por respuesta; si se supera se descarta el buffer entero |
| `MAX_ACTIVE_CAPTURES` | 16 | Máximo de respuestas con buffer activo; las demás pasan sin captura |
| `MAX_CLIENT_EVENTS` | 512 | Máximo de eventos pendientes por cliente SSE |

El proxy siempre devuelve los bytes originales de la respuesta. Un límite del inspector no interrumpe ni transforma la llamada al proveedor.

## Expulsión y protocolo SSE

- `store.add(rec, body)` devuelve los IDs expulsados, en orden FIFO. Actualiza un contador de bytes y expulsa hasta satisfacer ambos límites. Un cuerpo mayor que el presupuesto puede expulsar también el registro recién añadido.
- `store.push(rec, evicted_ids=())` conserva el evento actual si la lista está vacía. Si no, añade `evicted_ids` al evento `record`.
- Si el nuevo registro no quedó retenido, `push` publica un evento `evict` con `ids`, sin volver a insertarlo en el cliente.
- El snapshot HTTP añade `max_records: config.MAX`; no modifica los eventos recogidos por `scenario.run()`.
- El frontend elimina primero los IDs expulsados; procesa después el registro y limita defensivamente su Map a los IDs más altos hasta `max_records`. En snapshot sustituye todo el contenido y aplica ese límite.
- Cuando desaparece la selección, cierra el detalle y libera su cuerpo. Cuando cambia el snapshot o se limpia, invalida las respuestas HTTP pendientes.
- Los estados derivados `visible`, `successors` y opciones de filtros se recalculan desde los registros retenidos.

## Clientes SSE y lock

- Se conserva `threading.Lock`, no se cambia a `RLock` para ocultar llamadas anidadas.
- Funciones de estado de `store` requieren `LOCK` adquirido por el llamador; no lo adquieren internamente. El contrato pasa a incluir `publish`.
- Añadir/quitar clientes y tomar el snapshot se hacen bajo el mismo lock. Escritura HTTP, espera en colas, filesystem y logging se hacen fuera.
- Una cola llena se vacía y recibe un único evento interno `disconnect`. El handler lo consume, sale y cierra la conexión; no envía ese evento al navegador. EventSource reconecta y recibe un snapshot completo.
- Los suscriptores de replay usan el mismo registro y tamaño de cola. 512 supera los 131 eventos del escenario actual.

## Diagnósticos

- Logs de aplicación mediante `logging.getLogger(__name__)`; no se añade un handler global ni se registra contenido capturado, tokens o cabeceras.
- Petición no inspeccionable: warning con razón fija y sin cuerpo; se deja pasar sin `tap_id`.
- Captura de respuesta limitada: `capture_limited` opcional con valor `response_size` o `active_captures`. Al finalizar, `usage=None`, `raw_usage=[]`, `output=''`, veredicto `N/A`, nota «captura incompleta: límite de tamaño de respuesta» o «captura incompleta: límite de respuestas simultáneas». No se deduce un veredicto de un usage parcial.
- Fallo del jsonl: warning con ID y clase de excepción; el registro sigue completado y publicado. La escritura no mantiene el lock.
- Error de interfaz: mensaje visible mediante `textContent`, sin borrar los registros ni provocar promesas rechazadas sin manejar. No confundir 404 de cuerpo expulsado con error de red.

## Tipos

- Los JSON externos permiten heterogeneidad: `JsonValue` recursivo y `JsonObject` en `record.py`; si mypy requiere `Any` en el punto de deserialización, se permite allí con una nota local, no en contratos de dominio.
- `Segment`: obligatorios `name`, `hash`, `bytes`, `cc`, `preview`; opcional `same`.
- `Diff` y `Usage`: todos sus campos actuales obligatorios; conservan los valores `None` actuales.
- `Record`: `id` obligatorio, resto de campos existentes opcionales porque se completa por etapas. `state`, `verdict`, `ttl_anchor` y `capture_limited` usan aliases con `Literal`. Los tipos no sustituyen las validaciones de runtime.
- `CacheTTL`: obligatorios `ttl_s`, `ttl_source`, `ttl_anchor`; opcional `ttl_max_s`. `UsageEvent`: obligatorios `event` y `usage`.
- No se introduce una dataclass para el registro mutable JSON. Los hooks reciben `mitmproxy.http.HTTPFlow`; los tests pueden seguir usando flujos falsos sin estar incluidos en el chequeo estático de producción.

## Casos nuevos y caracterización

Los valores existentes citados en las tareas provienen del código/tests ejecutados al escribir el plan. Los resultados de comportamiento nuevo se marcan como **contrato nuevo**: se implementan y comprueban en su tarea, no se presentan como observaciones del estado actual.
