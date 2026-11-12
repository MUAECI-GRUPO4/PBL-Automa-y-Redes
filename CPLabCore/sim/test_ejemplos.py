"""Prueba de los ejemplos de aplicacion (ejemplos/*.scl) integrados en la libreria, con un modelo fisico sencillo."""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_libreria as T
from scl_sim import Machine, load_udts

AQUI = os.path.dirname(os.path.abspath(__file__))
EJ = os.path.join(AQUI, '..', 'ejemplos')
OUT = []


def check(n, c, d=''):
    OUT.append(dict(nombre=n, ok=bool(c)))
    print(('  OK  ' if c else '  FALLO ') + n + (('  -> ' + d) if d and not c else ''))


class BancoEj(T.Banco):
    """Banco con un FB de ejemplo como aplicacion + 'hw' (sensores simulados) que reacciona a sus salidas."""

    def __init__(self, fb, masc, tag, hw_step, pins_in, pins_out):
        T.Banco.__init__(self, fb, 'plantilla', tag=tag, masc=masc)
        srcs = [open(os.path.join(EJ, fb + '.scl'), encoding='utf-8').read()]
        self.m.fbs.update({k: v for k, v in Machine(srcs, self.m.udts).fbs.items()})
        self.g['app'] = self.m.new_instance(fb)
        self.fb, self.hw_step, self.pins_in, self.pins_out = fb, hw_step, pins_in, pins_out
        self.hw = dict(pins_in)
        self.g['hw'] = self.hw
        self.salidas_hw = {}

    def scan(self):  # igual que el del banco base, pero la app lleva pines fisicos
        g, db = self.g, self.g['DB']
        e = self.ent
        if e:
            g['Entradas_Basico'].update({k: e[k] for k in ('Boton_marcha', 'Boton_paro', 'Selector_modo', 'Boton_rearme',
                                                           'Sensor_ind_bien_pos', 'Seta_emergencia', 'Sensor_palet_izq',
                                                           'Sensor_palet_dch')})
            g['Entradas_Stopper'].update(Sensor_stopper_abajo=e['stopper_abajo'], Sensor_ind_0=e['ind0'])
            g['Entradas_RFID'].update(e['rfid'])
        self.m.now_ms = int(round(self.t_plc * 1000))
        ref = lambda *p: ('ref', p)  # noqa: E731
        params = [('InBasico', 'in', ref('Entradas_Basico')), ('InRFID', 'in', ref('Entradas_RFID')),
                  ('InStopper', 'in', ref('Entradas_Stopper')),
                  ('Direccion_lectura', 'in', ('lit', 0)), ('Direccion_escritura', 'in', ('lit', 0)),
                  ('Mascara_lectura', 'in', ('lit', self.masc[0])), ('Mascara_escritura', 'in', ('lit', self.masc[1])),
                  ('OutBasico', 'in', ref('Salidas_Basico')), ('OutRFID', 'in', ref('Salidas_RFID')),
                  ('Imagen_palet', 'in', ref('DB', 'Imagen_palet'))]
        for n in ('App_en_reposo', 'App_terminada', 'App_alarma', 'App_rearme_requerido', 'Inhibir_cinta'):
            params.append((n, 'in', ref('DB', n)))
        for n in ('App_inicio', 'Emergencia', 'Rearme'):
            params.append((n, 'out', ref('DB', n)))
        self.m.call(('est',), params, g)
        ap = [('App_inicio', 'in', ref('DB', 'App_inicio')), ('Emergencia', 'in', ref('DB', 'Emergencia')),
              ('Imagen_palet', 'in', ref('DB', 'Imagen_palet'))]
        ap += [(p, 'in', ref('hw', p)) for p in self.pins_in]
        for n in ('App_en_reposo', 'App_terminada', 'App_alarma', 'App_rearme_requerido', 'Inhibir_cinta'):
            ap.append((n, 'out', ref('DB', n)))
        for n in self.pins_out:
            self.salidas_hw.setdefault(n, 0)
            g.setdefault('hwo', {})[n] = self.salidas_hw[n]
            ap.append((n, 'out', ref('hwo', n)))
        self.m.call(('app',), ap, g)
        self.salidas_hw = dict(g['hwo'])
        self.hw_step(self)
        sb, sr = g['Salidas_Basico'], g['Salidas_RFID']
        self.q = dict(cinta=sb['Cinta_dch'], stopper_baja=sb['Bajar_stopper'], leer=sr['Tag_leer'],
                      escribir=sr['Tag_escribir'], ant_off=sr['Tag_antena_apagar'],
                      dir=sr['Tag_direccion_leer_escribir'], datos=list(sr['Tag_datos_a_escribir']))


