# Evidencia al redactar el plan

Fecha: 2026-10-30. Base de código: `ac0dc07`. No se enviaron prompts para redactar este plan.

## Capturas reales consultadas

Se consultaron únicamente snapshot y detalle de métricas del inspector ya activo; no los cuerpos, credenciales ni eventos crudos. Es una fotografía del momento, no un recuento fijo para futuros tests.

| Resultado del snapshot | Observado |
| --- | --- |
| Registros retenidos | 23 |
| HTTP | 20, todos `done` |
| WebSocket | 3, todos `error`, `status=101`, `verdict=ERR` |
| GPT-6 Luna | Una captura con la nota de solapamiento y otra con cierre antes de completar |
| GPT-6.1 Sol | Una captura con la nota de solapamiento |

Las tres capturas WebSocket no tienen usage validado. No se deduce su coste, consumo real ni número de llamadas facturadas a partir de los registros fallidos.

El usuario también informó de `Auto routing is unavailable; server-discovered preferences require the /auto endpoint`. Se trata como bloqueo separado de selección de modelo; no prueba por sí solo un fallo del inspector.

## Comprobaciones offline

- FULL pasó: 370 tests Python, 20 JS y Chrome completo incluida C34. Advertencias ya existentes de sockets y módulos Node no bloquearon el resultado.
- Mypy explícito sobre `scripts/check_copilot.py` pasó.
- El runner sin opciones imprimió exactamente `READY: no model calls; use --run-real`.
- Se ejecutó la matriz sintética que se fija en `casos.json`: todas sus entradas describen comportamiento existente, no una reproducción demostrada del protocolo real fallido.
- El create con `generate=false` pierde esa clave en la normalización actual y sigue creando una captura. Se anota como hipótesis de diagnóstico, no como causa probada.
- Se revisó sin llamadas nuevas la secuencia estructural de la captura anonimizada anterior al soporte: un create, created, in_progress y completed. No contiene el solapamiento de las nuevas capturas y no basta para atribuirles una causa.

## Qué falta

Los registros actuales no contienen orden de eventos, razones de ignorar terminales ni clasificación de metadatos descartados. No puede distinguirse solapamiento real, finalización no reconocida u otro patrón solo a partir de sus notas.

El primer objetivo es hacer observable esa diferencia sin guardar contenido y mantener la protección actual. La reparación del protocolo y otra llamada real quedan fuera de este plan, pendientes de evidencia y autorización.
