# Reglas para ejecutar una tarea

Lee este fichero, la fila de tu tarea en el índice y tu fichero de tarea. Las decisiones de cada tarea están dentro de ella; no necesitas leer las demás.

## Rutas y comandos

- RAÍZ = carpeta del repositorio. Todas las rutas parten de RAÍZ; ejecuta los comandos con RAÍZ como directorio de trabajo.
- TESTS = `venv/bin/python -m unittest discover -s tests -t . -q`.
- UI = `node tests/ui/check.mjs --full`. Usa Chrome instalado, Node con WebSocket global y los puertos de prueba 8901 y 9334; admite `CHROME_BIN`, `TAP_UI_PORT` y `TAP_DEBUG_PORT`.
- JS = `node --test tests/ui/unit/*.test.mjs`, disponible después de 1.01. Node 24 detecta los módulos ES; puede emitir MODULE_TYPELESS_PACKAGE_JSON sin fallar. No cambies un package.json ajeno al proyecto para silenciarlo.
- LINT = `venv/bin/python -m ruff check tap.py cachetap`, disponible después de 5.01.
- FORMAT = `venv/bin/python -m ruff format --check tap.py cachetap`, disponible después de 5.01.
- TYPES = `venv/bin/python -m mypy`, disponible después de 4.01.
- Cada tarea ejecuta TESTS y su comprobación específica. Ejecuta UI en las tareas que cambien interfaz o protocolo SSE. No uses tiempos exactos de ejecución como criterio de éxito.

## Antes de empezar

1. Comprueba `git status --short`; respeta los cambios existentes.
2. Consulta solo tu fila en `README.md`: todas las dependencias deben estar terminadas.
3. Marca la fila `en curso` y ejecuta TESTS. Si el estado de partida falla, marca `bloqueada` y comunica el fallo.

## Mientras trabajas

- Toca solo la lista cerrada de tu tarea y tu fila del índice. Crear un test indicado en una tarea forma parte de esa tarea.
- Importa módulos internos con prefijo. Los imports de tipos también usan el módulo; actualiza la tabla de dependencias cuando la tarea lo indique.
- Funciones puras para transformaciones; los nombres de las operaciones con efectos describen la modificación. No introduzcas clases, capas, frameworks ni dependencias de runtime para cumplir reglas de estilo.
- Python compatible con 3.12; documentación y notas del panel en español, identificadores y docstrings del código en inglés.
- Los tests usan cuerpos sintéticos, logs temporales y puertos efímeros. Nunca escriben en `data/requests.jsonl`, ni usan 8899/8900, ni acceden a `ca/`.
- Las pruebas de concurrencia usan barreras/eventos y deadlines; no dependen de un `sleep` para ordenar operaciones.
- `golden.json` permanece idéntico: las nuevas condiciones se prueban con casos independientes. Si una tarea descubre que necesita cambiar el golden, se bloquea y solicita revisar el plan.
- No añadas campos con valor por defecto a todos los registros: los nuevos indicadores de captura aparecen solo cuando corresponden.
- Al modificar `cachetap/`, termina con `touch tap.py` para permitir la recarga del addon. Es una operación de fecha, no un cambio de contenido fuera de alcance.
- No hagas `git add`, `git commit`, `git stash` ni instales hooks. No cambies configuraciones globales.

## Si algo no cuadra

Si un paso no se puede cumplir tal como está escrito, o la comprobación falla dos veces por el mismo motivo, marca `bloqueada`, registra el motivo y para. No silencies diagnósticos ni cambies los resultados esperados para conseguir verde.

## Al terminar

1. Ejecuta las comprobaciones y revisa `git diff --check` y el diff de tus ficheros.
2. Marca `terminada sin commit`; informa de resultados y desviaciones.
3. `terminada con commit` solo lo marca quien haga un commit solicitado por el usuario.
