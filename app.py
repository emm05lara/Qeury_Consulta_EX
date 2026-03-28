# app.py
# Dashboard Ejecutivo de Cobranza - Consulta por VREFERENCE
# Desarrollado con Streamlit y pandas
# Para ejecutar: streamlit run app.py
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FLUJO DE CARGA DE DATOS
#  1. La app intenta leer data/baseConsulta.xlsx (o .csv) automáticamente.
#  2. Si ese archivo existe, se usa SIN pedir al usuario que suba nada.
#  3. La sidebar ofrece UNA opción de carga manual como respaldo.
#  4. Para actualizar datos: reemplaza el archivo en data/ y haz push/deploy.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
#  SIDEBAR SIEMPRE VISIBLE
#  Se eliminó la dependencia del botón nativo de Streamlit para colapsar/expandir.
#  En su lugar, la configuración y filtros se presentan en un panel lateral fijo
#  usando initial_sidebar_state="expanded" y CSS reforzado para garantizar
#  que el botón de reapertura del sidebar siempre sea visible.
#  Si el usuario colapsa el sidebar, verá un botón "⚙️ Opciones" en el área
#  principal como respaldo adicional.
#
#  TEMA VISUAL INDEPENDIENTE
#  El tema oscuro ejecutivo se fuerza via:
#    a) .streamlit/config.toml (tema base dark + colores ejecutivos)
#    b) CSS inyectado con !important en cada elemento clave
#  Esto minimiza la dependencia del tema local del usuario.
#  NOTA: Streamlit no permite bloquear completamente el selector de tema del usuario,
#  pero los componentes HTML personalizados (tarjetas, filas, encabezados) siempre
#  mantendrán la paleta correcta porque usan CSS inyectado, no estilos de Streamlit.

import os
import streamlit as st
import pandas as pd

from utils.carga import (
    cargarArchivo,
    cargarDesdeRepo,
    rutaArchivoRepo,
    obtenerNombreArchivoRepo,
    validarColumnas,
    buscarCliente,
)
from utils.formato import (
    formatearMoneda,
    formatearFecha,
    formatearTexto,
    obtenerValorColumna,
    TEXTO_SIN_DATO,
)
from utils.calculos import calcularPlazo


# ─────────────────────────────────────────────
#  CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard de Cobranza | Consulta de Cliente",
    page_icon="🏦",
    layout="wide",
    # Sidebar expandida por defecto para que los controles estén siempre visibles.
    initial_sidebar_state="expanded",
)


