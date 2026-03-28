# utils/calculos.py
# Módulo de campos calculados y lógica de negocio derivada

import pandas as pd
from utils.formato import obtenerValorColumna, TEXTO_SIN_DATO


def calcularPlazo(fila: pd.Series) -> str:
    """
    Calcula el Plazo como: nTAmount / nDescuento
    Devuelve el resultado como entero (si es exacto) o TEXTO_SIN_DATO si no es calculable.

    Reglas:
    - Si nDescuento es 0, nulo o no numérico -> TEXTO_SIN_DATO
    - Si nTAmount es nulo o no numérico       -> TEXTO_SIN_DATO
    - De lo contrario -> resultado como entero redondeado

    Args:
        fila: pd.Series con los datos del cliente.

    Returns:
        String con el plazo como entero o TEXTO_SIN_DATO.
    """
    valorTAmount = obtenerValorColumna(fila, "nTAmount")
    valorDescuento = obtenerValorColumna(fila, "nDescuento")

    try:
        # Limpiar y convertir nDescuento
        descuento = _convertirAFloat(valorDescuento)
        if descuento is None or descuento == 0.0:
            return TEXTO_SIN_DATO

        # Limpiar y convertir nTAmount
        tAmount = _convertirAFloat(valorTAmount)
        if tAmount is None:
            return TEXTO_SIN_DATO

        resultado = tAmount / descuento

        # Mostrar como entero si el resultado es un número entero exacto
        if resultado == int(resultado):
            return str(int(resultado))
        else:
            return f"{resultado:.2f}"

    except (ZeroDivisionError, ValueError, TypeError):
        return TEXTO_SIN_DATO


def _convertirAFloat(valor) -> float | None:
    """
    Convierte un valor (str, int, float, None) a float de forma segura.
    Retorna None si no es posible la conversión.

    Args:
        valor: Valor a convertir.

    Returns:
        float o None.
    """
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None

    try:
        valorStr = str(valor).strip().replace(",", "").replace("$", "")
        if valorStr == "" or valorStr.lower() in ("nan", "none", "null"):
            return None
        return float(valorStr)
    except (ValueError, TypeError):
        return None
