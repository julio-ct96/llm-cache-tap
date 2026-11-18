# Handoff para Opus — Lectura observada de caché

**Estado (2026-11-18):** las fases 1 y 2 están terminadas, sin commit de la ronda final. Los tres clientes de IA tienen capturas útiles validadas en Chrome: siete invocaciones, una por modelo y sin reintentos. Detalle en [validacion-real.md](validacion-real.md). Quedan abiertos dos temas fuera de 2.01: la anomalía `ERR` de OpenCode + `gpt-6-luna` por HTTP `/responses` y los precios ausentes de Haiku 5.5. El resto de este fichero describe el estado anterior a la segunda ronda.

## Qué quedó entregado

- Lista (**Reparto**) y detalle (**Resumen**) comparten el indicador «Leído de caché». El 90 % se aplica a `usage.read / usage.input_total` de la **petición actual**, sin redondear para decidir el verde. Contadores ausentes o inválidos muestran «Lectura de caché: sin datos», no `0,0 %`.
- El indicador no cambia los veredictos ni sus contadores. Dos contrastes validados: una lectura incremental del **99,6 %** puede seguir en `N/A`; un `HIT` puede mostrar **87,5 %** sin verde. No se cambió backend, API/SSE, precios, TTL ni `tests/replay/golden.json`.
- `venv/bin/python scripts/check.py --full` pasó: **423 Python, 24 JS y C35 con 32 combinaciones** de replay (8 casos × 2 tamaños × 2 temas). El verificador `--inspect-cache-read` usa las mismas aserciones en un panel de prueba ya arrancado.

## Evidencia de la fase 2

| Cliente | Resultado | Qué falta |
| --- | --- | --- |
| Node `fetch`, Python `requests`, Python `httpx`, `curl` | **Pasaron.** Procesos reales contra un mock HTTPS local. Una fila por cliente, `9500/10000`, **95,0 %** verde y `HIT`; **16/16** combinaciones Chrome. El control HTTPS directo no creó fila. | Nada, salvo que cambie el alcance. No confundir con inferencia autenticada. |
| OpenCode 2.3.2 | **Bloqueado.** Con la cuenta habitual y un único `hola`, el proveedor GitHub Copilot rechazó `gpt-5.4-nano` con HTTP 400 en `/responses`, aunque ese modelo aparecía en el catálogo. El CLI informó que el modelo solicitado no estaba disponible y salió con código 1. | Una captura autenticada con `usage`. La causa de la discrepancia entre catálogo y disponibilidad no está demostrada. |
| Claude Code 2.1.327 | Se confirmó el inicio de sesión de Claude; **no se invocó**. | `/messages`, fila `done` con uso y cuatro combinaciones Chrome por fila. |
| Copilot CLI 1.0.112 | Se comprobó el binario; **no se invocó**. | En terminal de Orca, `gpt-6-luna` con esfuerzo `low`, `/responses` por WebSocket, fila `done` con uso y cuatro combinaciones Chrome por fila. |

**OpenCode, detalle relevante:** dentro de la única invocación, el cliente intentó otras dos peticiones (`gpt-6-luna` y `gpt-5.4-nano`). Una protección del proxy de prueba devolvió HTTP 403 local a ambas antes de que llegaran al proveedor. Chrome verificó **12/12** combinaciones: la respuesta 400 y los dos 403 se mostraron como `N/A` y «sin datos». Las tres filas eran `done`, que significa *captura terminada*, no éxito HTTP. No hubo `usage` ni un cargo informado. Se paró antes de probar los otros CLI. Los procesos y temporales de esas pruebas se cerraron y eliminaron; sus rutas en el informe son evidencia histórica, no archivos reutilizables.

## Cómo retomar

1. **Empieza por la decisión pendiente.** Pregunta si se continúa con Claude Code y Copilot CLI sin reintentar OpenCode. Si se quiere cerrar también OpenCode, acuerda por separado un modelo alternativo y una nueva invocación: no repitas ni sustituyas automáticamente. Un catálogo que lista un modelo no demuestra que acepte la petición.
2. **Respeta la preferencia del usuario:** OpenCode con su cuenta habitual, sin pedir otra cuenta ni copiar credenciales. Un proceso nuevo con `--standalone` solo sirve para heredar el proxy; no sustituye la cuenta. Trabaja en un directorio vacío y no cambies la configuración global ni la sesión abierta. Conserva el bloqueo de herramientas, MCP y plugins externos para la prueba.
3. **Si se autoriza continuar**, usa un proxy, panel, CA y datos temporales separados, sin tocar puertos 8899/8900, capturas habituales ni llaveros. Una invocación por cliente, `hola` o `holi`, modelo económico explícito, sin fallback ni reintentos. Conserva una protección que impida que un intento interno adicional llegue al proveedor; si falla un cliente o la atribución es dudosa, para antes del siguiente y documenta lo observado.
4. **Verifica cada fila útil** con el panel todavía en marcha. Deriva `label`, `high` e `incremental` del `usage` de la API, no del DOM. El manifiesto admite exactamente `id`, `verdict`, `label`, `high` e `incremental` por fila. Comprueba 4 combinaciones por fila y registra por separado los errores o las filas sin uso. No hace falta obtener un `HIT`.

```sh
TAP_UI_PORT=<puerto-de-prueba> TAP_DEBUG_PORT=<puerto-CDP-libre> \
  node tests/ui/check.mjs --inspect-cache-read <manifiesto.json>
```

**Criterio de cierre:** cada cliente obligatorio tiene al menos una captura útil y su validación visual. Actualiza el índice y el informe con evidencia saneada, sin payloads, cabeceras, credenciales ni IDs privados. Ejecuta FULL al cierre. No confundas replay, scripts contra un mock y clientes de IA autenticados.

## Referencias

- [Índice y estados](README.md) · [Reglas](reglas.md) · [Tarea 2.01](fase-2/2.01-clientes-reales.md) · [Informe de validación](validacion-real.md).
- [`tests/ui/check.mjs`](../../tests/ui/check.mjs): C35 y `--inspect-cache-read`. [`scripts/check_copilot.py`](../../scripts/check_copilot.py): reutilizar `reserve_ports`, `write_bootstrap`, `wait_for_dashboard`, `read_snapshot` y `stop_process`; no usar `run_real` para esta matriz.
- `a9a4d08`: cierre técnico de fase 1; `57b78ac`: evidencia de scripts; `ce46a38`: intento autenticado de OpenCode. No se hizo push.
