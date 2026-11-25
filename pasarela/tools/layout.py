"""Layout de un miembro serializado con Serialize. El arbol viene del XML de TIA:
hoja {"t": tipo}, array {"arr": [lo, hi], "el": arbol}, struct {"m": [(nombre, arbol), ...]}.
Hipotesis (no hay documento de Siemens verificado; el PLC manda la longitud real y se elige la que cuadre):
  H1 empaquetado: BOOL = 1 byte, sin relleno
  H2 S7: BOOL en bits, tipos de mas de 1 byte en direccion par, struct alineado a par y relleno final a par
  H3 bits sin relleno: BOOL en bits, sin alineacion, struct redondeado a byte
"""
import struct

TAM = {"Bool": 1, "Byte": 1, "USInt": 1, "SInt": 1, "Char": 1, "Int": 2, "UInt": 2, "Word": 2,
       "DInt": 4, "UDInt": 4, "DWord": 4, "Real": 4, "Time": 4, "LInt": 8, "ULInt": 8, "LWord": 8, "LReal": 8}
FMT = {"Byte": ">B", "USInt": ">B", "SInt": ">b", "Char": ">B", "Int": ">h", "UInt": ">H", "Word": ">H", "DInt": ">i",
       "UDInt": ">I", "DWord": ">I", "Real": ">f", "Time": ">i", "LInt": ">q", "ULInt": ">Q", "LWord": ">Q", "LReal": ">d"}
SISTEMA = {"TON_TIME": [("IN", "Bool"), ("Q", "Bool"), ("PT", "Time"), ("ET", "Time")],
           "TOF_TIME": [("IN", "Bool"), ("Q", "Bool"), ("PT", "Time"), ("ET", "Time")],
           "TP_TIME": [("IN", "Bool"), ("Q", "Bool"), ("PT", "Time"), ("ET", "Time")],
           "R_TRIG": [("CLK", "Bool"), ("Q", "Bool")], "F_TRIG": [("CLK", "Bool"), ("Q", "Bool")],
           "DTL": [("YEAR", "UInt"), ("MONTH", "USInt"), ("DAY", "USInt"), ("WEEKDAY", "USInt"),
                   ("HOUR", "USInt"), ("MINUTE", "USInt"), ("SECOND", "USInt"), ("NANOSECOND", "UDInt")]}


def hoja_sistema(t):
    return {"m": [(n, {"t": tp}) for n, tp in SISTEMA[t]]}


def recorre(arbol, hip):
    """Lista (ruta, tipo, byte, bit) de las hojas y longitud total, segun la hipotesis."""
    out, pos = [], [0, 0]   # byte, bit

    def cierra_bits():
        if pos[1]:
            pos[0] += 1; pos[1] = 0

    def hoja(ruta, t):
        if t == "Bool":
            if hip == 1:
                out.append((ruta, t, pos[0], 0)); pos[0] += 1
            else:
                out.append((ruta, t, pos[0], pos[1])); pos[1] += 1
                if pos[1] == 8: cierra_bits()
        else:
            cierra_bits()
            if hip == 2 and TAM[t] > 1 and pos[0] % 2: pos[0] += 1
            out.append((ruta, t, pos[0], 0)); pos[0] += TAM[t]

    def anda(a, ruta, raiz=False):
        if "t" in a:
            hoja(ruta, a["t"])
        elif "arr" in a:
            for i in range(a["arr"][0], a["arr"][1] + 1):
                anda(a["el"], "%s[%d]" % (ruta, i))
            if a["el"].get("t") == "Bool": cierra_bits()
        else:
            cierra_bits()
            if hip == 2 and pos[0] % 2: pos[0] += 1
            for n, h in a["m"]:
                anda(h, ruta + "." + n if ruta else n)
            cierra_bits()
            if hip == 2 and pos[0] % 2: pos[0] += 1

    anda(arbol, "")
    cierra_bits()
    return out, pos[0]


def longitudes(arbol):
    return {h: recorre(arbol, h)[1] for h in (1, 2, 3)}


def decodifica(arbol, datos):
    """(hipotesis, {ruta: valor}) o (None, {}) si la longitud no cuadra con ninguna."""
    for h in (2, 1, 3):
        hojas, n = recorre(arbol, h)
        if n == len(datos):
            vals = {}
            for ruta, t, b, bit in hojas:
                vals[ruta or "valor"] = bool(datos[b] >> bit & 1) if t == "Bool" else struct.unpack_from(FMT[t], datos, b)[0]
            return h, vals
    return None, {}
