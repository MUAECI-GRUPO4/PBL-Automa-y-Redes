"""Interprete minimo de SCL (el subconjunto que usa el proyecto) para probar
los FB exportados de TIA contra un modelo de la estacion OUT de CIROS.

Ejecuta las fuentes .scl tal cual salen de TIA (Openness GenerateSource) y
mapea las variables globales a la imagen de proceso segun la tabla de tags
y el orden de miembros de los UDT, igual que lo haria la CPU.
"""
import copy
import re
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------- lexer
TOK = re.compile(r"""
  (?P<ws>\s+)|
  (?P<comment>//[^\n]*|\(\*.*?\*\))|
  (?P<attr>\{[^}]*\})|
  (?P<time>T\#[0-9a-zA-Z_]+)|
  (?P<num>16\#[0-9A-Fa-f_]+|\d+)|
  (?P<qname>"[^"]+")|
  (?P<id>[\#%]?[A-Za-z_][A-Za-z0-9_]*)|
  (?P<op>:=|=>|<>|<=|>=|[=<>+\-*/(),;:.\[\]])
""", re.S | re.X)


def lex(src):
    out = []
    for m in TOK.finditer(src):
        k = m.lastgroup
        v = m.group()
        if k in ('ws', 'comment', 'attr'):
            continue
        if k == 'num':
            v = int(v[3:].replace('_', ''), 16) if v.startswith('16#') else int(v)
        elif k == 'time':
            t = v[2:].lower()
            mm = re.fullmatch(r'(\d+)(ms|s)', t)
            v = int(mm.group(1)) * (1 if mm.group(2) == 'ms' else 1000)
            k = 'num'
        elif k == 'id':
            up = v.upper()
            if up in KEYWORDS:
                k, v = 'kw', up
        out.append((k, v))
    out.append(('eof', None))
    return out


KEYWORDS = {'IF', 'THEN', 'ELSIF', 'ELSE', 'END_IF', 'CASE', 'OF', 'END_CASE', 'AND', 'OR', 'XOR', 'NOT',
            'TRUE', 'FALSE', 'FUNCTION_BLOCK', 'END_FUNCTION_BLOCK', 'VAR_INPUT', 'VAR_OUTPUT', 'VAR_IN_OUT',
            'VAR', 'END_VAR', 'CONSTANT', 'BEGIN', 'VERSION', 'MOD', 'VAR_TEMP', 'FOR', 'TO', 'DO', 'END_FOR', 'BY'}


