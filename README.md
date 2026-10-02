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

La primera vez tarda alrededor de medio minuto. Cuando está listo escribe:

```
[tap] dashboard: http://127.0.0.1:8900
```

Deja esa terminal abierta. Quedan en marcha dos cosas:

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

```bash
venv/bin/python -m unittest discover -s tests -t . -q   # tests, sin dependencias extra
venv/bin/python tests/replay/serve.py                   # panel con datos de prueba en el puerto 8901, sin proxy
```

mitmproxy recarga `tap.py` cada vez que se guarda; lo capturado en memoria se pierde en cada recarga.

El mapa del código para agentes está en [`AGENTS.md`](AGENTS.md) y el plan de refactorización en curso, en `.plans/arquitectura-localidad/`.
