#!/usr/bin/env python3
"""Escucha datagramas UDP de los PLC (contrato seccion 3) y los decodifica con senales/senales_<plc>.json.

Formato v2 (bloques serializados). Uso: escucha_udp.py [puerto=5000] [carpeta_senales=./senales]
Muestra por PLC: perdidos, duplicados, desordenados y las señales del ultimo datagrama.
Sin argumentos de verbose imprime un resumen cada 2 s. Es una herramienta de prueba, no el conector de la pasarela.
"""
import glob, json, socket, struct, sys, time
import layout
import os
SENALES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "senales")

def carga(carpeta):
    tablas = {}
    for f in glob.glob(carpeta + "/senales_*.json"):
        d = json.load(open(f))
        tablas[d["plc_id"]] = dict(nombre=d["estacion"], ids={e["id"]: e for e in d["bloques"]})
    return tablas


def decodifica(dat, tablas):
    """(plc_id, seq, ts_origin, {path: valor}, [paths sin decodificar]) o ValueError (rechazo U3).
    Cada bloque lleva id y longitud real medida por el PLC; layout.py elige la hipotesis de Serialize que cuadra."""
    if len(dat) < 18 or dat[:2] != b"PG" or dat[2] != 2:
        raise ValueError("magic o version")
    plc, seq, ts, n = dat[3], *struct.unpack(">IQH", dat[4:18])
    if plc not in tablas:
        raise ValueError("plc_id %d no configurado" % plc)
    pos, vals, raros = 18, {}, []
    for _ in range(n):
        bid, ln = struct.unpack(">HH", dat[pos:pos + 4]); pos += 4
        e = tablas[plc]["ids"].get(bid)
        if e is None or pos + ln > len(dat):
            raise ValueError("block_id %d desconocido o bloque cortado" % bid)
        arbol = e["arbol"]
        arbol = tuple_arbol(arbol)
        h, v = layout.decodifica(arbol, dat[pos:pos + ln]); pos += ln
        if h is None:
            raros.append("%s (%d B, esperado %s)" % (e["path"], ln, e["lon"]))
        else:
            vals.update({(e["path"] + "/" + k.replace(".", "/") if k != "valor" else e["path"]): x for k, x in v.items()})
    if pos != len(dat):
        raise ValueError("longitud no cuadra: %d de %d" % (pos, len(dat)))
    return plc, seq, ts, vals, raros


def tuple_arbol(a):
    """El JSON guarda los struct como listas [nombre, arbol]: layout.py las espera igual."""
    if "m" in a:
        return {"m": [(n, tuple_arbol(h)) for n, h in a["m"]]}
    if "el" in a:
        return {"arr": a["arr"], "el": tuple_arbol(a["el"])}
    return a


def main():
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    tablas = carga(sys.argv[2] if len(sys.argv) > 2 else SENALES)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("0.0.0.0", puerto)); s.settimeout(0.5)
    est = {p: dict(ultimo=None, rx=0, perdidos=0, dup=0, desorden=0, rechazos=0, senales={}) for p in tablas}
    t0 = time.time()
    while True:
        try:
            dat, dire = s.recvfrom(2048)
        except socket.timeout:
            dat = None
        if dat:
            try:
                plc, seq, ts, vals, raros = decodifica(dat, tablas)
                for r in raros: print('layout no cuadra en plc %d: %s' % (plc, r))
                e = est[plc]; e["rx"] += 1; e["senales"].update(vals)
                if e["ultimo"] is not None:
                    paso = (seq - e["ultimo"]) & 0xFFFFFFFF
                    if paso == 0: e["dup"] += 1
                    elif paso < 0x80000000: e["perdidos"] += paso - 1
                    else: e["desorden"] += 1; continue
                e["ultimo"] = seq
            except (ValueError, struct.error) as ex:
                for e in est.values(): pass
                print("rechazado de %s: %s" % (dire[0], ex))
        if time.time() - t0 > 2:
            t0 = time.time()
            for p, e in est.items():
                print("plc %d (%s): rx=%d perdidos=%d dup=%d desorden=%d senales=%d" % (
                    p, tablas[p]["nombre"], e["rx"], e["perdidos"], e["dup"], e["desorden"], len(e["senales"])))


if __name__ == "__main__":
    main()
