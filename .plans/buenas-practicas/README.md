# Buenas prácticas: índice de implementación

Objetivo: reforzar límites de recursos, validación, concurrencia, errores, legibilidad y tipos; automatizar las comprobaciones manteniendo una arquitectura sencilla.

## Punto de partida comprobado

Revisión del 2 de octubre de 2026, árbol limpio antes de crear este plan.

- `venv/bin/python -m unittest discover -s tests -t . -q`: **177 tests, OK**.
- `node tests/ui/check.mjs --full`: **todos los checks pasan**; escenario de 44 registros.
- Python local 3.14.6 y Node 24.14.1. El proyecto mantiene compatibilidad declarada con Python 3.12.
- El backend limita registros a 300; el frontend no limita su Map. Las colas SSE y buffers de respuesta no tienen límite.
- Raíz JSON list/null causa AttributeError; tools/messages enteros causan TypeError; input='hola' se cuenta como cuatro mensajes.
- `output_text('data: []\n\n')` causa AttributeError. El replay válido y sus hashes actuales son la referencia de compatibilidad.
- Configuración crea DATA durante el import; la escritura jsonl ocurre dentro de LOCK; retirada del cliente SSE no toma LOCK.
- pip no pudo consultar PyPI en esta sesión por certificado TLS no confiable. Las versiones elegidas de Ruff/mypy se verificaron en sus páginas de PyPI, pero **su instalación y ejecución se comprueban al ejecutar las tareas de herramientas**.

## Cómo se ejecuta

- Cada ejecutor lee `reglas.md`, su tarea y las secciones citadas de `contratos.md`; consulta solo su fila del índice para dependencias/estado.
- Una tarea comienza cuando sus dependencias están terminadas. Cada tarea deja las comprobaciones aplicables verdes.
- `venv/bin/python .plans/buenas-practicas/check_plan.py` comprueba índice, ficheros, dependencias y secciones de tareas.
- Estados: `pendiente`, `en curso`, `terminada sin commit`, `terminada con commit`, `bloqueada`.
- Se puede ejecutar en la misma sesión o delegar si el usuario pide ejecución con agentes. Este plan no lanza agentes ni implementa cambios.
- Al cerrar una fase se informa de resultados y se espera la confirmación para la siguiente, salvo instrucción de ejecutar todo el plan.

## Tareas

| ID | Tarea | Fichero | Depende de | Estado | Notas |
| --- | --- | --- | --- | --- | --- |
| 1.01 | Red de seguridad Python/JS | [1.01](fase-1/1.01-red-seguridad.md) | — | terminada con commit | 180 tests Python, 2 JS y UI completa OK; golden idéntico; runner JS corregido en 3346504 |
| 2.01 | Validación de peticiones | [2.01](fase-2/2.01-validacion-peticiones.md) | 1.01 | pendiente | Contratos de entrada |
| 2.02 | Eventos mal formados | [2.02](fase-2/2.02-eventos-malformados.md) | 1.01 | pendiente | Conserva datos válidos |
| 2.03 | Inicialización sin efectos al importar | [2.03](fase-2/2.03-inicializacion.md) | 1.01 | pendiente | Filesystem en escritura |
| 2.04 | Retención por bytes y expulsión | [2.04](fase-2/2.04-retencion-backend.md) | 2.01, 2.03 | pendiente | Protocolo compatible en casos existentes |
| 2.05 | Retención del navegador | [2.05](fase-2/2.05-retencion-frontend.md) | 2.04 | pendiente | Elimina crecimiento sin límite |
| 2.06 | Límites de respuestas | [2.06](fase-2/2.06-limites-respuestas.md) | 2.02, 2.04 | pendiente | Bytes originales siempre pasan |
| 2.07 | Colas SSE y lock | [2.07](fase-2/2.07-suscriptores.md) | 2.06 | pendiente | Cliente lento reconecta |
| 2.08 | Log resiliente fuera del lock | [2.08](fase-2/2.08-log-resiliente.md) | 2.07 | pendiente | Fallo local no rompe captura |
| 3.01 | Errores de stream y acciones | [3.01](fase-3/3.01-errores-stream-acciones.md) | 2.05, 2.08 | pendiente | Diagnósticos visibles |
| 3.02 | Detalle sin carreras HTTP | [3.02](fase-3/3.02-detalle-asincrono.md) | 3.01 | pendiente | Generación y cancelación |
| 3.03 | Coste de renderizado | [3.03](fase-3/3.03-coste-renderizado.md) | 3.02 | pendiente | Una ordenación y un frame por ráfaga |
| 4.01 | Contratos y mypy | [4.01](fase-4/4.01-contratos-tipos.md) | 2.08 | pendiente | Requiere instalar herramienta |
| 4.02 | Nombres de segmentación | [4.02](fase-4/4.02-nombres-segmentos.md) | 2.08 | pendiente | Cambio mecánico |
| 4.03 | Búsqueda pura del anterior | [4.03](fase-4/4.03-emparejado-puro.md) | 4.02, 3.03 | pendiente | Preparación explícita |
| 4.04a | Tipos de proveedores | [4.04a](fase-4/4.04a-tipos-proveedores.md) | 4.01, 4.03 | pendiente | Interfaces compartidas |
| 4.04 | Tipos del núcleo | [4.04](fase-4/4.04-tipos-nucleo.md) | 4.04a | pendiente | Dependencias de tipos declaradas |
| 4.05 | Tipos de integración | [4.05](fase-4/4.05-tipos-integracion.md) | 4.04 | pendiente | Incluye todos los módulos de producción |
| 5.01 | Ruff y formato | [5.01](fase-5/5.01-lint-formato.md) | 4.05 | pendiente | Diff mecánico aislado |
| 5.02 | Comando unificado y CI | [5.02](fase-5/5.02-comprobacion-unificada.md) | 5.01, 3.03 | pendiente | No necesita tráfico real |
| 5.03 | Documentación y cierre | [5.03](fase-5/5.03-documentacion-cierre.md) | 5.02 | pendiente | Verificación completa |

