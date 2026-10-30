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

El usuario lleva las decisiones y la ejecución real. No redactar comandos ni desbloquear estas puertas sin su receta auditada. Esta reserva no modifica ni delega lectura de `data/`; resultado real queda pendiente. No hay autorización aquí para reparar tarifa, correlación o protocolo.
