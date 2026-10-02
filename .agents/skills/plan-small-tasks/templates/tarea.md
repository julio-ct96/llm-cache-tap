# <ID> <Título>

**Objetivo:** <una frase: qué queda distinto al terminar>.

**Contexto:** <solo si hace falta: el porqué que evita un error previsible. Si no, quita esta línea>.

**Lee:** <ficheros y, dentro de ellos, las funciones o secciones concretas>.

**Puedes tocar:** <lista cerrada de ficheros; marca los nuevos con «(nuevo)»>.

## Pasos

1. <acción imperativa y cerrada>

2. <para mover código, una tabla>

   | En `<origen>` | En `<destino>` | Cambio |
   | --- | --- | --- |
   | `<nombre>` | `<nombre nuevo>` | sin cambio / <el único cambio permitido> |

3. <para sustituir usos, una tabla con todos los sitios>

   | Dónde | Antes | Después |
   | --- | --- | --- |
   | `<función>` | `<expresión>` | `<expresión>` |

   **No** se sustituyen: <apariciones que lo parecen y no lo son>.

4. <para tests, una tabla de casos con valores comprobados>

   | Test | Entrada | Resultado esperado |
   | --- | --- | --- |
   | <nombre> | `<entrada>` | `<valor>` |

## Verificación

- TESTS acaba bien.
- `<comando>` muestra `<salida esperada>`.
- `<comando que prueba que lo movido ya no está en el origen>` no muestra nada.
- <invariante del plan que aplique>
