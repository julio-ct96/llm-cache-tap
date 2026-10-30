# Diagnóstico estructural Copilot: índice

Objetivo: dos implementaciones offline acotadas (igualdad simbólica de IDs en diagnóstico de fallo; detalle allowlisted de `invalid_schema`), integración y una reserva operativa real bloqueada. No cambia atribución, proyección, validación estricta, precios ni tráfico.

**Autorización y límite.** El usuario autorizó llegar a validación real tras backup/activación, con esfuerzo `low`, saludos básicos y sin bucle de reintentos. El orquestador asume las decisiones y la ejecución real; Luna ejecuta cambios mecánicos cerrados. Los agentes offline no leen `data/`, panel, bodies, JSONL, binarios o prompts, ni activan, reinician o capturan. El inventario de solo lectura y el respaldo inicial ya fueron verificados por el orquestador. La reserva real sigue bloqueada hasta publicar su receta exacta.

## Ejecución

- Una tarea = un agente; lee `reglas.md`, su ficha y solo la sección citada de `contrato.md`.
- Ejecutar primero 1.02 (el sanitizador admite el nuevo campo opcional), después 1.01 y 1.03. Así cada commit conserva la suite completa en verde. 1.04 es una reserva hasta publicar su receta.
- Estados: `pendiente` · `en curso` · `terminada sin commit` · `terminada con commit` · `bloqueada`.
- No `git add`, `commit`, `push` ni `stash`. Al terminar esta fase se para antes de reparar precio/regla/protocolo.

## Tareas

| ID | Tarea | Fichero | Depende de | Estado | Notas |
| --- | --- | --- | --- | --- | --- |
| 1.01 | Símbolos de igualdad de ID | `fase-1/1.01-relaciones-simbolicas.md` | 1.02 | terminada con commit | Auditado: A-B-B/A-B-C diferenciados solo por ordinales, mapa acotado y limpio; FULL 405 Python/20 JS/Chrome. |
| 1.02 | Error `invalid_schema` sanitizado | `fase-1/1.02-invalid-schema-sanitizado.md` | — | terminada con commit | Auditado: raíz sin campo inventado, paths/tipos cerrados y símbolo server 1–32; FULL 404 Python/20 JS/Chrome. |
| 1.03 | Integración offline | `fase-1/1.03-integracion-offline.md` | 1.01, 1.02 | terminada con commit | Auditados hooks/API/sanitizador y exclusiones SSE/snapshot/body/JSONL; FULL 407 Python/20 JS/Chrome, sin mutar tráfico. |
| 1.04a | Preparar harness de evidencia | `fase-1/1.04a-harness-evidencia.md` | 1.02 | terminada con commit | Auditado: 8 pruebas fake, formas por familia contrastadas con backup, sin convertir contadores desconocidos en cero; artefactos solo locales. |
| 1.04 | Activación y adquisición real | `fase-1/1.04-reserva-operativa-real.md` | 1.03, 1.04a | pendiente | Receta y harness auditados; repetir preflight, ff-only y recarga nativa antes de cinco invocaciones máximas. |

## Estructura

```text
.plans/copilot-diagnostico-estructural/
  README.md
  reglas.md
  contrato.md
  verificacion-real.md
  fase-1/1.01-relaciones-simbolicas.md
  fase-1/1.02-invalid-schema-sanitizado.md
  fase-1/1.03-integracion-offline.md
  fase-1/1.04-reserva-operativa-real.md
```

## Decisiones y exclusiones

- Mapa por `_ActiveCapture`, máximo 32 identidades; ordinal entero 1–32. Sin hashes, colisiones al saturar ni `unknown` equivalente a “mismo”. Limpiar al liberar. No usarlo para atribución.
- Solo dos cambios de producción: `cachetap/record.py` + `cachetap/websocket.py`, y `scripts/check_copilot.py` para diagnóstico de schema/sanitización. Sin módulos, scripts genéricos, infraestructura o proyección nuevos.
- El runner conserva el código JSON `invalid_schema`, añade `diagnostic` opcional con ruta/tipos allowlisted, sin excepción dinámica ni JSON crudo. La validación estricta no cambia. No tocar `run_real` salvo propagar/publicar ese dato allowlisted de usage.
- Hecho aportado por el usuario: promoción Argon `2/.10/10` y `Default/Not applicable` confirmados por investigación oficial; sigue sin acreditarse tarifa/semántica de `cache_write`. Billing reports solo define una cantidad. No extrapolar nota OpenAI/Anthropic a Google; mantener `cost_missing`, `approved=false`, sin tocar precios.
- Cuota, nombre de modelo o crédito reportado no prueban tarifa. Ni ordinales entre eventos ni igualdad observada prueban relación con `response.create`.
- El orquestador ejecuta CHECK/FULL, tipos, Ruff y huellas antes de cada commit/push aprobado. Nunca dos FULL simultáneos. El antiguo `--baseline` fija diagnósticos idénticos y queda como comprobación histórica: tras añadir símbolos se comprueban acciones/resultados iguales, pero diagnósticos distintos, mediante los tests actualizados. El verificador antiguo sin `--baseline` sigue aplicando.
- No lanzar reservas anteriores. Protegidos (no modificar): `.plans/copilot-cli-websocket/README.md`, `.plans/copilot-cli-websocket/verificacion-real.md`, `AGENTS.md`, `cachetap/prices/openai.py`, `tests/test_dashboard.py`, `tests/test_prices.py`, `tests/test_prices_copilot.py`, `tests/test_prices_openai.py`; `venv/` también permanece sin tocar. No inspeccionar `data/`, `ca/`, panel, binarios, prompts o el harness privado en estas tareas.

## Fallos conocidos que no se arreglan

Relación de propiedad/atribución de IDs; `stream_id`; eventos de protocolo/proyección; campo histórico causante de `invalid_schema`; tarifa Argon `cache_write`; reglas de costes, precios, selección de modelo, retries internos del CLI o cualquier reparación de protocolo.