# ─────────────────────────────────────────────
#  CSS PERSONALIZADO - DISEÑO EJECUTIVO
#  Se usa !important en todos los selectores críticos para que el CSS
#  prevalezca sobre el tema del usuario (dark/light local o de navegador).
# ─────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Google Fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Variables de color (paleta ejecutiva fija) ── */
    :root {
        --color-bg:        #0d1117;
        --color-surface:   #161b22;
        --color-surface2:  #1c2333;
        --color-border:    #30363d;
        --color-accent:    #2563eb;
        --color-accent2:   #1e40af;
        --color-text:      #e6edf3;
        --color-muted:     #8b949e;
        --color-label:     #58a6ff;
        --color-positive:  #3fb950;
        --color-warning:   #d29922;
        --color-card-head: #21262d;
    }

    /* ── Fondo general — se fuerza con !important para ignorar tema local ── */
    html, body,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    .main, .block-container {
        background-color: var(--color-bg) !important;
        font-family: 'Inter', sans-serif !important;
        color: var(--color-text) !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div:first-child {
        background-color: var(--color-surface) !important;
        border-right: 1px solid var(--color-border) !important;
    }
    /* Todos los textos dentro del sidebar */
    [data-testid="stSidebar"] * {
        color: var(--color-text) !important;
        font-family: 'Inter', sans-serif !important;
    }

    /* ─────────────────────────────────────────────────────────
       SIDEBAR SIEMPRE ACCESIBLE
       Streamlit tiene un comportamiento inconsistente con el botón
       de toggle del sidebar según la versión y el navegador.
       Esta regla garantiza que el botón colapsado SIEMPRE sea visible
       contra el fondo oscuro de la app.
    ───────────────────────────────────────────────────────── */
    /* Botón de colapsar/expandir sidebar — siempre visible */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    section[data-testid="stSidebarCollapsedControl"] {
        visibility: visible !important;
        display: flex !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        z-index: 999 !important;
    }
    /* Estilo del botón para que se vea claramente en modo oscuro */
    [data-testid="collapsedControl"] button,
    [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="stSidebarCollapsedControl"] > * {
        background-color: #1c2333 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
        color: #58a6ff !important;
        width: 36px !important;
        height: 36px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    [data-testid="collapsedControl"] button:hover,
    [data-testid="stSidebarCollapsedControl"] button:hover {
        background-color: #2563eb !important;
        border-color: #2563eb !important;
        color: #ffffff !important;
    }

    /* Asegurar que el ícono SVG del toggle herede el color */
    [data-testid="collapsedControl"] button svg,
    [data-testid="stSidebarCollapsedControl"] button svg {
        fill: currentColor !important;
    }

    /* ── Header principal ── */
    .header-dashboard {
        background: linear-gradient(135deg, #1e3a5f 0%, #162032 100%);
        border: 1px solid var(--color-border);
        border-radius: 12px;
        padding: 24px 32px;
        margin-bottom: 28px;
        display: flex;
        align-items: center;
        gap: 20px;
    }
    .header-dashboard h1 {
        font-size: 1.8rem;
        font-weight: 700;
        color: #e6edf3;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .header-dashboard p {
        font-size: 0.9rem;
        color: var(--color-muted);
        margin: 4px 0 0 0;
    }

    /* ── Badge de fuente de datos ── */
    .badge-repo {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #0f2d10;
        border: 1px solid #3fb950;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #3fb950;
        margin-bottom: 4px;
    }
    .badge-manual {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #1e2d50;
        border: 1px solid #2563eb;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #58a6ff;
        margin-bottom: 4px;
    }

    /* ── Campo de búsqueda principal ── */
    .search-container {
        background: var(--color-surface);
        border: 1px solid var(--color-border);
        border-radius: 12px;
        padding: 24px 28px;
        margin-bottom: 28px;
    }
    .search-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--color-label);
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 8px;
    }

    /* ── Tarjetas de sección ── */
    .card {
        background: var(--color-surface);
        border: 1px solid var(--color-border);
        border-radius: 12px;
        padding: 0;
        margin-bottom: 20px;
        overflow: hidden;
    }
    .card-header {
        background: var(--color-card-head);
        border-bottom: 1px solid var(--color-border);
        padding: 12px 20px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .card-header span {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: var(--color-muted);
    }
    .card-body {
        padding: 16px 20px;
    }

    /* ── Fila de campo ── */
    .field-row {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        padding: 9px 0;
        border-bottom: 1px solid #21262d;
    }
    .field-row:last-child {
        border-bottom: none;
    }
    .field-label {
        font-size: 0.78rem;
        color: var(--color-muted);
        font-weight: 400;
        flex-shrink: 0;
        padding-right: 16px;
    }
    .field-value {
        font-size: 0.88rem;
        color: var(--color-text);
        font-weight: 500;
        text-align: right;
        word-break: break-word;
    }
    .field-value.moneda {
        color: #79c0ff;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }
    .field-value.fecha {
        color: #d2a8ff;
    }
    .field-value.vacio {
        color: var(--color-muted);
        font-style: italic;
        font-size: 0.82rem;
    }
    .field-value.destacado {
        font-size: 1.05rem;
        color: #e6edf3;
        font-weight: 700;
    }

    /* ── Chip de VREFERENCE ── */
    .vref-chip {
        display: inline-block;
        background: #1e3a5f;
        border: 1px solid #2563eb;
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 0.9rem;
        font-weight: 700;
        color: #79c0ff;
        letter-spacing: 1px;
        margin-bottom: 18px;
    }

    /* ── Alertas personalizadas ── */
    .alerta-info {
        background: #161b22;
        border-left: 4px solid var(--color-accent);
        border-radius: 0 8px 8px 0;
        padding: 14px 18px;
        margin-bottom: 18px;
        font-size: 0.85rem;
        color: var(--color-muted);
    }
    .alerta-warning {
        background: #2d2000;
        border-left: 4px solid var(--color-warning);
        border-radius: 0 8px 8px 0;
        padding: 14px 18px;
        margin-bottom: 18px;
        font-size: 0.85rem;
        color: #f0c050;
    }
    .alerta-error {
        background: #2d0e0e;
        border-left: 4px solid #f85149;
        border-radius: 0 8px 8px 0;
        padding: 14px 18px;
        margin-bottom: 18px;
        font-size: 0.85rem;
        color: #ff7b7b;
    }
    /* Alerta especial: archivo faltante */
    .alerta-sin-archivo {
        background: #1a1012;
        border: 1px solid #6e3030;
        border-left: 4px solid #f85149;
        border-radius: 8px;
        padding: 24px 28px;
        margin: 20px 0;
        font-size: 0.9rem;
        color: #ff7b7b;
        line-height: 1.7;
    }
    .alerta-sin-archivo h3 {
        color: #ff7b7b;
        font-size: 1rem;
        margin: 0 0 12px 0;
    }
    .alerta-sin-archivo code {
        background: #2d0e0e;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 0.85rem;
        color: #ffa0a0;
    }

    /* ── Ocultar branding de Streamlit sin afectar el botón del sidebar ── */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }

    /* ── Input text ── */
    .stTextInput > div > div > input {
        background-color: #0d1117 !important;
        border: 1px solid var(--color-border) !important;
        border-radius: 8px !important;
        color: var(--color-text) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 1rem !important;
        padding: 10px 14px !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: var(--color-accent) !important;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25) !important;
    }
    /* Placeholder text */
    .stTextInput > div > div > input::placeholder {
        color: var(--color-muted) !important;
        opacity: 0.7 !important;
    }

    /* ── Botones ── */
    .stButton > button {
        background-color: transparent !important;
        border: 1px solid var(--color-border) !important;
        border-radius: 8px !important;
        color: var(--color-muted) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.82rem !important;
        padding: 6px 16px !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        border-color: var(--color-accent) !important;
        color: var(--color-text) !important;
    }

    /* ── Expanders ── */
    [data-testid="stExpander"] {
        background-color: var(--color-surface2) !important;
        border: 1px solid var(--color-border) !important;
        border-radius: 8px !important;
    }
    [data-testid="stExpander"] summary {
        color: var(--color-text) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem !important;
    }

    /* ── Divider ── */
    hr {
        border: none;
        border-top: 1px solid var(--color-border);
        margin: 20px 0;
    }

    /* ── Uploader (modo respaldo) ── */
    [data-testid="stFileUploader"] {
        background-color: var(--color-surface2) !important;
        border-radius: 8px !important;
        border: 1px dashed var(--color-border) !important;
    }

    /* ── Select / radio / checkbox nativos — forzar paleta oscura ── */
    /* NOTA: Streamlit puede ignorar algunos de estos si el tema del usuario
       lo sobrescribe. El config.toml mitiga esto, pero no es 100% garantizado. */
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background-color: var(--color-surface2) !important;
        border-color: var(--color-border) !important;
        color: var(--color-text) !important;
    }

    /* ── Scrollbar personalizado ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--color-bg); }
    ::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--color-muted); }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
#  ESTADO DE SESIÓN
# ─────────────────────────────────────────────
if "dataframe" not in st.session_state:
    st.session_state.dataframe = None
if "busquedaActual" not in st.session_state:
    st.session_state.busquedaActual = ""
if "resultadoCliente" not in st.session_state:
    st.session_state.resultadoCliente = None
# Nombre y fuente del archivo actualmente cargado
if "archivoNombre" not in st.session_state:
    st.session_state.archivoNombre = None
# Fuente: "repo" | "manual" | None
if "fuenteArchivo" not in st.session_state:
    st.session_state.fuenteArchivo = None


# ─────────────────────────────────────────────
#  CARGA AUTOMÁTICA DESDE EL REPOSITORIO
#  Se ejecuta en cada rerun, pero solo carga el DF si no hay uno en sesión.
#  Si hay un DF manual en sesión, no se sobreescribe.
# ─────────────────────────────────────────────
def intentarCargaRepo():
    """
    Intenta cargar automáticamente el archivo desde data/ si no hay
    un DataFrame ya en sesión. Actualiza st.session_state.
    """
    # Solo actuar si no hay un df ya cargado (no sobreescribir carga manual activa)
    if st.session_state.dataframe is None:
        nombreRepo = obtenerNombreArchivoRepo()
        if nombreRepo is not None:
            df = cargarDesdeRepo()
            if df is not None:
                esValido, columnasFaltantes = validarColumnas(df)
                if esValido:
                    st.session_state.dataframe = df
                    st.session_state.archivoNombre = nombreRepo
                    st.session_state.fuenteArchivo = "repo"
                # Si no es válido, se dejará dataframe en None y se mostrará error en sidebar


intentarCargaRepo()


# ─────────────────────────────────────────────
#  FUNCIONES DE RENDERIZADO
# ─────────────────────────────────────────────
def renderizarFila(label: str, valor: str, tipo: str = "texto"):
    """
    Renderiza una fila de campo con su etiqueta y valor formateado.

    Args:
        label: Etiqueta del campo.
        valor: Valor ya formateado como string.
        tipo:  'texto' | 'moneda' | 'fecha' | 'destacado'
    """
    esSinDato = valor == TEXTO_SIN_DATO

    if esSinDato:
        claseValor = "field-value vacio"
    elif tipo == "moneda":
        claseValor = "field-value moneda"
    elif tipo == "fecha":
        claseValor = "field-value fecha"
    elif tipo == "destacado":
        claseValor = "field-value destacado"
    else:
        claseValor = "field-value"

    st.markdown(
        f"""
        <div class="field-row">
            <span class="field-label">{label}</span>
            <span class="{claseValor}">{valor}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizarTarjeta(titulo: str, icono: str, contenido_fn):
    """
    Renderiza un bloque tipo tarjeta con cabecera y cuerpo.

    Args:
        titulo:      Título de la sección.
        icono:       Emoji o ícono de la sección.
        contenido_fn: Función callable que renderiza el contenido interno.
    """
    st.markdown(
        f"""
        <div class="card">
            <div class="card-header">
                <span style="font-size:1rem">{icono}</span>
                <span>{titulo}</span>
            </div>
            <div class="card-body">
        """,
        unsafe_allow_html=True,
    )
    contenido_fn()
    st.markdown("</div></div>", unsafe_allow_html=True)


def renderizarResultado(fila: pd.Series):
    """
    Renderiza el dashboard completo de información de un cliente.

    Args:
        fila: pd.Series con los datos de la primera fila encontrada.
    """
    # ── VREFERENCE chip ──
    vRef = formatearTexto(obtenerValorColumna(fila, "vReference"))
    st.markdown(f'<div class="vref-chip">📌 VREFERENCE: {vRef}</div>', unsafe_allow_html=True)

    # ── Calcular plazo (campo derivado) ──
    plazo = calcularPlazo(fila)

    # ── Layout principal: columna izquierda + columna derecha ──
    colIzq, colDer = st.columns([1, 1], gap="large")

    # ────── COLUMNA IZQUIERDA ──────────────────────────────────
    with colIzq:

        # ── Tarjeta: Datos del Cliente ──
        def contenidoCliente():
            renderizarFila("Nombre", formatearTexto(obtenerValorColumna(fila, "vName")), "destacado")
            renderizarFila("Bucket", formatearTexto(obtenerValorColumna(fila, "Bucket Inicio")))
            renderizarFila("Gestor", formatearTexto(obtenerValorColumna(fila, "Gestor")))

        renderizarTarjeta("Datos del Cliente", "👤", contenidoCliente)

        # ── Tarjeta: Montos de Negociación ──
        def contenidoMontos():
            renderizarFila(
                "Monto Descuento",
                formatearMoneda(obtenerValorColumna(fila, "nDescuento")),
                "moneda",
            )
            renderizarFila(
                "Monto Amortización",
                formatearMoneda(obtenerValorColumna(fila, "Amortizacion")),
                "moneda",
            )
            renderizarFila(
                "Mínimo para Current / Saldo Vencido",
                formatearMoneda(obtenerValorColumna(fila, "nDueBalance_x")),
                "moneda",
            )
            renderizarFila(
                "Mínimo para Contener",
                formatearMoneda(obtenerValorColumna(fila, "Minimo para contener")),
                "moneda",
            )
            renderizarFila(
                "Monto a Liquidar",
                formatearMoneda(obtenerValorColumna(fila, "Monto Liquidacion")),
                "moneda",
            )

        renderizarTarjeta("Montos de Negociación", "💰", contenidoMontos)

        # ── Tarjeta: Pago del Mes ──
        def contenidoPago():
            renderizarFila(
                "Pago Recibido / Aplicado",
                formatearMoneda(obtenerValorColumna(fila, "Pago cash")),
                "moneda",
            )
            renderizarFila(
                "Fecha del Pago Aplicado",
                formatearFecha(obtenerValorColumna(fila, "F.Aplicacion")),
                "fecha",
            )

        renderizarTarjeta("Pago del Mes", "📅", contenidoPago)

    # ────── COLUMNA DERECHA ─────────────────────────────────────
    with colDer:

        # ── Tarjeta: Historial de Pagos ──
        def contenidoHistorial():
            renderizarFila(
                "Fecha Último Pago",
                formatearFecha(obtenerValorColumna(fila, "vUltPago")),
                "fecha",
            )
            renderizarFila(
                "Fecha Apertura",
                formatearFecha(obtenerValorColumna(fila, "vOpenned")),
                "fecha",
            )

        renderizarTarjeta("Historial de Pagos", "🗓️", contenidoHistorial)

        # ── Tarjeta: Saldos ──
        def contenidoSaldos():
            renderizarFila(
                "Saldo Total",
                formatearMoneda(obtenerValorColumna(fila, "nTotBalance")),
                "moneda",
            )
            renderizarFila(
                "Saldo Vencido",
                formatearMoneda(obtenerValorColumna(fila, "nDueBalance_x")),
                "moneda",
            )

        renderizarTarjeta("Saldos", "📊", contenidoSaldos)

        # ── Tarjeta: Información del Crédito ──
        def contenidoCredito():
            renderizarFila(
                "Monto Solicitado",
                formatearMoneda(obtenerValorColumna(fila, "nAmount")),
                "moneda",
            )
            renderizarFila(
                "Monto Pagaré",
                formatearMoneda(obtenerValorColumna(fila, "nTAmount")),
                "moneda",
            )
            renderizarFila(
                "Frecuencia",
                formatearTexto(obtenerValorColumna(fila, "vFrecuencia")),
            )
            renderizarFila(
                "Plazo (calculado)",
                plazo if plazo != TEXTO_SIN_DATO else TEXTO_SIN_DATO,
            )

        renderizarTarjeta("Información del Crédito", "📄", contenidoCredito)


# ─────────────────────────────────────────────
#  SIDEBAR
#  Se mantiene siempre expandida (initial_sidebar_state="expanded").
#  El CSS reforza el botón de toggle para que siempre sea visible.
#  El contenido de configuración/filtros nunca queda "atrapado" sin acceso.
# ─────────────────────────────────────────────
with st.sidebar:
    # ── Logotipo / Título ──
    st.markdown(
        """
        <div style="padding:8px 0 24px 0">
            <div style="font-size:1.4rem;font-weight:700;color:#e6edf3;letter-spacing:-0.5px">
                🏦 Cobranza
            </div>
            <div style="font-size:0.75rem;color:#8b949e;margin-top:2px">
                Dashboard Ejecutivo
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Sección: Fuente de Datos ──
    st.markdown(
        '<span style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:1.2px;color:#58a6ff">📂 Fuente de Datos</span>',
        unsafe_allow_html=True,
    )

    # ── Mostrar estado del archivo actualmente cargado ──
    if st.session_state.dataframe is not None:
        dfActual = st.session_state.dataframe
        fuenteActual = st.session_state.fuenteArchivo or "repo"
        nombreActual = st.session_state.archivoNombre or "Archivo de datos"

        # Badge según la fuente
        if fuenteActual == "repo":
            st.markdown(
                f'<div class="badge-repo">✅ Desde repositorio &nbsp;·&nbsp; {nombreActual}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="badge-manual">📤 Carga manual &nbsp;·&nbsp; {nombreActual}</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div style="font-size:0.78rem;color:#8b949e;margin-top:6px;margin-bottom:8px">
                {len(dfActual):,} registros · {len(dfActual.columns)} columnas
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Botón para forzar recarga del archivo del repo (útil tras deploy)
        if fuenteActual == "repo":
            if st.button("🔄 Recargar datos del repo", use_container_width=True):
                st.session_state.dataframe = None
                st.session_state.archivoNombre = None
                st.session_state.fuenteArchivo = None
                st.session_state.busquedaActual = ""
                st.session_state.resultadoCliente = None
                st.rerun()
        else:
            # Si es carga manual, botón para descartarla y volver al repo
            if st.button("↩️ Usar archivo del repo", use_container_width=True):
                st.session_state.dataframe = None
                st.session_state.archivoNombre = None
                st.session_state.fuenteArchivo = None
                st.session_state.busquedaActual = ""
                st.session_state.resultadoCliente = None
                st.rerun()

    else:
        # Sin datos cargados: mostrar aviso sobre el archivo esperado
        rutaEsperada = os.path.join("data", obtenerNombreArchivoRepo() or "baseConsulta.xlsx")
        st.markdown(
            f"""
            <div style="background:#1a1012;border:1px solid #6e3030;border-radius:8px;
            padding:10px 14px;margin-bottom:12px;font-size:0.8rem;color:#ff7b7b">
                ⚠️ No se encontró el archivo en:<br>
                <code style="font-size:0.75rem">{rutaEsperada}</code>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Separador ──
    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Carga Manual (modo respaldo) ──
    st.markdown(
        '<span style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:1.2px;color:#8b949e">📤 Carga Manual (respaldo)</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-size:0.74rem;color:#484f58;margin-bottom:8px">'
        'Usa esta opción si necesitas cargar un archivo diferente al del repositorio.'
        '</div>',
        unsafe_allow_html=True,
    )

    archivoSubido = st.file_uploader(
        label="Sube tu archivo de datos",
        type=["csv", "xlsx", "xls"],
        help="Soporta archivos CSV y Excel (.xlsx / .xls). "
             "Este modo es de respaldo; el archivo principal viene del repositorio.",
        label_visibility="collapsed",
    )

    # Procesar carga manual solo cuando hay un archivo nuevo
    if archivoSubido is not None:
        esNuevoArchivo = (
            archivoSubido.name != st.session_state.archivoNombre
            or st.session_state.fuenteArchivo != "manual"
        )

        if esNuevoArchivo:
            df = cargarArchivo(archivoSubido)

            if df is not None:
                esValido, columnasFaltantes = validarColumnas(df)

                if esValido:
                    st.session_state.dataframe = df
                    st.session_state.archivoNombre = archivoSubido.name
                    st.session_state.fuenteArchivo = "manual"
                    st.session_state.busquedaActual = ""
                    st.session_state.resultadoCliente = None
                    st.rerun()
                else:
                    st.session_state.dataframe = None
                    st.session_state.archivoNombre = None
                    st.session_state.fuenteArchivo = None
                    st.markdown(
                        f"""
                        <div style="background:#2d0e0e;border:1px solid #f85149;border-radius:8px;
                        padding:10px 14px;margin-top:12px;font-size:0.82rem;color:#ff7b7b">
                            ⚠️ <strong>Columnas faltantes:</strong><br>
                            <code style="font-size:0.76rem">{'<br>'.join(columnasFaltantes)}</code>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Diagnóstico: columnas detectadas ──
    if st.session_state.dataframe is not None:
        with st.expander("🔍 Columnas detectadas", expanded=False):
            for col in st.session_state.dataframe.columns:
                st.markdown(
                    f'<span style="font-size:0.78rem;color:#8b949e">• {col}</span>',
                    unsafe_allow_html=True,
                )

    # ── Footer de versión ──
    st.markdown(
        '<div style="position:fixed;bottom:20px;font-size:0.68rem;color:#484f58">'
        "v1.1.0 · Dashboard Ejecutivo</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
#  CONTENIDO PRINCIPAL
# ─────────────────────────────────────────────

# ── Header principal ──
st.markdown(
    """
    <div class="header-dashboard">
        <div style="font-size:2.2rem">🏦</div>
        <div>
            <h1>Dashboard de Cobranza</h1>
            <p>Consulta individual de cliente por número de referencia</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Estado: sin archivo cargado ──
if st.session_state.dataframe is None:
    # Determinar si el archivo del repo no existe
    existeArchivoRepo = rutaArchivoRepo() is not None

    if not existeArchivoRepo:
        # Mensaje elegante de archivo faltante
        st.markdown(
            """
            <div class="alerta-sin-archivo">
                <h3>📂 Archivo de datos no encontrado</h3>
                <p>
                    El dashboard busca automáticamente el archivo de datos en:<br>
                    <code>data/baseConsulta.xlsx</code> &nbsp;o&nbsp; <code>data/baseConsulta.csv</code>
                </p>
                <p>
                    <strong>¿Qué hacer?</strong><br>
                    1. Agrega tu archivo de datos a la carpeta <code>data/</code> del repositorio.<br>
                    2. Nómbralo <code>baseConsulta.xlsx</code> (o <code>baseConsulta.csv</code>).<br>
                    3. Haz push al repositorio y redespliega en Render.<br>
                    4. Alternativamente, usa la carga manual en el panel lateral (⬅️).
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # El archivo existe pero falló la carga (columnas inválidas u otro error)
        st.markdown(
            """
            <div class="alerta-error">
                <strong>⚠️ El archivo de datos existe pero no pudo ser cargado correctamente.</strong><br>
                Revisa que el archivo tenga las columnas requeridas o usa la carga manual en el panel lateral.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.stop()

df = st.session_state.dataframe

# ── Campo de búsqueda por VREFERENCE ──
st.markdown(
    """
    <div class="search-container">
        <div class="search-label">🔎 Búsqueda por VREFERENCE</div>
    """,
    unsafe_allow_html=True,
)

colBusqueda, colLimpiar = st.columns([5, 1], gap="small")

with colBusqueda:
    valorBusqueda = st.text_input(
        label="VREFERENCE",
        value=st.session_state.busquedaActual,
        placeholder="Pega o escribe el número de referencia del cliente...",
        key="inputVReference",
        label_visibility="collapsed",
    )

with colLimpiar:
    if st.button("✕ Limpiar", use_container_width=True):
        st.session_state.busquedaActual = ""
        st.session_state.resultadoCliente = None
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# ── Lógica de búsqueda ──
if valorBusqueda and valorBusqueda.strip():
    st.session_state.busquedaActual = valorBusqueda.strip()
    resultados = buscarCliente(df, valorBusqueda.strip())

    if resultados.empty:
        st.markdown(
            f"""
            <div class="alerta-error">
                <strong>❌ Cliente no encontrado</strong><br>
                No se encontró ningún registro con VREFERENCE = <code>{valorBusqueda.strip()}</code>.
                Verifica que el valor sea correcto y que el archivo esté actualizado.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Avisar si hubo múltiples coincidencias
        if len(resultados) > 1:
            st.markdown(
                f"""
                <div class="alerta-warning">
                    ⚠️ Se encontraron <strong>{len(resultados)} registros</strong> con el mismo VREFERENCE.
                    Se muestra el primero de ellos.
                </div>
                """,
                unsafe_allow_html=True,
            )

        filaCliente = resultados.iloc[0]
        renderizarResultado(filaCliente)

else:
    # Estado inicial sin búsqueda
    st.markdown(
        """
        <div class="alerta-info">
            Ingresa un número <strong>VREFERENCE</strong> en el campo de búsqueda para consultar
            la información del cliente.
        </div>
        """,
        unsafe_allow_html=True,
    )
