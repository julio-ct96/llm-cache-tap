# Precios comprobados

Dólares de EE. UU. por millón de tokens, leídos el 6 de octubre de 2026. «—» significa que ese concepto no se factura aparte.

## Fuentes

| Tarifa | Página | Cómo se leyó |
| --- | --- | --- |
| Copilot | `docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing` | texto en bruto de la página |
| Anthropic | `platform.claude.com/docs/en/about-claude/pricing` | texto en bruto de la página |
| OpenAI | `developers.openai.com/api/docs/pricing` | a través de un resumen automático; las filas coinciden con la tabla de GitHub |

Copilot factura por token desde el 1 de junio de 2026, al precio de lista de cada proveedor; 1 crédito de IA = 0,01 $.

## Anthropic

Escritura de caché a 5 minutos = 1,25 × entrada; a 1 hora = 2 × entrada; salida = 5 × entrada. Ningún modelo de la tabla tiene tarifa de contexto largo.

| Modelo | Entrada | Leído | Escrito 5 min | Escrito 1 h | Salida |
| --- | --- | --- | --- | --- | --- |
| claude-fable-5.1 | 10 | 0,25 | 12,5 | 20 | 50 |
| claude-fable-5 | 10 | 1 | 12,5 | 20 | 50 |
| claude-opus-5.5 | 4 | 0,2 | 5 | 8 | 20 |
| claude-opus-5 | 5 | 0,5 | 6,25 | 10 | 25 |
| claude-opus-4.8 | 5 | 0,5 | 6,25 | 10 | 25 |
| claude-opus-4.7 | 5 | 0,5 | 6,25 | 10 | 25 |
| claude-sonnet-5.5 | 2 | 0,2 | 2,5 | 4 | 10 |
| claude-sonnet-5 | 2 | 0,2 | 2,5 | 4 | 10 |
| claude-sonnet-4.6 | 3 | 0,3 | 3,75 | 6 | 15 |
| claude-haiku-4.5 | 1 | 0,1 | 1,25 | 2 | 5 |

## OpenAI

Escritura de caché = 1,25 × entrada, solo en GPT-5.6 y posteriores. Contexto largo: con más de 272.000 tokens de entrada, toda la petición paga 2 × entrada, leído y escrito, y 1,5 × salida.

| Modelo | Entrada | Leído | Escrito | Salida | Contexto largo |
| --- | --- | --- | --- | --- | --- |
| gpt-6-astra | 10 | 1 | 12,5 | 50 | sí |
| gpt-6-sol | 2 | 0,2 | 2,5 | 10 | sí |
| gpt-6-luna | 0,1 | 0,01 | 0,125 | 0,5 | sí |
| gpt-6.1-sol | 2 | 0,1 | 2,5 | 10 | sí |
| gpt-5.6-sol | 4 | 0,4 | 5 | 20 | sí |
| gpt-5.6-terra | 2 | 0,2 | 2,5 | 12 | sí |
| gpt-5.6-luna | 0,2 | 0,02 | 0,25 | 1,2 | sí |
| gpt-5.5 | 5 | 0,5 | — | 30 | sí |
| gpt-5.4 | 2,5 | 0,25 | — | 15 | sí |
| gpt-5.4-mini | 0,75 | 0,075 | — | 4,5 | no |
| gpt-5.4-nano | 0,2 | 0,02 | — | 1,25 | no |
| gpt-5.3-codex | 1,75 | 0,175 | — | 14 | no |
| gpt-5-mini | 0,25 | 0,025 | — | 2 | no |
| gpt-4.1 | 2 | 0,5 | — | 8 | no |

## Copilot

Las filas de Claude y GPT son las de las dos tablas anteriores con estas diferencias, más los modelos que solo lista GitHub.

| Modelo | Diferencia o precio |
| --- | --- |
| todos los Claude | una sola tarifa de escritura (la de 5 minutos); sin tarifa de 1 hora |
| gpt-5.6-luna | el contexto largo empieza en más de 200.000 tokens, no en 272.000 |
| gpt-4.1, gpt-4o, gpt-4o-mini | 0 / 0 / 0: modelos utilitarios, no consumen créditos |
| gemini-3.5-flash | entrada 1,5 · leído 0,15 · salida 9 |
| gemini-3.6-flash, gemini-3.7-flash, gemini-3.8-flash | entrada 0,75 · leído 0,075 · salida 3,75 (promocional hasta el 31-12-2026) |
| grok-4.5, grok-4.6, grok-4.7 | entrada 2 · leído 0,5 · salida 6; con más de 200.000 tokens: 4 · 1 · 12 |
| kimi-k3 | entrada 3 · leído 0,3 · salida 15 |
| kimi-k2.7-code | entrada 0,95 · leído 0,19 · salida 4 |
| mai-code-1.1-flash | entrada 0,2 · leído 0,02 · salida 1,2 |

## Lo que no se pudo comprobar

| Duda | Qué se hizo |
| --- | --- |
| Si `cache_write_tokens` de OpenAI forma parte de `input_tokens` | se supone que sí; lo comprueba la tarea 4.02 |
| Si Copilot cobra distinto la escritura de Claude a 1 hora | se aplica la única tarifa que publica GitHub |
| GitHub lista el leído de grok-4.5 a 0,5 y xAI a 0,3 | se usa el de GitHub, que es quien factura |
| GitHub no dice si el contexto largo afecta a toda la petición | se aplica a toda, como documentan OpenAI y xAI |
| `mai-code-1-flash-picker`: modelo retirado, identificador no confirmado | no se añade |
| Descuento del 10 % de la selección automática de Copilot; niveles batch, flex y fast | no se ven en la petición; no se reflejan |
