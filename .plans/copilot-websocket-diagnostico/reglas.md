# Reglas de ejecución

Lee estas reglas, tu tarea y las secciones de `contrato.md` que cite. Del índice consulta solo tu fila y sus dependencias. No ejecutes otras tareas por iniciativa propia.

## Rutas y comprobaciones

- RAÍZ = ruta absoluta del checkout; PLAN = `RAÍZ/.plans/copilot-websocket-diagnostico`. Usa RAÍZ como directorio de trabajo, sin publicar rutas personales.
- CHECK = `venv/bin/python scripts/check.py`; salida final `all checks passed`.
- FULL = `venv/bin/python scripts/check.py --full`; salida final `all checks passed`, incluida C34. Requiere Chrome.
- RUNNER-TYPES = `venv/bin/python -m mypy scripts/check_copilot.py`; salida `Success: no issues found in 1 source file`.
- RUNNER-LINT = `venv/bin/python -m ruff check scripts/check_copilot.py tests/test_check_copilot.py`; salida `All checks passed!`.
- RUNNER-FORMAT = `venv/bin/python -m ruff format --check scripts/check_copilot.py tests/test_check_copilot.py`; código 0.
- PLAN-CHECK = `venv/bin/python .plans/copilot-websocket-diagnostico/check_plan.py`; salida `Plan OK: 5 tareas; 7 casos offline; invariantes preservadas`.
- Un módulo de tests: `venv/bin/python -m unittest tests.<nombre> -q`; salida `OK`. No fijes el total futuro de tests.
- Ejecuta cada comando por separado. Todas las comprobaciones son offline, salvo servidores propios de pruebas en loopback.

## Antes de empezar

1. Comprueba las dependencias y marca tu fila `en curso`.
2. Lee `AGENTS.md`, revisa `git status --short` y ejecuta CHECK y PLAN-CHECK. Si fallan antes de tus cambios, bloquea y para.
3. No sobrescribas un fichero marcado nuevo si ya contiene trabajo ajeno.
4. La ejecución que modifica `cachetap` requiere un checkout sin proxy de usuario cargado desde ese directorio. El orquestador debe resolver ese aislamiento antes de lanzar 1.02: preferentemente checkout separado con los mismos invariantes; nunca detener ni recargar el inspector activo sin permiso. No pierdas las capturas del usuario para desarrollar.

## Límites

- Solo toca tu lista cerrada y tu propia fila del índice. No hagas add, commit, push, stash, resets ni descartes. Los commits y push los hace el orquestador después de auditar, conforme al acuerdo anterior.
- Conserva las diez huellas de `base-ejecucion.json`: ocho ficheros ya modificados antes de este plan, golden y fixture original. No modifiques el plan anterior para presentar su prueba real como aprobada.
- No envíes prompts, no ejecutes `--run-real`, no consultes endpoints de proveedores, no hagas login, instalaciones ni actualizaciones. El error de Auto se documenta como problema separado; no se arregla aquí.
- Los tests usan `config.LOG` temporal, estado aislado y puerto 0. No usan 8899/8900, no escriben en `data/requests.jsonl` ni leen configuración/credenciales del usuario. La lectura del panel real ya se hizo al redactar la evidencia; no se convierte en dependencia de los tests.
- No retengas eventos crudos, cabeceras, cuerpos, texto, razonamiento, IDs reales ni hashes de IDs. No hagas dumps de excepciones o de stdout/stderr del CLI.
- Mantén los imports de `cachetap` como módulos con prefijo, los TypedDict y la tabla de dependencias actual. Este plan no añade módulos de producción ni dependencias.
- Toda mutación de `store` se hace bajo `store.LOCK`. Nunca logging, I/O ni esperas dentro del lock.
- El diagnóstico es observacional: no cambia el emparejamiento, `decode_client` público, los mensajes, el historial de mitmproxy, la política ante ambigüedad, los tokens, el coste ni sus acumulados.
- No reconstruyas contexto incremental, no aceptes concurrencia por orden de llegada y no quites el guard de solapamiento. No cambies precios, UI, proveedores, `start.sh` ni `via.sh`.
- Tras cambiar `cachetap`, actualiza el mtime de `tap.py` solo en el checkout aislado autorizado; no cambies su contenido en tareas que no lo permiten.

## Cierre

1. Ejecuta las comprobaciones de tu tarea, CHECK, PLAN-CHECK y `git diff --check`.
2. Verifica los invariantes y el alcance del diff. Si una comprobación falla dos veces, falta evidencia o el contrato no encaja, marca `bloqueada` y para; no inventes una reparación.
3. Marca `terminada sin commit` e informa de ficheros, resultados y desviaciones. No afirme nadie que el WebSocket real ya funciona por pasar tests sintéticos.
4. El usuario autorizó ejecutar las cinco tareas con Luna; al cerrar cada fase el orquestador audita y resume antes de continuar. Este plan acaba en diagnóstico offline: corregir el protocolo y hacer otra prueba real requieren un plan/encargo posterior y autorización explícita.
