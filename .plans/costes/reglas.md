# Reglas para ejecutar una tarea

Lee este fichero, la fila de tu tarea en el índice y tu fichero de tarea. Si tu tarea cita `precios.md`, lee solo la sección que cite. No leas otras tareas.

## Rutas y comandos

- RAÍZ = carpeta del repositorio. Todas las rutas parten de RAÍZ; ejecuta los comandos con RAÍZ como directorio de trabajo.
- TESTS = `venv/bin/python -m unittest discover -s tests -t . -q`.
- UNO = `venv/bin/python -m unittest tests.<módulo> -q` para un solo fichero de test.
- JS = `node --test tests/ui/unit/*.test.mjs`. Node 24 puede emitir MODULE_TYPELESS_PACKAGE_JSON sin fallar; no lo silencies.
- UI = `node tests/ui/check.mjs --full`. Usa Chrome instalado y los puertos de prueba 8901 y 9334.
- TODO = `venv/bin/python scripts/check.py`: Ruff, formato, mypy, TESTS y JS. Con `--full` añade UI.
- HUELLA = `shasum -a 256 tests/replay/golden.json`.

## Antes de empezar

1. Comprueba `git status --short`; respeta los cambios existentes.
2. Consulta solo tu fila en `README.md`: todas las dependencias deben estar terminadas.
3. Marca la fila `en curso` y ejecuta TESTS. Si el estado de partida falla, marca `bloqueada` y comunica el fallo.

## Mientras trabajas

- Toca solo la lista cerrada de tu tarea y tu fila del índice.
- Los precios viven en `cachetap/prices/`; `cachetap/providers/` no sabe de precios. No mezcles los dos paquetes.
- Importa los módulos de `cachetap` como módulo y úsalos con prefijo. Un módulo nuevo se añade a la tabla de `tests/test_dependencies.py` y a `files` de mypy en `pyproject.toml`.
- Los precios son dólares de EE. UU. por millón de tokens. Ningún precio se inventa ni se estima: si un modelo no está en `precios.md`, no se añade.
- Los importes calculados se redondean a 8 decimales.
- Un campo nuevo del registro aparece solo cuando corresponde; no añadas valores por defecto a todos los registros.
- Las funciones de estado de `store` se llaman con `store.LOCK` adquirido por el llamador; dentro del lock no hay I/O ni logging.
- En la interfaz no interpoles datos externos como HTML sin `esc`; usa `textContent` para texto.
- Documentación y textos del panel en español; identificadores y docstrings del código en inglés.
- Los tests usan casos sintéticos. Nunca escriben en `data/requests.jsonl`, ni usan los puertos 8899 y 8900, ni lanzan `opencode` ni ningún cliente real.
- `tests/replay/golden.json` solo lo regenera la tarea 2.04 con `TAP_UPDATE_GOLDEN=1`. En las demás tareas HUELLA no cambia.
- Al modificar `cachetap/`, termina con `touch tap.py`.
- No hagas `git add`, `git commit` ni `git stash`.

## Si algo no cuadra

Si un paso no se puede cumplir tal como está escrito, o la comprobación falla dos veces por el mismo motivo, marca `bloqueada`, escribe el motivo en «Notas» y para. No cambies un resultado esperado para conseguir verde.

## Al terminar

1. TESTS acaba bien, y también JS y UI si tu tarea toca `ui/` o el protocolo de eventos.
2. HUELLA no ha cambiado, salvo en la tarea 2.04.
3. Cambia el estado de tu fila a `terminada sin commit`.
4. Informa en pocas líneas: ficheros creados o modificados, resultado de cada comprobación y desviaciones.

El estado `terminada con commit` lo pone quien haga el commit.
