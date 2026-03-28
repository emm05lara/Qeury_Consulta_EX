# utils/carga.py
# Módulo de carga y validación del archivo de datos (CSV o Excel)
#
# ESTRATEGIA DE CARGA (orden de prioridad):
#   1. Archivo precargado desde el repositorio: data/baseConsulta.xlsx (o .csv)
#   2. Carga manual desde la sidebar como modo de respaldo.
#
# Para actualizar los datos, simplemente reemplaza el archivo en data/ y
# haz push. Al redeploy en Render, la app usará el nuevo archivo automáticamente.

import os
import pandas as pd
import streamlit as st

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
    "vName",
    "Bucket Inicio",
    "nDescuento",
    "Amortizacion",
    "nDueBalance_x",
    "Minimo para contener",
    "Monto Liquidacion",
    "Gestor",
    "Pago cash",
    "F.Aplicacion",
    "vUltPago",
    "nTotBalance",
    "vOpenned",
    "nAmount",
    "vFrecuencia",
    "nTAmount",
]


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


def cargarDesdeRepo() -> pd.DataFrame | None:
    """
    Carga el archivo de datos desde la ruta del repositorio (data/).
    Soporta .xlsx, .xls y .csv.
    Retorna el DataFrame o None si hay error / archivo no encontrado.

    Returns:
        pd.DataFrame o None.
    """
    ruta = rutaArchivoRepo()
    if ruta is None:
        return None

    try:
        nombreArchivo = os.path.basename(ruta).lower()

        if nombreArchivo.endswith(".csv"):
            # Intentar primero UTF-8, luego latin-1 como fallback
            try:
                df = pd.read_csv(ruta, dtype=str)
            except UnicodeDecodeError:
                df = pd.read_csv(ruta, dtype=str, encoding="latin-1")

        elif nombreArchivo.endswith((".xlsx", ".xls")):
            # Cargar hoja configurada (por defecto la primera)
            df = pd.read_excel(ruta, sheet_name=HOJA_EXCEL_DEFECTO, dtype=str)

        else:
            return None

        # Limpiar espacios en nombres de columnas
        df.columns = df.columns.str.strip()
        return df

    except Exception as e:
        # El error se mostrará en la UI desde app.py
        st.error(f"❌ Error al leer el archivo del repositorio: {e}")
        return None


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

def cargarArchivo(archivoSubido) -> pd.DataFrame | None:
    """
    Carga un archivo CSV o Excel subido manualmente por el usuario y retorna un DataFrame.
    Este es el modo secundario/respaldo; el flujo principal es cargarDesdeRepo().
    Retorna None si hay un error en la carga.

    Args:
        archivoSubido: Objeto de archivo de Streamlit (st.file_uploader).

    Returns:
        pd.DataFrame o None si ocurre un error.
    """
    try:
        nombreArchivo = archivoSubido.name.lower()

        if nombreArchivo.endswith(".csv"):
            try:
                df = pd.read_csv(archivoSubido, dtype=str)
            except UnicodeDecodeError:
                archivoSubido.seek(0)
                df = pd.read_csv(archivoSubido, dtype=str, encoding="latin-1")

        elif nombreArchivo.endswith((".xlsx", ".xls")):
            # Para archivos subidos manualmente, cargamos la primera hoja
            df = pd.read_excel(archivoSubido, sheet_name=HOJA_EXCEL_DEFECTO, dtype=str)

        else:
            st.error("❌ Formato no compatible. Por favor sube un archivo .csv o .xlsx")
            return None

        # Limpiar espacios en nombres de columnas y en valores de texto
        df.columns = df.columns.str.strip()
        return df

    except Exception as e:
        st.error(f"❌ Error al cargar el archivo: {e}")
        return None


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
