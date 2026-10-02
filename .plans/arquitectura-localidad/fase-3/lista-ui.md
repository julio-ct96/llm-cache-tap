# Lista de comprobación de la interfaz

La usan las tareas de la fase 3 y la 4.02. Está automatizada: no hace falta abrir un navegador ni usar herramientas MCP.

## Cómo se ejecuta

| Lista | Comando | Comprueba |
| --- | --- | --- |
| corta | `node RAÍZ/tests/ui/check.mjs` | C1 a C6 y C15 |
| completa | `node RAÍZ/tests/ui/check.mjs --full` | todas |

El script arranca él solo el panel de prueba (`tests/replay/serve.py`, puerto 8901) y un Chrome sin ventana, ejecuta las comprobaciones,
lo cierra todo y escribe una línea por comprobación (`ok` o `FAIL`). Tarda unos 10 segundos.

- **Pasa** cuando la última línea es `all checks passed (...)` y el código de salida es 0.
- Si una tarea pide la lista corta «y además» algún punto de la completa, ejecuta la completa.
- No arranques `serve.py` por tu cuenta antes: si el puerto 8901 está ocupado, el script falla con `port 8901 is already in use`.
- Si falla con `FAIL setup`, el problema es del entorno (Chrome o puertos), no de tu tarea: pon la tarea en `bloqueada` con el mensaje y para.
- Si falla una comprobación, la línea `FAIL C1` suele traer la causa (por ejemplo `ReferenceError: esc is not defined`).

No modifiques `tests/ui/check.mjs` salvo que tu tarea lo diga.

## Qué comprueba cada punto

| N.º | Acción | Resultado esperado |
| --- | --- | --- |
| C1 | toda la sesión | la consola no tiene errores ni excepciones, y ninguna petición de red ha devuelto 400 o más |
| C2 | cargar la página | hay 44 filas en `#rows`; `#conn-text` dice `en vivo` |
| C3 | — | cabecera: `#s-n` = `44`, `#s-hit` = `9`, `#s-miss` = `9`, `#s-srv` = `2`, `#s-eff` = `2 / 3`, `#s-rate` = `33.6 %` |
| C4 | clic en la fila 6 | `#detail` se muestra y contiene `#6`, `MISS`, `Primer cambio del prefijo` y `system @ 40` |
| C5 | `Escape`, después `ArrowDown` | el detalle se oculta; después se muestra con `#44` |
| C6 | `Escape`; clic en `#f-bad` dos veces | 10 filas; después 44 |
| C15 | esperar 2 segundos | el texto de un temporizador de caché vivo cambia |
| C7 | clic en `#f-eff` dos veces | 3 filas; después 44 |
| C8 | elegir `gpt-5.6` en `#f-model`; después la opción vacía | 5 filas; después 44 |
| C9 | escribir `c13` en `#f-text`; después `zzz`; después clic en `#reset` | 3 filas; 0 filas y `#no-match` visible; 44 filas y el campo vacío |
| C10 | pulsar `/` sin foco en ningún campo | el foco pasa a `#f-text` |
| C11 | clic en la fila 1 y abrir «Cuerpo de la petición» | aparece el árbol JSON con la palabra `model` |
| C13 | con el detalle abierto | `#resizer` es visible |
| C12 | clic en `#help-open` | el diálogo se abre con 3 tablas de 5, 5 y 4 filas (5, 5 y 5 cuando exista `#help-min`, tras la tarea 4.02) |
| C16 | esperar a las fuentes | al menos una fuente incluida en el proyecto queda cargada |
| C14 | clic en `#clear` dos veces | 0 filas y `#empty` visible |
