# Reglas para ejecutar una tarea

Lee este fichero y el de tu tarea. No leas otras tareas ni el resto del plan.

## Rutas y comandos

- RAÍZ = `/Users/joub/development/llm-cache-tap`. Toda ruta relativa de una tarea parte de RAÍZ.
- En los comandos usa siempre rutas absolutas. No uses `cd`.
- PY = `RAÍZ/venv/bin/python`
- TESTS (toda la batería): `PY -m unittest discover -s RAÍZ/tests -t RAÍZ -q`
- Un solo fichero de test: añade `-p 'test_nombre.py'` a TESTS.
- PROXY (solo lectura): `curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8900/`

## Antes de empezar

1. Abre `README.md` de esta carpeta y busca la fila de tu tarea.
2. Si alguna tarea de su columna «Depende de» no está en `terminada sin commit` o `terminada con commit`, no empieces: avisa y para.
3. Cambia el estado de tu fila a `en curso`.
4. Ejecuta PROXY y anota el resultado (`200` = el proxy real está en marcha).
5. Si existe `RAÍZ/tests/replay/golden.json`, anota su `shasum`.

## Mientras trabajas

- Toca solo los ficheros de la sección «Puedes tocar» de tu tarea, más tu fila del `README.md`.
- **Mover** significa cortar y pegar. No cambies lógica, textos, orden de claves ni nombres, salvo los cambios que la tarea enumere.
  Los comentarios y docstrings viajan con el código que acompañan.
- No arregles fallos ni mejores nada que la tarea no pida. Si ves un fallo, anótalo en la columna «Notas» de tu fila.
- Los módulos de `cachetap` se importan como módulo y se usan con prefijo: `from cachetap import segments` y luego `segments.dump(...)`.
  Nunca `from cachetap.segments import dump`. Así `config.LOG` y `config.MAX` se pueden sustituir en los tests.
- Todos los `import` van al principio del fichero.
- Comentarios y nombres en inglés. Textos que ve el usuario en castellano.
- Sin dependencias nuevas: solo la librería estándar de Python y `unittest`. No instales nada.
- No toques `data/`, `ca/`, `venv/` ni `.plans/` (salvo tu fila).
- Ningún test puede escribir en `data/requests.jsonl` ni escuchar en los puertos 8899 u 8900.
  Todo test que use los hooks llama antes a `adapter.reset(...)` con una ruta temporal.
- `tests/replay/golden.json` solo se genera en la tarea 1.07. Fuera de ella no uses `TAP_UPDATE_GOLDEN`.
- No hagas `git commit`, `git add` ni `git stash`.

## Si algo no cuadra

Si un paso no se puede cumplir tal como está escrito, o la verificación falla dos veces seguidas, **para**.
Pon el estado `bloqueada`, escribe el motivo en «Notas» y explica qué has visto. No improvises una solución alternativa.

## Al terminar

1. TESTS debe acabar en `OK`. Si falla en un fichero que no es de tu tarea y hay otra tarea `en curso` en el `README.md`, espera un minuto y repite una vez.
2. Salvo en la tarea 1.07, el `shasum` de `golden.json` debe ser el mismo que al empezar.
3. Si PROXY daba `200` al empezar y tu tarea ha tocado `tap.py`: espera 3 segundos y ejecuta PROXY. Debe dar `200`.
   Si no lo da, ejecuta `touch RAÍZ/tap.py`, espera 3 segundos y repite una sola vez.
4. Cambia el estado de tu fila a `terminada sin commit`.
5. Informa en pocas líneas: ficheros creados o modificados con su número de líneas, y cualquier desviación.

El estado `terminada con commit` lo pone quien haga el commit, y solo por orden del usuario.
