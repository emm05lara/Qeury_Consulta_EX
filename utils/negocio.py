# utils/negocio.py
# Módulo de lógica de negocio específica del dashboard de cobranza.
# Todos los helpers aquí son NUEVOS y no modifican utils existentes.
#
# Helpers públicos:
#   - getPagoInfo(fila)          → dict con info del pago más reciente
#   - getMontoPagadoTotal(fila)  → float con nPaid + pagoDetectado
#   - isDescuentoEnabled(bucket) → bool, true si bucket es E o mayor (90+)
#   - getSemaforo(fila)          → dict con color, label, motivo y hex_bg

import pandas as pd
from utils.formato import obtenerValorColumna, TEXTO_SIN_DATO


# ─────────────────────────────────────────────────────────────────
#  HELPER INTERNO: Parseo robusto de Bucket Inicio
# ─────────────────────────────────────────────────────────────────
# Bucket puede venir como:
#   "A", "B", "C", "D", "E" ...
#   "D) 61 a 90", "E) 91 a 120"  (con texto descriptivo)
# Siempre se extrae la primera letra en mayúscula.

def _parsearLetraBucket(valor) -> str:
    """
    Extrae la letra inicial del Bucket Inicio de forma robusta.
    Retorna la letra en mayúsculas o cadena vacía si no se puede determinar.

    Ejemplos:
        "D) 61 a 90" → "D"
        "e"          → "E"
        ""           → ""
        None         → ""
    """
    if valor is None:
        return ""
    s = str(valor).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return ""
    # Tomar el primer carácter y convertir a mayúscula
    primera = s[0].upper()
    # Verificar que sea una letra del alfabeto
    if primera.isalpha():
        return primera
    return ""


# Letras de bucket que califican para descuento (90+ días)
_BUCKETS_DESCUENTO = {"E", "F", "G", "H", "I", "J"}

# Letras de bucket "al corriente" (sin vencimiento grave)
_BUCKETS_VERDE = {"A", "B", "C", "D"}


# ─────────────────────────────────────────────────────────────────
#  HELPER INTERNO: Conversión segura a float
# ─────────────────────────────────────────────────────────────────

def _toFloat(valor) -> float | None:
    """
    Convierte un valor a float de forma segura.
    Retorna None si no es convertible.
    """
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    try:
        s = str(valor).strip().replace(",", "").replace("$", "")
        if s == "" or s.lower() in ("nan", "none", "null"):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────
#  getPagoInfo
# ─────────────────────────────────────────────────────────────────

def getPagoInfo(fila: pd.Series) -> dict:
    """
    Detecta el pago más reciente y su tipo (domi o cash).

    Reglas de negocio:
    - Pago domiciliado: monto en columna 'Pago domi', fecha en 'vDateMovement'
    - Pago en efectivo: monto en columna 'Pago cash',  fecha en 'F.Aplicacion'
    - Si solo uno tiene valor > 0  → usar ese
    - Si ambos tienen valor > 0    → sumar ambos (pagoDetectado = suma)
    - Si ambos son 0 o vacíos      → pagoDetectado = 0

    Retorna:
        {
          "tipoPago":      str  ("domi" | "cash" | "ambos" | "ninguno"),
          "montoPago":     float (monto relevante o 0),
          "fechaPago":     valor crudo de la columna de fecha correspondiente,
          "pagoDomi":      float,
          "pagoCash":      float,
          "pagoDetectado": float  (valor final a usar en cálculos),
        }
    """
    rawDomi = obtenerValorColumna(fila, "Pago domi")
    rawCash = obtenerValorColumna(fila, "Pago cash")
    fechaDomi = obtenerValorColumna(fila, "vDateMovement")
    fechaCash = obtenerValorColumna(fila, "F.Aplicacion")

    pagoDomi = _toFloat(rawDomi) or 0.0
    pagoCash = _toFloat(rawCash) or 0.0

    tieneDomi = pagoDomi > 0
    tieneCash = pagoCash > 0

    if tieneDomi and tieneCash:
        # Ambos tienen valor: mostrar ambos y sumar
        return {
            "tipoPago":      "ambos",
            "montoPago":     pagoDomi + pagoCash,
            "fechaPago":     fechaCash,   # fecha principal = F.Aplicacion cuando hay ambos
            "pagoDomi":      pagoDomi,
            "pagoCash":      pagoCash,
            "pagoDetectado": pagoDomi + pagoCash,
        }
    elif tieneDomi:
        return {
            "tipoPago":      "domi",
            "montoPago":     pagoDomi,
            "fechaPago":     fechaDomi,
            "pagoDomi":      pagoDomi,
            "pagoCash":      pagoCash,
            "pagoDetectado": pagoDomi,
        }
    elif tieneCash:
        return {
            "tipoPago":      "cash",
            "montoPago":     pagoCash,
            "fechaPago":     fechaCash,
            "pagoDomi":      pagoDomi,
            "pagoCash":      pagoCash,
            "pagoDetectado": pagoCash,
        }
    else:
        return {
            "tipoPago":      "ninguno",
            "montoPago":     0.0,
            "fechaPago":     None,
            "pagoDomi":      0.0,
            "pagoCash":      0.0,
            "pagoDetectado": 0.0,
        }


