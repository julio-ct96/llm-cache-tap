# Precios por familia: índice

Objetivo: organizar cada tabla de precios en bloques con nombre (tirada en OpenAI, familia en Anthropic, generación en Google, proveedor en Copilot) sin cambiar ningún precio, y después añadir los modelos oficiales que faltaban. No cambian `cost.py`, `lookup`, los proveedores ni la interfaz.

## Cómo se ejecuta

- Una tarea = un agente. Cada agente lee `reglas.md` y el fichero de su tarea, nada más.
- Una tarea se puede lanzar cuando todas las de «Depende de» están terminadas. Las que cumplen eso a la vez se pueden lanzar en paralelo.
- Estados: `pendiente` · `en curso` · `terminada sin commit` · `terminada con commit` · `bloqueada`.
- Al cerrar cada fase se para y se resume.

## Tareas

| ID | Tarea | Fichero | Depende de | Estado | Notas |
| --- | --- | --- | --- | --- | --- |
| 1.01 | OpenAI por tiradas | `fase-1/1.01-openai-por-tirada.md` | — | terminada con commit | |
| 1.02 | Anthropic por familias | `fase-1/1.02-anthropic-por-familia.md` | — | terminada con commit | |
| 1.03 | Google por generaciones | `fase-1/1.03-google-por-generacion.md` | — | terminada con commit | |
| 1.04 | Copilot por proveedor | `fase-1/1.04-copilot-por-proveedor.md` | — | terminada con commit | |
| 2.01 | Anthropic: modelos que faltan | `fase-2/2.01-anthropic-modelos.md` | 1.01, 1.02, 1.03, 1.04 | terminada con commit | |
| 2.02 | OpenAI: modelos que faltan | `fase-2/2.02-openai-modelos.md` | 2.01 | terminada con commit | |
| 2.03 | Google: modelos que faltan | `fase-2/2.03-google-modelos.md` | 2.02 | terminada con commit | |
| 2.04 | Copilot: Opus 4.8 en modo rápido | `fase-2/2.04-copilot-opus-rapido.md` | 2.03 | terminada con commit | |
| 3.01 | Documentar la nueva organización | `fase-3/3.01-documentacion.md` | 2.04 | terminada con commit | |

## Qué se puede lanzar a la vez

- 1.01, 1.02, 1.03 y 1.04 tocan un fichero distinto cada una y no cambian ningún nombre que use otra: van en paralelo. Su invariante es que HUELLA no cambia.
- La fase 2 es una cadena: todas sus tareas editan el recuento de `tests/test_prices.py`, y 2.01 y 2.02 regeneran `tests/replay/golden.json` y editan `tests/ui/check.mjs`. Cada HUELLA «antes» es la «después» de la anterior.

## Estructura final

```
cachetap/prices/
  anthropic.py  _claude, _family; FABLE, MYTHOS, OPUS, SONNET, HAIKU; PRICES = su unión
  openai.py     _gpt, _release, _without_cached_input; GPT_6_2 … GPT_4O, O3; PRICES = su unión
  google.py     constantes de promoción; GEMINI_4, GEMINI_3, GEMINI_2_5; PRICES; AFTER_PROMO
  copilot.py    FROM_LISTS, DIFFERENT_TIERS, UTILITY_MODELS, CLAUDE_FAST, GEMINI, GROK, KIMI, MAI; PRICES; AFTER_PROMO
.plans/precios-por-familia/
  huella.py       recuento y huella del contenido de cada tarifa, y filas de la ayuda
  golden_diff.py  registros del golden que cambian respecto al último commit
```

## Decisiones ya tomadas

- Eje por proveedor: OpenAI por tirada, porque sus rasgos (escrituras de 30 min y 12 h, contexto largo) cambian por tirada; Anthropic por familia, porque así publica y así varía el mínimo cacheable; Google por generación; Copilot por proveedor de origen, porque sus filas propias son lo que difiere de las listas.
- El orden de las filas en la ayuda pasa a ser el de los bloques, de lo nuevo a lo viejo. La huella ignora el orden a propósito.
- Los valores esperados (huellas, filas de la ayuda, diff del golden y textos de C30 y C33) se midieron aplicando los datos de la fase 2 en un worktree temporal el 2026-11-18.
- Fuentes de los precios nuevos, consultadas el 2026-11-18: páginas oficiales de precios de Anthropic, OpenAI (Standard), Google AI Studio (Standard, texto) y GitHub Copilot.
- Las versiones Pro de OpenAI no publican precio de caché: lectura igual a entrada, con nota visible.
- Copilot hereda todas las filas de las listas de Anthropic y OpenAI, aunque GitHub no venda todos esos modelos. Es el comportamiento que ya había.
- Fuera de este plan: MAI Code 2 y MAI Code 2 Flash (GitHub no publica su ID), Mythos Preview (sin precio publicado), modelos de imagen, audio, embeddings y Gemini Omni o Robotics, precios de audio de Gemini, la redirección de Gemini 2.5 a partir del 1 de diciembre de 2026, el mínimo cacheable de los GPT anteriores a 5.6 (OpenAI no da número) y la retención `24h` exclusiva de GPT-5.5.
