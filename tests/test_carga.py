# tests/test_carga.py
# Pruebas de la carga selectiva (usecols) y de la base compartida entre sesiones.
# Solo datos sintéticos; usa unittest + pandas (dependencias del proyecto).

import glob
import io
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd
from pandas.testing import assert_frame_equal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from utils import carga
from utils.carga import (
    COLUMNAS_OPCIONALES,
    COLUMNAS_REQUERIDAS,
    COLUMNAS_USADAS,
    BaseRepo,
    buscarCliente,
    buscarOtrosVReference,
    cargarArchivo,
    cargarBaseRepo,
    leerDatos,
    recargarBaseRepo,
)
from utils.negocio import getAfiliadoInfo, getPagoInfo, getSemaforo

# Columnas que existen en el archivo pero la app no usa (con un encabezado con
# espacios y otro con acento, como en la base real).
COLUMNAS_EXTRA = ["Etiqueta Nueva", " Bucket Gestión ", "Calle"]


def _csvSintetico(incluirOpcionales=True, extra=True) -> str:
    cols = list(COLUMNAS_REQUERIDAS)
    if incluirOpcionales:
        cols += COLUMNAS_OPCIONALES
    if extra:
        cols += COLUMNAS_EXTRA
    filas = []
    for i in range(6):
        fila = {}
        for c in cols:
            fila[c] = f"{c[:3]}{i}"
        fila["vReference"] = f"REF{i}"
        fila["iPersonId_x"] = "P1" if i < 3 else f"P{i}"   # P1 tiene 3 préstamos
        fila["Bucket Inicio"] = "E) 91 a 120" if i % 2 == 0 else "B"
        for c in ("nTAmount", "nDescuento", "Pago domi", "Pago cash", "nPaid",
                  "nAmount", "nTotBalance", "nDueBalance_x"):
            if c in fila:
                fila[c] = str(100.0 * (i + 1))
        if i == 2:
            fila["Gestor"] = ""                      # vacío -> NaN
            if "vAfiliado" in fila:
                fila["vAfiliado"] = "Pensionado"
        if i == 3 and "Telefono" in fila:
            fila["Telefono"] = ""
        filas.append(fila)
    return pd.DataFrame(filas, columns=cols).to_csv(index=False)


class _ArchivoSubido(io.BytesIO):
    """Imita el UploadedFile de Streamlit (BytesIO con .name)."""
    def __init__(self, contenido: bytes, name: str):
        super().__init__(contenido)
        self.name = name


