# Reglas para ejecutar una tarea

Lee estas reglas, el fichero de tu tarea y las secciones de `protocolo.md` que tu tarea cite. Del índice lee solo tu fila y el estado de sus dependencias. No leas otras tareas.

## Rutas y comandos

- RAÍZ = raíz del repositorio; PLAN = `RAÍZ/.plans/copilot-cli-websocket`.
- Define RAÍZ como ruta absoluta del checkout donde trabajas; ejecuta los comandos con ese directorio de trabajo. No copies rutas personales de esta sesión.
- CHECK = `"$RAÍZ/venv/bin/python" "$RAÍZ/scripts/check.py"`.
- FULL = `"$RAÍZ/venv/bin/python" "$RAÍZ/scripts/check.py" --full`.
- PLAN-CHECK = `"$RAÍZ/venv/bin/python" "$RAÍZ/.plans/copilot-cli-websocket/check_plan.py"`.
- Un módulo de tests: `"$RAÍZ/venv/bin/python" -m unittest tests.<módulo> -q`.
- CHECK debe terminar con `all checks passed`; unittest debe terminar con `OK`. Los recuentos aumentarán: no fijes el total de tests nuevos.
- FULL requiere Chrome/Chromium. La batería de navegador sigue usando sus puertos de pruebas configurables, nunca los del usuario.

## Antes de empezar

1. Comprueba en tu fila que las dependencias están terminadas y marca `en curso`.
2. Lee `AGENTS.md` y ejecuta `git status --short`. Conserva todos los cambios previos.
3. Ejecuta CHECK. Si falla antes de tus cambios, marca `bloqueada` y comunica el fallo; no arregles otros trabajos.
4. Comprueba si ya existen los ficheros marcados como nuevos. Si contienen trabajo no descrito por el plan, para antes de sobrescribirlos.

## Mientras trabajas

- Toca solo los ficheros autorizados por tu tarea y tu fila del índice. No ejecutes otras tareas por iniciativa propia.
- No hagas `git add`, `git commit`, `git stash`, resets ni descartes cambios.
- Los imports de `cachetap` son de módulos y se usan con prefijo. Actualiza la tabla de dependencias y la lista de mypy cuando tu tarea añada un módulo.
- Mantén los contratos `TypedDict`; los campos nuevos exclusivos de WebSocket no se añaden a los registros HTTP.
- Solo se guarda el cuerpo de inferencia normalizado y sin el sobre de transporte. Nunca leas cabeceras HTTP de petición, guardes tokens de sesión, vuelques eventos WebSocket crudos o copies razonamiento cifrado desde los eventos servidor.
- Las pruebas automáticas son sintéticas y sin llamadas a proveedores. Usa log temporal y servidores en `127.0.0.1` con puerto `0`; no escribas en `data/requests.jsonl` ni uses 8899/8900.
- No cambies `tests/replay/golden.json` ni definas `TAP_UPDATE_GOLDEN`. El escenario histórico debe seguir idéntico.
- Todo acceso mutable a `store` se hace bajo `store.LOCK`. Logging, fichero y HTTP quedan fuera. `count_cost` se llama una sola vez por registro.
- No cambies el mensaje, sus bytes, `dropped`, `injected` ni el historial WebSocket de mitmproxy. Las limitaciones del inspector no deben interrumpir al cliente.
- No cambies precios, descuentos de Auto, reglas de otros proveedores, UI de producción ni añadas dependencias.
- Tras modificar `cachetap`, guarda también `tap.py` o actualiza su mtime al cerrar la tarea, como exige `AGENTS.md`.

## Si algo no cuadra

Si una instrucción no encaja con el código, aparece otro protocolo, o una verificación falla dos veces, para. Marca `bloqueada`, escribe el hecho observado en tu fila y pide revisión del plan. No inventes otro esquema ni hagas llamadas reales para investigar.

## Al terminar

1. Ejecuta la verificación específica, CHECK y PLAN-CHECK.
2. Revisa `git diff` para confirmar que no alteraste el golden, los precios ni cambios ajenos.
3. Marca `terminada sin commit` e informa de los ficheros cambiados y comandos pasados.
4. Al cerrar una fase, para y espera confirmación antes de la siguiente. La comprobación real final es optativa y no bloquea la entrega offline.
