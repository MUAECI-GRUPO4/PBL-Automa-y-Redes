# Monitorización: InfluxDB y Grafana (tarea 2.10, DG)

InfluxDB guarda los datos de la planta y Grafana los muestra. No hay Telegraf ni otro agente:
el alimentador que escribe en InfluxDB es propio (tarea 2.9, commit C6).

```
PLC -> pasarela -> MQTT -> alimentador propio -> InfluxDB -> Grafana
                                                 \___ esta carpeta ___/
```

## Puesta en marcha

Requisitos: Docker con Compose v2, `bash` y `openssl`.

```bash
bash preparar.sh          # crea .env con contraseñas aleatorias (una sola vez)
docker compose up -d
docker compose ps         # los dos servicios deben salir "healthy"
```

- Grafana: <http://localhost:3000>
- InfluxDB: <http://localhost:8086>

Decisiones y pruebas: [`docs/monitorizacion.md`](../docs/monitorizacion.md).

Los usuarios y las contraseñas están en `.env`. La fuente de datos «InfluxDB» ya aparece creada en Grafana
(Connections > Data sources); como es de solo lectura, se comprueba con una consulta en Explore:

```flux
buckets()
```

Debe aparecer el bucket `planta`.

## Ficheros

| Fichero | Para qué |
|---|---|
| `docker-compose.yml` | Los dos servicios, con versión fija, comprobación de salud y rearranque automático |
| `.env.example` | Plantilla de configuración, sin secretos |
| `.env` | Configuración real con contraseñas. **No se versiona** |
| `preparar.sh` | Genera `.env` |
| `grafana/provisioning/` | Fuente de datos como código |

## Notas

- Los puertos se publican solo en `127.0.0.1`. Para verlos desde otro equipo de la red IT, cambiar `IP_PUBLICADA`.
- `docker compose down` conserva los datos; `docker compose down -v` **los borra**.
- Las claves de InfluxDB se fijan en el primer arranque: cambiar `.env` después no las cambia.
- Pendiente: esquema de datos (C2), token de solo lectura para Grafana, paneles en JSON y usuario de solo lectura (C7).
