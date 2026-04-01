# utils/formato.py
# Módulo de formateo de valores: monedas, fechas, nulos

import pandas as pd


# Texto a mostrar cuando un campo no tiene dato disponible
TEXTO_SIN_DATO = "—"


def formatearMoneda(valor, prefijo: str = "$") -> str:
    """
    Formatea un valor numérico como moneda con separadores de miles y 2 decimales.
    Si el valor es nulo, vacío o no convertible, retorna TEXTO_SIN_DATO.

    Args:
        valor: Valor a formatear (str, int, float, None, NaN).
        prefijo: Símbolo de moneda (por defecto '$').

    Returns:
        String formateado como moneda o TEXTO_SIN_DATO.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return TEXTO_SIN_DATO

    try:
        valorStr = str(valor).strip()
        if valorStr == "" or valorStr.lower() in ("nan", "none", "null"):
            return TEXTO_SIN_DATO

        # Eliminar símbolos existentes de moneda o comas para limpiar el valor
        valorStr = valorStr.replace(",", "").replace("$", "").strip()
        valorFloat = float(valorStr)
        return f"{prefijo}{valorFloat:,.2f}"
    except (ValueError, TypeError):
        return TEXTO_SIN_DATO


def formatearFecha(valor) -> str:
    """
    Intenta parsear y formatear una fecha de forma legible (DD/MM/YYYY).
    Si el valor es nulo, vacío o no parseable, retorna TEXTO_SIN_DATO.

    Args:
        valor: Valor a formatear (str, datetime, None, NaN).

    Returns:
        String de fecha formateado o TEXTO_SIN_DATO.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return TEXTO_SIN_DATO

    try:
        valorStr = str(valor).strip()
        if valorStr == "" or valorStr.lower() in ("nan", "none", "null", "nat"):
            return TEXTO_SIN_DATO

        fechaParseada = pd.to_datetime(valorStr, dayfirst=True, infer_datetime_format=True)
        return fechaParseada.strftime("%d/%m/%Y")
    except Exception:
        # Si no se puede parsear, devolver el valor original como string
        return str(valor).strip() if str(valor).strip() else TEXTO_SIN_DATO


def formatearTexto(valor) -> str:
    """
    Retorna un valor de texto limpio. Si es nulo o vacío, retorna TEXTO_SIN_DATO.

    Args:
        valor: Valor a limpiar (str, None, NaN).

    Returns:
        String limpio o TEXTO_SIN_DATO.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return TEXTO_SIN_DATO

    valorStr = str(valor).strip()
    if valorStr == "" or valorStr.lower() in ("nan", "none", "null"):
        return TEXTO_SIN_DATO

    return valorStr


def obtenerValorColumna(fila: pd.Series, nombreColumna: str, default=None):
    """
    Extrae de forma segura el valor de una columna en una fila/Serie de pandas.
    Retorna `default` si la columna no existe.

    Args:
        fila: pd.Series con los datos del cliente.
        nombreColumna: Nombre exacto de la columna.
        default: Valor por defecto si la columna no existe.

    Returns:
        Valor de la celda o `default`.
    """
    if nombreColumna not in fila.index:
        return default
    valor = fila[nombreColumna]
    # Tratar NaN de pandas como None para manejo uniforme
    if isinstance(valor, float) and pd.isna(valor):
        return None
    return valor
