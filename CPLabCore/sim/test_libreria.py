"""Banco de pruebas de la libreria CPLabCore v1.0.0 (fuentes SCL tal cual salen de TIA).

Ejecuta Est_FB_Estacion (y sus FB) contra un modelo de cinta + stopper + lector RFID real
(bloque de 28 bytes, sin eco de la orden, dato valido solo cuando "listo" vuelve a subir).
La aplicacion de cada estacion se modela en Python respetando el contrato de la libreria.

Uso: python3 test_libreria.py            (imprime resultados y escribe ../figuras/*.png y ../resultados.json)
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from scl_sim import Machine, load_udts  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTES = os.path.join(AQUI, '..', 'fuentes')
DT = 0.01
CICLO_PLANTA = 4  # la planta se refresca cada 4 scans

# Bloque RFID de ejemplo (columna "Ejemplo" de Mapa_RFID_CPLab.xlsx)
BLOQUE = [0xA5, 7, 1, 15, 7, 1, 0, 0, 4, 3, 42, 1, 3, 2, 0x07, 0xD0, 2, 0, 1, 0, 3, 1, 2, 1, 0, 0, 0, 0]

# Configuracion por estacion: bytes que lee, bytes que escribe (offsets del bloque) y su logica (ver Excel, hoja "Lógica")
ESTACIONES = {
    'Camara':    dict(lee=[0, 3, 8, 20], escribe=[0, 1, 2, 3, 4, 5, 6, 9, 10, 11], extra_lectura=[1, 2, 4, 5, 6, 9, 10, 11]),
    'BackCover': dict(lee=[3, 23], escribe=[4, 12], extra_lectura=[4, 12]),
    'Press':     dict(lee=[3, 12, 13, 14, 15], escribe=[4, 16], extra_lectura=[4, 16]),
    'Out':       dict(lee=[5, 9, 17, 21, 22], escribe=list(range(28)), extra_lectura=[]),
}


def mascara(bytes_):
    m = 0
    for b in bytes_:
        m |= 1 << b
    return m


def mascaras(est):
    c = ESTACIONES[est]
    return mascara(sorted(set(c['lee']) | set(c['extra_lectura']))), mascara(c['escribe'])


class Planta:
    """Cinta con un palet, stopper y lector RFID real."""

    def __init__(self, tag):
        self.t = 0.0
        self.seta, self.marcha, self.rearme, self.auto = True, False, False, True
        self.palet, self.palet_t = 0, 0.0
        self.stopper = 0.0
        self.tag = list(tag) + [0] * (108 - len(tag))  # memoria del transpondedor (108 bytes)
        self.rf, self.rf_t, self.rf_cmd = 'idle', 0.0, None
        self.r_listo, self.r_leido, self.r_escrito, self.r_datos, self.r_dir = False, False, False, [0] * 28, 0
        self.inyectar_error = False
        self.escrituras = []  # (t, direccion, 28 bytes) de cada escritura al tag
        self.en_tope = False

    def entra_palet(self):
        self.palet, self.palet_t = 1, 0.0

    def step(self, dt, q):
        """q: salidas del PLC {cinta, stopper_baja, leer, escribir, ant_off, dir, datos}. Devuelve entradas."""
        self.t += dt
        cinta, bajar = q['cinta'], q['stopper_baja']
        self.stopper = min(1.0, self.stopper + dt / 0.1) if bajar else max(0.0, self.stopper - dt / 0.1)
        s_izq = s_dch = bien = False
        if self.palet == 1:
            if cinta:
                self.palet_t += dt
            s_izq = self.palet_t < 0.3
            if self.palet_t >= 2.0:
                self.palet, self.palet_t = 2, 0.0
        if self.palet == 2:
            bien = True
            if self.stopper > 0.99 and cinta:
                self.palet, self.palet_t = 3, 0.0
        if self.palet == 3:
            if cinta:
                self.palet_t += dt
            bien = self.palet_t < 0.2
            s_dch = 1.0 <= self.palet_t < 1.5
            if self.palet_t >= 1.5:
                self.palet = 0
        self.en_tope = bien
        # --- lector RFID real
        presente = bien and not q['ant_off']
        self.rf_t += dt
        if not self.seta or not presente or (not q['leer'] and not q['escribir']):
            self.rf, self.r_leido, self.r_escrito, self.r_datos = 'idle', False, False, [0] * 28
            self.r_listo = presente
        elif self.rf == 'idle' and (q['leer'] != q['escribir']):
            self.rf, self.rf_t, self.rf_cmd, self.r_dir = 'busy', 0.0, 'leer' if q['leer'] else 'escribir', q['dir']
            self.r_listo = False
        elif self.rf == 'busy' and self.rf_t > 0.12:
            self.rf, self.rf_t = 'done', 0.0
            self.r_listo = True
            if self.rf_cmd == 'leer':
                self.r_leido = True
                self.r_datos = self.tag[self.r_dir:self.r_dir + 28]
            else:
                self.r_escrito = True
                self.tag[self.r_dir:self.r_dir + 28] = q['datos']
                self.escrituras.append((round(self.t, 2), self.r_dir, list(q['datos'])))
        error = self.inyectar_error and (q['leer'] or q['escribir']) and presente
        return dict(
            Boton_marcha=self.marcha, Boton_paro=True, Selector_modo=self.auto, Boton_rearme=self.rearme,
            Sensor_ind_bien_pos=bien, Seta_emergencia=self.seta, Sensor_palet_izq=s_izq, Sensor_palet_dch=s_dch,
            stopper_abajo=self.stopper > 0.99, ind0=bien,
            rfid=dict(Tag_datos_escritos=self.r_escrito, Tag_datos_leidos=self.r_leido,
                      Tag_antena_apagada=q['ant_off'], Tag_detectado=presente, Tag_error=error,
                      Tag_proceso_listo=self.r_listo, Tag_codigo_error=0x21 if error else 0,
                      Tag_direccion_confirmada=self.r_dir, Tag_datos_leidos_escritos=list(self.r_datos)))


class AppPy:
    """Aplicacion de una estacion, cumpliendo el contrato: en_reposo -> (inicio) -> trabajo -> terminada."""

    def __init__(self, trabajo, tiempo=1.0):
        self.trabajo, self.tiempo, self.fase, self.t0 = trabajo, tiempo, 'reposo', 0.0
        self.vio = None

    def step(self, t, db):
        db['App_en_reposo'] = self.fase == 'reposo'
        db['App_terminada'] = self.fase == 'fin'
        if db['Emergencia']:
            self.fase = 'reposo'
            return
        if self.fase == 'reposo' and db['App_inicio']:
            self.fase, self.t0 = 'trabajo', t
            self.vio = list(db['Imagen_palet'])
        elif self.fase == 'trabajo' and t - self.t0 >= self.tiempo:
            self.trabajo(db['Imagen_palet'])
            self.fase = 'fin'
        elif self.fase == 'fin' and not db['App_inicio']:
            self.fase = 'reposo'


# --- logica de cada estacion (hoja "Lógica estaciones" del Excel) ---
def app_camara(img):
    img[4] |= 0x01      # bit 0: Camara completada
    img[5] = 1          # calidad global OK
    img[9] = 3          # inspeccionado + OK
    img[10] = 42        # ImageID
    img[11] = 1         # intentos


def app_backcover(img):
    img[4] |= 0x02
    img[12] = img[12] | 0x02   # tapa trasera colocada


def app_press(img):
    img[4] |= 0x04
    img[16] = img[13]          # golpes realizados = golpes pedidos


def app_out(img):
    for i in range(28):
        img[i] = 0             # el palet empieza limpio la siguiente vuelta


LOGICA = {'Camara': app_camara, 'BackCover': app_backcover, 'Press': app_press, 'Out': app_out}


class Banco:
    def __init__(self, estacion=None, app=None, tag=BLOQUE, masc=None, dir_lectura=0, dir_escritura=0):
        srcs = [open(os.path.join(FUENTES, n + '.scl'), encoding='utf-8').read()
                for n in ('Est_FB_Estacion', 'Est_FB_Modo', 'Est_FB_Cinta', 'Est_FB_RFID', 'Est_FB_App_Plantilla')]
        udts = load_udts(glob.glob(os.path.join(FUENTES, 'type_*.xml')))
        self.m = Machine(srcs, udts)
        v = self.m.new_value
        self.g = {'Entradas_Basico': v('UDT_Entradas_Basico'), 'Entradas_RFID': v('UDT_Entradas_RFID'),
                  'Entradas_Stopper': v('UDT_Entradas_Stopper'), 'Salidas_Basico': v('UDT_Salidas_Basico'),
                  'Salidas_RFID': v('UDT_Salidas_RFID'), 'Entradas_APP': v('UDT_Entradas_APP'),
                  'Salidas_APP': v('UDT_Salidas_APP'),
                  'DB': dict(Imagen_palet=[0] * 28, App_inicio=False, App_en_reposo=False, App_terminada=False,
                             App_alarma=False, App_rearme_requerido=False, Inhibir_cinta=False, Emergencia=False,
                             Rearme=False),
                  'est': self.m.new_instance('Est_FB_Estacion')}
        if app == 'plantilla':
            self.g['app'] = self.m.new_instance('Est_FB_App_Plantilla')
            self.app = None
        else:
            self.app = app
        ml, me = masc if masc else (0x0FFFFFFF, 0)
        self.masc = (ml, me)
        self.dirs = (dir_lectura, dir_escritura)
        self.p = Planta(tag)
        self.t_plc, self.k, self.q = 0.0, 0, dict(cinta=False, stopper_baja=False, leer=False, escribir=False,
                                                  ant_off=True, dir=0, datos=[0] * 28)
        self.ent = None
        self.traza = []
        self.estacion = estacion

    # --- una pasada de PLC
    def scan(self):
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
                  ('Direccion_lectura', 'in', ('lit', self.dirs[0])), ('Direccion_escritura', 'in', ('lit', self.dirs[1])),
                  ('Mascara_lectura', 'in', ('lit', self.masc[0])), ('Mascara_escritura', 'in', ('lit', self.masc[1])),
                  ('OutBasico', 'in', ref('Salidas_Basico')), ('OutRFID', 'in', ref('Salidas_RFID')),
                  ('Imagen_palet', 'in', ref('DB', 'Imagen_palet'))]
        for n in ('App_en_reposo', 'App_terminada', 'App_alarma', 'App_rearme_requerido', 'Inhibir_cinta'):
            params.append((n, 'in', ref('DB', n)))
        for n in ('App_inicio', 'Emergencia', 'Rearme'):
            params.append((n, 'out', ref('DB', n)))
        self.m.call(('est',), params, g)
        # la aplicacion
        if self.app is None:
            ap = [('Entradas_app', 'in', ref('Entradas_APP')), ('App_inicio', 'in', ref('DB', 'App_inicio')),
                  ('Emergencia', 'in', ref('DB', 'Emergencia')), ('Rearme', 'in', ref('DB', 'Rearme')),
                  ('Salidas_app', 'in', ref('Salidas_APP')), ('Imagen_palet', 'in', ref('DB', 'Imagen_palet'))]
            for n in ('App_en_reposo', 'App_terminada', 'App_alarma', 'App_rearme_requerido', 'Inhibir_cinta'):
                ap.append((n, 'out', ref('DB', n)))
            self.m.call(('app',), ap, g)
        else:
            self.app.step(self.t_plc, db)
        sb, sr = g['Salidas_Basico'], g['Salidas_RFID']
        self.q = dict(cinta=sb['Cinta_dch'], stopper_baja=sb['Bajar_stopper'], leer=sr['Tag_leer'],
                      escribir=sr['Tag_escribir'], ant_off=sr['Tag_antena_apagar'],
                      dir=sr['Tag_direccion_leer_escribir'], datos=list(sr['Tag_datos_a_escribir']))

    def step(self):
        self.t_plc += DT
        self.k += 1
        if self.k % CICLO_PLANTA == 0 or self.ent is None:
            self.ent = self.p.step(CICLO_PLANTA * DT, self.q)
        self.scan()
        est, db = self.g['est'], self.g['DB']
        self.traza.append(dict(t=self.t_plc, gestion=est['Etapa_gestion'], cinta=est['FB3_Cinta_Instance']['Etapa_cinta']
                               if 'FB3_Cinta_Instance' in est else est['FB3_Cinta_Instance']['Etapa_cinta'],
                               rfid=est['FB4_RFID_Instance']['Etapa_rfid'],
                               palet=self.p.palet, leer=self.q['leer'], escribir=self.q['escribir'],
                               listo=self.p.r_listo, app_inicio=db['App_inicio'], app_term=db['App_terminada'],
                               emerg=db['Emergencia'], cinta_on=self.q['cinta'], stopper=self.q['stopper_baja']))

    def wait(self, s):
        for _ in range(int(round(s / DT))):
            self.step()

    def until(self, cond, timeout):
        for _ in range(int(timeout / DT)):
            self.step()
            if cond():
                return True
        return False

    def pulso(self, campo, s=0.3):
        setattr(self.p, campo, True)
        self.wait(s)
        setattr(self.p, campo, False)
        self.wait(0.2)

    def ciclo_completo(self, timeout=60):
        """Arranca (marcha en auto), mete un palet y espera a que salga."""
        self.wait(0.3)
        self.pulso('marcha')
        self.p.entra_palet()
        return self.until(lambda: self.p.palet == 0 and self.traza and self.p.escrituras != [] or
                          (self.p.palet == 0 and self.estacion == 'sin_escritura'), timeout) and \
            self.until(lambda: self.g['est']['Etapa_gestion'] == 0 and self.p.palet == 0, 10)


# ---------------------------------------------------------------- pruebas
RESULT = {}


def comprobar(nombre, cond, detalle=''):
    RESULT.setdefault('comprobaciones', []).append(dict(nombre=nombre, ok=bool(cond), detalle=detalle))
    print(('  OK  ' if cond else '  FALLO ') + nombre + (('  -> ' + detalle) if detalle and not cond else ''))
    return bool(cond)


def prueba_estacion(nombre):
    print('\n== Estacion %s ==' % nombre)
    ml, me = mascaras(nombre)
    print('   Mascara_lectura  = 16#%08X\n   Mascara_escritura = 16#%08X' % (ml, me))
    app = AppPy(LOGICA[nombre])
    b = Banco(nombre, app, masc=(ml, me))
    inicial = list(b.p.tag[:28])
    ok = b.ciclo_completo()
    comprobar('%s: el palet completa el ciclo y sale' % nombre, ok)
    final = b.p.tag[:28]
    # imagen que vio la app: solo los bytes de la mascara de lectura, el resto a 0
    vio = app.vio or [0] * 28
    comprobar('%s: la app solo ve los bytes de Mascara_lectura' % nombre,
              all((vio[i] == inicial[i]) if (ml >> i) & 1 else vio[i] == 0 for i in range(28)),
              'vio=%s' % vio)
    # esperado: aplicar la logica sobre una imagen "vista" y volcar solo los bytes de Mascara_escritura
    img = [inicial[i] if (ml >> i) & 1 else 0 for i in range(28)]
    LOGICA[nombre](img)
    esperado = [img[i] if (me >> i) & 1 else inicial[i] for i in range(28)]
    comprobar('%s: el tag queda como esperado' % nombre, final == esperado,
              'final=%s esperado=%s' % (final, esperado))
    ajenos = [i for i in range(28) if not (me >> i) & 1]
    comprobar('%s: los bytes ajenos (fuera de Mascara_escritura) no cambian' % nombre,
              all(final[i] == inicial[i] for i in ajenos))
    cambiados = [i for i in range(28) if final[i] != inicial[i]]
    print('   bytes modificados en el tag:', cambiados)
    RESULT.setdefault('estaciones', {})[nombre] = dict(ml='%08X' % ml, me='%08X' % me, inicial=inicial, final=list(final),
                                                       cambiados=cambiados, escrituras=len(b.p.escrituras))
    comprobar('%s: una sola escritura al tag por palet' % nombre, len(b.p.escrituras) == 1,
              'escrituras=%d' % len(b.p.escrituras))
    return b


def prueba_plantilla():
    print('\n== Plantilla de app (Est_FB_App_Plantilla) ==')
    b = Banco('Plantilla', 'plantilla', masc=(0x0FFFFFFF, 0))
    b.wait(0.3)
    b.pulso('marcha')
    b.p.entra_palet()
    ok = b.until(lambda: b.p.palet == 0 and b.p.t > 3, 40)
    comprobar('plantilla: el palet entra, se procesa y sale con la plantilla tal cual', ok)
    return b


def prueba_error_rfid():
    print('\n== Fallo del RFID ==')
    app = AppPy(app_camara)
    ml, me = mascaras('Camara')
    b = Banco('sin_escritura', app, masc=(ml, me))
    b.p.inyectar_error = True
    b.wait(0.3)
    b.pulso('marcha')
    b.p.entra_palet()
    ok = b.until(lambda: b.g['est']['Etapa_gestion'] == 6, 20)
    comprobar('error RFID: la gestion pasa a "fallo RFID" (etapa 6)', ok)
    comprobar('error RFID: la app no llega a arrancar', not any(r['app_inicio'] for r in b.traza))
    b.p.inyectar_error = False
    b.pulso('rearme')
    ok = b.until(lambda: b.p.palet == 0, 15)
    comprobar('error RFID: tras rearmar el palet se evacua', ok)
    comprobar('error RFID: no se escribe nada en el tag', b.p.escrituras == [] and b.p.tag[:28] == BLOQUE)
    return b


def prueba_emergencia():
    print('\n== Emergencia durante la aplicacion ==')
    app = AppPy(app_camara, tiempo=3.0)
    ml, me = mascaras('Camara')
    b = Banco('sin_escritura', app, masc=(ml, me))
    b.wait(0.3)
    b.pulso('marcha')
    b.p.entra_palet()
    ok = b.until(lambda: app.fase == 'trabajo', 20)
    comprobar('emergencia: la app esta trabajando', ok)
    b.p.seta = False
    b.wait(0.5)
    comprobar('emergencia: Emergencia activa y la gestion vuelve a 0',
              b.g['DB']['Emergencia'] and b.g['est']['Etapa_gestion'] == 0)
    comprobar('emergencia: la cinta y el stopper se paran',
              not b.q['cinta'] and not b.q['stopper_baja'])
    b.wait(4.0)
    comprobar('emergencia: no se escribe nada en el tag', b.p.escrituras == [] and b.p.tag[:28] == BLOQUE)
    b.p.seta = True
    b.wait(0.3)
    b.pulso('rearme')
    b.wait(0.5)
    comprobar('emergencia: tras soltar la seta y rearmar, Emergencia vuelve a 0', not b.g['DB']['Emergencia'])
    return b


def figura(b, nombre_png, titulo):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tr = b.traza
    # recorte: desde la entrada del palet hasta que sale
    i0 = next((i for i, r in enumerate(tr) if r['palet'] == 1), 0)
    i1 = max((i for i, r in enumerate(tr) if r['palet'] in (1, 2, 3)), default=len(tr) - 1) + 100
    tr = tr[max(0, i0 - 30):min(len(tr), i1)]
    t0 = tr[0]['t']
    t = [r['t'] - t0 for r in tr]
    fig, ax = plt.subplots(8, 1, figsize=(10, 7.2), sharex=True,
                           gridspec_kw=dict(height_ratios=[1.3, 1.3, 1.3, 1, 1, 1, 1, 1]))
    col = '#1f4e79'

    def num(a, clave, etiqueta, ticks):
        a.step(t, [r[clave] for r in tr], where='post', color=col, lw=1.6)
        a.set_ylabel(etiqueta, rotation=0, ha='right', va='center', fontsize=8)
        a.set_yticks(ticks)
        a.tick_params(labelsize=7)
        a.grid(alpha=.3)
        a.set_ylim(min(ticks) - .5, max(ticks) + .5)

    def dig(a, clave, etiqueta):
        a.step(t, [int(r[clave]) for r in tr], where='post', color=col, lw=1.6)
        a.fill_between(t, [int(r[clave]) for r in tr], step='post', color=col, alpha=.12)
        a.set_ylabel(etiqueta, rotation=0, ha='right', va='center', fontsize=8)
        a.set_yticks([0, 1])
        a.set_ylim(-.15, 1.25)
        a.tick_params(labelsize=7)
        a.grid(alpha=.3)

    num(ax[0], 'gestion', 'Etapa gestión\n(FB Estacion)', [0, 1, 2, 3, 4, 5, 6])
    num(ax[1], 'cinta', 'Etapa cinta\n(Est_FB_Cinta)', [0, 1, 3, 4, 5, 6, 7])
    num(ax[2], 'rfid', 'Etapa RFID\n(Est_FB_RFID)', [0, 1, 2, 3, 4, 5, 6, 8])
    dig(ax[3], 'cinta_on', 'Cinta')
    dig(ax[4], 'leer', 'Orden leer')
    dig(ax[5], 'escribir', 'Orden escribir')
    dig(ax[6], 'app_inicio', 'App_inicio')
    dig(ax[7], 'app_term', 'App_terminada')
    ax[-1].set_xlabel('tiempo (s)')
    fig.suptitle(titulo, fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(AQUI, '..', 'figuras', nombre_png), dpi=170)


if __name__ == '__main__':
    os.makedirs(os.path.join(AQUI, '..', 'figuras'), exist_ok=True)
    bancos = {n: prueba_estacion(n) for n in ESTACIONES}
    prueba_plantilla()
    prueba_error_rfid()
    prueba_emergencia()
    figura(bancos['Camara'], 'crono_ciclo_camara.png', 'Un palet en la estación Cámara (simulación de la librería)')
    figura(bancos['Out'], 'crono_ciclo_out.png', 'Un palet en la estación Out (simulación de la librería)')
    fallos = [c for c in RESULT['comprobaciones'] if not c['ok']]
    RESULT['resumen'] = dict(total=len(RESULT['comprobaciones']), fallos=len(fallos))
    json.dump(RESULT, open(os.path.join(AQUI, '..', 'resultados.json'), 'w'), indent=1)
    print('\n%d comprobaciones, %d fallos' % (len(RESULT['comprobaciones']), len(fallos)))
    sys.exit(1 if fallos else 0)
