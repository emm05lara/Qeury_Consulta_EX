# tests/test_negocio.py
# Pruebas de la clasificación de tipo de afiliado (ACTIVO / PENSIONADO).
# Usa unicamente unittest + pandas (ya son dependencias del proyecto).

import math
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.negocio import clasificarAfiliado, getTipoAfiliado, TEXTO_AFILIADO_SIN_DATO


class TestClasificarAfiliado(unittest.TestCase):

    def test_pensionado_mayusculas(self):
        self.assertEqual(clasificarAfiliado("PENSIONADO"), "PENSIONADO")

    def test_pensionado_minusculas(self):
        self.assertEqual(clasificarAfiliado("pensionado"), "PENSIONADO")

    def test_pensionado_capitalizado(self):
        self.assertEqual(clasificarAfiliado("Pensionado"), "PENSIONADO")

    def test_pensionado_con_espacios(self):
        self.assertEqual(clasificarAfiliado("  PENSIONADO  "), "PENSIONADO")

    def test_pensionado_con_texto_adicional(self):
        self.assertEqual(clasificarAfiliado("PENSIONADO IMSS"), "PENSIONADO")
        self.assertEqual(clasificarAfiliado("Pensionado IMSS"), "PENSIONADO")

    def test_pensionado_precedido_de_texto(self):
        self.assertEqual(clasificarAfiliado("Cliente pensionado"), "PENSIONADO")
        self.assertEqual(clasificarAfiliado(" cliente pensionado"), "PENSIONADO")

    def test_activo_explicito(self):
        self.assertEqual(clasificarAfiliado("ACTIVO"), "ACTIVO")
        self.assertEqual(clasificarAfiliado("Empleado activo"), "ACTIVO")
        self.assertEqual(clasificarAfiliado("EMPLEADO ACTIVO"), "ACTIVO")

    def test_afiliado_generico_es_activo(self):
        self.assertEqual(clasificarAfiliado("AFILIADO"), "ACTIVO")

    def test_vacio_es_activo(self):
        self.assertEqual(clasificarAfiliado(""), "ACTIVO")
        self.assertEqual(clasificarAfiliado("   "), "ACTIVO")

    def test_none_es_activo(self):
        self.assertEqual(clasificarAfiliado(None), "ACTIVO")

    def test_nan_es_activo(self):
        self.assertEqual(clasificarAfiliado(float("nan")), "ACTIVO")
        self.assertEqual(clasificarAfiliado(pd.NA if hasattr(pd, "NA") else math.nan), "ACTIVO")


class TestGetTipoAfiliado(unittest.TestCase):

    def test_columna_existe_pensionado(self):
        fila = pd.Series({"vReference": "1", "vAfiliado": "PENSIONADO IMSS"})
        self.assertEqual(getTipoAfiliado(fila), "PENSIONADO")

    def test_columna_existe_activo(self):
        fila = pd.Series({"vReference": "1", "vAfiliado": "ACTIVO"})
        self.assertEqual(getTipoAfiliado(fila), "ACTIVO")

    def test_columna_existe_pero_vacia_es_activo(self):
        fila = pd.Series({"vReference": "1", "vAfiliado": ""})
        self.assertEqual(getTipoAfiliado(fila), "ACTIVO")

    def test_columna_existe_pero_nan_es_activo(self):
        fila = pd.Series({"vReference": "1", "vAfiliado": float("nan")})
        self.assertEqual(getTipoAfiliado(fila), "ACTIVO")

    def test_columna_no_existe_no_rompe_y_marca_sin_dato(self):
        fila = pd.Series({"vReference": "1", "vName": "JUAN PEREZ"})
        self.assertNotIn("vAfiliado", fila.index)
        self.assertEqual(getTipoAfiliado(fila), TEXTO_AFILIADO_SIN_DATO)


if __name__ == "__main__":
    unittest.main()
