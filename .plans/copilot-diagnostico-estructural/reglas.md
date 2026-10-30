# Reglas comunes

Lee este fichero, tu tarea y solo la sección de `contrato.md` citada por tu tarea.

## Rutas y verificaciones

- `RAIZ` es la raíz del checkout. Las fichas indican comandos con rutas relativas al repo; ejecútalos desde `RAIZ`.
- Tests Python relevantes: cada ficha da selección `unittest` pequeña y offline.
- Runner sin llamada: `venv/bin/python scripts/check_copilot.py`; salida esperada `READY: no model calls; use --run-real`.
- No ejecutar `scripts/check.py`, FULL, Chrome ni `--run-real` en 1.01–1.03.

## Límites

- Toca solo los archivos de «Puedes tocar» y tu fila del índice. No añadas scripts/infra ni cambies `tap.py`.
- Las tareas 1.01–1.03 no leen/copían `data/`, panel, cuerpos, JSONL, credenciales, CA, binarios, variables secretas o prompts. No usan 8899/8900 en tests. La reserva 1.04 queda bloqueada; una futura tarea operativa del usuario/orquestador podrá tratar los artefactos solo según su receta auditada, fuera de este plan.
- No persistir IDs, hashes ni contenido crudo. Los símbolos se usan solo como diagnóstico; no alteran atribución ni proyección.
- Preserva validación estricta. `run_real` y su ciclo operativo no se modifican, excepto propagar/publicar el diagnóstico allowlisted de usage.
- No modificar precios, coste, `cost_missing`, `approved=false`, proveedores, UI, golden, planes previos o los ficheros protegidos del checkout.
- La tarea 1.04 queda bloqueada: no escribir una receta real ni leer la ruta privada de harness. El usuario/orquestador decide y ejecuta después de auditarla.
- No `git add`, `commit`, `push` ni `stash`.

## Al cerrar

Ejecuta solo las verificaciones relevantes de la ficha. Si un test muestra que una decisión cambia o un límite no se sostiene, bloquea y para; no amplíes alcance. La salida real de este plan puede seguir pendiente/insuficiente.
