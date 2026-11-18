"""Comprueba que la configuración de ejemplo y los contratos de docs/contratos.md son válidos.

Ejecutar desde pasarela/:  python -m unittest discover -s tests
"""
import ast
import configparser
import re
import struct
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


class ConfigEjemplo(unittest.TestCase):
    def setUp(self):
        self.cfg = configparser.ConfigParser()
        self.cfg.read(RAIZ / "config" / "ejemplo.ini", encoding="utf-8")

    def test_secciones(self):
        for s in ("gateway", "acquisition", "acquisition.udp", "outputs", "signals"):
            self.assertIn(s, self.cfg)

    def test_valores_sin_comentarios_pegados(self):
        for sec in self.cfg.sections():
            for k, v in self.cfg[sec].items():
                self.assertNotIn("#", v, f"[{sec}] {k}")

    def test_solo_lectura_por_defecto(self):  # O1
        self.assertTrue(self.cfg["gateway"].getboolean("read_only"))

    def test_cuatro_plc_y_cuatro_salidas(self):
        plcs = [p.split(":")[0] for p in self.cfg["acquisition.udp"]["plcs"].split(",")]
        self.assertEqual(len(set(plcs)), 4)
        salidas = {s.strip() for s in self.cfg["outputs"]["enabled"].split(",")}
        self.assertEqual(salidas, {"opcua", "mqtt", "modbus", "tcp"})


class Contratos(unittest.TestCase):
    texto = (RAIZ / "docs" / "contratos.md").read_text(encoding="utf-8")

    def test_interfaz_python_compila_y_define_los_contratos(self):
        codigo = re.search(r"```python\n(.*?)```", self.texto, re.S).group(1)
        arbol = ast.parse(codigo)
        clases = {n.name for n in arbol.body if isinstance(n, ast.ClassDef)}
        self.assertEqual(clases, {"Signal", "AcquisitionConnector", "Core", "OutputConnector"})

    def test_cabecera_del_datagrama_mide_18_bytes(self):
        # magic(2) ver(1) plc_id(1) seq(4) ts_origin(8) n(2), big-endian
        self.assertEqual(struct.calcsize(">2sBBIQH"), 18)
        self.assertIn("18", self.texto)


if __name__ == "__main__":
    unittest.main()
