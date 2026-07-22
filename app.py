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
#  SIDEBAR
#  El sidebar usa el comportamiento NATIVO de Streamlit para colapsar/reabrir
#  (botones stSidebarCollapseButton y stExpandSidebarButton). El CSS solo aplica
#  estilos visuales seguros y NO fuerza display/position/visibility/tamaño sobre
#  esos controles, de modo que el toggle funciona de forma repetida sin recargar.
#  Arranca expandido con initial_sidebar_state="expanded".
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
    buscarOtrosVReference,
)
from utils.formato import (
    formatearMoneda,
    formatearFecha,
    formatearTexto,
    obtenerValorColumna,
    TEXTO_SIN_DATO,
)
from utils.calculos import calcularPlazo
from utils.negocio import getPagoInfo, getMontoPagadoTotal, isDescuentoEnabled, getSemaforo


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

    /* ── Tipografía del sidebar ──
       IMPORTANTE: NO se usa el selector global [data-testid="stSidebar"] *
       para asignar la fuente. Ese selector aplicaba 'Inter' con !important
       también a los iconos nativos de Streamlit (span[data-testid="stIconMaterial"]),
       que son LIGADURAS de la fuente "Material Symbols Rounded". Al forzarles Inter,
       la ligadura no se resolvía y aparecía el nombre interno del icono como texto
       (keyboard_double_arrow_left, upload, arrow_right, etc.).
       Solución: aplicar Inter SOLO a elementos textuales, nunca a los iconos. */
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] li,
    [data-testid="stSidebar"] a,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] h6,
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] span:not([data-testid="stIconMaterial"]) {
        color: var(--color-text) !important;
        font-family: 'Inter', sans-serif !important;
    }

    /* ── Restaurar la fuente de los iconos nativos (Material Symbols) ──
       Se aplica GLOBALMENTE (no solo dentro del sidebar) para que también el
       botón de reapertura del sidebar, que Streamlit monta en el header, muestre
       su icono correctamente. Se listan varios selectores por resiliencia entre
       versiones: el data-testid es el estable en Streamlit 1.52.x; las clases
       .material-symbols-* actúan como respaldo si el testid cambiara. */
    [data-testid="stIconMaterial"],
    span[data-testid="stIconMaterial"],
    .material-symbols-rounded,
    .material-symbols-outlined,
    .material-symbols-sharp {
        font-family: 'Material Symbols Rounded',
                     'Material Symbols Outlined',
                     'Material Symbols Sharp' !important;
        font-weight: normal !important;
        font-style: normal !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        white-space: nowrap !important;
        direction: ltr !important;
        -webkit-font-feature-settings: 'liga' !important;
        font-feature-settings: 'liga' !important;
        -webkit-font-smoothing: antialiased !important;
    }

    /* ── Botones de colapsar / reabrir el sidebar ──
       Se confía en el comportamiento y la posición NATIVOS de Streamlit.
       Solo se aplican estilos visuales seguros (color / fondo / borde) que NO
       alteran display, position, width, height, visibility ni pointer-events,
       por lo que no interfieren con el toggle ni con la animación del sidebar.
       Selectores reales de Streamlit 1.52.x:
         - stSidebarCollapseButton → colapsar (dentro del header del sidebar)
         - stExpandSidebarButton   → reabrir (montado en el header de la app) */
    [data-testid="stSidebarCollapseButton"] button:hover,
    [data-testid="stExpandSidebarButton"] button:hover {
        background-color: var(--color-surface2) !important;
        color: var(--color-label) !important;
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

    /* ── Ocultar branding de Streamlit ──
       [data-testid="stToolbar"] se oculta para esconder el menú/branding nativo.
       PERO: cuando el sidebar está colapsado, Streamlit (1.52.x) monta el botón
       de reapertura (stExpandSidebarButton) DENTRO de ese mismo stToolbar. Un
       display:none incondicional sobre el ancestro deja ese botón inexistente
       para el layout y el puntero, y el sidebar queda irrecuperable sin recargar.
       La excepción con :has() mantiene oculto el branding en todos los casos
       excepto cuando el toolbar es, específicamente, el que contiene el botón
       de reapertura. */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stToolbar"]:has([data-testid="stExpandSidebarButton"]) {
        display: flex !important;
    }
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
        /* El encabezado completo debe ser clickeable y sin solapamientos */
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
    }
    /* La flecha del expander es un icono Material; no debe encimarse con el título */
    [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
        flex-shrink: 0 !important;
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
    /* La dropzone contiene: icono (Material) + texto + botón "Browse".
       Se permite que el contenido se ajuste al ancho del sidebar sin overflow. */
    [data-testid="stFileUploaderDropzone"] {
        flex-wrap: wrap !important;
        gap: 8px !important;
        padding: 12px 14px !important;
    }
    [data-testid="stFileUploaderDropzone"] > div {
        min-width: 0 !important;
    }
    /* Instrucciones y tipos permitidos: legibles y sin desbordar */
    [data-testid="stFileUploaderDropzoneInstructions"] {
        min-width: 0 !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] span,
    [data-testid="stFileUploaderDropzoneInstructions"] small {
        color: var(--color-muted) !important;
        white-space: normal !important;
        word-break: break-word !important;
    }
    /* Nombre del archivo subido: que no se salga del contenedor */
    [data-testid="stFileUploaderFile"] {
        min-width: 0 !important;
    }
    [data-testid="stFileUploaderFileName"] {
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    /* El sidebar nunca debe producir scroll horizontal */
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        overflow-x: hidden !important;
    }

    /* ── Ajustes responsive para pantallas estrechas (~320–400px) ── */
    @media (max-width: 480px) {
        [data-testid="stFileUploaderDropzone"] {
            flex-direction: column !important;
            align-items: stretch !important;
        }
        [data-testid="stFileUploaderDropzone"] button {
            width: 100% !important;
        }
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

    /* ── Sección: Otros VReference del Cliente ── */
    .otras-vref-section {
        background: var(--color-surface);
        border: 1px solid var(--color-border);
        border-radius: 12px;
        padding: 0;
        margin-top: 24px;
        overflow: hidden;
    }
    .otras-vref-header {
        background: linear-gradient(90deg, #1a2744 0%, #21262d 100%);
        border-bottom: 1px solid var(--color-border);
        padding: 14px 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
    }
    .otras-vref-title {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: var(--color-muted);
    }
    .otras-vref-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #1a2d50;
        border: 1px solid #2563eb;
        border-radius: 20px;
        padding: 3px 10px;
        font-size: 0.72rem;
        font-weight: 600;
        color: #58a6ff;
    }
    .otras-vref-body {
        padding: 16px 20px;
    }
    .otras-vref-meta {
        display: flex;
        gap: 24px;
        margin-bottom: 16px;
        flex-wrap: wrap;
    }
    .otras-vref-meta-item {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .otras-vref-meta-label {
        font-size: 0.68rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: var(--color-muted);
    }
    .otras-vref-meta-value {
        font-size: 0.85rem;
        font-weight: 600;
        color: #79c0ff;
    }
    .vref-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.8rem;
    }
    .vref-table th {
        background: #0d1117;
        color: var(--color-muted);
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 8px 10px;
        text-align: left;
        border-bottom: 1px solid var(--color-border);
    }
    .vref-table td {
        padding: 8px 10px;
        border-bottom: 1px solid #21262d;
        color: var(--color-text);
        vertical-align: middle;
    }
    .vref-table tr:last-child td {
        border-bottom: none;
    }
    .vref-table tr:hover td {
        background: #1c2333;
    }
    .vref-table td.vref-code {
        font-weight: 700;
        color: #79c0ff;
        font-family: 'Courier New', monospace;
        letter-spacing: 0.5px;
    }
    .vref-table td.moneda-tabla {
        color: #79c0ff;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }
    .vref-table td.estatus {
        color: #3fb950;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .sin-otros-vref {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 0;
        font-size: 0.83rem;
        color: var(--color-muted);
        font-style: italic;
    }

    /* ── Semáforo de riesgo ── */
    .semaforo-badge {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        border-radius: 10px;
        padding: 10px 18px;
        margin-bottom: 20px;
        border: 1px solid;
        font-family: 'Inter', sans-serif;
    }
    .semaforo-emoji { font-size: 1.2rem; }
    .semaforo-label {
        font-size: 0.82rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .semaforo-motivo {
        font-size: 0.72rem;
        font-weight: 400;
        opacity: 0.8;
        margin-left: 4px;
    }

    /* ── Calculadora de Descuento ── */
    .calc-section {
        background: var(--color-surface);
        border: 1px solid var(--color-border);
        border-radius: 12px;
        padding: 0;
        margin-top: 20px;
        margin-bottom: 20px;
        overflow: hidden;
    }
    .calc-header {
        background: linear-gradient(90deg, #1a2450 0%, #21262d 100%);
        border-bottom: 1px solid var(--color-border);
        padding: 12px 20px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .calc-header span.calc-title {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: var(--color-muted);
    }
    .calc-body { padding: 18px 20px; }
    .calc-sub-title {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: var(--color-label);
        margin-bottom: 8px;
        margin-top: 14px;
        padding-bottom: 4px;
        border-bottom: 1px solid #21262d;
    }
    .calc-result-row {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        padding: 8px 0;
        border-bottom: 1px solid #21262d;
    }
    .calc-result-row:last-child { border-bottom: none; }
    .calc-result-label {
        font-size: 0.78rem;
        color: var(--color-muted);
    }
    .calc-result-value {
        font-size: 0.9rem;
        font-weight: 600;
        color: #79c0ff;
        font-variant-numeric: tabular-nums;
    }
    .calc-result-value.highlight {
        color: #3fb950;
        font-size: 1rem;
    }
    .calc-disabled {
        background: #161b22;
        border: 1px solid #30363d;
        border-left: 4px solid #6e3030;
        border-radius: 8px;
        padding: 16px 20px;
        font-size: 0.85rem;
        color: #8b949e;
        margin: 16px 0;
    }
    .pago-tipo-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-left: 8px;
    }
    .pago-tipo-domi  { background:#1a2d50; color:#58a6ff; border:1px solid #2563eb; }
    .pago-tipo-cash  { background:#1a2d1a; color:#3fb950; border:1px solid #238636; }
    .pago-tipo-ambos { background:#2d2500; color:#e3b341; border:1px solid #9e6a03; }
    .field-value.total-pago { color: #3fb950; font-weight: 700; font-size: 0.95rem; }
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
if "inputVReference" not in st.session_state:
    st.session_state.inputVReference = ""
# Nombre y fuente del archivo actualmente cargado
if "archivoNombre" not in st.session_state:
    st.session_state.archivoNombre = None
# Fuente: "repo" | "manual" | None
if "fuenteArchivo" not in st.session_state:
    st.session_state.fuenteArchivo = None


def limpiarBusqueda():
    """
    Callback del botón "✕ Limpiar" (y de los flujos que deben dejar la
    búsqueda en blanco). Se ejecuta ANTES del rerun provocado por la
    interacción, por lo que modificar st.session_state.inputVReference aquí
    es seguro: el widget con esa key todavía no ha sido instanciado en el
    rerun que esta función origina.
    """
    st.session_state.inputVReference = ""
    st.session_state.busquedaActual = ""
    st.session_state.resultadoCliente = None


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

    # ── Semáforo de riesgo (se muestra inmediatamente debajo del chip) ──
    renderizarSemaforo(fila)

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

        # ── Tarjeta: Pago del Mes (extendida con detección inteligente) ──
        # NUEVO: Se detecta automáticamente si el pago fue domiciliado o en efectivo.
        # Si ambos tienen valor > 0, se muestran ambos y se suma el total.
        def contenidoPago():
            pagoInfo = getPagoInfo(fila)
            tipoPago = pagoInfo["tipoPago"]

            # Mostrar siempre los montos individuales presentes en los datos
            renderizarFila(
                "Pago Domiciliado",
                formatearMoneda(obtenerValorColumna(fila, "Pago domi")),
                "moneda",
            )
            renderizarFila(
                "Pago en Efectivo",
                formatearMoneda(obtenerValorColumna(fila, "Pago cash")),
                "moneda",
            )

            # Badge visual indicando el tipo de pago detectado
            if tipoPago == "ambos":
                badgeHtml = '<span class="pago-tipo-badge pago-tipo-ambos">⚡ Ambos pagos</span>'
            elif tipoPago == "domi":
                badgeHtml = '<span class="pago-tipo-badge pago-tipo-domi">🏛 Domiciliado</span>'
            elif tipoPago == "cash":
                badgeHtml = '<span class="pago-tipo-badge pago-tipo-cash">💵 Efectivo</span>'
            else:
                badgeHtml = ""

            # Fecha según tipo de pago detectado:
            # domi  → vDateMovement
            # cash  → F.Aplicacion
            # ambos → F.Aplicacion (fecha de aplicación como referencia)
            fechaPago = pagoInfo["fechaPago"]
            if tipoPago == "domi":
                labelFecha = "Fecha Pago Domiciliado"
            elif tipoPago == "ambos":
                labelFecha = "Fecha Pago Aplicado"
            else:
                labelFecha = "Fecha del Pago Aplicado"

            if badgeHtml:
                st.markdown(
                    f'<div style="padding:6px 0 2px 0">'
                    f'<span style="font-size:0.74rem;color:#8b949e">Tipo detectado:</span>'
                    f'{badgeHtml}</div>',
                    unsafe_allow_html=True,
                )

            renderizarFila(labelFecha, formatearFecha(fechaPago), "fecha")

            # nPaid: cuánto ha pagado el cliente al corte
            renderizarFila(
                "Pagado al Corte (nPaid)",
                formatearMoneda(obtenerValorColumna(fila, "nPaid")),
                "moneda",
            )

            # Monto pagado total = nPaid + pagoDetectado (campo de negocio)
            montoTotal = getMontoPagadoTotal(fila)
            st.markdown(
                f"""
                <div class="field-row" style="border-top:1px solid #30363d;margin-top:6px;padding-top:10px">
                    <span class="field-label">Monto Pagado Total<br>
                        <span style="font-size:0.68rem;color:#484f58">(nPaid + pago detectado)</span>
                    </span>
                    <span class="field-value total-pago">{formatearMoneda(montoTotal)}</span>
                </div>
                """,
                unsafe_allow_html=True,
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
        # Saldo Vencido → columna real: nDueBalance_x
        # nDueBalance_y: si viene en los datos, también se etiqueta como "Saldo Vencido"
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
            # Si nDueBalance_y existe y tiene valor, mostrarlo también
            valDueY = obtenerValorColumna(fila, "nDueBalance_y")
            if valDueY is not None:
                renderizarFila(
                    "Saldo Vencido (período 2)",
                    formatearMoneda(valDueY),
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

    # ── Calculadora de Descuento (sección nueva, debajo del layout de columnas) ──
    renderizarCalculadora(fila)


def renderizarSemaforo(fila: pd.Series):
    """
    Renderiza el badge semáforo de riesgo del crédito.
    Aparece inmediatamente debajo del chip VREFERENCE.
    """
    semaforo = getSemaforo(fila)
    st.markdown(
        f"""
        <div class="semaforo-badge" style="
            background-color:{semaforo['hex_bg']};
            border-color:{semaforo['hex_brd']};
            color:{semaforo['hex_text']};
        ">
            <span class="semaforo-emoji">{semaforo['emoji']}</span>
            <div>
                <span class="semaforo-label">{semaforo['label']}</span>
                <span class="semaforo-motivo">· {semaforo['motivo']}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _safeFloat(valor) -> float | None:
    """Helper para conversión segura a float sin ciclos."""
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


def renderizarCalculadora(fila: pd.Series):
    """
    Renderiza la Calculadora de Descuento como sección independiente.
    """
    bucketRaw = obtenerValorColumna(fila, "Bucket Inicio")
    habilitada = isDescuentoEnabled(bucketRaw)

    # ── Cabecera HTML de la sección ──
    st.markdown(
        """
        <div class="calc-section">
            <div class="calc-header">
                <span style="font-size:1rem">🧮</span>
                <span class="calc-title">Calculadora de Descuento</span>
            </div>
            <div class="calc-body">
        """,
        unsafe_allow_html=True,
    )

    if not habilitada:
        st.markdown(
            f"""
            <div class="calc-disabled">
                🔒 La calculadora de descuento <strong>solo aplica para Bucket Inicio 90+</strong>
                (E, F, G, H, I, J).<br>
                Bucket actual: <strong>{formatearTexto(bucketRaw)}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    # ── Datos base ──
    pagoInfo     = getPagoInfo(fila)
    nAmount      = _safeFloat(obtenerValorColumna(fila, "nAmount"))  or 0.0
    nTAmount     = _safeFloat(obtenerValorColumna(fila, "nTAmount")) or 0.0
    nPaid        = _safeFloat(obtenerValorColumna(fila, "nPaid"))    or 0.0
    pagoDetectado = pagoInfo["pagoDetectado"]

    montoPagado    = round(nPaid + pagoDetectado, 2)
    montoPendiente = round(nTAmount - montoPagado, 2)

    # ── Tabla de datos base (HTML estático) ──
    st.markdown('<div class="calc-sub-title">📋 Datos Base del Crédito</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="calc-result-row">
            <span class="calc-result-label">Préstamo Solicitado (nAmount)</span>
            <span class="calc-result-value">{formatearMoneda(nAmount)}</span>
        </div>
        <div class="calc-result-row">
            <span class="calc-result-label">Pagaré Firmado (nTAmount)</span>
            <span class="calc-result-value">{formatearMoneda(nTAmount)}</span>
        </div>
        <div class="calc-result-row">
            <span class="calc-result-label">Monto Pagado (nPaid + pago detectado)</span>
            <span class="calc-result-value">{formatearMoneda(montoPagado)}</span>
        </div>
        <div class="calc-result-row">
            <span class="calc-result-label">Monto Pendiente (nTAmount − Monto Pagado)</span>
            <span class="calc-result-value">{formatearMoneda(montoPendiente)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Cerrar el HTML antes de los widgets nativos de Streamlit
    st.markdown("</div></div>", unsafe_allow_html=True)

    # ── Separador y parámetros del gestor (widgets nativos) ──
    st.markdown("---")
    st.markdown(
        '<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:1.2px;color:#58a6ff;margin-bottom:4px">✏️ Parámetros del Gestor</p>',
        unsafe_allow_html=True,
    )

    # Claves únicas de st.session_state por vReference para persistir los valores
    vRefKey  = str(obtenerValorColumna(fila, "vReference") or "").strip()
    keyPorc  = f"calc_porcentaje_{vRefKey}"
    keyMeses = f"calc_meses_{vRefKey}"

    if keyPorc not in st.session_state:
        st.session_state[keyPorc]  = 0.0
    if keyMeses not in st.session_state:
        st.session_state[keyMeses] = 1

    colA, colB, colC = st.columns([2, 2, 1])
    with colA:
        porcentaje = st.number_input(
            "Porcentaje de Descuento (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state[keyPorc]),
            step=1.0,
            format="%.1f",
            help="Porcentaje a negociar (ej. 20 = 20%)",
            key=keyPorc,
        )
    with colB:
        meses = st.number_input(
            "Número de Meses",
            min_value=1,
            max_value=360,
            value=int(st.session_state[keyMeses]),
            step=1,
            help="Meses para la alternativa de pago",
            key=keyMeses,
        )
    with colC:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Limpiar", key=f"calc_limpiar_{vRefKey}", use_container_width=True):
            st.session_state[keyPorc]  = 0.0
            st.session_state[keyMeses] = 1
            st.rerun()

    # ── Validaciones ──
    hayError = False
    if porcentaje < 0 or porcentaje > 100:
        st.markdown(
            '<div class="alerta-warning">⚠️ El porcentaje debe estar entre 0 y 100.</div>',
            unsafe_allow_html=True,
        )
        hayError = True
    if meses <= 0:
        st.markdown(
            '<div class="alerta-warning">⚠️ El número de meses debe ser mayor a 0.</div>',
            unsafe_allow_html=True,
        )
        hayError = True
    if montoPendiente <= 0 and not hayError:
        st.markdown(
            '<div class="alerta-info">ℹ️ El monto pendiente es 0 o negativo; '
            'el crédito podría estar saldado.</div>',
            unsafe_allow_html=True,
        )

    if not hayError:
        # ── Cálculos finales ──
        descuento         = round(montoPendiente * (porcentaje / 100), 2)
        promocionLiquidar = round(montoPendiente - descuento, 2)
        pagoMensual       = round(promocionLiquidar / meses, 2) if meses > 0 else 0.0

        # ── Tabla de resultados ──
        st.markdown(
            '<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
            'letter-spacing:1.2px;color:#58a6ff;margin-top:16px;margin-bottom:4px">'
            '📊 Resultados</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div style="background:#0d1117;border:1px solid #30363d;border-radius:10px;
                        padding:16px 20px;margin-top:8px">
                <div class="calc-result-row">
                    <span class="calc-result-label">Descuento aplicado ({porcentaje:.1f}%)</span>
                    <span class="calc-result-value">− {formatearMoneda(descuento)}</span>
                </div>
                <div class="calc-result-row">
                    <span class="calc-result-label">🎯 Promoción para Liquidar</span>
                    <span class="calc-result-value highlight">{formatearMoneda(promocionLiquidar)}</span>
                </div>
                <div class="calc-result-row">
                    <span class="calc-result-label">💳 Pago Mensual ({meses} mes{'es' if meses != 1 else ''})</span>
                    <span class="calc-result-value highlight">{formatearMoneda(pagoMensual)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def renderizarOtrosVReference(fila: pd.Series, dfCompleto: pd.DataFrame):
    """
    Renderiza la sección 'Otros VReference del Cliente'.

    Lógica:
    - Toma iPersonId_x del registro actual.
    - Busca en el dataset completo todos los vReference del mismo cliente.
    - Excluye el vReference actual de la lista de 'otros'.
    - Muestra tabla con: vReference, iCredId, nAmount, nTotBalance,
      nDueBalance_x (Saldo Vencido), vEstatCred_x.

    Args:
        fila:       pd.Series del registro actualmente visualizado.
        dfCompleto: DataFrame completo para la búsqueda.
    """
    vRefActual  = str(obtenerValorColumna(fila, "vReference") or "").strip()
    iPersonId   = str(obtenerValorColumna(fila, "iPersonId_x") or "").strip()

    # Contar total de préstamos del cliente (incluyendo el actual)
    if iPersonId and iPersonId.lower() not in ("nan", "none", ""):
        mascTotal = dfCompleto["iPersonId_x"].astype(str).str.strip() == iPersonId
        totalPrestamos = dfCompleto[mascTotal]["vReference"].nunique()
    else:
        totalPrestamos = 1

    # Obtener otros VReference
    otros = buscarOtrosVReference(dfCompleto, iPersonId, vRefActual)

    # ── Encabezado de la sección ──
    st.markdown(
        f"""
        <div class="otras-vref-section">
            <div class="otras-vref-header">
                <div style="display:flex;align-items:center;gap:10px">
                    <span style="font-size:1rem">🔗</span>
                    <span class="otras-vref-title">Otros VReference del Cliente</span>
                </div>
                <div class="otras-vref-badge">
                    🗂️ {totalPrestamos} préstamo{'s' if totalPrestamos != 1 else ''} totales
                </div>
            </div>
            <div class="otras-vref-body">
                <div class="otras-vref-meta">
                    <div class="otras-vref-meta-item">
                        <span class="otras-vref-meta-label">ID Cliente (iPersonId_x)</span>
                        <span class="otras-vref-meta-value">{iPersonId if iPersonId and iPersonId.lower() not in ('nan','none','') else '—'}</span>
                    </div>
                    <div class="otras-vref-meta-item">
                        <span class="otras-vref-meta-label">Préstamo Actual</span>
                        <span class="otras-vref-meta-value">{vRefActual if vRefActual else '—'}</span>
                    </div>
                    <div class="otras-vref-meta-item">
                        <span class="otras-vref-meta-label">Otros Préstamos Encontrados</span>
                        <span class="otras-vref-meta-value">{len(otros)}</span>
                    </div>
                </div>
        """,
        unsafe_allow_html=True,
    )

    if otros.empty:
        # Caso: cliente con un solo préstamo
        st.markdown(
            '<div class="sin-otros-vref">'
            '✅ Este cliente no tiene otros VReference asociados.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        # Construir filas HTML de la tabla
        filas_html = ""
        for _, row in otros.iterrows():
            _v  = formatearTexto(obtenerValorColumna(row, "vReference"))
            _c  = formatearTexto(obtenerValorColumna(row, "iCredId"))
            _am = formatearMoneda(obtenerValorColumna(row, "nAmount"))
            _tb = formatearMoneda(obtenerValorColumna(row, "nTotBalance"))
            _db = formatearMoneda(obtenerValorColumna(row, "nDueBalance_x"))
            # Intentar vEstatCred_x primero, luego vEstatCred_y
            _es = formatearTexto(obtenerValorColumna(row, "vEstatCred_x"))
            if _es == TEXTO_SIN_DATO:
                _es = formatearTexto(obtenerValorColumna(row, "vEstatCred_y"))

            filas_html += f"""
            <tr>
                <td class="vref-code">{_v}</td>
                <td>{_c}</td>
                <td class="moneda-tabla">{_am}</td>
                <td class="moneda-tabla">{_tb}</td>
                <td class="moneda-tabla">{_db}</td>
                <td class="estatus">{_es}</td>
            </tr>"""

        st.markdown(
            f"""
            <table class="vref-table">
                <thead>
                    <tr>
                        <th>VReference</th>
                        <th>ID Crédito</th>
                        <th>Monto Otorgado</th>
                        <th>Saldo Total</th>
                        <th>Saldo Vencido</th>
                        <th>Estatus</th>
                    </tr>
                </thead>
                <tbody>
                    {filas_html}
                </tbody>
            </table>
            """,
            unsafe_allow_html=True,
        )

    # Cerrar divs de la sección
    st.markdown("</div></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  SIDEBAR
#  Arranca expandida (initial_sidebar_state="expanded"). El colapso y la
#  reapertura los gestiona Streamlit de forma nativa; el CSS no interfiere.
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
                limpiarBusqueda()
                st.rerun()
        else:
            # Si es carga manual, botón para descartarla y volver al repo
            if st.button("↩️ Usar archivo del repo", use_container_width=True):
                st.session_state.dataframe = None
                st.session_state.archivoNombre = None
                st.session_state.fuenteArchivo = None
                limpiarBusqueda()
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
                    limpiarBusqueda()
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
        "v1.2.0 · Dashboard Ejecutivo</div>",
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
        placeholder="Pega o escribe el número de referencia del cliente...",
        key="inputVReference",
        label_visibility="collapsed",
    )

with colLimpiar:
    st.button(
        "✕ Limpiar",
        use_container_width=True,
        on_click=limpiarBusqueda,
    )

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

        # ── Sección: Otros VReference del mismo cliente ──
        renderizarOtrosVReference(filaCliente, df)

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
