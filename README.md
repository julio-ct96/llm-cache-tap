# llm-cache-tap

Inspector local de la caché de prompts de los LLM. Es un proxy que se pone entre tu cliente (opencode, Claude Code, un script…)
y la API del proveedor, y muestra en un panel en vivo si cada petición acertó la caché y, si no, por qué.

Entiende las APIs de Anthropic (`/messages`) y de OpenAI (`/responses` y `/chat/completions`).

## Requisitos

- macOS o Linux.
- Python 3.12 o superior, accesible como `python3`.
- Conexión a internet la primera vez, para instalar mitmproxy.

No hay que instalar nada a mano: el primer arranque crea un entorno virtual en `venv/` e instala mitmproxy dentro.

## Arranque

```bash
git clone https://github.com/julio-ct96/llm-cache-tap.git
cd llm-cache-tap
./start.sh
```

La primera vez tarda alrededor de medio minuto. El panel queda disponible en:

```
http://127.0.0.1:8900
```

El addon anuncia esa URL con `logger.info`; `start.sh` usa nivel `warn`, por lo que el aviso informativo no se muestra con su configuración predeterminada. Deja esa terminal abierta. Quedan en marcha dos cosas:

| Qué | Dónde |
| --- | --- |
| Proxy | `127.0.0.1:8899` |
| Panel | <http://127.0.0.1:8900> |

En **otra terminal**, lanza tu cliente a través del proxy:

```bash
./via.sh opencode
./via.sh claude
./via.sh node mi-script.js
```

Abre el panel y haz una petición desde el cliente: aparece una fila por cada llamada al LLM.

## Certificados

Para leer el tráfico HTTPS, el proxy necesita su propia autoridad certificadora (CA). **No hay que generarla a mano ni viene en el repositorio.**

- **Cuándo se crea.** mitmproxy la genera sola en la carpeta `ca/` la primera vez que se ejecuta `./start.sh`. Es distinta en cada máquina.
- **Por qué no está en git.** `ca/` contiene la clave privada de esa CA. Quien la tenga puede interceptar el tráfico de cualquier proceso que confíe en ella, así que nunca se sube.
- **Quién confía en ella.** Solo el proceso que lanzas con `./via.sh`. No se instala nada en el llavero del sistema ni en el navegador.
- **Cómo regenerarla.** Para el proxy, borra la carpeta `ca/` y vuelve a ejecutar `./start.sh`.

`via.sh` configura la confianza para clientes hechos en **Node.js** (opencode, Claude Code…) con la variable `NODE_EXTRA_CA_CERTS`.
Para un cliente de otro tipo, indícale tú el certificado público, `ca/mitmproxy-ca-cert.pem`:

| Cliente | Variable que hay que añadir |
| --- | --- |
| Python con `requests` | `REQUESTS_CA_BUNDLE=ca/mitmproxy-ca-cert.pem` |
| Python con `httpx` u OpenSSL en general | `SSL_CERT_FILE=ca/mitmproxy-ca-cert.pem` |
| `curl` | `CURL_CA_BUNDLE=ca/mitmproxy-ca-cert.pem` |

Por ejemplo, desde la carpeta del proyecto:

```bash
SSL_CERT_FILE="$PWD/ca/mitmproxy-ca-cert.pem" ./via.sh python mi_script.py
```

## Configuración

Todo es opcional y se pasa como variable de entorno.

| Variable | Por defecto | Para qué | A quién se le pasa |
| --- | --- | --- | --- |
| `TAP_PROXY_PORT` | `8899` | Puerto del proxy | A `start.sh` **y** a `via.sh`, con el mismo valor |
| `TAP_UI_PORT` | `8900` | Puerto del panel | A `start.sh` |
| `TAP_TTL_S` | sin definir | Fuerza un TTL de caché, en segundos, para todas las peticiones en lugar de deducirlo del modelo | A `start.sh` |

```bash
TAP_PROXY_PORT=9001 TAP_UI_PORT=9002 ./start.sh
TAP_PROXY_PORT=9001 ./via.sh opencode
```

## Privacidad

- Las cabeceras de la petición nunca se leen ni se guardan: ahí viaja tu token.
- Los cuerpos de las peticiones solo viven en memoria (las últimas 300) para poder enseñarlos en el panel.
- `data/requests.jsonl` guarda solo métricas, no contenido. Esa carpeta tampoco se sube a git.
- El panel solo responde a `127.0.0.1` y `localhost`.

## Panel local y datos

El servidor escucha solo en `127.0.0.1` (puerto `TAP_UI_PORT`, por defecto 8900) y atiende estas rutas:

| Método y ruta | Respuesta |
| --- | --- |
| `GET /` y recursos de `ui/` | Interfaz estática; solo sirve ficheros dentro de `ui/` |
| `GET /api/reference` | Referencia de TTL y mínimos cacheables de los proveedores |
| `GET /api/record/<id>` | Registro público completo, sin claves internas |
| `GET /api/body/<id>` | Cuerpo de petición retenido; devuelve 404 si ya fue expulsado |
| `GET /events` | Stream SSE: `snapshot`, `record`, `evict` y `clear` |
| `POST /api/clear` | Limpia registros retenidos y emite `clear` |

