# Escribir un plan

El plan se escribe una vez y se lee muchas, casi siempre por un modelo que no puede preguntar. El esfuerzo va aquí.

## Proceso

1. **Lee el código que se va a tocar, entero.** No planifiques desde una descripción ni desde un resumen.
2. **Fija el destino.** Estructura final de ficheros, qué contiene cada uno y quién puede depender de quién. Las decisiones de nombres se toman ahora.
3. **Diseña la red de seguridad.** Qué tests fijan el comportamiento actual. Si no existen, las primeras tareas del plan los crean. Sin esto no se toca código existente.
4. **Corta en tareas.** Una tarea es un paso que deja el proyecto funcionando. Si dos tareas editan el mismo fichero, van en cadena.
5. **Comprueba cada hecho.** Ejecuta contra el código real todo lo que vayas a afirmar: resultados esperados, recuentos, patrones de búsqueda, comandos de verificación.
6. **Escribe los ficheros** con las plantillas de `templates/`: primero `reglas.md`, después las tareas, al final el índice.
7. **Cruza índice y ficheros.** Toda tarea del índice tiene fichero y al revés; toda dependencia nombrada existe.

## Cómo cortar las tareas

- **Tamaño:** una tarea tiene un solo objetivo y una sola verificación, y cabe en una sesión corta de un modelo pequeño. Pártela cuando tenga dos objetivos
  o cuando una mitad se pueda comprobar sin la otra, no por lo que ocupe su fichero: una tabla larga de casos no la hace grande.
- **Mover es cortar y pegar.** Una tarea de extracción nombra cada función que se mueve, su nombre nuevo y cada sitio de llamada que cambia. Los cambios de lógica, si los hay, se enumeran aparte y son los únicos permitidos.
- **Cambios mecánicos masivos:** lista todas las apariciones por función o bloque, di cuáles **no** se tocan aunque lo parezcan, y da recuentos que el ejecutor pueda comprobar.
- **Independencia real:** dos tareas son paralelas solo si no comparten ningún fichero. Un índice o un fichero de registro compartido no cuenta si cada una edita solo su línea.
- **Orden:** la red de seguridad primero; después de dentro afuera (lo que no depende de nada antes que lo que lo usa); el cableado y la documentación al final.
- **Tareas que necesitan al usuario** (credenciales, reiniciar algo suyo, gastar cuota): van aparte, marcadas, y nunca bloquean a las demás.

## Qué lleva cada tarea

Objetivo en una línea, qué leer, qué ficheros puede tocar, pasos numerados y verificación. Ver `templates/tarea.md`.

- **«Lee»** nombra funciones o secciones concretas, no «el módulo X». Menos lectura es menos coste y menos distracción.
- **«Puedes tocar»** es una lista cerrada. Marca cuáles son nuevos.
- **Los pasos** son imperativos y cerrados. Donde haya una elección, tómala tú y escribe el resultado.
- **Los tests** se especifican como tabla de entrada y resultado esperado, con valores que has obtenido ejecutando el código.
- **La verificación** son comandos con su salida esperada, incluidos los que prueban que algo ya **no** está donde estaba.

## Trampas conocidas

Revisa el plan contra esta lista antes de darlo por terminado. Todas han ocurrido.

| Trampa | Cómo evitarla |
| --- | --- |
| Al quitar un prefijo o renombrar, un parámetro o variable local pasa a tapar a una función del mismo nombre | busca cada nombre nuevo como parámetro y como variable local en el código que se mueve |
| Una variable local se llama igual que algo que se va a importar; si se declara más abajo en la misma función, falla en ejecución | busca el nombre en todo el fichero antes de introducirlo; añade el renombrado como paso previo |
| Dos módulos nuevos se importan entre sí | dibuja quién importa a quién; lo compartido va a un tercer fichero |
| Un patrón de búsqueda de la verificación casa con algo legítimo (`^function render` casa con `renderDetail`) | ejecuta cada patrón sobre el código y sobre el resultado esperado |
| Un test de apoyo pasa hoy solo porque nadie usa todavía el caso que falla | prueba el test también contra el estado final previsto, no solo contra el actual |
| Un límite arbitrario (número máximo de líneas) obliga a degradar el resultado | pon límites solo donde protegen algo, y con margen |
| Una comprobación depende de algo asíncrono (fuentes, red, tiempos) y da falsos positivos | espera explícitamente al evento antes de medir; repite la medición dos veces para ver que es estable |
| La verificación exige herramientas que el ejecutor puede no tener (navegador, MCP) | sustitúyela por un script de un solo comando antes de empezar |
| Un módulo se llama igual que una función o un punto de entrada existente | comprueba los nombres nuevos contra los ya usados en el fichero que los importa |
| Rutas absolutas de tu máquina en ficheros que se publican | usa una variable (`RAÍZ`) definida en `reglas.md` |

## Antes de entregar

- [ ] Cada tarea se entiende sin leer ninguna otra.
- [ ] No hay código de ejemplo; hay tablas.
- [ ] Todos los valores esperados salen de una ejecución real.
- [ ] Cada tarea deja los tests en verde y dice cómo comprobarlo.
- [ ] El índice dice de qué depende cada tarea y qué puede ir en paralelo.
- [ ] Las decisiones ya tomadas y los fallos conocidos que no se arreglan están escritos en el índice.