def tag_con(**kw):
    t = list(T.BLOQUE)
    for k, v in kw.items():
        t[int(k[1:])] = v
    return t


def ciclo(b, extra=lambda b: None, t_max=90):
    b.wait(0.3)
    b.pulso('marcha')
    b.p.entra_palet()
    ok = b.until(lambda: b.p.palet == 0 and b.p.t > 3 and b.p.escrituras != [], t_max)
    b.until(lambda: b.g['est']['Etapa_gestion'] == 0, 10)
    return ok


# ------------------------------------------------------------------ Press
def hw_press(b):
    h, o, t = b.hw, b.salidas_hw, b.t_plc
    st = b.__dict__.setdefault('pr', dict(z=1.0))
    if o.get('Prensa_bajar'):
        st['z'] = max(0.0, st['z'] - 0.01 / 0.3)
    elif o.get('Prensa_subir'):
        st['z'] = min(1.0, st['z'] + 0.01 / 0.3)
    h['Prensa_arriba'] = st['z'] >= 0.999
    h['Prensa_presion_inferior'] = st['z'] <= 0.001
    h['Hay_tapa_trasera'] = True


def prueba_press():
    print('\n== Ejemplo Press ==')
    ml, me = T.mascaras('Press')
    ini = tag_con(**{'b4': 3, 'b12': 3, 'b13': 2, 'b14': 0x07, 'b15': 0xD0, 'b16': 0})
    b = BancoEj('FB_App_Press_Ejemplo', (ml, me), ini, hw_press,
                dict(Prensa_arriba=True, Prensa_presion_inferior=False, Hay_tapa_trasera=True),
                ['Prensa_bajar', 'Prensa_subir'])
    ok = ciclo(b)
    f = b.p.tag[:28]
    check('Press: completa el ciclo', ok)
    check('Press: golpes realizados = 2 (byte 16)', f[16] == 2, str(f[16]))
    check('Press: bit 2 de "completadas" puesto (byte 4 = 7)', f[4] == 7, str(f[4]))
    check('Press: el resto del bloque intacto', all(f[i] == ini[i] for i in range(28) if i not in (4, 16)))
    # sin tapa trasera marcada: no prensa
    ini2 = tag_con(**{'b4': 3, 'b12': 0, 'b13': 2, 'b16': 0})
    b2 = BancoEj('FB_App_Press_Ejemplo', (ml, me), ini2, hw_press,
                 dict(Prensa_arriba=True, Prensa_presion_inferior=False, Hay_tapa_trasera=True),
                 ['Prensa_bajar', 'Prensa_subir'])
    ciclo(b2)
    f2 = b2.p.tag[:28]
    check('Press: sin tapa trasera en el tag no prensa ni marca completada', f2[4] == 3 and f2[16] == 0, str(f2[4:17]))
    # no pedida
    ini3 = tag_con(**{'b3': 0x05, 'b4': 3, 'b12': 3, 'b13': 2, 'b16': 0})   # Camara + Press? 0x05 = Cam + Press
    ini3[3] = 0x03                                                         # solo Camara y BackCover
    b3 = BancoEj('FB_App_Press_Ejemplo', (ml, me), ini3, hw_press,
                 dict(Prensa_arriba=True, Prensa_presion_inferior=False, Hay_tapa_trasera=True),
                 ['Prensa_bajar', 'Prensa_subir'])
    ciclo(b3)
    f3 = b3.p.tag[:28]
    check('Press: si no esta en "estaciones a realizar", el palet pasa sin cambios', f3 == ini3, str(f3))
    return b


# ------------------------------------------------------------------ BackCover
def hw_back(b):
    h, o = b.hw, b.salidas_hw
    st = b.__dict__.setdefault('bc', dict(t=0.0))
    st['t'] = st['t'] + 0.01 if o.get('Colocar_tapa') else 0.0
    h['Tapa_colocada'] = st['t'] > 0.5 and not b.__dict__.get('sin_confirmar', False)


