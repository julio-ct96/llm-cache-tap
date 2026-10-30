# Reglas de ejecución

Lee estas reglas, tu tarea y solo las secciones de evidencia que cite. Del índice consulta tu fila y sus dependencias. El usuario autorizó ejecutar la fase 1 con Luna y auditoría del orquestador, con commit/push por tarea aprobada. Las siguientes fases requieren la confirmación prevista al cerrar esta.

## Rutas y comandos

- RAÍZ = ruta absoluta del checkout autorizado; PLAN = `RAÍZ/.plans/copilot-reparacion-capturas`. Ejecuta los comandos con RAÍZ como directorio de trabajo, sin encadenarlos. No publiques rutas personales.
- Los nombres de documentos de este plan (`evidencia.md`, `casos.json`, `contratos/...`, `resultado.md`) son relativos a PLAN; las rutas `cachetap/`, `scripts/`, `tests/` y `AGENTS.md` son relativas a RAÍZ.
- CHECK = `venv/bin/python scripts/check.py`; termina en `all checks passed`.
- FULL = `venv/bin/python scripts/check.py --full`; termina en `all checks passed`, incluido Chrome/C34.
- PLAN-CHECK = `venv/bin/python .plans/copilot-reparacion-capturas/check_plan.py`; termina en `Plan OK: 9 tareas; invariantes preservadas`.
- BASELINE = el mismo comando con `--baseline`; además imprime `Baseline OK: 6 secuencias WebSocket; 3 variantes CLI rechazadas`. Solo se usa antes de las reparaciones, no es un contrato para perpetuar el fallo.
- EVIDENCE = el mismo comando con `--evidence`; además imprime `Evidence OK: 16 ficheros originales verificados`. Es una comprobación local optativa, nunca una dependencia de CI.
- GATE = el mismo comando con `--gate websocket`, `--gate uso-cli` o `--gate precios`. Mientras falte evidencia o aprobación termina con código 1 y `Gate <nombre>: BLOCKED`; solo una puerta aprobada da código 0 y `Gate <nombre>: APPROVED`.
- RUNNER-TYPES = `venv/bin/python -m mypy scripts/check_copilot.py`; salida `Success: no issues found in 1 source file`.
- RUNNER-LINT = `venv/bin/python -m ruff check scripts/check_copilot.py tests/test_check_copilot.py`; salida `All checks passed!`.
- RUNNER-FORMAT = `venv/bin/python -m ruff format --check scripts/check_copilot.py tests/test_check_copilot.py`; código 0.
- Un módulo de tests: `venv/bin/python -m unittest tests.<nombre> -q`; resultado `OK`. No fijes el total futuro de tests.

## Antes de empezar

1. El orquestador obtiene autorización de ejecución. Usa un subagente Luna por tarea, con el modelo verificado mediante el catálogo; no deduzcas un identificador de modelo.
2. Desarrolla en un checkout separado del inspector vivo. Conserva en él las huellas de `base-ejecucion.json`, incluidos los ocho ficheros sucios preexistentes; no los incluyas en commits. No basta con copiar solo HEAD, porque cambia la base de precios comprobada.
3. Comprueba dependencias y estado; una tarea `bloqueada` nunca se lanza. Marca únicamente tu fila `en curso`.
4. Lee `AGENTS.md`, revisa `git status --short`, ejecuta CHECK y PLAN-CHECK. Si fallan antes de tus cambios, bloquea y para.

## Alcance y seguridad

- Toca solo la lista cerrada de tu tarea y su fila del índice. No hagas add, commit, push, stash, resets ni descartes. El orquestador audita, hace un commit y push por tarea aprobada y actualiza su estado. No publica cambios ajenos ni fuerza push.
- No modifiques los diez ficheros protegidos por huella, ni los planes anteriores. No regeneres golden. Los tests nuevos de precios van en un fichero nuevo, no en los tests de precios con cambios del usuario.
- No leas ni escribas capturas reales salvo la lectura local expresamente citada de la evidencia ya guardada. No modifiques su manifiesto. Nunca uses `data/requests.jsonl`, los puertos 8899/8900, credenciales, configuración privada o el inspector vivo en tests.
- No envíes prompts, no ejecutes `--run-real`, no reintentes pruebas pagadas ni actives Auto. Consultar documentación pública de protocolo/precios no es una llamada de inferencia; solo 1.02, 1.03 y 1.04 permiten esas lecturas públicas, sin login.
- No retengas eventos crudos, cabeceras, cuerpos privados, razonamiento, IDs reales ni hashes de IDs. Las huellas de ficheros completas solo sirven para integridad, no para correlacionar respuestas. Usa IDs artificiales en fixtures.
- No aceptes terminales por orden de llegada ni por ser la única petición activa. No quites el guard de solapamiento, no reconstruyas contexto incremental ni implementes multiplexación.
- Conserva imports con prefijo de módulo, TypedDicts, dependencias, límites y locks de `AGENTS.md`. Ningún I/O ni logging dentro de `store.LOCK`.
- No amplíes alcance a UI, TTL, Auto, modelos auxiliares o proveedores directos. El runner actual comprueba WebSocket: que Gemini/Grok funcionen por HTTP no lo convierte en un comprobador HTTP genérico.
- No actualices ni instales CLI/paquetes para encontrar una fuente. La versión 0.0.365 localizada antes no demuestra el comportamiento de 1.0.105.
- Cambios de `cachetap` y cualquier `touch tap.py` se realizan solo en el checkout aislado. Activar/reiniciar el inspector del usuario queda exclusivamente en 4.01, con permiso posterior.

## Puertas y cierre

1. Las tareas de evidencia pueden concluir con `status=insuficiente`. Eso es un resultado válido de investigación, no una reparación: sus descendientes siguen bloqueados.
2. Solo el orquestador puede poner `approved=true` en un contrato, después de auditar sus fuentes y sustituir la reserva de fase 2 por una receta cerrada con tests y valores comprobados. Un JSON bien formado no demuestra causalidad.
3. Ejecuta las comprobaciones de tu tarea, CHECK, PLAN-CHECK y `git diff --check`. Si falta evidencia no contemplada como resultado `insuficiente` de una investigación, una instrucción exige interpretar o una verificación falla dos veces, marca `bloqueada`, explica y para.
4. Marca `terminada sin commit` e informa de ficheros, resultados y desviaciones. Al cerrar cada fase se detiene la ejecución y se pide confirmación para la siguiente.
5. Tests sintéticos aprobados no equivalen a reparación real confirmada. No repares retrospectivamente las filas ERR ni declares aprobada la prueba histórica de Auto.
