# Pasarela multiprotocolo (PBL 2, parte de Redes)

Puente entre los PLC de la maqueta (OT) y los sistemas superiores (IT): adquisición, núcleo de datos y salidas, con InfluxDB y Grafana como primer consumidor.

| Carpeta | Contenido |
|---|---|
| `docs/` | contratos de interfaz ([`contratos.md`](docs/contratos.md)) y diagramas |
| `config/` | configuración de ejemplo; la real es `pasarela.ini` y no se versiona |
| `src/core`, `src/acq`, `src/outputs`, `src/feeder` | núcleo de datos, conectores de adquisición, de salida y alimentador de InfluxDB |
| `plc/` | programas de los PLC (exportación de TIA Portal) |
| `deploy/` | Docker Compose, InfluxDB y paneles de Grafana en JSON |
| `tests/` | pruebas |

Pruebas (solo biblioteca estándar, Python 3.10 o superior), desde esta carpeta:

```
python -m unittest discover -s tests
```
