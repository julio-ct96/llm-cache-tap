# Verificación de tarifa: Gemini 4 Argon en Copilot

## Fuentes

Consulta pública, sin iniciar sesión, realizada el **2026-10-30**:

1. GitHub Docs, [Models and pricing for GitHub Copilot — Pricing tables, Google](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing#google), fila **Gemini 4 Argon** y nota de que todos los precios son por 1 millón de tokens. La página enmarca esta tabla como precios de modelos disponibles en GitHub Copilot.
2. GitHub Docs, [nota promocional de Gemini 4 Argon](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing#user-content-fn-gemini-4-argon-promo), enlazada desde esa fila.
3. GitHub Docs, [Supported AI models in GitHub Copilot](https://docs.github.com/en/copilot/reference/ai-models/supported-models#supported-ai-models-in-copilot), fila **Gemini 4 Argon**: proveedor Google, estado GA.

La tabla de precios citada es la tarifa publicada por GitHub Copilot, no la tarifa directa de Google. No remite para Argon a otro tarifario oficial. La página explica que 1 AI credit equivale a USD 0.01; las cifras de la fila, sin embargo, se publican como precios en USD por millón de tokens, y no se convierten aquí a créditos ni a multiplicadores.

## Fila y unidades

| Campo | Evidencia oficial consultada |
| --- | --- |
| Modelo y canal | **Gemini 4 Argon**, listado en la tabla de precios de GitHub Copilot bajo Google; GA, categoría Powerful y tier Default. El nombre canónico interno es `gemini-4-argon`. Esto acredita la tarifa Copilot, no una tarifa de Google ni la disponibilidad en cada cliente o plan. |
| Input | USD 2.00 por millón de tokens, precio promocional. |
| Read / cached input | USD 0.10 por millón de tokens, precio promocional. |
| Output | USD 10.00 por millón de tokens, precio promocional. |
| Escritura de caché | La fila de Google no tiene una columna de cache write. La fuente no dice expresamente si la escritura se factura aparte ni publica una tarifa de escritura; queda desconocido, no USD 0. |

## Caché y contexto

La fila distingue **Cached input** de **Input**, por lo que acredita la tarifa de lectura de caché indicada arriba. No publica una columna de escritura de caché; esa ausencia no acredita si escribir se cobra aparte ni qué tarifa tendría. El umbral de contexto de la fila es **Not applicable** y el tier publicado es **Default**. Son datos positivos: para la tarifa publicada no hay un umbral de contexto largo ni otra tarifa long-context que aplicar. No se infiere que una escritura cueste cero ni se extrapola ningún nivel de otra tarifa.

## Vigencia

La nota oficial indica que los precios promocionales de Gemini 4 Argon —USD 2.00 input, USD 0.10 cached input y USD 10.00 output por millón de tokens— son válidos **until December 1, 2026**. La página se consultó el **2026-10-30**, la misma fecha que el orquestador confirmó para las pruebas guardadas (también fechadas en `evidencia.md`); por tanto, las tarifas promocionales publicadas quedan verificadas para esa fecha y para peticiones nuevas dentro de la vigencia indicada. La fuente no da la fecha de inicio ni publica el tarifario que regirá después del 1 de diciembre. Esa incertidumbre futura no pone en duda la tarifa promocional publicada para el 2026-10-30.

## Decisión

**Insuficiente; `approved=false`.** Las tarifas promocionales de input, cached input y output, así como el tier Default y el umbral Not applicable, están verificados para el 2026-10-30. La única carencia que impide codificar una fila completa sin supuestos es que la fuente no acredita la semántica ni la tarifa de escritura de caché; no se interpreta la ausencia de esa columna como cero. Las tarifas posteriores a la promoción siguen sin publicarse, pero esa es una limitación futura, no una carencia de la tarifa promocional vigente. Conservar `cost_missing`; no añadir ni implementar tarifas.
