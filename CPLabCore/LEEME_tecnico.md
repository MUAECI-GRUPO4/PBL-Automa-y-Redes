# CPLabCore: documentación y pruebas (12/11/2026)

- `doc/` fuente LaTeX (`tectonic main.tex`), `CPLabCore_guia_v1.0.1.pdf` es el resultado.
- `doc/gen_tablas.py` genera tablas desde el Excel, los UDT y los resultados (ejecutar antes de compilar).
- `fuentes/` SCL exportado de TIA (v1.0.0). `Est_FB_Estacion.scl` está CORREGIDO (línea 156); `Est_FB_Estacion_v1.0.0_con_error.scl` es el original.
- `ejemplos/` aplicaciones de ejemplo (Press, BackCover, Cámara); compilan en TIA V20.
- `sim/` simulador: `python3 test_libreria.py && python3 test_ejemplos.py && python3 gen_recorrido.py` (48 comprobaciones).
- `capturas/` capturas de TIA de la VM.