# ---------------------------------------------------------------- parser
class P:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self, o=0):
        return self.t[self.i + o]

    def nxt(self):
        x = self.t[self.i]
        self.i += 1
        return x

    def expect(self, v):
        k, x = self.nxt()
        if x != v:
            raise SyntaxError('esperaba %r, encontrado %r (tok %d)' % (v, x, self.i))

    def accept(self, v):
        if self.peek()[1] == v:
            self.i += 1
            return True
        return False

    # --- declaraciones
    def fb(self):
        while self.peek()[1] != 'FUNCTION_BLOCK':
            self.nxt()
        self.nxt()
        name = self.nxt()[1].strip('"')
        while self.peek()[1] not in ('VAR_INPUT', 'VAR_OUTPUT', 'VAR_IN_OUT', 'VAR', 'VAR_TEMP', 'BEGIN'):
            self.nxt()
        sections = {}
        while self.peek()[1] in ('VAR_INPUT', 'VAR_OUTPUT', 'VAR_IN_OUT', 'VAR', 'VAR_TEMP'):
            sec = self.nxt()[1]
            if self.accept('CONSTANT'):
                sec = 'CONST'
            decls = sections.setdefault(sec, [])
            while not self.accept('END_VAR'):
                vname = self.nxt()[1]
                self.expect(':')
                k, typ = self.nxt()
                typ = typ.strip('"')
                if typ.upper() == 'ARRAY':
                    self.expect('[')
                    lo = self.nxt()[1]
                    self.expect('.')
                    self.expect('.')
                    hi = self.nxt()[1]
                    self.expect(']')
                    self.expect('OF')
                    typ = 'Array[%d..%d] of %s' % (lo, hi, self.nxt()[1])
                init = None
                if self.accept(':='):
                    init = self.expr()
                self.expect(';')
                decls.append((vname, typ, init))
        self.expect('BEGIN')
        body = self.stmts(('END_FUNCTION_BLOCK',))
        return name, sections, body

    # --- sentencias
    def is_case_label(self):
        j = self.i
        while self.t[j][0] == 'num':
            j += 1
            if self.t[j][1] == ',':
                j += 1
                continue
            return self.t[j][1] == ':'
        return False

    def stmts(self, ends, case_mode=False):
        out = []
        while True:
            k, v = self.peek()
            if v in ends or (case_mode and self.is_case_label()):
                return out
            out.append(self.stmt())

    def stmt(self):
        k, v = self.peek()
        if v == ';':
            self.nxt()
            return ('nop',)
        if v == 'IF':
            self.nxt()
            arms = []
            c = self.expr()
            self.expect('THEN')
            arms.append((c, self.stmts(('ELSIF', 'ELSE', 'END_IF'))))
            els = []
            while True:
                if self.accept('ELSIF'):
                    c = self.expr()
                    self.expect('THEN')
                    arms.append((c, self.stmts(('ELSIF', 'ELSE', 'END_IF'))))
                elif self.accept('ELSE'):
                    els = self.stmts(('END_IF',))
                else:
                    break
            self.expect('END_IF')
            self.accept(';')
            return ('if', arms, els)
        if v == 'CASE':
            self.nxt()
            sel = self.expr()
            self.expect('OF')
            arms = []
            els = []
            while True:
                if self.is_case_label():
                    labels = [self.nxt()[1]]
                    while self.accept(','):
                        labels.append(self.nxt()[1])
                    self.expect(':')
                    arms.append((labels, self.stmts(('ELSE', 'END_CASE'), case_mode=True)))
                elif self.accept('ELSE'):
                    els = self.stmts(('END_CASE',))
                else:
                    break
            self.expect('END_CASE')
            self.accept(';')
            return ('case', sel, arms, els)
        if v == 'FOR':
            self.nxt()
            var = self.lvalue()
            self.expect(':=')
            lo = self.expr()
            self.expect('TO')
            hi = self.expr()
            self.expect('DO')
            body = self.stmts(('END_FOR',))
            self.expect('END_FOR')
            self.accept(';')
            return ('for', var, lo, hi, body)
        # asignacion o llamada
        target = self.lvalue()
        if self.accept(':='):
            e = self.expr()
            self.expect(';')
            return ('assign', target, e)
        if self.accept('('):
            params = []
            while not self.accept(')'):
                pname = self.nxt()[1]
                op = self.nxt()[1]
                if op == ':=':
                    params.append((pname, 'in', self.expr()))
                else:
                    params.append((pname, 'out', self.lvalue()))
                self.accept(',')
            self.expect(';')
            return ('call', target, params)
        raise SyntaxError('sentencia rara en %r' % (self.peek(),))

    def lvalue(self):
        k, v = self.nxt()
        path = [v.lstrip('#').strip('"')]
        while self.peek()[1] in ('.', '['):
            sep = self.nxt()[1]
            k2, v2 = self.nxt()
            if sep == '[' and k2 == 'id':
                v2 = ('var', v2.lstrip('#'))
            path.append(v2)
            if sep == '[':
                self.expect(']')
        return ('ref', tuple(path))

    # --- expresiones
    def expr(self):
        return self.bin(0)

    LEVELS = [('OR',), ('XOR',), ('AND',), ('=', '<>'), ('<', '>', '<=', '>='), ('+', '-'), ('*', '/', 'MOD')]

    def bin(self, lvl):
        if lvl == len(self.LEVELS):
            return self.unary()
        a = self.bin(lvl + 1)
        while self.peek()[1] in self.LEVELS[lvl]:
            op = self.nxt()[1]
            b = self.bin(lvl + 1)
            a = ('bin', op, a, b)
        return a

    def unary(self):
        if self.accept('NOT'):
            return ('not', self.unary())
        if self.accept('-'):
            return ('neg', self.unary())
        if self.accept('('):
            e = self.expr()
            self.expect(')')
            return e
        k, v = self.peek()
        if v == 'TRUE':
            self.nxt()
            return ('lit', True)
        if v == 'FALSE':
            self.nxt()
            return ('lit', False)
        if k == 'num':
            self.nxt()
            return ('lit', v)
        if k == 'id' and not v.startswith('#') and self.peek(1)[1] == '(':
            self.nxt()
            self.expect('(')
            args = []
            while not self.accept(')'):
                if self.peek(1)[1] == ':=':
                    self.nxt()
                    self.nxt()
                args.append(self.expr())
                self.accept(',')
            return ('fn', v.upper(), args)
        return self.lvalue()


# ---------------------------------------------------------------- runtime
class TON:
    def __init__(self):
        self.Q = False
        self.ET = 0
        self.IN = False
        self.PT = 0


