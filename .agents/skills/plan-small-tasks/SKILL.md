---
name: plan-small-tasks
description: "Writes and executes implementation plans as small, verifiable, independent task files with an index of dependencies and status, so that a less capable model can carry them out without interpreting anything. Use when the user says 'crea un plan', 'plan por tareas', 'plan para un modelo menos capaz', 'ejecuta el plan', 'sigue con el plan', 'lanza la fase', or asks to refactor or build something progressively with subagents."
---

# Planes por tareas pequeñas

Un plan de este tipo lo escribe un modelo capaz y lo ejecuta, tarea a tarea, un modelo menos capaz que **solo lee las reglas y el fichero de su tarea**.
Todo lo que el ejecutor tendría que deducir es un fallo del plan.

## Cuándo usarla

- Trabajo que no cabe en una sesión o que conviene repartir: refactorizaciones, migraciones, funcionalidades de varias piezas.
- El usuario pide progresividad, subagentes, o poder parar y retomar.

No la uses para un cambio que se resuelve en unas pocas ediciones: hazlo directamente.

## Principios

1. **Nada que interpretar.** Cada tarea dice qué leer, qué ficheros puede tocar, qué pasos dar y cómo comprobarlo. Las decisiones se toman al escribir el plan, no al ejecutarlo.
2. **Sin código de ejemplo.** Se describe con tablas: qué se mueve, a dónde, con qué nombre; qué entrada da qué resultado. El código de ejemplo se copia mal y envejece.
3. **Tareas pequeñas, verificables e independientes.** Un fichero por tarea, entre 20 y 100 líneas. Cada una deja el proyecto funcionando y con los tests en verde.
4. **Primero la red de seguridad.** Antes de tocar código existente, tests que fijen su comportamiento actual. Después, cada tarea se juzga contra ellos.
5. **Hechos comprobados, no supuestos.** Todo número, nombre, recuento o resultado esperado que aparezca en el plan se ha verificado contra el código real antes de escribirlo.
6. **Verificación con un comando.** Cada comprobación es un comando con su salida esperada. Lo que exija mirar a ojo o usar herramientas interactivas se automatiza antes.
7. **Parar antes que improvisar.** Si un paso no se puede cumplir tal cual, el ejecutor marca `bloqueada`, explica qué vio y se detiene.
8. **Contexto mínimo.** El ejecutor no lee el plan entero ni otras tareas. Lo común vive en un único fichero de reglas, corto.

## Estructura de un plan

```
.plans/<nombre-del-plan>/
  README.md          índice: una fila por tarea con dependencias y estado
  reglas.md          lo único común que lee todo ejecutor
  fase-1/1.01-<slug>.md
  fase-1/1.02-<slug>.md
  fase-2/...
```

Estados de una tarea: `pendiente` · `en curso` · `terminada sin commit` · `terminada con commit` · `bloqueada`.

## Qué leer según lo que te pidan

| Te piden | Lee |
| --- | --- |
| escribir un plan | `WRITING.md` y las plantillas de `templates/` |
| ejecutar un plan, una fase o una tarea con subagentes | `EXECUTING.md` |
| ejecutar tú mismo una tarea concreta | solo `reglas.md` del plan y el fichero de esa tarea |

Las rutas son relativas a la carpeta de esta skill.