Los contratos de Python están en `cachetap/record.py`: `Record` se completa progresivamente y solo requiere `id`; `state`, `verdict`, eventos y demás estados cerrados son `Literal`/`TypedDict`. En la API los registros de lista omiten campos pesados e internos; el endpoint de detalle expone los campos no internos. Los cuerpos no se escriben en el jsonl.

## Si algo falla

| Síntoma | Causa y arreglo |
| --- | --- |
| El cliente da un error de certificado (`self-signed certificate`, `unable to verify`, `CERTIFICATE_VERIFY_FAILED`) | El cliente no confía en la CA. Lánzalo con `./via.sh`; si no es de Node.js, añade la variable de la tabla de certificados |
| El cliente no conecta (`ECONNREFUSED 127.0.0.1:8899`) | El proxy no está en marcha, o usas un `TAP_PROXY_PORT` distinto en `start.sh` y en `via.sh` |
| `./start.sh` termina con `address already in use` | Ya hay un proxy en marcha o el puerto está ocupado. Para el otro proceso o cambia `TAP_PROXY_PORT` y `TAP_UI_PORT` |
| El panel está vacío aunque el cliente funciona | El cliente no pasa por el proxy: no se lanzó con `./via.sh`, o ignora `HTTPS_PROXY` |
| `./start.sh` falla al instalar mitmproxy | Comprueba `python3 --version` (3.12 o superior) y la conexión. Borra `venv/` y repite |
| `permission denied` al ejecutar los scripts | `chmod +x start.sh via.sh` |

## Desarrollo

Requisitos de las comprobaciones: Python 3.12 o superior, Node.js 24 (módulos ES y WebSocket global) y Chrome/Chromium para la suite de navegador. El entorno `venv/` debe tener las dependencias runtime y de desarrollo:

```bash
python3 -m venv venv
venv/bin/python -m pip install -r requirements-ci.txt  # dependencias directas para desarrollo/CI
```

`requirements-ci.txt` fija las dependencias directas de ejecución y referencia `requirements-dev.txt`; este último fija Ruff y mypy. No es un lock de dependencias transitivas. Para añadir las herramientas a un entorno existente que ya tenga mitmproxy:

```bash
venv/bin/python -m pip install -r requirements-dev.txt
```

Comprobaciones:

```bash
venv/bin/python scripts/check.py          # Ruff, mypy, 229 tests Python y checks JS
venv/bin/python scripts/check.py --full   # lo anterior y la suite completa de Chrome
node tests/ui/check.mjs --full            # suite de navegador por separado
venv/bin/python -m unittest discover -s tests -t . -q   # tests, sin dependencias extra
node --test tests/ui/unit/*.test.mjs                   # tests unitarios JS
node tests/ui/benchmark.mjs                            # benchmark informativo, sin umbral
venv/bin/python tests/replay/serve.py                   # panel con datos de prueba en el puerto 8901, sin proxy
```

La comprobación `--full` inicia el replay en `127.0.0.1:8901` y Chrome headless en el puerto de depuración `9334`; `TAP_UI_PORT`, `TAP_DEBUG_PORT` y `CHROME_BIN` permiten sustituirlos. No uses los puertos 8899/8900 para pruebas. La suite completa ejercita interfaz, accesibilidad/errores visibles, filtros, datos SSE y carreras; el runner local ejecuta también Ruff, formato, mypy, unittest y Node.

Los límites de `cachetap/config.py` son políticas del inspector, no cotas de memoria del proceso: 300 registros; 4 MiB por cuerpo de petición inspeccionable; 64 MiB de cuerpos UTF-8 retenidos en conjunto; 8 MiB por buffer de respuesta; 16 capturas de respuesta simultáneas y 512 eventos pendientes por cliente SSE. Una petición mayor de 4 MiB pasa sin inspección. Al exceder el límite de una respuesta se descarta su buffer y su veredicto pasa a `N/A`; si se alcanzan 16 capturas, las siguientes respuestas pasan sin captura y también quedan `N/A`. El tráfico hacia el proveedor conserva sus bytes originales. El presupuesto solo contabiliza los cuerpos retenidos: no incluye las estructuras Python, buffers internos de mitmproxy ni la memoria total/RSS del proceso. Una cola SSE llena se vacía, recibe una señal de desconexión y se cierra; EventSource se reconecta y recibe un snapshot completo.

`venv/bin/python scripts/check.py --full` pasó localmente con Python 3.14.6 y Node 24.14.1. La suite comprobó 229 tests Python y 11 tests unitarios JS; el chequeo UI completo es el comando `node tests/ui/check.mjs --full`. El workflow de GitHub está configurado para Python 3.12, Node 24 y Chrome, pero no se consultó un resultado remoto en esta sesión. El benchmark de `tests/ui/benchmark.mjs` es informativo (30, 300 y 3000 registros); no fija umbrales ni demuestra una mejora temporal frente a una versión anterior.

mitmproxy recarga `tap.py` cada vez que se guarda; lo capturado en memoria se pierde en cada recarga.

El mapa del código para agentes y las reglas de mantenimiento están en [`AGENTS.md`](AGENTS.md). Planes completados: [arquitectura por localidad](.plans/arquitectura-localidad/README.md) y [buenas prácticas](.plans/buenas-practicas/README.md).
