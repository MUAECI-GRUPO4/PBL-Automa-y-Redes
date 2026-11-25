# Lado PLC: envío UDP a la pasarela (tarea 2.4)

Cada PLC de la maqueta (Cámara = 1, BackCover = 2, Prensa = 3, Out = 4; el Escritor no) manda por UDP **todas** sus variables cada 100 ms. Formato del datagrama: [`docs/contratos.md`](../../docs/contratos.md) y [`docs/diagramas/datagrama-udp.svg`](../../docs/diagramas/datagrama-udp.svg).

## Qué hay aquí
| Archivo | Contenido |
|---|---|
| `scl/FB_UDP_Pasarela_<PLC>.scl` | bloque de función: conexión `TCON`, temporización y envío con `TUSEND` |
| `scl/FC_UDP_Bloque_<PLC>.scl` | serializa cada variable con `Serialize` y la añade al datagrama como bloque `id \| len \| datos` |
| `scl/OB_UDP_Pasarela.scl` | OB cíclico (n.º 123) que llama al FB |
| `plantilla_*.scl` | plantillas de las que un generador (script local, no incluido) produjo lo anterior; `@...@` se sustituye por PLC |

Los `.scl` son **generados**: no se editan a mano. Se importan a TIA Portal como fuente externa.

## Cómo se exportaron los datos
1. Se exportan en XML los bloques de cada PLC con TIA Openness (solo lectura): instancias de DB (Input/Output/Static), DB globales y tags de E/S/M.
2. Un generador lee el XML y escribe, por PLC, el FB y el FC con **un bloque por miembro**. Asigna un `block_id` en orden y guarda el árbol de tipos en `tools/senales/senales_<PLC>.json` (y una tabla legible en `.csv`).
3. Se importan al proyecto (DB n.º 900, OB 123) y se compila. Cada miembro se copia a una variable local antes de serializar, porque `Serialize` rechaza variables de solo lectura (entradas, `Q/ET/IN/PT` de temporizadores).
4. En el PLC: `TCON_IP_v4` con `ActiveEstablished = FALSE`, `InterfaceId = 64`, `ID = 1`; `TUSEND` con `TADDR_Param`.

Parámetros del FB (`DB_UDP_Pasarela`): `Ip_pasarela` (por defecto `172.21.0.200`), `Puerto` (0 = 5000), `Periodo` (0 = 100 ms), `Deshabilitar`. Salidas de diagnóstico: `Conectado`, `Enviados`, `Fallidos`, `Bloques_omitidos`, `Estado_tcon`, `Estado_tusend`, `Intentos_tcon`, `Errores_tcon`, `Conexiones_ok`, `Ultimo_error_tcon`.

## Hecho con ayuda de Claude
Las partes más tediosas (enumerar cientos de variables por PLC y escribir el SCL que las envía) las generamos con scripts que escribió Claude (Anthropic) bajo nuestra dirección. Elegimos el diseño y las alternativas; revisamos el resultado y lo probamos con los PLC reales.

- **`exportar.ps1`** (PowerShell + TIA Openness, solo lectura): se engancha al TIA Portal abierto y exporta a XML, por cada PLC, los bloques, los tipos y las tablas de variables.
- **`generar.py`**: lee ese XML, recorre los DB y tags y despliega los miembros (structs, arrays y UDT). Reparte las señales en bloques que quepan en un datagrama (<1380 B), asigna el `block_id` y escribe a partir de las plantillas el FB, el FC y el OB de cada PLC. Genera también las tablas `senales_<PLC>.json/csv` con el árbol de tipos, que usa el receptor para decodificar.
- Otros dos scripts de PowerShell importaron los SCL al proyecto de TIA y los compilaron.

Los scripts no están en el repo (solo su resultado). Todo SCL generado se compiló sin errores y se contrastó con tráfico real antes de darlo por bueno.

## Por qué así
Primero probamos a leer la memoria cruda con `PEEK_BLK` (peek/poke): es lo más simple, pero los bytes salen sin nombres ni tipos y no sirve con DB optimizados. Valoramos también un UDT de pasarela escrito a mano (legible, pero solo salen las señales elegidas), una primera versión con una entrada por variable (~2000 líneas de SCL por PLC, descartada) y el servidor OPC UA del PLC (no es UDP). Nos quedamos con `Serialize` por bloques.

| Ventajas | Desventajas |
|---|---|
| Sale **todo** (DB optimizados incluidos) con un FC corto e igual en los 4 PLC | La disposición de bytes de `Serialize` no está documentada oficialmente: la comprobamos con tráfico real (H2) |
| Un formato uniforme: el receptor se genera de las tablas de señales | Los `block_id` cambian si cambia el programa: hay que regenerar |
| Los tipos nuevos no exigen código nuevo | ~2,1 kB por foto: 2 datagramas y más carga de CPU del PLC que un envío selectivo |
| | Algunos miembros solo lectura exigen copia previa a una variable local |

## Datagrama v2 (resumen)
Cabecera de 18 B: `"PG"`, versión = 2, `plc_id`, `seq` u32, `ts_origin` u64 (ms UTC), `n` u16. Después `n` bloques `block_id u16 | len u16 | datos`. Menos de 1380 B de bloques por datagrama, siempre bloques enteros: una foto completa (~2,1 kB) son 2 datagramas.

La disposición real de `Serialize` (bits y bytes alineados al estilo S7, hipótesis H2 de `tools/layout.py`) se comprobó con tráfico real: 4 PLC, ~15 datagramas/s cada uno, 0 perdidos, 4621 bloques decodificados.

## Si cambia el código de un PLC
Los `block_id` cambian (se asignan en orden), así que hay que volver a exportar, regenerar e importar, y usar los `senales_<PLC>.json` nuevos en la pasarela.

## Probar la recepción
Ver [`../../tools/README.md`](../../tools/README.md). La IP de la pasarela es del PC (172.21.0.200): los PLC solo alcanzan la red 172.21.x.x y el cortafuegos debe dejar entrar UDP al puerto 5000.