## Paralelismo permitido

- Después de 1.01: 2.01, 2.02 y 2.03 tienen ficheros distintos y pueden ejecutarse a la vez.
- Después de 2.04: 2.05 puede ir con 2.06; la primera cambia UI y la segunda backend.
- Después de 2.08: 4.01 y 4.02 pueden adelantarse mientras avanza 3.01/3.02. 4.03 espera 3.03 porque comparten linking.py.
- 4.04a en adelante forman una cadena. No ejecutes formato junto a otras tareas de Python.
- Touch de tap.py para recarga y la edición de una fila del índice no cuentan como cambios de contenido compartido; evita ejecutar suites completas simultáneas con el mismo puerto UI.

## Estructura final y dependencias

| Fichero nuevo | Responsabilidad | Dependencias internas |
| --- | --- | --- |
| `cachetap/request_body.py` | Parsear/validar la petición inspeccionable | `record` cuando se añadan tipos |
| `ui/status.js` | Mensaje accesible de operación/error | `format.js` |
| `ui/events.js` | Validación pura de eventos SSE | — |
| `tests/ui/unit/*.test.mjs` | Tests JS puros con node:test | Módulos UI bajo prueba |
| `tests/ui/benchmark.mjs` | Medición informativa de filtros/resumen | `list.js` con import sin acceso DOM en top-level |
| `pyproject.toml` | Ruff y mypy | — |
| `requirements-dev.txt` | Herramientas fijadas de desarrollo | — |
| `requirements-ci.txt` | Dependencias directas fijadas para CI | — |
| `scripts/check.py` | Comprobación local única | Herramientas ya instaladas |
| `.github/workflows/check.yml` | Verificación en GitHub | Runner local |

Los módulos de dominio pueden importar `record` para sus tipos. Ningún módulo interno importa tap; el despacho de proveedores mantiene su orden y los tests de arquitectura siguen activos.

## Cobertura de las recomendaciones

| Práctica | Tareas |
| --- | --- |
| KISS, funciones legibles, nombres del dominio | 4.02, 4.03, 5.03 |
| Pureza y efectos explícitos | 2.03, 2.08, 3.03, 4.03 |
| Complejidad temporal/memoria y medición | 2.04–2.07, 3.03 |
| Validación en entradas y excepciones específicas | 2.01, 2.02, 2.08, 3.01, 3.02 |
| Concurrencia y carreras asíncronas | 2.07, 2.08, 3.02 |
| Tipos útiles y estados cerrados | 4.01, 4.04a, 4.04, 4.05 |
| IDs/data attributes, escape y errores accesibles | 3.01, 3.02, 5.03; se conserva el uso adecuado actual |
| Tests de comportamiento y automatización | 1.01 y cada corrección; 5.01, 5.02 |

## Decisiones tomadas

- **21 tareas y cinco fases.** Los contratos nuevos se especifican antes de ejecutar; cada cambio de comportamiento incorpora tests del mismo caso en su tarea para no dejar un paso intermedio rojo.
- Mantener ES modules sin build, unittest y arquitectura modular. No añadir frontend framework, Pydantic, dataclasses para registros JSON ni una capa genérica de repositorios.
- Mantener IDs de controles únicos y data-id/data-act para filas/acciones. No migrar selectores por una regla estética.
- Preservar hashes, serialización, TTL, emparejado y veredictos de capturas completas válidas; golden idéntico. Cambios visibles intencionados: errores explícitos, datos expulsados, captura limitada y recuento de string input.
- Los límites son política inicial revisable, no un resultado de benchmark. No prometen acotar la memoria que mitmproxy asigna antes del hook ni el tamaño de todas las estructuras Python.
- Mypy gradual hasta incluir todo el backend de producción; Ruff sobre producción. Herramientas fuera del runtime normal. CI también ejecuta tests JS y navegador.
- El benchmark mide funciones puras sin fijar umbrales inestables ni introducir índices de conversación antes de necesitarlo.
- Fuera de alcance: actualizar reglas de TTL/modelos (incluido el nombre histórico de Haiku), cambiar semántica SSE multilínea o detección TTFT por chunks, rotación del jsonl y reescribir el servidor HTTP. Son decisiones de producto independientes de estas mejoras.

## Criterio de cierre

Todas las tareas terminadas, `venv/bin/python scripts/check.py --full` verde, golden idéntico, límites/casos de error comprobados y documentación actualizada. No requiere credenciales ni llamadas reales a proveedores.
