# utils/carga.py
# Módulo de carga y validación del archivo de datos (CSV o Excel)
#
# ESTRATEGIA DE CARGA (orden de prioridad):
#   1. Archivo precargado desde el repositorio: data/baseConsulta.xlsx (o .csv)
#   2. Carga manual desde la sidebar como modo de respaldo.
#
# Para actualizar los datos, simplemente reemplaza el archivo en data/ y
# haz push. Al redeploy en Render, la app usará el nuevo archivo automáticamente.

import gc
import os
from typing import NamedTuple

import pandas as pd
import streamlit as st

from utils.memoria import registrarMemoria

# ─────────────────────────────────────────────────────────────────
#  RUTA DEL ARCHIVO PRECARGADO
#  Edita esta constante si cambias el nombre o la ubicación del archivo.
# ─────────────────────────────────────────────────────────────────
# Ruta relativa calculada desde la raíz del proyecto (donde vive app.py).
# Soporta Excel (.xlsx) o CSV (.csv); se detecta automáticamente.
RUTA_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Nombres posibles del archivo de datos (se probarán en orden).
# El primero que exista será usado.
NOMBRES_ARCHIVO_DATOS = [
    "baseConsulta.xlsx",
    "baseConsulta.xls",
    "baseConsulta.csv",
]

# Hoja de Excel a usar cuando el archivo tiene múltiples hojas.
# Usa None para que pandas seleccione la primera hoja automáticamente.
HOJA_EXCEL_DEFECTO = 0   # 0 = primera hoja (índice); cambia a nombre si lo prefieres

# Columnas requeridas para el funcionamiento del dashboard.
# Se buscan por nombre de encabezado, no por posición.
COLUMNAS_REQUERIDAS = [
    "vReference",
    "iPersonId_x",   # Llave única del cliente — usada para agrupar préstamos
    "vName",
    "Bucket Inicio",
    "nDescuento",
    "Amortizacion",
    "nDueBalance_x",  # Saldo Vencido
    "Minimo para contener",
    "Monto Liquidacion",
    "Gestor",
    "Pago domi",      # Pago Domiciliado
    "Pago cash",      # Pago en Efectivo
    "F.Aplicacion",
    "vUltPago",
    "nTotBalance",
    "vOpenned",
    "nAmount",
    "vFrecuencia",
    "nTAmount",
]

# Columnas opcionales: la app las lee si existen, pero funciona sin ellas
# (los valores ausentes se muestran como TEXTO_SIN_DATO).
COLUMNAS_OPCIONALES = [
    "Telefono",
    "Tipo",            # mostrado como "Institución"
    "nPaid",
    "nDueBalance_y",
    "iCredId",
    "vEstatCred_x",
    "vEstatCred_y",
    "vDateMovement",
    "vAfiliado",
]

# ÚNICA definición de las columnas que se cargan en memoria. El archivo
# completo tiene ~89 columnas; solo estas se leen (usecols). Si el código
# empieza a usar otra columna, debe agregarse aquí (lo verifica tests/test_carga.py).
COLUMNAS_USADAS = COLUMNAS_REQUERIDAS + [
    c for c in COLUMNAS_OPCIONALES if c not in COLUMNAS_REQUERIDAS
]
_COLUMNAS_USADAS_SET = frozenset(COLUMNAS_USADAS)


class BaseRepo(NamedTuple):
    """
    Base del repositorio compartida por todas las sesiones.

    CONTRATO DE SOLO LECTURA: `df` es el MISMO objeto para todas las sesiones.
    Nadie debe modificarlo en sitio (asignar columnas, inplace=True, etc.);
    quien necesite alterar datos debe trabajar sobre una copia del subconjunto.
    """
    df: pd.DataFrame
    nombre: str
    columnasArchivo: tuple   # encabezados originales (todas las columnas del archivo)


# ─────────────────────────────────────────────────────────────────
#  CARGA DESDE EL REPOSITORIO (flujo principal)
# ─────────────────────────────────────────────────────────────────

def rutaArchivoRepo() -> str | None:
    """
    Busca el archivo de datos precargado dentro de la carpeta data/.
    Retorna la ruta absoluta del primer archivo encontrado, o None si no existe ninguno.

    Returns:
        str con la ruta absoluta, o None.
    """
    for nombre in NOMBRES_ARCHIVO_DATOS:
        rutaCompleta = os.path.join(RUTA_DATA_DIR, nombre)
        if os.path.exists(rutaCompleta):
            return rutaCompleta
    return None


