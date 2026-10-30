# Reserva real: PENDIENTE / BLOQUEADA

**Estado:** PENDIENTE y BLOQUEADA hasta que usuario/orquestador revise y publique la receta exacta. Los hechos de inventario read-only indicados aquí fueron aportados por el usuario y se dan por válidos; esta tarea no lee `data/`, panel, cuerpos, JSONL ni binarios.

## Inventario aportado

- PID `73039` sirve `8899/8900` desde `ORIGINAL` (checkout original, ruta local no publicada).
- Snapshot `/events`: 25 filas, 4 WS. `/api/record/<id>` conserva `ws_diagnostic`; `/api/body/<id>` conserva cuerpos. JSONL light no incluye diagnósticos ni `output`.
- Original `main` `697f091`, detrás de `a41417d`, sin solapamiento protegido. Solo se contempla fast-forward-only después de backup y comprobación del diff.
- El backup debe retener snapshot inicial+final, todos los detalles/cuerpos, JSONL y manifest con hashes/estabilidad. Debe fallar si falta el detalle de una fila del snapshot o cambia el estado durante el backup. Es best effort, no atómico.
- No reutilizar `scripts/check_copilot.py --run-real`: `auto/efficiency` no garantiza low, `TemporaryDirectory` elimina artefactos y stdout va a `DEVNULL`.
- Candidato de harness: `data/model-checks/20261030-194813-low-dt3k5lzg`, solo tras revisión del orquestador. Alternativa manual equivalente: razonamiento low, modelos explícitos Terra/MAI/Gemini/Grok/Opus, saludos `hola`/`que tal`/`buenas`, conservar prompts/stdout/usage/API, sin bucle de retries.
- La ausencia de retry en harness no prueba ausencia de retries internos del CLI; declarar el límite y verificar request counts.

## Bloqueos

1. **Backup:** falta receta auditada para recopilar/relacionar snapshot inicial y final, detalle y body de cada fila, JSONL y manifest/hash/estabilidad, con fallo ante detalles ausentes o cambio durante best-effort no atómico.
2. **Fast-forward:** falta receta auditada de verificación ancestry, fast-forward-only y comprobación de diff posterior. No avanzar `main` desde este plan.
3. **Activación:** el proceso/puertos están inventariados, pero falta receta exacta para activar sin interrupción ni pérdida de estado. No tocar PID 73039, checkout original, `tap.py`, puertos, `start.sh` ni procesos.
4. **Prueba real:** falta revisión del harness privado o receta manual equivalente y su captura verificable de request counts/modelos/prompts/usage/API/stdout. No abrir el harness ni ejecutar llamadas en esta fase.

El orquestador lleva las decisiones y la ejecución real autorizadas por el usuario. Las tareas offline no leen `data/`; el acceso operativo requiere su receta auditada. No hay autorización aquí para inventar tarifa, correlación o protocolo.

## Comprobaciones operativas ya realizadas por el orquestador

- Respaldo inicial local creado con permisos 0700/0600: dos snapshots iguales, 25 detalles y 25 cuerpos, manifest y SHA256SUMS verificados. JSONL de 1.172.714 bytes, SHA-256 `c4ccc3f1dfda834e080ecc1efd622543aeaba464f403bad8ed1d238a69c2e1b0`. Ninguna fila activa durante el respaldo. Es una muestra estable, no un snapshot atómico.
- Se revisó el harness anterior: ya fija modelos explícitos, esfuerzo `low`, herramientas denegadas, timeout y una sola invocación por directorio exclusivo. Borra el uso bruto temporal y conserva solo la respuesta del asistente y métricas proyectadas. La siguiente versión debe conservar además el error estructural allowlisted y los tipos/presencia de los campos conocidos antes de limpiar temporales.
- Campaña máxima prevista: cinco invocaciones CLI, una por familia, sin `auto`: Terra/`hola`, Opus/`que tal`, Argon/`buenas`, Grok/`hola`, MAI/`que tal`. El límite de sesión usado anteriormente fue 30 AI credits; no equivale a un coste consumido ni a una garantía de prepago por petición.
- Sin reintentos del harness; la política interna del CLI no está controlada. Verificar los contadores observados y no afirmar ausencia de retries internos. Un error de captura o `invalid_schema` esperado se conserva como evidencia, no se reintenta. Detener campaña ante fallo CLI, timeout, autenticación/cuota, múltiples peticiones observadas o atribución ambigua.
- No guardar eventos CLI crudos, razonamiento, IDs wire, credenciales ni cuerpos de sistema en la evidencia estructural. Guardar prompts sintéticos, respuesta final proyectada, métricas/diagnóstico allowlisted y manifiesto de hashes. El backup privado completo anterior es independiente y no se publica.
- Antes de activar, repetir inventario y respaldo si el estado cambió; verificar huellas protegidas y diff entrante, fast-forward-only del original sin stash/reset, y `touch tap.py` para recarga nativa. La recarga vacía el estado en memoria; este queda preservado en backup, no se promete reimportación al panel. No reiniciar el proceso si basta recargar. Verificar PID/puertos y readiness local después. La ejecución sigue bloqueada hasta terminar integración y auditar el harness nuevo.
