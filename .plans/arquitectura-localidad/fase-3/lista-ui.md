# Lista de comprobación de la interfaz

La usan las tareas de la fase 3 y la 4.02. Cada tarea dice si aplica la **lista corta** (C1 a C6) o la **completa** (C1 a C14).

## Preparación

1. Arranca en segundo plano `PY RAÍZ/tests/replay/serve.py`. Sirve el panel en `http://127.0.0.1:8901` con 44 peticiones de prueba.
2. Abre esa dirección con las herramientas de navegador que tengas (por ejemplo las de `chrome-devtools`: abrir página, evaluar script, leer consola, hacer clic, pulsar tecla).
   Si no tienes ninguna herramienta de navegador, pon tu tarea en `bloqueada` con la nota `falta verificación en navegador` y para.
3. Al terminar, detén el proceso de `serve.py`.

Si has cambiado ficheros después de abrir la página, recárgala antes de comprobar.

## Lista corta

| N.º | Acción | Resultado esperado |
| --- | --- | --- |
| C1 | cargar la página | la consola no tiene errores ni excepciones, y ninguna petición de red ha devuelto 404 |
| C2 | — | hay 44 elementos `#rows tr`; el texto de `#conn-text` es `en vivo` |
| C3 | — | textos de la cabecera: `#s-n` = `44`, `#s-hit` = `9`, `#s-miss` = `9`, `#s-srv` = `2`, `#s-eff` = `2 / 3`, `#s-rate` = `33.6 %` |
| C4 | clic en la fila `#rows tr[data-id="6"]` | `#detail` deja de estar oculto y su texto contiene `#6`, `MISS`, `Primer cambio del prefijo` y `system @ 40` |
| C5 | pulsar `Escape`; después pulsar `ArrowDown` | tras `Escape`, `#detail` está oculto; tras `ArrowDown`, `#detail` es visible y su texto contiene `#44` |
| C6 | pulsar `Escape`; clic en `#f-bad`; clic otra vez en `#f-bad` | tras el primer clic hay 10 filas; tras el segundo, 44 |

## Lista completa (además de la corta)

| N.º | Acción | Resultado esperado |
| --- | --- | --- |
| C7 | clic en `#f-eff`; clic otra vez | 3 filas; después 44 |
| C8 | elegir `gpt-5.6` en `#f-model`; después elegir la opción vacía | 5 filas; después 44 |
| C9 | escribir `c13` en `#f-text`; después sustituirlo por `zzz`; después clic en `#reset` | 3 filas; después 0 filas y `#no-match` visible; después 44 filas y `#f-text` vacío |
| C10 | con el foco fuera de cualquier campo, pulsar `/` | el foco pasa a `#f-text` |
| C11 | clic en la fila de `data-id="1"`; clic en el título de la sección «Cuerpo de la petición» | dentro de `#detail` aparece un árbol JSON (`[data-tree="body"]` deja de decir `cargando…` y contiene la palabra `model`) |
| C12 | clic en `#help-open` | el diálogo `#help` está abierto y contiene 3 tablas; la de TTL tiene 5 filas de datos y la de mínimo cacheable tiene 4 (5 a partir de la tarea 4.02) |
| C13 | cerrar la ayuda; con el detalle abierto | `#resizer` es visible |
| C14 | clic en `#clear` dos veces seguidas | 0 filas y `#empty` visible. Es la última comprobación: para repetir la lista hay que reiniciar `serve.py` |
