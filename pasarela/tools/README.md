# Receptor UDP provisional

Herramienta de prueba para ver qué mandan los PLC. **No es el conector de la pasarela** (ese irá en `src/acq`, tarea 2.3).

```
python3 tools/escucha_udp.py [puerto=5000] [carpeta_senales=tools/senales]
python3 tools/test_decodifica.py          # autocomprobación sin red
```

- Decodifica el datagrama v2 con `senales/senales_<PLC>.json` (el `block_id` de cada bloque dice qué variable es).
- `layout.py` prueba tres hipótesis de cómo `Serialize` coloca booleanos y pares; elige la que cuadra con la longitud del bloque y avisa si ninguna cuadra. En los PLC reales siempre cuadra la H2.
- Cada 2 s muestra por PLC: recibidos, perdidos, duplicados, desordenados y número de señales.
- Rechaza (y lo escribe) lo que no empiece por `PG` con versión 2, o con `plc_id`/`block_id` desconocido, o con longitudes que no cuadran.

Solo biblioteca estándar de Python 3. Si no llega nada, mirar el cortafuegos del PC: `sudo ufw allow in on <interfaz> proto udp from 172.21.0.0/16 to any port 5000`.