def prueba_backcover():
    print('\n== Ejemplo BackCover ==')
    ml, me = T.mascaras('BackCover')
    ini = tag_con(**{'b4': 1, 'b12': 0})
    pins = dict(Tapa_frontal_presente=True, Tapa_trasera_presente=False, Almacen_vacio=False, Tapa_colocada=False)
    b = BancoEj('FB_App_BackCover_Ejemplo', (ml, me), ini, hw_back, dict(pins),
                ['Colocar_tapa'])
    ok = ciclo(b)
    f = b.p.tag[:28]
    check('BackCover: completa el ciclo', ok)
    check('BackCover: estado = requerida + colocada (byte 12 = 3)', f[12] == 3, str(f[12]))
    check('BackCover: bit 1 de "completadas" (byte 4 = 3)', f[4] == 3, str(f[4]))
    check('BackCover: el resto del bloque intacto', all(f[i] == ini[i] for i in range(28) if i not in (4, 12)))
    pins2 = dict(pins, Almacen_vacio=True)
    b2 = BancoEj('FB_App_BackCover_Ejemplo', (ml, me), ini, hw_back, pins2, ['Colocar_tapa'])
    ciclo(b2)
    f2 = b2.p.tag[:28]
    check('BackCover: sin stock -> byte 12 = requerida + falta stock (5) y sin bit de completada',
          f2[12] == 5 and f2[4] == 1, '%s %s' % (f2[12], f2[4]))
    return b


# ------------------------------------------------------------------ Camara
def hw_cam(b):
    h, o = b.hw, b.salidas_hw
    st = b.__dict__.setdefault('cm', dict(t=0.0, job=None))
    st['t'] = st['t'] + 0.01 if o.get('Camara_disparar') else 0.0
    if o.get('Camara_disparar') and st['job'] is None:
        st['job'] = o.get('Camara_job')
        b.job_usado = st['job']
    if not o.get('Camara_disparar'):
        st['job'] = None
    h['Camara_lista'] = st['t'] > 0.4
    h['Camara_id_imagen'] = 42


def prueba_camara():
    print('\n== Ejemplo Camara ==')
    ml, me = T.mascaras('Camara')
    base = dict(Camara_lista=False, Camara_resultado_ok=True, Camara_orientacion_ok=True, Camara_id_imagen=0)
    # tag vacio -> inicializa; sin fusibles -> job por defecto
    b = BancoEj('FB_App_Camara_Ejemplo', (ml, me), [0] * 28, hw_cam, dict(base), ['Camara_disparar', 'Camara_job'])
    ok = ciclo(b)
    f = b.p.tag[:28]
    check('Camara: completa el ciclo con el tag vacio', ok)
    check('Camara: inicializa el bloque (byte 0 = A5)', f[0] == 0xA5, str(f[0]))
    check('Camara: usa el job por defecto (4) sin datos', getattr(b, 'job_usado', None) == 4, str(getattr(b, 'job_usado', None)))
    check('Camara: calidad OK (5=1), resultado (9=7), ImageID (10=42), intentos (11=1), completada (4=1)',
          (f[5], f[9], f[10], f[11], f[4]) == (1, 7, 42, 1, 1), str((f[5], f[9], f[10], f[11], f[4])))
    # NOK
    nok = dict(base, Camara_resultado_ok=False)
    b2 = BancoEj('FB_App_Camara_Ejemplo', (ml, me), tag_con(**{'b8': 0, 'b20': 2}), hw_cam, nok, ['Camara_disparar', 'Camara_job'])
    ciclo(b2)
    f2 = b2.p.tag[:28]
    check('Camara: job deducido de los fusibles (byte 20 = 2 -> job 3)', getattr(b2, 'job_usado', None) == 3,
          str(getattr(b2, 'job_usado', None)))
    check('Camara: NOK -> calidad 2 y rechazo 16#11', (f2[5], f2[6]) == (2, 0x11), str((f2[5], f2[6])))
    check('Camara: los bytes que no escribe (8, 20) no cambian',
          f2[8] == 0 and f2[20] == 2 and f2[12:20] == T.BLOQUE[12:20])
    return b


if __name__ == '__main__':
    prueba_press()
    prueba_backcover()
    prueba_camara()
    falla = [o for o in OUT if not o['ok']]
    res = json.load(open(os.path.join(AQUI, '..', 'resultados.json')))
    res['ejemplos'] = OUT
    json.dump(res, open(os.path.join(AQUI, '..', 'resultados.json'), 'w'), indent=1)
    print('\n%d comprobaciones de ejemplos, %d fallos' % (len(OUT), len(falla)))
    sys.exit(1 if falla else 0)
