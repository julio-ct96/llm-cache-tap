# <Nombre del plan>: índice

Objetivo: <una o dos frases: qué cambia y qué no cambia>.

## Cómo se ejecuta

- Una tarea = un agente. Cada agente lee `reglas.md` y el fichero de su tarea, nada más.
- Una tarea se puede lanzar cuando todas las de «Depende de» están terminadas. Las que cumplen eso a la vez se pueden lanzar en paralelo.
- Estados: `pendiente` · `en curso` · `terminada sin commit` · `terminada con commit` · `bloqueada`.
- Al cerrar cada fase se para y se espera la confirmación del usuario.

## Tareas

| ID | Tarea | Fichero | Depende de | Estado | Notas |
| --- | --- | --- | --- | --- | --- |
| 1.01 | <título corto> | `fase-1/1.01-<slug>.md` | — | pendiente | |
| 1.02 | <título corto> | `fase-1/1.02-<slug>.md` | 1.01 | pendiente | |

## Qué se puede lanzar a la vez

- <tareas sin dependencias entre sí y sin ficheros compartidos>
- <qué fases son una cadena y por qué>

## Estructura final

```
<árbol de ficheros de destino, con una línea de descripción por fichero>
```

## Decisiones ya tomadas

- <nombres, herramientas y alternativas descartadas, con el motivo en una frase>
- Fallos conocidos que **no** se arreglan en este plan: <lista>
