# Costes: índice de implementación

Objetivo: cada petición nueva muestra lo que costó, lo que ahorró la caché y lo que perdió por un fallo de caché, con totales por conversación, por modelo y por causa. No cambian los veredictos, las notas ni el emparejado de peticiones.

## Cómo se escribió este plan

El plan se escribió el 6 de octubre de 2026 **después** de implementar el código, a petición del usuario, para reconducir el trabajo a la skill `plan-small-tasks`. Las tareas 1.01 a 4.01 describen lo ya hecho y ningún ejecutor las ha recorrido desde cero, así que su redacción no está validada por una ejecución. Tras una primera versión con los precios dentro de `cachetap/providers/`, se movieron a `cachetap/prices/` y el desglose del detalle a `ui/detail-cost.js` para respetar la localidad que pide `AGENTS.md`; el plan describe ese estado final. Los valores esperados sí salen de ejecuciones reales sobre el código final.

## Punto de partida y estado comprobado

- Partida: commit `7445963`, árbol limpio, 229 tests Python y 11 tests JS.
- Estado final: `venv/bin/python scripts/check.py --full` acaba con `all checks passed`: Ruff, formato, mypy (20 fuentes), 295 tests Python, 20 tests JS y 34 comprobaciones en Chrome.
- `tests/replay/golden.json` regenerado en 2.04: quitando las claves `cost`, `cost_missing`, `miss_causes` y `convs`, es idéntico al de partida. Su SHA-256 empieza por `c48e2cd230af19dc`.
- No se ha probado con tráfico real ni se ha lanzado `opencode`.

## Cómo se ejecuta

- Una tarea = un agente. Cada agente lee `reglas.md`, su tarea y la sección de `precios.md` que cite, nada más.
- Una tarea se puede lanzar cuando todas las de «Depende de» están terminadas.
- `venv/bin/python .plans/costes/check_plan.py` comprueba índice, ficheros, dependencias y secciones.
- Estados: `pendiente` · `en curso` · `terminada sin commit` · `terminada con commit` · `bloqueada`.
- Al cerrar cada fase se para y se espera la confirmación del usuario.

## Tareas

| ID | Tarea | Fichero | Depende de | Estado | Notas |
| --- | --- | --- | --- | --- | --- |
| 1.01 | Forma del precio y nombre canónico | [1.01](fase-1/1.01-precio-y-nombre.md) | — | terminada con commit | 5dd29c5; 7 tests |
| 1.02 | Precios de lista de Anthropic | [1.02](fase-1/1.02-precios-anthropic.md) | 1.01 | terminada con commit | 5dd29c5; 4 tests |
| 1.03 | Precios de lista de OpenAI | [1.03](fase-1/1.03-precios-openai.md) | 1.02 | terminada con commit | 5dd29c5; 4 tests |
| 1.04 | Tarifa de Copilot | [1.04](fase-1/1.04-tarifa-copilot.md) | 1.03 | terminada con commit | 5dd29c5; 8 tests |
| 1.05 | Elección de tarifa y referencia de precios | [1.05](fase-1/1.05-eleccion-de-tarifa.md) | 1.04 | terminada con commit | 5dd29c5; 9 tests; 60 filas de precios |
| 1.06 | Lectura de lo escrito en caché | [1.06](fase-1/1.06-lectura-de-lo-escrito.md) | — | terminada con commit | 70a5a9f; 29 y 30 tests; supuesto sobre `cache_write_tokens` pendiente de 4.02 |
| 2.01 | Causas del fallo en el veredicto | [2.01](fase-2/2.01-causas-del-fallo.md) | — | terminada con commit | f3c1ddc; 15 tests |
| 2.02 | Contrato y cálculo del coste | [2.02](fase-2/2.02-calculo-del-coste.md) | 1.05, 2.01 | terminada con commit | f3c1ddc; 23 tests |
| 2.03 | Acumulado por conversación | [2.03](fase-2/2.03-acumulado-por-conversacion.md) | 2.02 | terminada con commit | f3c1ddc; 21 y 16 tests |
| 2.04 | Cableado en el addon y golden | [2.04](fase-2/2.04-cableado-y-golden.md) | 2.03, 1.06 | terminada con commit | f3c1ddc; 295 tests; golden revisado: solo claves nuevas |
| 3.01 | Formato y estado de conversaciones | [3.01](fase-3/3.01-formato-y-estado.md) | 2.04 | terminada con commit | b0466a8 |
| 3.02 | Columnas, totales, filtro y orden | [3.02](fase-3/3.02-columnas-filtro-y-orden.md) | 3.01 | terminada con commit | b0466a8 |
| 3.03 | Desglose en el detalle | [3.03](fase-3/3.03-desglose-en-el-detalle.md) | 3.02 | terminada con commit | b0466a8 |
| 3.04 | Diálogo de costes | [3.04](fase-3/3.04-dialogo-de-costes.md) | 3.02 | terminada con commit | b0466a8; 20 tests JS |
| 3.05 | Precios en la ayuda | [3.05](fase-3/3.05-precios-en-la-ayuda.md) | 3.04 | terminada con commit | b0466a8 |
| 3.06 | Comprobaciones en Chrome | [3.06](fase-3/3.06-comprobaciones-en-chrome.md) | 3.03, 3.05 | terminada con commit | b0466a8; 34 comprobaciones |
| 4.01 | Documentación | [4.01](fase-4/4.01-documentacion.md) | 3.06 | terminada con commit | d44d7fb |
| 4.02 | Verificación con tráfico real de Copilot | [4.02](fase-4/4.02-verificacion-con-trafico-real.md) | 2.04 | pendiente | necesita al usuario: gasta cuota y usa su cliente |

