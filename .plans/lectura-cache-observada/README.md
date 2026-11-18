# Lectura observada de caché: índice

**Objetivo:** dar la misma lectura de caché en lista y detalle para cualquier cliente soportado, aunque el diagnóstico diga `N/A`. Conservar el significado de los veredictos y el design system del panel.

## Ejecución

- Una tarea por ejecutor; lee [reglas.md](reglas.md) y solo el fichero de la tarea, más las secciones que esta cite. No ejecutar este plan automáticamente al redactarlo.
- Fase 1: cero cuota; todas las rutas se verifican en Chrome. Para al cerrar la fase y pide autorización de la fase 2.
- Fase 2: validación con cada herramienta documentada. No se cierra el plan si alguna falta. Distingue siempre replay de ejecución real.
- Estados: `pendiente` · `en curso` · `terminada sin commit` · `terminada con commit` · `bloqueada`.

| ID | Tarea | Fichero | Depende de | Estado | Notas |
| --- | --- | --- | --- | --- | --- |
| 1.01 | Red de seguridad del veredicto y contadores | [1.01](fase-1/1.01-red-seguridad.md) | — | terminada con commit | FULL: 423 Python, 21 JS y Chrome; producción y golden intactos |
| 1.02 | Componente de lectura observada | [1.02](fase-1/1.02-indicador-presentacion.md) | 1.01 | terminada con commit | FULL: indicador aislado, umbral y contadores inválidos cubiertos |
| 1.03 | Colocar en Reparto y Resumen | [1.03](fase-1/1.03-lista-detalle.md) | 1.02 | terminada con commit | FULL: C3, C6, C30 y C34 intactos; matriz obligatoria para cerrar la fase |
| 1.04 | Ayuda y README | [1.04](fase-1/1.04-ayuda.md) | 1.03 | pendiente | Explica los dos denominadores |
| 1.05 | Matriz visual de las rutas en Chrome | [1.05](fase-1/1.05-matriz-visual.md) | 1.04 | pendiente | C35: 32 combinaciones, sin llamadas reales |
| 1.06 | Verificador visual reutilizable | [1.06](fase-1/1.06-verificador-panel.md) | 1.05 | pendiente | Aplica la misma prueba a un panel de prueba ya iniciado |
| 2.01 | Validar visualmente por cliente real | [2.01](fase-2/2.01-clientes-reales.md) | 1.06 | bloqueada | Requiere autorización de cuota y perfiles; no ejecutada |

La cadena es deliberada: primero el contrato, luego la presentación, después la documentación y la matriz contra el estado final. No se comparte el navegador de FULL entre tareas paralelas.

## Destino y decisiones

| Dónde | Resultado |
| --- | --- |
| `ui/parts.js` y `ui/css/parts.css` | Componente común que reutiliza estilos y tokens existentes; sin paquetes nuevos |
| `ui/list.js` y `ui/detail.js` | Lectura junto al reparto/resumen; explicación incremental en el detalle |
| `ui/index.html` y `README.md` | Ayuda coherente sin modificar las tablas de referencia |
| `tests/test_verdict.py`, `tests/ui/unit/` | Contrato del veredicto, contadores y presentación |
| `tests/replay/cache_read_ui.py` y `tests/ui/check.mjs` | Fixtures y comprobación visual en claro/oscuro y escritorio/estrecho |
| `validacion-real.md` de este plan | Evidencia por cliente, solo al ejecutar la fase 2 |

- El verde de lectura indica `read / input_total >= 90 %` **sobre la petición actual**. No tiene la clase `.v-hit` ni se suma al contador de `HIT`. Ejemplo: **«Leído de caché: 99,6 %»** y a la vez **`N/A`**, con «Prefijo: no comparable (contexto incremental)» en el detalle.
- El contraste inverso también importa: un `HIT` por comparación con una petición anterior puede coexistir con lectura actual del **87,5 %**, sin verde en el indicador de lectura. Sin contadores utilizables, muestra «sin datos», no `0,0 %`.
- El panel normaliza por formato del proveedor, no por nombre del cliente. Cobertura: Anthropic Messages, OpenAI Responses y Chat Completions, Gemini Developer API JSON y SSE, y Copilot HTTP y Responses WebSocket. La fase real incluye Claude Code, OpenCode, Copilot CLI y los clientes de script documentados.
- No se cambia captura/normalización, atribución de IDs, agrupación, precios, TTL, contadores ni el contrato API/SSE. No se arregla Auto de Copilot, no se demuestra transferencia de caché entre modelos, ni se añaden Vertex AI o Antigravity.

## Línea base observada al redactar

`venv/bin/python scripts/check.py --full` pasó: 422 pruebas Python, 20 JS y Chrome completo. Se verificaron los porcentajes de la matriz con `pct`, el `N/A` incremental con las proyecciones reales del inspector y el layout base en Chrome en ambos tamaños y temas. No se lanzaron llamadas de IA para redactar el plan ni se cambió código de producción.