class TRIG:
    def __init__(self, rising):
        self.rising = rising
        self.Q = False
        self.M = False
        self.CLK = False


SLICE = {'%B0': 0, '%B1': 8}


def array_len(typ):
    lo, hi = re.match(r'Array\[(\d+)\.\.(\d+)\]', typ).groups()
    return int(hi) - int(lo) + 1


class Machine:
    def __init__(self, fb_sources, udts):
        self.fbs = {}
        self.udts = udts
        self.now_ms = 0
        for src in fb_sources:
            name, secs, body = P(lex(src)).fb()
            self.fbs[name] = (secs, body)

    def new_value(self, typ, init=None):
        if typ in ('TON_TIME', 'TON'):
            return TON()
        if typ == 'R_TRIG':
            return TRIG(True)
        if typ == 'F_TRIG':
            return TRIG(False)
        if typ.startswith('Array'):
            return [0] * array_len(typ)
        if typ in self.udts:
            return {m: self.new_value(t) for m, t in self.udts[typ]}
        if typ in self.fbs:
            return self.new_instance(typ)
        if init is not None:
            return self.eval(init, {})
        return False if typ == 'Bool' else 0

    def new_instance(self, fbname):
        secs, body = self.fbs[fbname]
        inst = {'__fb__': fbname}
        for sec, decls in secs.items():
            for n, t, init in decls:
                inst[n] = self.new_value(t, init)
        return inst

    # --- acceso
    def get(self, frame, path):
        o = frame[path[0]]
        for p in path[1:]:
            if isinstance(p, tuple):
                p = frame[p[1]]
            if not isinstance(p, tuple) and p in SLICE:
                o = o >> SLICE[p] & 0xFF
            else:
                o = o[p] if isinstance(o, (dict, list)) else getattr(o, p)
        return o

    def set(self, frame, path, val):
        if path[-1] in SLICE:
            sh = SLICE[path[-1]]
            val = self.get(frame, path[:-1]) & ~(0xFF << sh) | (val & 0xFF) << sh
            path = path[:-1]
        if len(path) == 1:
            frame[path[0]] = val
            return
        o = self.get(frame, path[:-1])
        last = frame[path[-1][1]] if isinstance(path[-1], tuple) else path[-1]
        if isinstance(o, (dict, list)):
            o[last] = val
        else:
            setattr(o, path[-1], val)

    def eval(self, e, f):
        k = e[0]
        if k == 'lit':
            return e[1]
        if k == 'ref':
            return self.get(f, e[1])
        if k == 'not':
            return not self.eval(e[1], f)
        if k == 'neg':
            return -self.eval(e[1], f)
        if k == 'fn':
            a = [self.eval(x, f) for x in e[2]]
            if e[1] == 'SHR':
                return a[0] >> a[1]
            if e[1] == 'SHL':
                return (a[0] << a[1]) & 0xFFFFFFFF
            if e[1] in ('BYTE_TO_INT', 'WORD_TO_INT', 'INT_TO_BYTE', 'BYTE_TO_WORD', 'DINT_TO_TIME', 'INT_TO_DINT'):
                return int(a[0]) & (0xFF if e[1] == 'INT_TO_BYTE' else 0xFFFFFFFF if e[1] in ('DINT_TO_TIME', 'INT_TO_DINT') else 0xFFFF)
            raise ValueError('funcion ' + e[1])
        op, a, b = e[1], self.eval(e[2], f), self.eval(e[3], f)
        if op in ('AND', 'OR', 'XOR') and not (isinstance(a, bool) and isinstance(b, bool)):
            return a & b if op == 'AND' else a | b if op == 'OR' else a ^ b
        if op == 'AND':
            return bool(a) and bool(b)
        if op == 'OR':
            return bool(a) or bool(b)
        if op == 'XOR':
            return bool(a) != bool(b)
        if op == '=':
            return a == b
        if op == '<>':
            return a != b
        if op == '<':
            return a < b
        if op == '>':
            return a > b
        if op == '<=':
            return a <= b
        if op == '>=':
            return a >= b
        if op == '+':
            return a + b
        if op == '-':
            return a - b
        if op == '*':
            return a * b
        if op == '/':
            return a // b
        if op == 'MOD':
            return a % b
        raise ValueError(op)

    def run(self, stmts, f):
        for s in stmts:
            k = s[0]
            if k == 'assign':
                v = self.eval(s[2], f)
                cur = self.get(f, s[1][1])
                if isinstance(cur, list):
                    cur[:] = v
                    continue
                if isinstance(cur, bool):
                    v = bool(v)
                elif isinstance(cur, int) and not isinstance(cur, bool):
                    v = int(v)
                self.set(f, s[1][1], v)
            elif k == 'if':
                for c, body in s[1]:
                    if self.eval(c, f):
                        self.run(body, f)
                        break
                else:
                    self.run(s[2], f)
            elif k == 'case':
                sel = self.eval(s[1], f)
                for labels, body in s[2]:
                    if sel in labels:
                        self.run(body, f)
                        break
                else:
                    self.run(s[3], f)
            elif k == 'for':
                lo, hi = self.eval(s[2], f), self.eval(s[3], f)
                for n in range(lo, hi + 1):
                    self.set(f, s[1][1], n)
                    self.run(s[4], f)
            elif k == 'call':
                self.call(s[1][1], s[2], f)

    def call(self, path, params, f):
        inst = self.get(f, path)
        if isinstance(inst, TON):
            for n, d, e in params:
                setattr(inst, n, self.eval(e, f))
            if inst.IN:
                if not hasattr(inst, 't0') or inst.t0 is None:
                    inst.t0 = self.now_ms
                inst.ET = min(self.now_ms - inst.t0, inst.PT)
                inst.Q = inst.ET >= inst.PT
            else:
                inst.t0 = None
                inst.ET = 0
                inst.Q = False
            return
        if isinstance(inst, TRIG):
            for n, d, e in params:
                clk = bool(self.eval(e, f))
            inst.Q = (clk and not inst.M) if inst.rising else (not clk and inst.M)
            inst.M = clk
            return
        secs, body = self.fbs[inst['__fb__']]
        kinds = {}
        for sec, decls in secs.items():
            for n, t, i in decls:
                kinds[n] = sec
        copy_back = []
        for n, d, e in params:
            if d == 'out':
                copy_back.append((n, e))
                continue
            if kinds[n] == 'VAR_IN_OUT':
                cur = self.get(f, e[1])
                if isinstance(cur, (dict, list)):
                    inst[n] = cur              # struct/array InOut: por referencia
                else:
                    inst[n] = cur
                    copy_back.append((n, e))
            else:
                v = self.eval(e, f)
                inst[n] = copy.deepcopy(v) if isinstance(v, (dict, list)) else v
        self.run(body, inst)
        for n, e in copy_back:
            self.set(f, e[1], inst[n])