def _esColumnaUsada(nombre) -> bool:
    return str(nombre).strip() in _COLUMNAS_USADAS_SET


def _leerCsvSelectivo(origen) -> tuple[pd.DataFrame, list[str]]:
    """
    Lee solo las columnas de COLUMNAS_USADAS de un CSV (ruta o archivo subido).
    Devuelve (df, encabezados originales del archivo, ya sin espacios).
    Intenta UTF-8 y, si falla, latin-1 (igual que antes).
    """
    kwEncoding = {}
    try:
        df = pd.read_csv(origen, dtype=str, usecols=_esColumnaUsada)
    except UnicodeDecodeError:
        kwEncoding = {"encoding": "latin-1"}
        if hasattr(origen, "seek"):
            origen.seek(0)
        df = pd.read_csv(origen, dtype=str, usecols=_esColumnaUsada, **kwEncoding)

    # Encabezados completos: se leen 0 filas, no se cargan datos.
    if hasattr(origen, "seek"):
        origen.seek(0)
    encabezados = pd.read_csv(origen, dtype=str, nrows=0, **kwEncoding).columns
    df.columns = df.columns.str.strip()
    return df, [str(c).strip() for c in encabezados]


def _leerExcelSelectivo(origen) -> tuple[pd.DataFrame, list[str]]:
    """
    Lee la hoja configurada y conserva solo las columnas de COLUMNAS_USADAS.
    (Excel no permite leer por columnas sin parsear la hoja; la reducción se
    hace de inmediato y el DataFrame completo se libera.)
    """
    df = pd.read_excel(origen, sheet_name=HOJA_EXCEL_DEFECTO, dtype=str)
    df.columns = df.columns.str.strip()
    encabezados = list(df.columns)
    df = df[[c for c in df.columns if c in _COLUMNAS_USADAS_SET]].copy()
    return df, encabezados


def leerDatos(origen, nombreArchivo: str) -> tuple[pd.DataFrame, list[str]] | None:
    """
    Lee un archivo de datos (ruta o archivo subido) cargando solo las columnas
    usadas. Retorna (df, encabezados originales) o None si el formato no es compatible.
    """
    nombre = nombreArchivo.lower()
    if nombre.endswith(".csv"):
        return _leerCsvSelectivo(origen)
    if nombre.endswith((".xlsx", ".xls")):
        return _leerExcelSelectivo(origen)
    return None


def _firmaArchivo(ruta: str) -> tuple[int, int]:
    """(mtime_ns, tamaño): si el archivo cambia, la caché compartida se renueva."""
    info = os.stat(ruta)
    return info.st_mtime_ns, info.st_size


@st.cache_resource(max_entries=1, show_spinner=False)
def _cargarBaseCacheada(ruta: str, firma: tuple) -> BaseRepo | None:
    """
    Carga la base del repo UNA vez por proceso (y por versión del archivo) y
    la comparte entre todas las sesiones. `firma` forma parte de la clave de
    caché. Si las columnas requeridas faltan retorna None (barato de cachear).
    Los errores de lectura se propagan: Streamlit no los cachea y se reintentan.
    """
    registrarMemoria("antes_carga_base")
    resultado = leerDatos(ruta, os.path.basename(ruta))
    if resultado is None:
        raise ValueError("Formato de archivo no compatible")
    df, encabezados = resultado
    esValido, _ = validarColumnas(df)
    base = BaseRepo(df, os.path.basename(ruta), tuple(encabezados)) if esValido else None
    registrarMemoria("despues_carga_base")
    return base


def cargarBaseRepo() -> BaseRepo | None:
    """
    Retorna la base compartida del repositorio, o None si no existe, no es
    válida (faltan columnas requeridas) o no se pudo leer (se muestra el error).
    """
    ruta = rutaArchivoRepo()
    if ruta is None:
        return None
    try:
        return _cargarBaseCacheada(ruta, _firmaArchivo(ruta))
    except Exception as e:
        # El error se mostrará en la UI desde app.py
        st.error(f"❌ Error al leer el archivo del repositorio: {e}")
        return None


