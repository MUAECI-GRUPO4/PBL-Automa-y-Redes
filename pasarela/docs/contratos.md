# Contratos de interfaz de la pasarela multi-PLC

**Estado:** borrador C0 de DL (tareas 2.1, 2.3). Se acuerda en el grupo antes de implementar; después, nadie lo cambia sin avisar y reabrir el apartado en un pull request.

## 1. Modelo de datos

Cada señal es un `Signal` con estos campos (D1):

| Campo | Tipo | Significado |
|---|---|---|
| `path` | str | `planta/estacion/senal`, único en toda la pasarela |
| `value` | bool, int, float | valor ya decodificado |
| `ts_origin` | int | ms desde epoch UTC, marca del PLC (no la de escritura en InfluxDB) |
| `ts_rx` | int | ms desde epoch UTC en que llegó a la pasarela |
| `quality` | `GOOD` o `BAD` | `BAD` si se supera el tiempo máximo de recepción (D3) o el dato es inválido |
| `unit` | str | unidad, vacía si no aplica |
| `plc_id` | int | PLC de origen |

## 2. Interfaz interna entre los tres componentes

Ningún componente importa a otro: solo conocen estas interfaces (A1). Los conectores se cargan por nombre desde la configuración, así que añadir, quitar o sustituir uno solo toca `config/pasarela.ini` (A2 a A4).

```python
from dataclasses import dataclass
from typing import Callable, Protocol

@dataclass(frozen=True)
class Signal:
    path: str; value: bool | int | float
    ts_origin: int; ts_rx: int
    quality: str; unit: str; plc_id: int

class AcquisitionConnector(Protocol):      # src/acq/<nombre>.py
    def start(self, sink: Callable[[Signal], None]) -> None: ...
    def stop(self) -> None: ...

class Core(Protocol):                      # implementación en src/core/
    def ingest(self, s: Signal) -> None: ...            # adquisición -> núcleo
    def subscribe(self, cb: Callable[[Signal], None]) -> None: ...  # salidas reciben cambios
    def snapshot(self) -> dict[str, Signal]: ...        # salidas leen el estado actual
    def health(self) -> dict: ...                       # contadores para el panel de salud (O3)

class OutputConnector(Protocol):           # src/outputs/<nombre>.py
    def start(self, core: Core) -> None: ...
    def stop(self) -> None: ...
```

Reglas:

- El núcleo **no ofrece ninguna operación de escritura hacia el PLC**: las salidas son de solo lectura por construcción (O1).
- Un conector de adquisición nunca decide la calidad: solo entrega datos. Calidad, pérdidas y alarmas son del núcleo.
- Si un consumidor no está disponible, la salida decide (guardar y reenviar o descartar y registrar), pero siempre cuenta lo perdido en `health()`.

## 3. Datagrama UDP PLC a pasarela (U1 a U3)

Orden de bytes **big-endian** (el de los S7). Un datagrama lleva varias señales de un mismo PLC.

```
 0        2     3       4          8                 16      18
 +--------+-----+-------+----------+-----------------+-------+------------+
 | magic  | ver | plc_id|   seq    |    ts_origin    |   n   | n entradas |
 | "PG"   | u8  |  u8   |  u32     |      u64 (ms)   |  u16  |            |
 +--------+-----+-------+----------+-----------------+-------+------------+
 entrada:  signal_id u16 | tipo u8 | valor
 tipo:     0 = BOOL (1 B), 1 = INT (2 B), 2 = DINT (4 B), 3 = REAL (4 B)
```

- `signal_id` se traduce a `path` con la tabla `[signals]` de la configuración, no viaja el nombre.
- **Pérdidas, duplicados y desorden** (U1, D2), por cada `plc_id`:
  - `seq` mayor que el esperado: se cuentan los `seq` saltados como perdidos.
  - `seq` igual al último recibido: duplicado, se descarta y se cuenta.
  - `seq` menor que el último recibido: desordenado, se descarta y se cuenta.
  - El contador `u32` da la vuelta al llegar al máximo; la comparación debe tenerlo en cuenta.
- **Rechazo** (U3): se descarta y se registra todo datagrama con magic o versión distintos, `plc_id` no configurado, longitud que no cuadra con `n` y tipos, o `signal_id` desconocido.

## 4. Calidad en cada protocolo de salida (borrador)

| Salida | Cómo se comunica una calidad mala |
|---|---|
| OPC UA | `StatusCode` del nodo (`Good` o `Bad`) |
| MQTT | campo `q` en el JSON del mensaje (`good`, `bad`) |
| Modbus TCP | no tiene campo de calidad: un registro de estado por estación, con un bit por señal |
| TCP propio | campo `quality` en la respuesta |

## 5. Convenciones

- Configuración en `config/pasarela.ini` (no versionado); `config/ejemplo.ini` documenta cada opción.
- Los logs llevan nivel, marca de tiempo y origen.
- Nombres de ficheros y de `path` en minúsculas con `_`, sin tildes ni espacios.

## 6. Preguntas abiertas

1. ¿Cómo genera el PLC `ts_origin` en milisegundos desde un `LDT` del S7-1500? Lo decide quien programe el PLC (2.4), de acuerdo con DL.
2. ¿Qué señales lleva cada PLC y con qué periodo? Lo acuerdan Redes y Automatización (D4).
3. ¿Qué PLC lleva cada uno de los dos que programamos (DL y DG)?