class _BaseConRepoTemporal(unittest.TestCase):
    """Crea un data/ temporal con un CSV sintético y limpia la caché compartida."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.rutaCsv = os.path.join(self.dir.name, "baseConsulta.csv")
        with open(self.rutaCsv, "w", encoding="utf-8", newline="") as f:
            f.write(_csvSintetico())
        parche = mock.patch.object(carga, "RUTA_DATA_DIR", self.dir.name)
        parche.start()
        self.addCleanup(parche.stop)
        silencio = mock.patch.object(carga, "registrarMemoria")   # sin ruido [MEM] en pruebas
        silencio.start()
        self.addCleanup(silencio.stop)
        carga._cargarBaseCacheada.clear()
        self.addCleanup(carga._cargarBaseCacheada.clear)
        self.addCleanup(self.dir.cleanup)


class TestColumnasUsadas(unittest.TestCase):

    def test_sin_duplicados_y_contiene_requeridas(self):
        self.assertEqual(len(COLUMNAS_USADAS), len(set(COLUMNAS_USADAS)))
        for c in COLUMNAS_REQUERIDAS:
            self.assertIn(c, COLUMNAS_USADAS)

    def test_codigo_no_usa_columnas_fuera_de_columnas_usadas(self):
        """Detecta omisiones: toda columna leída en el código debe estar en COLUMNAS_USADAS."""
        patron = re.compile(
            r'obtenerValorColumna\(\s*\w+\s*,\s*"([^"]+)"'
            r'|\b(?:df|dfCompleto|todosDelCliente|otros)\[\s*"([^"]+)"\s*\]'
            r'|"([^"]+)"\s+(?:not\s+)?in\s+(?:fila\.index|df\.columns)'
        )
        archivos = [os.path.join(RAIZ, "app.py")] + [
            f for f in glob.glob(os.path.join(RAIZ, "utils", "*.py"))
            if not f.endswith("carga.py")   # carga.py es quien define las listas
        ]
        encontradas = set()
        for ruta in archivos:
            with open(ruta, encoding="utf-8") as f:
                for m in patron.finditer(f.read()):
                    encontradas.add(next(g for g in m.groups() if g))
        self.assertGreater(len(encontradas), 20)   # el escaneo sí encuentra columnas
        faltantes = sorted(encontradas - set(COLUMNAS_USADAS))
        self.assertEqual(faltantes, [], f"Columnas usadas en el código y no cargadas: {faltantes}")


class TestLecturaSelectiva(unittest.TestCase):

    def _leerSelectivo(self, texto, nombre="x.csv", **kw):
        return leerDatos(io.BytesIO(texto.encode("utf-8")), nombre)

    def test_solo_carga_columnas_usadas_y_conserva_valores_y_nulos(self):
        texto = _csvSintetico()
        df, enc = self._leerSelectivo(texto)
        completo = pd.read_csv(io.StringIO(texto), dtype=str)
        completo.columns = completo.columns.str.strip()

        self.assertEqual(set(df.columns), set(COLUMNAS_USADAS))
        self.assertNotIn("Calle", df.columns)
        # mismos valores (incluidos los NaN) y mismo orden de filas/columnas
        assert_frame_equal(df, completo[list(df.columns)])
        self.assertTrue(df["Gestor"].isna().iloc[2])      # vacío sigue siendo nulo
        self.assertEqual(df["vReference"].tolist(), [f"REF{i}" for i in range(6)])

    def test_conserva_todos_los_encabezados_originales(self):
        texto = _csvSintetico()
        _, enc = self._leerSelectivo(texto)
        esperados = [c.strip() for c in pd.read_csv(io.StringIO(texto), nrows=0).columns]
        self.assertEqual(enc, esperados)
        self.assertIn("Bucket Gestión", enc)               # acento y espacios limpiados
        self.assertIn("Calle", enc)                        # columna no cargada, pero listada
        self.assertGreater(len(enc), len(COLUMNAS_USADAS))

    def test_columnas_opcionales_faltantes(self):
        df, enc = self._leerSelectivo(_csvSintetico(incluirOpcionales=False))
        esValido, faltantes = carga.validarColumnas(df)
        self.assertTrue(esValido, faltantes)
        self.assertNotIn("vAfiliado", df.columns)
        # la app sigue funcionando sin ellas
        fila = df.iloc[0]
        self.assertEqual(getAfiliadoInfo(fila)["categoria"], "sin_dato")
        self.assertEqual(getPagoInfo(fila)["tipoPago"] in ("domi", "cash", "ambos", "ninguno"), True)

    def test_columna_requerida_faltante_se_reporta(self):
        texto = _csvSintetico().replace("vName", "vNombreOtro")
        df, _ = self._leerSelectivo(texto)
        esValido, faltantes = carga.validarColumnas(df)
        self.assertFalse(esValido)
        self.assertEqual(faltantes, ["vName"])

    def test_fallback_latin1(self):
        texto = _csvSintetico().replace("Calle", "Dirección")
        df, enc = leerDatos(io.BytesIO(texto.encode("latin-1")), "x.csv")
        self.assertIn("Dirección", enc)
        self.assertEqual(df["vReference"].iloc[0], "REF0")

    def test_excel_conserva_encabezados_y_reduce_columnas(self):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl no está disponible")
        df0 = pd.read_csv(io.StringIO(_csvSintetico()), dtype=str)
        buf = io.BytesIO()
        df0.to_excel(buf, index=False)
        buf.seek(0)
        df, enc = leerDatos(buf, "x.xlsx")
        self.assertEqual(set(df.columns), set(COLUMNAS_USADAS))
        self.assertIn("Calle", enc)

    def test_formato_no_compatible(self):
        self.assertIsNone(leerDatos(io.BytesIO(b"x"), "x.txt"))


class TestBaseCompartida(_BaseConRepoTemporal):

    def test_reutiliza_el_mismo_dataframe_entre_llamadas_y_sesiones(self):
        a = cargarBaseRepo()
        self.assertIsInstance(a, BaseRepo)
        for _ in range(5):   # "5 sesiones" distintas
            self.assertIs(cargarBaseRepo().df, a.df)

    def test_carga_una_sola_vez(self):
        with mock.patch.object(carga, "leerDatos", wraps=carga.leerDatos) as espia:
            cargarBaseRepo(); cargarBaseRepo(); cargarBaseRepo()
        self.assertEqual(espia.call_count, 1)

    def test_no_guarda_copia_en_session_state(self):
        import streamlit as st
        antes = dict(st.session_state)
        cargarBaseRepo()
        self.assertEqual(dict(st.session_state), antes)

    def test_recargar_invalida_y_libera_la_version_anterior(self):
        import weakref
        a = cargarBaseRepo()
        ref = weakref.ref(a.df)
        del a
        recargarBaseRepo()
        import gc; gc.collect()
        self.assertIsNone(ref(), "La base anterior sigue referenciada tras invalidar la caché")
        self.assertIsNotNone(cargarBaseRepo())

    def test_recargar_devuelve_nuevo_objeto(self):
        a = cargarBaseRepo().df
        recargarBaseRepo()
        self.assertIsNot(cargarBaseRepo().df, a)

    def test_archivo_actualizado_se_detecta(self):
        a = cargarBaseRepo().df
        with open(self.rutaCsv, "w", encoding="utf-8", newline="") as f:
            f.write(_csvSintetico().replace("REF0", "REFNUEVA"))
        b = cargarBaseRepo().df
        self.assertIsNot(a, b)
        self.assertEqual(b["vReference"].iloc[0], "REFNUEVA")

    def test_archivo_con_columnas_invalidas_retorna_none(self):
        with open(self.rutaCsv, "w", encoding="utf-8", newline="") as f:
            f.write(_csvSintetico().replace("vName", "otra"))
        self.assertIsNone(cargarBaseRepo())

    def test_sin_archivo_retorna_none(self):
        os.remove(self.rutaCsv)
        self.assertIsNone(cargarBaseRepo())

    def test_nombre_y_encabezados_de_la_base(self):
        base = cargarBaseRepo()
        self.assertEqual(base.nombre, "baseConsulta.csv")
        self.assertIn("Calle", base.columnasArchivo)


class TestCargaManualIndependiente(_BaseConRepoTemporal):

    def test_cargas_manuales_son_independientes_entre_si_y_de_la_base(self):
        base = cargarBaseRepo().df
        contenido = _csvSintetico().encode("utf-8")
        d1, enc1 = cargarArchivo(_ArchivoSubido(contenido, "a.csv"))
        d2, enc2 = cargarArchivo(_ArchivoSubido(contenido, "b.csv"))
        self.assertIsNot(d1, d2)
        self.assertIsNot(d1, base)
        d1.loc[0, "vName"] = "MODIFICADO"       # modificar una carga manual...
        self.assertNotEqual(d2.loc[0, "vName"], "MODIFICADO")   # ...no afecta a otra
        self.assertNotEqual(base.loc[0, "vName"], "MODIFICADO")  # ni a la base
        self.assertEqual(enc1, enc2)

    def test_formato_no_compatible_retorna_none_none(self):
        self.assertEqual(cargarArchivo(_ArchivoSubido(b"x", "a.txt")), (None, None))


class TestSinMutacionYEquivalencia(_BaseConRepoTemporal):
    """Los consumidores no modifican la base compartida y dan el mismo resultado que con el archivo completo."""

    def _recorrerConsumidores(self, df):
        salidas = []
        for ref in df["vReference"].tolist() + ["NO-EXISTE"]:
            r = buscarCliente(df, ref)
            usadas = [c for c in COLUMNAS_USADAS if c in r.columns]   # la app solo lee estas
            salidas.append(("buscar", ref, r[usadas].to_dict("list")))
            if not r.empty:
                fila = r.iloc[0]
                otros = buscarOtrosVReference(df, fila["iPersonId_x"], fila["vReference"])
                salidas.append(("otros", ref, otros[usadas].to_dict("list")))
                salidas.append(("sem", ref, getSemaforo(fila)))
                salidas.append(("pago", ref, getPagoInfo(fila)))
                salidas.append(("afil", ref, getAfiliadoInfo(fila)))
        return salidas

    def test_consumidores_no_modifican_el_dataframe_compartido(self):
        df = cargarBaseRepo().df
        antes = df.copy(deep=True)
        self._recorrerConsumidores(df)
        assert_frame_equal(df, antes)
        self.assertEqual(list(df.columns), list(antes.columns))

    def test_resultados_identicos_con_archivo_completo_y_selectivo(self):
        selectivo = cargarBaseRepo().df
        completo = pd.read_csv(self.rutaCsv, dtype=str)
        completo.columns = completo.columns.str.strip()
        self.assertEqual(
            repr(self._recorrerConsumidores(selectivo)),
            repr(self._recorrerConsumidores(completo)),
        )


class TestAppCompleta(_BaseConRepoTemporal):
    """Ejecuta app.py con datos sintéticos (streamlit.testing, sin navegador)."""

    def _app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=60).run()

    def test_consulta_y_sidebar_muestran_totales_del_archivo_completo(self):
        at = self._app()
        self.assertFalse(at.exception)
        textos = " ".join(str(m.value) for m in at.sidebar.markdown)
        self.assertIn("6 registros", textos)
        self.assertIn(f"{len(pd.read_csv(self.rutaCsv, nrows=0).columns)} columnas", textos)  # no 28
        at.text_input(key="inputVReference").set_value("REF0").run()
        self.assertFalse(at.exception)
        self.assertIn("REF0", " ".join(str(m.value) for m in at.markdown))

    def test_session_state_no_guarda_la_base_del_repo(self):
        at = self._app()
        self.assertIsNone(at.session_state["dataframe"])
        self.assertEqual(at.session_state["fuenteArchivo"], "repo")

    def test_recargar_libera_la_version_anterior_aun_con_sesiones_inactivas(self):
        import gc
        import weakref
        a, b = self._app(), self._app()           # dos sesiones abiertas
        viejo = weakref.ref(cargarBaseRepo().df)
        next(x for x in a.sidebar.button if "Recargar" in x.label).click().run()
        gc.collect()
        # `b` sigue inactiva (no se re-ejecutó): aun así no debe retener la versión vieja.
        self.assertIsNone(viejo(), "Una sesión retiene la versión anterior de la base compartida")
        b.run()   # al volver a usarla, b recarga sin errores y comparte la nueva versión
        self.assertFalse(a.exception or b.exception)


class TestRegistroMemoria(unittest.TestCase):

    def setUp(self):
        from utils import memoria
        self.memoria = memoria
        memoria._ultimaVez.clear()

    def _capturar(self, **kw):
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            self.memoria.registrarMemoria("etapa_x", **kw)
        return buf.getvalue()

    def test_formato_de_la_linea(self):
        out = self._capturar()
        self.assertRegex(out, r"^\[MEM\] etapa=etapa_x proceso_rss_mb=\S+ proceso_pico_mb=\S+ "
                              r"contenedor_mb=\S+ contenedor_limite_mb=\S+\n$")

    def test_lee_proc_y_cgroup_en_linux(self):
        archivos = {
            "/proc/self/status": "Name:\tpython\nVmHWM:\t  409600 kB\nVmRSS:\t  307200 kB\n",
            "/sys/fs/cgroup/memory.current": "419430400\n",
            "/sys/fs/cgroup/memory.max": "536870912\n",
        }
        with mock.patch.object(self.memoria, "_leerTexto",
                               side_effect=lambda r: archivos.get(r, "").strip() or None):
            out = self._capturar()
        self.assertIn("proceso_rss_mb=300.0", out)
        self.assertIn("proceso_pico_mb=400.0", out)
        self.assertIn("contenedor_mb=400.0", out)
        self.assertIn("contenedor_limite_mb=512.0", out)

    def test_sin_datos_informa_nd(self):
        with mock.patch.object(self.memoria, "_leerTexto", return_value=None):
            out = self._capturar()
        self.assertIn("proceso_rss_mb=n/d", out)
        self.assertIn("contenedor_mb=n/d", out)

    def test_una_vez_y_limite_de_frecuencia(self):
        self.assertNotEqual(self._capturar(unaVez=True), "")
        self.assertEqual(self._capturar(unaVez=True), "")
        self.memoria._ultimaVez.clear()
        self.assertNotEqual(self._capturar(minIntervaloSeg=60), "")
        self.assertEqual(self._capturar(minIntervaloSeg=60), "")

    def test_nunca_lanza_excepciones(self):
        with mock.patch.object(self.memoria, "_memoriaProceso", side_effect=RuntimeError):
            self.assertEqual(self._capturar(), "")


if __name__ == "__main__":
    unittest.main()
