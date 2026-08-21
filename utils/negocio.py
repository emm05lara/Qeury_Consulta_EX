# utils/negocio.py
# Módulo de lógica de negocio específica del dashboard de cobranza.
# Todos los helpers aquí son NUEVOS y no modifican utils existentes.
#
# Helpers públicos:
#   - getPagoInfo(fila)          → dict con info del pago más reciente
#   - getMontoPagadoTotal(fila)  → float con nPaid + pagoDetectado
#   - isDescuentoEnabled(bucket) → bool, true si bucket es E o mayor (90+)
#   - getSemaforo(fila)          → dict con color, label, motivo y hex_bg
#   - getAfiliadoInfo(fila)      → dict con el valor real de vAfiliado y su categoría visual

import re

import pandas as pd
from utils.formato import obtenerValorColumna, TEXTO_SIN_DATO


# Texto mostrado cuando la columna vAfiliado no existe o el valor está vacío.
TEXTO_AFILIADO_SIN_DATO = "SIN DATO"

# Términos que determinan la categoría visual "pensionado" (violeta):
# "pensionado", "pensionados" o "jyp", como palabra completa (límites de
# palabra) e insensible a mayúsculas/minúsculas.
_PATRON_CATEGORIA_PENSIONADO = re.compile(
    r"\b(?:pensionados?|jyp)\b",
    flags=re.IGNORECASE,
)


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

    NUEVAS REGLAS DE NEGOCIO (Prioridad estricta):
      1. Si Bucket Inicio es E o mayor (E, F, G, H, I, J) → SIEMPRE VERDE ("Aplica convenio")
      2. Si Bucket Inicio es A, B, C, D:
         - Si nPaid >= 50% de nTAmount → AMARILLO ("Revisar status Convenio")
         - Si nPaid < 50% de nTAmount  → ROJO ("Sin Convenio")

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

    # Calcular porcentaje pagado (evitando divisiones por cero)
    rawNPaid   = obtenerValorColumna(fila, "nPaid")
    rawNTAmount = obtenerValorColumna(fila, "nTAmount")
    nPaid    = _toFloat(rawNPaid)   or 0.0
    nTAmount = _toFloat(rawNTAmount) or 0.0

    abonoSuficiente = (nTAmount > 0) and (nPaid >= 0.5 * nTAmount)

    # ── Prioridad 1: VERDE (Bucket E o mayor) ──
    if letra in _BUCKETS_DESCUENTO:
        return {
            "color":    "verde",
            "label":    "Aplica convenio",
            "motivo":   f"Bucket {letra} — 90+ días",
            "hex_bg":   "#0f2d12",
            "hex_text": "#3fb950",
            "hex_brd":  "#238636",
            "emoji":    "🟢",
        }

    # ── Prioridad 2: AMARILLO (Bucket A-D y abono >= 50%) ──
    if letra in _BUCKETS_VERDE and abonoSuficiente:
        return {
            "color":    "amarillo",
            "label":    "Revisar status Convenio",
            "motivo":   f"Bucket {letra} con nPaid ≥ 50%",
            "hex_bg":   "#2d1f00",
            "hex_text": "#e3b341",
            "hex_brd":  "#9e6a03",
            "emoji":    "🟡",
        }

    # ── Prioridad 3: ROJO (Bucket A-D y abono < 50% o casos no definidos) ──
    return {
        "color":    "rojo",
        "label":    "Sin Convenio",
        "motivo":   f"Bucket {letra if letra else '?'} con nPaid < 50%",
        "hex_bg":   "#2d0e0e",
        "hex_text": "#f85149",
        "hex_brd":  "#da3633",
        "emoji":    "🔴",
    }


# ─────────────────────────────────────────────────────────────────
#  getAfiliadoInfo
# ─────────────────────────────────────────────────────────────────

def getAfiliadoInfo(fila: pd.Series) -> dict:
    """
    Determina cómo presentar el campo 'vAfiliado' del cliente.

    IMPORTANTE: el texto original de la celda NUNCA se reemplaza ni se
    transforma (solo se le aplica strip()). La categoría es puramente una
    etiqueta interna para decidir el estilo visual (verde/violeta/gris);
    no debe mostrarse en lugar del valor real.

    Reglas:
      - Columna 'vAfiliado' ausente, o valor None/NaN/vacío/solo espacios
        → valor "SIN DATO", categoría "sin_dato".
      - Valor que contenga el término "pensionado", "pensionados" o "jyp"
        como palabra completa (insensible a mayúsculas) → categoría
        "pensionado" (estilo violeta).
      - Cualquier otro contenido no vacío → categoría "activo" (estilo verde).

    Args:
        fila: pd.Series con los datos del cliente.

    Returns:
        {
          "valor":     str  (texto original de la celda, o "SIN DATO"),
          "categoria": str  ("activo" | "pensionado" | "sin_dato"),
        }
    """
    if "vAfiliado" not in fila.index:
        return {"valor": TEXTO_AFILIADO_SIN_DATO, "categoria": "sin_dato"}

    valorCrudo = obtenerValorColumna(fila, "vAfiliado")
    if valorCrudo is None:
        return {"valor": TEXTO_AFILIADO_SIN_DATO, "categoria": "sin_dato"}
    if isinstance(valorCrudo, float) and pd.isna(valorCrudo):
        return {"valor": TEXTO_AFILIADO_SIN_DATO, "categoria": "sin_dato"}

    valorTexto = str(valorCrudo).strip()
    if valorTexto == "":
        return {"valor": TEXTO_AFILIADO_SIN_DATO, "categoria": "sin_dato"}

    if _PATRON_CATEGORIA_PENSIONADO.search(valorTexto.casefold()):
        categoria = "pensionado"
    else:
        categoria = "activo"

    return {"valor": valorTexto, "categoria": categoria}
