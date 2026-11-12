# CPLabCore

Librería de TIA Portal V20 con todo lo común de una estación de la CP-Lab (modos, emergencia, cinta, stopper, lector RFID y secuencia del palet), para que cada estación programe solo su aplicación.

**Empieza por la guía:** [`CPLabCore_guia_v1.0.1.pdf`](CPLabCore_guia_v1.0.1.pdf) (100 páginas: qué es, cómo instalarla y cómo migrar tu estación paso a paso).

> **Versión 1.0.1.** La v1.0.0 tenía un error en `Est_FB_Estacion` (la cinta no arrancaba). Si algún compañero tiene un `CPLabCore.zal20` anterior a la 1.0.1, que lo borre y use [`CPLabCore_v1.0.1.zal20`](CPLabCore_v1.0.1.zal20).

**Instalar:** en TIA Portal V20, panel *Libraries*, botón *Open global library*, tipo *Compressed libraries*, elegir el `.zal20`. Los pasos completos están en el capítulo 7 de la guía.

## Contenido

| Ruta | Qué es |
|---|---|
| `CPLabCore_v1.0.1.zal20` | La librería, lista para abrir en TIA Portal V20 |
| `CPLabCore_guia_v1.0.1.pdf` | La guía de uso y migración |
| `doc/` | Fuente LaTeX de la guía (`python3 gen_tablas.py` y `tectonic main.tex`) |
| `fuentes/` | Código SCL de la librería, exportado de TIA, y los UDT |
| `ejemplos/` | Aplicaciones de ejemplo de Press, BackCover y Cámara (compilan en TIA V20) |
| `sim/` | Simulador de pruebas (48 comprobaciones): `python3 test_libreria.py && python3 test_ejemplos.py` |
| `capturas/` | Capturas de TIA usadas en la guía |
| `doc/datos/Mapa_RFID_CPLab.xlsx` | Mapa de los 28 bytes del tag RFID acordado por el grupo |

## Estado

- Compilada en TIA Portal V20 e instalada en un proyecto vacío sin errores.
- 48 comprobaciones del simulador correctas con el arreglo de la v1.0.1.
- **No probada en la maqueta real.** Puntos abiertos en el apéndice E de la guía.