# ---------------------------------------------------------------- imagen de proceso
def load_udts(paths):
    udts = {}
    for p in paths:
        s = open(p, encoding='utf-8-sig').read()
        name = re.search(r'<Name>([^<]+)</Name>', s).group(1)
        udts[name] = re.findall(r'<Member Name="([^"]+)" Datatype="([^"]+)"', s)
    return udts


def layout(udt_members, base_byte):
    """Bools seguidos bit a bit; Byte en el siguiente byte; Word alineado a par."""
    pos = []
    byte, bit = base_byte, 0
    for name, typ in udt_members:
        if typ == 'Bool':
            pos.append((name, typ, byte, bit))
            bit += 1
            if bit == 8:
                byte, bit = byte + 1, 0
        else:
            if bit:
                byte, bit = byte + 1, 0
            if typ != 'Byte' and (byte - base_byte) % 2:
                byte += 1
            pos.append((name, typ, byte, 0))
            byte += array_len(typ) if typ.startswith('Array') else 1 if typ == 'Byte' else 2
    return pos


class ProcessImage:
    def __init__(self):
        self.I = bytearray(256)
        self.Q = bytearray(256)

    def getbit(self, area, b, n):
        return bool(area[b] >> n & 1)

    def setbit(self, area, b, n, v):
        area[b] = (area[b] | 1 << n) if v else (area[b] & ~(1 << n))

    def read_struct(self, area, lay, dst):
        for name, typ, b, n in lay:
            if typ == 'Bool':
                dst[name] = self.getbit(area, b, n)
            elif typ == 'Byte':
                dst[name] = area[b]
            elif typ.startswith('Array'):
                dst[name][:] = area[b:b + array_len(typ)]
            else:
                dst[name] = area[b] << 8 | area[b + 1]

    def write_struct(self, area, lay, src):
        for name, typ, b, n in lay:
            if name.startswith('Reservado') or name.startswith('Tag_reservado'):
                continue  # la CPU no escribe bits que el programa no toca
            v = src[name]
            if typ == 'Bool':
                self.setbit(area, b, n, v)
            elif typ == 'Byte':
                area[b] = v & 0xFF
            elif typ.startswith('Array'):
                area[b:b + len(v)] = bytes(v)
            else:
                area[b], area[b + 1] = v >> 8 & 0xFF, v & 0xFF
