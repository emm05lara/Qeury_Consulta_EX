# tests/test_negocio.py
# Pruebas de getAfiliadoInfo: el valor mostrado debe ser siempre el texto
# original de vAfiliado (solo con strip()); la categoría ("activo" |
# "pensionado" | "sin_dato") es exclusivamente para el estilo visual.
# Usa unicamente unittest + pandas (ya son dependencias del proyecto).

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.negocio import getAfiliadoInfo, TEXTO_AFILIADO_SIN_DATO
from utils.carga import COLUMNAS_REQUERIDAS


def _fila(vAfiliado=None, incluir_columna=True, **extra):
    datos = dict(extra)
    if incluir_columna:
        datos["vAfiliado"] = vAfiliado
    return pd.Series(datos)


class TestGetAfiliadoInfo(unittest.TestCase):

    def test_activo_texto_exacto(self):
        info = getAfiliadoInfo(_fila("ACTIVO"))
        self.assertEqual(info, {"valor": "ACTIVO", "categoria": "activo"})

    def test_activo_conserva_texto_original_no_lo_uppercase_ni_lo_reemplaza(self):
        info = getAfiliadoInfo(_fila("Empleado activo"))
        self.assertEqual(info["valor"], "Empleado activo")
        self.assertEqual(info["categoria"], "activo")

    def test_pensionado_texto_exacto(self):
        info = getAfiliadoInfo(_fila("PENSIONADO"))
        self.assertEqual(info, {"valor": "PENSIONADO", "categoria": "pensionado"})

    def test_pensionado_con_texto_adicional_conserva_valor_original(self):
        info = getAfiliadoInfo(_fila("Pensionado IMSS"))
        self.assertEqual(info["valor"], "Pensionado IMSS")
        self.assertEqual(info["categoria"], "pensionado")

    def test_pensionados_plural_texto_exacto(self):
        info = getAfiliadoInfo(_fila("PENSIONADOS"))
        self.assertEqual(info, {"valor": "PENSIONADOS", "categoria": "pensionado"})

    def test_pensionados_plural_con_texto_adicional(self):
        info = getAfiliadoInfo(_fila("Pensionados IMSS"))
        self.assertEqual(info["valor"], "Pensionados IMSS")
        self.assertEqual(info["categoria"], "pensionado")

    def test_jyp_mayusculas(self):
        info = getAfiliadoInfo(_fila("JYP"))
        self.assertEqual(info, {"valor": "JYP", "categoria": "pensionado"})

    def test_jyp_minusculas(self):
        info = getAfiliadoInfo(_fila("jyp"))
        self.assertEqual(info, {"valor": "jyp", "categoria": "pensionado"})

    def test_jyp_capitalizado(self):
        info = getAfiliadoInfo(_fila("Jyp"))
        self.assertEqual(info, {"valor": "Jyp", "categoria": "pensionado"})

    def test_jyp_pensionados_mayusculas(self):
        info = getAfiliadoInfo(_fila("JYP PENSIONADOS"))
        self.assertEqual(info, {"valor": "JYP PENSIONADOS", "categoria": "pensionado"})

    def test_jyp_pensionados_conserva_valor_original_exacto(self):
        info = getAfiliadoInfo(_fila("Jyp Pensionados"))
        self.assertEqual(info["valor"], "Jyp Pensionados")
        self.assertEqual(info["categoria"], "pensionado")

    def test_cualquier_otro_texto_no_vacio_es_categoria_activo(self):
        for texto in ("AFILIADO", "TRABAJADOR", "SEP ACTIVOS", "CUALQUIER OTRO TEXTO"):
            with self.subTest(texto=texto):
                info = getAfiliadoInfo(_fila(texto))
                self.assertEqual(info["valor"], texto)
                self.assertEqual(info["categoria"], "activo")

    def test_jyp_no_produce_falso_positivo_dentro_de_otra_palabra(self):
        # "jyp" no debe dispararse si aparece pegado a otras letras (no es la
        # palabra completa "jyp"), gracias al límite de palabra \b en el regex.
        info = getAfiliadoInfo(_fila("ABCJYPXYZ"))
        self.assertEqual(info["categoria"], "activo")

    def test_espacios_exteriores_se_recortan_con_strip(self):
        info = getAfiliadoInfo(_fila("  PENSIONADO IMSS  "))
        self.assertEqual(info["valor"], "PENSIONADO IMSS")
        self.assertEqual(info["categoria"], "pensionado")

    def test_cadena_vacia_es_sin_dato(self):
        info = getAfiliadoInfo(_fila(""))
        self.assertEqual(info, {"valor": TEXTO_AFILIADO_SIN_DATO, "categoria": "sin_dato"})

    def test_solo_espacios_es_sin_dato(self):
        info = getAfiliadoInfo(_fila("   "))
        self.assertEqual(info, {"valor": TEXTO_AFILIADO_SIN_DATO, "categoria": "sin_dato"})

    def test_none_es_sin_dato(self):
        info = getAfiliadoInfo(_fila(None))
        self.assertEqual(info, {"valor": TEXTO_AFILIADO_SIN_DATO, "categoria": "sin_dato"})

    def test_nan_es_sin_dato(self):
        info = getAfiliadoInfo(_fila(float("nan")))
        self.assertEqual(info, {"valor": TEXTO_AFILIADO_SIN_DATO, "categoria": "sin_dato"})

    def test_columna_inexistente_es_sin_dato_y_no_rompe(self):
        fila = _fila(incluir_columna=False, vName="JUAN PEREZ")
        self.assertNotIn("vAfiliado", fila.index)
        info = getAfiliadoInfo(fila)
        self.assertEqual(info, {"valor": TEXTO_AFILIADO_SIN_DATO, "categoria": "sin_dato"})


class TestColumnaTelefono(unittest.TestCase):
    """
    La columna AP del Excel (índice 41) corresponde al encabezado real
    'Telefono' en baseConsulta.csv. Se valida que ese nombre exacto se pueda
    recuperar de una fila y que NO se haya agregado a COLUMNAS_REQUERIDAS
    (para no romper cargas manuales/antiguas que no la incluyan).
    """

    def test_recupera_telefono_por_nombre_real_de_columna(self):
        from utils.formato import obtenerValorColumna

        fila = pd.Series({"vReference": "123456", "Telefono": "0445512345678"})
        valor = obtenerValorColumna(fila, "Telefono")
        self.assertEqual(valor, "0445512345678")
        # Debe conservarse como texto: sin conversión numérica ni pérdida de ceros.
        self.assertIsInstance(valor, str)
        self.assertTrue(valor.startswith("04455"))

    def test_telefono_no_es_columna_requerida(self):
        self.assertNotIn("Telefono", COLUMNAS_REQUERIDAS)


if __name__ == "__main__":
    unittest.main()
