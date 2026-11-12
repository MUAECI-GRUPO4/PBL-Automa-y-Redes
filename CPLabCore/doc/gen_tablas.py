"""Genera las tablas LaTeX a partir de datos/Mapa_RFID_CPLab.xlsx y de la logica de mascaras (la misma que prueban los tests)."""
import re, sys, zipfile, xml.etree.ElementTree as ET
sys.path.insert(0, '../sim')
import test_libreria as T

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def leer_xlsx(path):
    z = zipfile.ZipFile(path)
    ss = [''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS)]
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    hojas = {}
    for i, s in enumerate(wb.find('m:sheets', NS), 1):
        filas = []
        for row in ET.fromstring(z.read('xl/worksheets/sheet%d.xml' % i)).iter('{%s}row' % NS['m']):
            d = {}
            for c in row.findall('m:c', NS):
                v = c.find('m:v', NS)
                if v is None:
                    continue
                col = re.match(r'[A-Z]+', c.get('r')).group()
                d[col] = ss[int(v.text)] if c.get('t') == 's' else v.text
            filas.append((int(row.get('r')), d))
        hojas[s.get('name')] = filas
    return hojas


def esc(s):
    s = str(s)
    for a, b in (('\\', '\\textbackslash{}'), ('&', '\\&'), ('%', '\\%'), ('#', '\\#'), ('_', '\\_'), ('$', '\\$')):
        s = s.replace(a, b)
    for a, b in (('←', '$\\leftarrow$'), ('→', '$\\rightarrow$'), ('·', '\\,\\textperiodcentered\\,'), ('≥', '$\\geq$'),
                 ('ª', '\\textordfeminine{}'), ('º', '\\textordmasculine{}')):
        s = s.replace(a, b)
    return s


def entero(x):
    try:
        return str(int(float(x)))
    except Exception:
        return x


h = leer_xlsx('datos/Mapa_RFID_CPLab.xlsx')
mapa = [d for r, d in h['Mapa RFID'] if 6 <= r <= 29]

COL = {'General': 'gris', 'Cámara': 'cam', 'BackCover': 'back', 'Press': 'press', 'Out': 'out', 'Compartido': 'comp'}

# ---- tabla completa del mapa
with open('datos/tabla_mapa.tex', 'w') as f:
    f.write('\\begin{longtable}{>{\\raggedleft\\arraybackslash}p{0.9cm}p{3.6cm}p{2.0cm}p{2.5cm}p{2.3cm}p{3.5cm}}\n')
    f.write('\\toprule\n\\textbf{Byte} & \\textbf{Campo} & \\textbf{Estación} & \\textbf{Lo escribe} & \\textbf{Lo lee} & \\textbf{Valores} \\\\\n\\midrule\n\\endhead\n')
    for d in mapa:
        off, n = int(float(d['A'])), int(float(d['B']))
        rango = str(off) if n == 1 else '%d--%d' % (off, off + n - 1)
        est = d['F']
        f.write('\\rowcolor{%s!18}%s & %s & %s & %s & %s & %s \\\\\n' % (
            COL.get(est, 'gris'), rango, esc(d['E']), esc(est), esc(d['G']), esc(d['H']), esc(d['I'])))
    f.write('\\bottomrule\n\\end{longtable}\n')

# ---- logica por estacion (hoja 3)
with open('datos/tabla_logica.tex', 'w') as f:
    f.write('\\begin{tabularx}{\\textwidth}{>{\\bfseries}l p{2.6cm} p{3.6cm} X}\n\\toprule\nEstación & Lee (bytes) & Escribe (bytes) & Secuencia resumida \\\\\n\\midrule\n')
    for r, d in h['Lógica estaciones']:
        if r >= 4:
            f.write('%s & %s & %s & %s \\\\\n\\midrule\n' % tuple(esc(d.get(k, '')) for k in 'ABCD'))
    f.write('\\bottomrule\n\\end{tabularx}\n')

# ---- mascaras de las cuatro estaciones
nombres = {'Camara': 'Cámara', 'BackCover': 'BackCover', 'Press': 'Press', 'Out': 'Out'}
with open('datos/tabla_mascaras.tex', 'w') as f:
    f.write('\\begin{tabularx}{\\textwidth}{>{\\bfseries}l p{3.1cm} c c X}\n\\toprule\nEstación & Bytes que usa & \\texttt{Mascara\\_lectura} & \\texttt{Mascara\\_escritura} & Qué escribe \\\\\n\\midrule\n')
    quien = {'Camara': 'bytes 0 a 6 (los 0 a 3 solo si el tag está vacío), 9, 10 y 11',
             'BackCover': 'byte 4 (bit 1) y byte 12',
             'Press': 'byte 4 (bit 2) y byte 16',
             'Out': 'los 28 bytes: deja el bloque a cero'}
    for k, c in T.ESTACIONES.items():
        ml, me = T.mascaras(k)
        f.write('%s & %s & \\texttt{16\\#%08X} & \\texttt{16\\#%08X} & %s \\\\\n' % (
            nombres[k], ', '.join(str(x) for x in sorted(set(c['lee']) | set(c['escribe']) if k != 'Out' else c['lee'])), ml, me, quien[k]))
    f.write('\\bottomrule\n\\end{tabularx}\n')

