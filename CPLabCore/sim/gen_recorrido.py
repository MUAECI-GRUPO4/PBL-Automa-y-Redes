"""Recorrido de un palet por Camara -> BackCover -> Press -> Out con el codigo real (libreria + ejemplos). Escribe doc/datos/tabla_recorrido.tex"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_libreria as T
import test_ejemplos as E

AQUI = os.path.dirname(os.path.abspath(__file__))
ini = [0] * 28
ini[0], ini[1], ini[2], ini[3] = 0xA5, 7, 1, 0x0F      # lo deja la HMI o la 1a estacion
ini[13], ini[14], ini[15] = 2, 0x07, 0xD0                # 2 golpes de 2000 ms
pasos = [('Inicio', ini)]

ml, me = T.mascaras('Camara')
b = E.BancoEj('FB_App_Camara_Ejemplo', (ml, me), ini, E.hw_cam, dict(Camara_lista=False, Camara_resultado_ok=True,
              Camara_orientacion_ok=True, Camara_id_imagen=0), ['Camara_disparar', 'Camara_job'])
E.ciclo(b); t1 = b.p.tag[:28]; pasos.append(('Cámara', t1))
ml, me = T.mascaras('BackCover')
b = E.BancoEj('FB_App_BackCover_Ejemplo', (ml, me), t1, E.hw_back, dict(Tapa_frontal_presente=True, Tapa_trasera_presente=False,
              Almacen_vacio=False, Tapa_colocada=False), ['Colocar_tapa'])
E.ciclo(b); t2 = b.p.tag[:28]; pasos.append(('BackCover', t2))
ml, me = T.mascaras('Press')
b = E.BancoEj('FB_App_Press_Ejemplo', (ml, me), t2, E.hw_press, dict(Prensa_arriba=True, Prensa_presion_inferior=False,
              Hay_tapa_trasera=True), ['Prensa_bajar', 'Prensa_subir'])
E.ciclo(b); t3 = b.p.tag[:28]; pasos.append(('Press', t3))
ml, me = T.mascaras('Out')
app = T.AppPy(T.LOGICA['Out'])
b = T.Banco('Out', app, tag=t3, masc=(ml, me))
b.ciclo_completo(); t4 = b.p.tag[:28]; pasos.append(('Out', t4))

campos = {0: 'Marca de bloque válido', 1: 'ID de palet', 2: 'Receta', 3: 'Estaciones a realizar', 4: 'Estaciones completadas',
          5: 'Calidad global', 6: 'Código de rechazo', 8: 'Job de la cámara', 9: 'Resultado de la cámara', 10: 'ImageID',
          11: 'Intentos de inspección', 12: 'Estado BackCover', 13: 'Nº de golpes', 14: 'Tiempo de prensado (alto)',
          15: 'Tiempo de prensado (bajo)', 16: 'Golpes realizados'}
filas = [i for i in range(28) if any(p[1][i] for p in pasos)]
with open(os.path.join(AQUI, '..', 'doc', 'datos', 'tabla_recorrido.tex'), 'w') as f:
    f.write('\\begin{tabular}{r l' + ' r' * len(pasos) + '}\n\\toprule\nByte & Campo & ' + ' & '.join('\\textbf{%s}' % p[0] for p in pasos) + ' \\\\\n\\midrule\n')
    for i in filas:
        vals = []
        prev = None
        for n, t in pasos:
            v = t[i]
            cel = '\\texttt{%02X}' % v
            if prev is not None and v != prev:
                cel = '\\cellcolor{naranja!25}' + cel
            vals.append(cel)
            prev = v
        f.write('%d & %s & %s \\\\\n' % (i, campos.get(i, ''), ' & '.join(vals)))
    f.write('\\bottomrule\n\\end{tabular}\n')
json.dump({n: t for n, t in pasos}, open(os.path.join(AQUI, '..', 'recorrido.json'), 'w'))
print('\n'.join('%-10s %s' % (n, ' '.join('%02X' % x for x in t)) for n, t in pasos))
