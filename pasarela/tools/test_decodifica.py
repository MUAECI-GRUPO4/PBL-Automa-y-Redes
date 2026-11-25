#!/usr/bin/env python3
"""Rellena cada bloque con ceros del tamaño que daria cada hipotesis de Serialize, monta el datagrama
como el FB (cabecera 18 B + id, longitud, datos) y comprueba que se decodifica y que se trocea bien."""
import glob, json, struct, sys
import layout
import os
SENALES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "senales")
from escucha_udp import carga, decodifica

CARPETA = sys.argv[1] if len(sys.argv) > 1 else SENALES
tablas = carga(CARPETA)
total = hip = 0
for f in glob.glob(CARPETA + "/senales_*.json"):
    d = json.load(open(f))
    for h in (1, 2, 3):
        cuerpo = b""
        for e in d["bloques"]:
            ln = e["lon"][str(h)]
            cuerpo += struct.pack(">HH", e["id"], ln) + bytes(ln)
        # troceo como el FB: bloques enteros, <= 1380 B
        i = 0; seq = 0
        while i < len(cuerpo):
            j, n = i, 0
            while j < len(cuerpo):
                ln = struct.unpack(">H", cuerpo[j + 2:j + 4])[0] + 4
                if j - i + ln > 1380 and n: break
                j += ln; n += 1
            dat = b"PG" + bytes([2, d["plc_id"]]) + struct.pack(">IQH", seq, 1700000000000, n) + cuerpo[i:j]
            assert len(dat) <= 1400
            plc, s, ts, vals, raros = decodifica(dat, tablas)
            assert not raros, raros[:2]
            total += len(vals); i = j; seq += 1
        hip += 1
    print(d["plc"], "ok: hipotesis 1, 2 y 3")
print(total, "valores decodificados en", hip, "pruebas")