# ---- esquema TikZ del bloque de 28 bytes, coloreado por estacion
campos = {}
for d in mapa:
    off, n = int(float(d['A'])), int(float(d['B']))
    for i in range(off, off + n):
        campos[i] = (d['F'], d['E'])
with open('datos/fig_bloque.tex', 'w') as f:
    f.write('\\begin{tikzpicture}[x=0.585cm,y=1cm]\n')
    for fila, ini in enumerate((0, 14)):
        y = -1.55 * fila
        for i in range(ini, ini + 14):
            est, _ = campos[i]
            x = i - ini
            f.write('\\fill[%s!35] (%d,%.2f) rectangle (%d,%.2f);\\draw[gray!70] (%d,%.2f) rectangle (%d,%.2f);\n' % (
                COL[est], x, y, x + 1, y + 0.8, x, y, x + 1, y + 0.8))
            f.write('\\node[font=\\scriptsize\\bfseries] at (%.1f,%.2f) {%d};\n' % (x + .5, y + .4, i))
    f.write('\\end{tikzpicture}\n')
print('tablas generadas')

# ---- direcciones de los UDT (bit a bit) a partir de los XML exportados de TIA
from scl_sim import load_udts, layout, array_len
import glob
udts = load_udts(glob.glob('../fuentes/type_*.xml'))
BASE = [('UDT_Entradas_Basico', 'I', 1, 'Entradas\\_Basico'), ('UDT_Salidas_Basico', 'Q', 1, 'Salidas\\_Basico'),
        ('UDT_Entradas_Stopper', 'I', 42, 'Entradas\\_Stopper'), ('UDT_Entradas_RFID', 'I', 10, 'Entradas\\_RFID'),
        ('UDT_Salidas_RFID', 'Q', 10, 'Salidas\\_RFID')]
with open('datos/tabla_udt.tex', 'w') as f:
    for nombre, area, base, tag in BASE:
        f.write('\\subsection*{\\texttt{%s}}\nTag \\texttt{%s}, desde \\texttt{\\%%%s%d.0}.\\par\\smallskip\n' % (esc(nombre), tag, area, base))
        f.write('\\begin{tabular}{>{\\ttfamily\\small}p{5.2cm}>{\\ttfamily\\small}p{4.2cm}>{\\ttfamily\\small}p{2.4cm}}\n\\toprule\n\\textnormal{\\textbf{Miembro}} & \\textnormal{\\textbf{Tipo}} & \\textnormal{\\textbf{Dirección}} \\\\\n\\midrule\n')
        for n, t, b, bit in layout(udts[nombre], base):
            if t == 'Bool':
                d = '%%%s%d.%d' % (area, b, bit)
            elif t == 'Byte':
                d = '%%%sB%d' % (area, b)
            elif t == 'Word':
                d = '%%%sW%d' % (area, b)
            else:
                d = '%%%s%d.0 ... %%%s%d.7' % (area, b, area, b + array_len(t) - 1)
            f.write('%s & %s & %s \\\\\n' % (esc(n), esc(t), esc(d)))
        f.write('\\bottomrule\n\\end{tabular}\n\n\\medskip\n')
print('udt ok')

# ---- lista de comprobaciones del simulador
import json
res = json.load(open('../resultados.json'))
with open('datos/tabla_pruebas.tex', 'w') as f:
    f.write('\\begin{longtable}{r p{12.2cm} c}\n\\toprule\n\\textbf{N.º} & \\textbf{Comprobación} & \\textbf{Resultado} \\\\\n\\midrule\n\\endhead\n')
    n = 0
    for grupo, titulo in (('comprobaciones', 'Librería'), ('ejemplos', 'Ejemplos de aplicación')):
        f.write('\\multicolumn{3}{l}{\\sffamily\\bfseries\\color{azul} %s}\\\\\n' % titulo)
        for c in res[grupo]:
            n += 1
            f.write('%d & %s & %s \\\\\n' % (n, esc(c['nombre']), '\\textcolor{verde}{\\ding{51}}' if c['ok'] else '\\textcolor{rojo}{\\ding{55}}'))
    f.write('\\bottomrule\n\\end{longtable}\n')
print('pruebas', n)