# ─────────────────────────────────────────────────────────────────
#  getMontoPagadoTotal
# ─────────────────────────────────────────────────────────────────

def getMontoPagadoTotal(fila: pd.Series) -> float:
    """
    Calcula el monto pagado total visible:
        nPaid + pagoDetectado

    - nPaid          = lo que el cliente ha pagado al corte
    - pagoDetectado  = Pago domi o Pago cash (o suma si ambos > 0)

    Si nPaid no existe o es nulo, se trata como 0.
    """
    rawNPaid = obtenerValorColumna(fila, "nPaid")
    nPaid = _toFloat(rawNPaid) or 0.0

    pagoInfo = getPagoInfo(fila)
    pagoDetectado = pagoInfo["pagoDetectado"]

    return round(nPaid + pagoDetectado, 2)


# ─────────────────────────────────────────────────────────────────
#  isDescuentoEnabled
# ─────────────────────────────────────────────────────────────────

def isDescuentoEnabled(bucketInicio) -> bool:
    """
    Determina si la calculadora de descuento aplica para este crédito.
    Solo aplica cuando Bucket Inicio es E, F, G, H, I o J (90+ días).

    Args:
        bucketInicio: Valor crudo de la columna 'Bucket Inicio'

    Returns:
        True si aplica descuento, False en caso contrario.
    """
    letra = _parsearLetraBucket(bucketInicio)
    return letra in _BUCKETS_DESCUENTO


# ─────────────────────────────────────────────────────────────────
#  getSemaforo
# ─────────────────────────────────────────────────────────────────

def getSemaforo(fila: pd.Series) -> dict:
    """
    Calcula el estado del semáforo de riesgo del crédito.

    Prioridad (implementada en este orden para evitar conflictos):
      1. Bucket A/B/C/D → VERDE  ("Aplica convenio")
      2. nPaid >= 50% de nTAmount Y no es A/B/C/D → AMARILLO ("Revisar status Convenio")
      3. Bucket E en adelante Y no cumple amarillo → ROJO ("Sin Convenio")
      4. Si bucket desconocido y no aplica amarillo → ROJO por defecto

    La prioridad VERDE sobre AMARILLO es intencional por coherencia de negocio:
    si el cliente está en bucket bajo (A-D), siempre se le ofrece convenio
    independientemente de cuánto haya pagado ya.

    Returns:
        {
          "color":   str ("verde" | "amarillo" | "rojo"),
          "label":   str (texto a mostrar),
          "motivo":  str (explicación breve),
          "hex_bg":  str (color de fondo HEX para CSS),
          "hex_text":str (color de texto HEX para CSS),
          "hex_brd": str (color de borde HEX para CSS),
          "emoji":   str,
        }
    """
    bucketRaw = obtenerValorColumna(fila, "Bucket Inicio")
    letra = _parsearLetraBucket(bucketRaw)

    # Calcular si aplica AMARILLO: nPaid >= 50% de nTAmount
    rawNPaid   = obtenerValorColumna(fila, "nPaid")
    rawNTAmount = obtenerValorColumna(fila, "nTAmount")
    nPaid    = _toFloat(rawNPaid)   or 0.0
    nTAmount = _toFloat(rawNTAmount) or 0.0

    aplicaAmarillo = (nTAmount > 0) and (nPaid >= 0.5 * nTAmount)

    # ── Prioridad 1: VERDE ──
    if letra in _BUCKETS_VERDE:
        return {
            "color":    "verde",
            "label":    "Aplica convenio",
            "motivo":   f"Bucket {letra} — al corriente",
            "hex_bg":   "#0f2d12",
            "hex_text": "#3fb950",
            "hex_brd":  "#238636",
            "emoji":    "🟢",
        }

    # ── Prioridad 2: AMARILLO ──
    if aplicaAmarillo:
        return {
            "color":    "amarillo",
            "label":    "Revisar status Convenio",
            "motivo":   f"nPaid ≥ 50% del pagaré (Bucket {letra if letra else '?'})",
            "hex_bg":   "#2d1f00",
            "hex_text": "#e3b341",
            "hex_brd":  "#9e6a03",
            "emoji":    "🟡",
        }

    # ── Prioridad 3: ROJO (bucket E+ o desconocido sin pago suficiente) ──
    return {
        "color":    "rojo",
        "label":    "Sin Convenio",
        "motivo":   f"Bucket {letra if letra else '?'} — vencido 90+ días",
        "hex_bg":   "#2d0e0e",
        "hex_text": "#f85149",
        "hex_brd":  "#da3633",
        "emoji":    "🔴",
    }
