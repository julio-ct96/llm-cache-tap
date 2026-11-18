# Reglas para ejecutar una tarea

Lee este fichero y el de tu tarea. No leas otras tareas ni el resto del plan.

## Rutas y comandos

- RAÍZ = la carpeta del repositorio (la que contiene `tap.py`). Toda ruta relativa de una tarea parte de RAÍZ.
- Lanza los comandos con RAÍZ como directorio de trabajo, cada uno por separado (sin `&&`).
- TESTS (toda la batería Python): `venv/bin/python -m unittest discover -s tests -t . -q`
- CHECK (Ruff, formato, mypy y tests): `venv/bin/python scripts/check.py`
- FULL (CHECK más Chrome): `venv/bin/python scripts/check.py --full`. No lo lances si otra tarea está `en curso`.
- FORMATO de un fichero: `venv/bin/ruff format <fichero>`
- HUELLA: `venv/bin/python .plans/precios-por-familia/huella.py`. Imprime una línea por tarifa con «nombre, número de modelos, huella del contenido» y una última con las filas de la ayuda. La huella no depende del orden ni de cómo se construye cada tabla: solo de los nombres y los precios.
- GOLDEN-NUEVO: `TAP_UPDATE_GOLDEN=1 venv/bin/python -m unittest tests.test_replay -q` (solo si tu tarea lo pide).
- GOLDEN-DIFF: `venv/bin/python .plans/precios-por-familia/golden_diff.py`. Lista los registros del golden que difieren del último commit.

## Antes de empezar

1. Abre `README.md` de esta carpeta y busca la fila de tu tarea.
2. Si alguna tarea de su columna «Depende de» no está terminada, no empieces: avisa y para.
3. Cambia el estado de tu fila a `en curso`.
4. Ejecuta HUELLA y comprueba que coincide con la línea «Antes» de tu tarea.

## Mientras trabajas

- Toca solo los ficheros de «Puedes tocar» de tu tarea, más tu fila del `README.md`.
- No cambies ningún precio, nombre de modelo ni texto que la tarea no enumere. Los números de cada tabla de la tarea se copian tal cual.
- Los módulos de `cachetap` se importan como módulo y se usan con prefijo (`base.Price`), como ya hace el código.
- Los comentarios del código van en inglés, como los existentes. Los textos visibles para el usuario van en español.
- No uses los puertos 8899 ni 8900 ni escribas en `data/`.
- No hagas `git commit`, `git add` ni `git stash`.

## Si algo no cuadra

Si un paso no se puede cumplir tal como está escrito, o una verificación falla dos veces seguidas, **para**.
Pon el estado `bloqueada`, escribe el motivo en «Notas» y explica qué has visto. No improvises una solución alternativa.

## Al terminar

1. CHECK debe acabar con `all checks passed`. Si falla en un fichero que no es de tu tarea y hay otra tarea `en curso`, espera un minuto y repite una vez. Si falla por formato en un fichero tuyo, aplica FORMATO a ese fichero y repite.
2. HUELLA debe coincidir con la línea «Después» de tu tarea.
3. Cambia el estado de tu fila a `terminada sin commit`.
4. Informa en pocas líneas: ficheros modificados, salida de HUELLA y de cada verificación, y cualquier desviación.

El estado `terminada con commit` lo pone quien haga el commit.