def recargarBaseRepo() -> None:
    """
    Invalida la base compartida (para todas las sesiones). La siguiente llamada
    a cargarBaseRepo() la vuelve a leer. Se libera ANTES de la nueva lectura para
    no tener dos versiones a la vez; si otra sesión está en pleno render, conserva
    su referencia hasta que termine ese rerun.
    """
    _cargarBaseCacheada.clear()
    gc.collect()
    registrarMemoria("despues_invalidar_cache")


def obtenerNombreArchivoRepo() -> str | None:
    """
    Retorna solo el nombre del archivo de datos del repo, o None si no existe.

    Returns:
        str con el nombre del archivo, o None.
    """
    ruta = rutaArchivoRepo()
    return os.path.basename(ruta) if ruta else None


# ─────────────────────────────────────────────────────────────────
#  CARGA DESDE UPLOADER (modo de respaldo / manual)
# ─────────────────────────────────────────────────────────────────

def cargarArchivo(archivoSubido) -> tuple[pd.DataFrame, list[str]] | tuple[None, None]:
    """
    Carga un archivo CSV o Excel subido manualmente por el usuario.
    Este es el modo secundario/respaldo; el flujo principal es cargarBaseRepo().
    Solo se conservan las columnas de COLUMNAS_USADAS.

    Args:
        archivoSubido: Objeto de archivo de Streamlit (st.file_uploader).

    Returns:
        (DataFrame, encabezados originales del archivo) o (None, None) si hay error.
    """
    try:
        resultado = leerDatos(archivoSubido, archivoSubido.name)
        if resultado is None:
            st.error("❌ Formato no compatible. Por favor sube un archivo .csv o .xlsx")
            return None, None
        return resultado

    except Exception as e:
        st.error(f"❌ Error al cargar el archivo: {e}")
        return None, None


# ─────────────────────────────────────────────────────────────────
#  VALIDACIÓN Y BÚSQUEDA
# ─────────────────────────────────────────────────────────────────

def validarColumnas(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    Verifica que el DataFrame contenga las columnas mínimas requeridas.

    Args:
        df: DataFrame a validar.

    Returns:
        Tuple (es_valido: bool, columnas_faltantes: list[str])
    """
    columnasFaltantes = [col for col in COLUMNAS_REQUERIDAS if col not in df.columns]
    esValido = len(columnasFaltantes) == 0
    return esValido, columnasFaltantes


def buscarCliente(df: pd.DataFrame, valorVReference: str) -> pd.DataFrame:
    """
    Busca filas en el DataFrame cuya columna 'vReference' coincida con el valor dado.
    La búsqueda es insensible a mayúsculas/minúsculas y espacios en blanco.

    Args:
        df: DataFrame cargado.
        valorVReference: Valor a buscar en la columna vReference.

    Returns:
        DataFrame con las filas que coinciden (puede estar vacío si no hay resultados).
    """
    valorNormalizado = str(valorVReference).strip()
    mascara = df["vReference"].astype(str).str.strip().str.lower() == valorNormalizado.lower()
    resultados = df[mascara].copy()
    return resultados


def buscarOtrosVReference(df: pd.DataFrame, iPersonId: str, vReferenceActual: str) -> pd.DataFrame:
    """
    Dado un iPersonId_x, devuelve todos los registros del mismo cliente
    excluyendo el vReference actual.

    Columna clave del cliente: iPersonId_x
    Identificador de préstamo:  vReference

    Args:
        df:               DataFrame completo cargado.
        iPersonId:        Valor de iPersonId_x del registro actual.
        vReferenceActual: vReference del registro que se está viendo (se excluye).

    Returns:
        DataFrame con los demás préstamos del cliente.
        Puede estar vacío si el cliente solo tiene un préstamo.
    """
    if "iPersonId_x" not in df.columns or "vReference" not in df.columns:
        return pd.DataFrame()

    personIdNorm = str(iPersonId).strip()
    vRefNorm = str(vReferenceActual).strip().lower()

    # Filtrar por mismo cliente
    mascCliente = df["iPersonId_x"].astype(str).str.strip() == personIdNorm
    todosDelCliente = df[mascCliente].copy()

    # Excluir el vReference actual
    mascExcluir = todosDelCliente["vReference"].astype(str).str.strip().str.lower() != vRefNorm
    otros = todosDelCliente[mascExcluir].copy()

    # Eliminar duplicados de vReference
    if not otros.empty:
        otros = otros.drop_duplicates(subset=["vReference"])

    return otros
