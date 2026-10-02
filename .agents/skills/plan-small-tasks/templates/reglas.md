# Reglas para ejecutar una tarea

Lee este fichero y el de tu tarea. No leas otras tareas ni el resto del plan.

## Rutas y comandos

- RAÍZ = la carpeta del repositorio. Toda ruta relativa de una tarea parte de RAÍZ.
- En los comandos usa rutas absolutas. <restricciones del entorno, por ejemplo «no uses `cd`»>
- TESTS (toda la batería): `<comando>`
- Un solo fichero de test: `<comando>`
- <otros comandos con nombre que las tareas vayan a citar>

## Antes de empezar

1. Abre `README.md` de esta carpeta y busca la fila de tu tarea.
2. Si alguna tarea de su columna «Depende de» no está terminada, no empieces: avisa y para.
3. Cambia el estado de tu fila a `en curso`.
4. <anota el estado inicial de lo que vayas a comprobar al final>

## Mientras trabajas

- Toca solo los ficheros de la sección «Puedes tocar» de tu tarea, más tu fila del `README.md`.
- **Mover** significa cortar y pegar. No cambies lógica, textos ni nombres, salvo los cambios que la tarea enumere.
- No arregles fallos ni mejores nada que la tarea no pida. Si ves un fallo, anótalo en la columna «Notas» de tu fila.
- <convenciones del proyecto que afecten a todas las tareas: imports, idioma, dependencias permitidas>
- <recursos que ningún test o tarea puede tocar: datos reales, puertos en uso, secretos>
- No hagas `git commit`, `git add` ni `git stash`.

## Si algo no cuadra

Si un paso no se puede cumplir tal como está escrito, o la verificación falla dos veces seguidas, **para**.
Pon el estado `bloqueada`, escribe el motivo en «Notas» y explica qué has visto. No improvises una solución alternativa.

## Al terminar

1. TESTS debe acabar bien. Si falla en un fichero que no es de tu tarea y hay otra tarea `en curso`, espera un minuto y repite una vez.
2. <invariantes del plan: lo que no debe haber cambiado>
3. Cambia el estado de tu fila a `terminada sin commit`.
4. Informa en pocas líneas: ficheros creados o modificados, y cualquier desviación.

El estado `terminada con commit` lo pone quien haga el commit.