## Qué se puede lanzar a la vez

- 1.01 a 1.05 editan `tests/test_dependencies.py` y `pyproject.toml`: van en cadena. 1.06 y 2.01 no dependen de ellas y tocan otros ficheros.
- 2.01, 2.02 y 2.03 editan `cachetap/record.py`: van en cadena.
- 3.01 puede ir a la vez que la fase 2: solo toca `ui/` y sus tests.
- 3.02, 3.04 y 3.05 editan `ui/index.html`; 3.02 y 3.04 editan además `ui/costs.js`, `ui/list.js` y `ui/app.js`: van en cadena. 3.03 solo comparte con ellas lo que lee.
- 4.02 no bloquea a ninguna otra.

## Commits

En la rama `feat/costes`, uno por fase, cada uno comprobado en una copia aislada de lo que se iba a commitear (Ruff, formato, mypy, TESTS y JS; UI además en el de interfaz):

| Commit | Tareas | Contenido |
| --- | --- | --- |
| `5dd29c5` | 1.01 a 1.05 | paquete `cachetap/prices/` y sus tests |
| `70a5a9f` | 1.06 | lectura de lo escrito en caché en `cachetap/providers/` |
| `f3c1ddc` | 2.01 a 2.04 | causas del fallo, cálculo del coste, acumulado por conversación, cableado y golden |
| `b0466a8` | 3.01 a 3.06 | interfaz y sus tests |
| `d44d7fb` | 4.01 | `README.md` y `AGENTS.md` |

`tests/test_dependencies.py` y `pyproject.toml` entraron en dos pasos (`5dd29c5` sin las filas de `cost.py`, `f3c1ddc` con ellas) para que cada commit quede en verde. Ningún otro fichero aparece en más de un commit.

## Pendiente

- **4.02**, cuando el usuario quiera gastar esas peticiones.
- Fusionar `feat/costes` en `main` y hacer push, cuando el usuario lo pida.

## Estructura final y dependencias

| Fichero nuevo | Responsabilidad | Dependencias internas |
| --- | --- | --- |
| `cachetap/prices/base.py` | Forma de un precio, nombre canónico y contexto largo | — |
| `cachetap/prices/anthropic.py`, `openai.py` | Precios de lista de cada proveedor | `prices.base` |
| `cachetap/prices/copilot.py` | Tarifa de GitHub Copilot | `prices.base`, `prices.anthropic`, `prices.openai` |
| `cachetap/prices/__init__.py` | Qué tarifa paga una petición y referencia para la ayuda | las tres tablas, `prices.base`, `providers` |
| `cachetap/cost.py` | Coste, ahorro y perdido de un registro | `prices`, `prices.base`, `record` |
| `ui/costs.js` | Sumas por modelo y causa, orden por importe y diálogo de costes | `state.js`, `format.js` |
| `ui/detail-cost.js` | Sección «Coste» del detalle | `state.js`, `format.js` |
| `tests/test_cost.py`, `tests/test_prices*.py` | Un test por módulo nuevo | — |
| `tests/ui/unit/costs.test.mjs`, `format.test.mjs` | Tests JS puros de `costs.js` y `format.js` | el módulo bajo prueba |

`cachetap/providers/` no importa `prices`; `prices` importa `providers` solo para saber de quién es un modelo. `store` sigue dependiendo solo de `config` y `record`: lee `cost` del registro y no importa `cost.py`. `ui/list.js` importa `ui/costs.js`, y no al revés.

## Decisiones ya tomadas

Respuestas del usuario del 6 de octubre de 2026:

| Pregunta | Decisión |
| --- | --- |
| Qué es «ahorro» | tres cosas: ahorrado por la caché, perdido por un fallo y porcentaje de descuento |
| Dónde se ve | columna en la lista, desglose en el detalle, total por conversación y totales globales |
| De dónde salen los precios | tabla en el repositorio, un fichero por tarifa, con fecha de revisión; se actualiza a mano |
| Qué tarifa se aplica | según el host: Copilot para `githubcopilot.com`, precio de lista para llamadas directas |
| Total de una conversación larga | acumulado real en el backend, que sobrevive al desalojo de sus peticiones |
| Histórico de `data/requests.jsonl` | no se costea; solo peticiones nuevas |
| Modelo sin precio | sin coste y con aviso; nunca se estima |
| Extras | coste por causa del fallo, ordenar y filtrar por coste, precios en la ayuda. Descartado: coste en euros |

Decisiones de diseño:

- El coste se calcula al capturar y viaja en el registro y en el jsonl; no se recalcula si cambian los precios.
- `gpt-4.1`, `gpt-4o` y `gpt-4o-mini` en Copilot cuestan 0 con una nota, porque GitHub los documenta como utilitarios. No son «modelo sin precio».
- Copilot no recurre al precio de lista si le falta un modelo.
- Lo perdido se carga a la primera causa del fallo.
- Los detalles de precios y lo que no se pudo comprobar están en `precios.md`.

Fallos conocidos que **no** se arreglan en este plan: los nombres de modelo del escenario sintético que no existen en las tablas (`gpt-5.6`, `gpt-5.2`, `claude-sonnet-4-5`…) quedan sin precio; el escenario no tiene ninguna petición a Copilot, que solo cubren los tests unitarios.
