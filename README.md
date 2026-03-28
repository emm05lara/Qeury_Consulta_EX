# 🏦 Dashboard de Cobranza — Consulta por VREFERENCE

Dashboard ejecutivo interactivo desarrollado con **Python + Streamlit** para consulta individual de clientes a partir del identificador `VREFERENCE`.

---

## 📋 Estructura del Proyecto

```
CONSULTA_QUERY/
├── app.py                  # Aplicación principal Streamlit
├── requirements.txt        # Dependencias Python
├── render.yaml             # Configuración de deploy en Render
├── .gitignore              # Archivos excluidos de Git
├── README.md               # Este archivo
├── data/
│   └── baseConsulta.xlsx   # ← ARCHIVO DE DATOS (agrega el tuyo aquí)
│       baseConsulta.csv    #   (alternativa CSV, se detecta automáticamente)
├── .streamlit/
│   └── config.toml         # Configuración de Streamlit + tema visual forzado
└── utils/
    ├── __init__.py         # Inicializador del paquete
    ├── carga.py            # Carga y validación del archivo (repo + manual)
    ├── formato.py          # Formateo de monedas, fechas y nulos
    └── calculos.py         # Campos calculados (ej. Plazo)
```

---

## 📂 Archivo de Datos (IMPORTANTE)

### Ruta esperada
El dashboard carga automáticamente el archivo de datos desde:

```
data/baseConsulta.xlsx   ← Principal (Excel, primera hoja)
data/baseConsulta.csv    ← Alternativa (CSV, UTF-8 o latin-1)
```

> ⚠️ Sin este archivo, la app mostrará un mensaje claro indicando qué hacer.

### Cómo actualizar los datos
1. Reemplaza el archivo en la carpeta `data/` con la nueva versión.
2. Haz `git add data/baseConsulta.xlsx && git commit -m "update: datos" && git push`.
3. Render redespliega automáticamente con los nuevos datos.

### Si el archivo tiene varias hojas (Excel)
La app usa la **primera hoja** por defecto (índice 0). Si necesitas cambiar esto, edita la constante `HOJA_EXCEL_DEFECTO` en `utils/carga.py`:

```python
# utils/carga.py
HOJA_EXCEL_DEFECTO = 0        # primera hoja (por índice)
HOJA_EXCEL_DEFECTO = "Hoja1"  # o por nombre de hoja
```

### Carga manual (respaldo)
La sidebar siempre ofrece un uploader de respaldo para cargar un archivo diferente sin necesidad de push.

---

## 🚀 Correr Localmente

### 1. Prerrequisitos

- Python 3.10 o superior
- pip actualizado

### 2. Crear entorno virtual e instalar dependencias

```bash
# Crear entorno virtual
python -m venv venv

# Activar (Windows)
venv\Scripts\activate

# Activar (macOS / Linux)
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Agregar archivo de datos

```bash
# Copia tu archivo Excel o CSV a la carpeta data/
cp tuarchivo.xlsx data/baseConsulta.xlsx
```

### 4. Ejecutar la app

```bash
streamlit run app.py
```

La app abrirá automáticamente en `http://localhost:8501`.  
Si `data/baseConsulta.xlsx` existe, se cargará automáticamente.

---

## 📁 Columnas esperadas en el archivo

El archivo debe contener los siguientes encabezados (sin importar el orden):

| Campo Dashboard | Columna en archivo |
|---|---|
| VREFERENCE | `vReference` |
| NOMBRE | `vName` |
| BUCKET | `Bucket Inicio` |
| MONTO DESCUENTO | `nDescuento` |
| MONTO AMORTIZACIÓN | `Amortizacion` |
| MÍNIMO CURRENT / SALDO VENCIDO | `nDueBalance_x` |
| MÍNIMO PARA CONTENER | `Minimo para contener` |
| MONTO A LIQUIDAR | `Monto Liquidacion` |
| GESTOR | `Gestor` |
| PAGO RECIBIDO/APLICADO | `Pago cash` |
| FECHA PAGO APLICADO | `F.Aplicacion` |
| FECHA ÚLTIMO PAGO | `vUltPago` |
| SALDO TOTAL | `nTotBalance` |
| FECHA APERTURA | `vOpenned` |
| MONTO SOLICITADO | `nAmount` |
| FRECUENCIA | `vFrecuencia` |
| MONTO PAGARÉ | `nTAmount` |
| PLAZO *(calculado)* | `nTAmount / nDescuento` |

---

## 🎨 Tema Visual

La identidad visual del dashboard se fuerza mediante dos mecanismos complementarios:

1. **`.streamlit/config.toml`**: establece el tema base `dark` y los colores de acento. Esto afecta los widgets nativos de Streamlit (inputs, botones, expanders).

2. **CSS inyectado en `app.py`**: todos los componentes personalizados (tarjetas, filas de datos, badges, alertas) usan CSS con `!important` y son inmunes al tema local del usuario.

> **Nota**: Streamlit permite al usuario cambiar el tema desde la UI (Settings → Theme). Esto puede afectar widgets nativos pero **NO** altera los componentes HTML personalizados que forman el cuerpo principal del dashboard.

---

## 🐙 Subir a GitHub

```bash
# Inicializar repositorio (solo la primera vez)
git init
git add .
git commit -m "feat: dashboard ejecutivo de cobranza v1.1"

# Crear repositorio en https://github.com/new y luego:
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git branch -M main
git push -u origin main
```

> ✅ El archivo `data/baseConsulta.xlsx` **SÍ debe subirse a GitHub** para que Render lo use en producción. No está en `.gitignore`.

---

## ☁️ Desplegar en Render

### Opción A: Con `render.yaml` (recomendado)

1. Sube el proyecto a GitHub (ver sección anterior).
2. Ve a [https://dashboard.render.com](https://dashboard.render.com) y haz clic en **"New → Web Service"**.
3. Conecta tu repositorio de GitHub.
4. Render detectará automáticamente el archivo `render.yaml`.
5. Confirma y haz clic en **"Create Web Service"**.

Render instalará las dependencias y ejecutará:
```
streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
```

### Opción B: Configuración manual en Render

| Campo | Valor |
|---|---|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true` |

> 💡 El puerto es dinámico via la variable `$PORT` que Render asigna automáticamente.

---

## 🌐 Conectar Dominio con Cloudflare

### Paso 1 — Obtener la URL de Render
Después del deploy, Render te dará una URL pública como:
```
https://consulta-query-dashboard.onrender.com
```

### Paso 2 — Agregar sitio en Cloudflare
1. En [https://dash.cloudflare.com](https://dash.cloudflare.com), ve a **"Add a Site"**.
2. Ingresa tu dominio (ej. `miempresa.com`).
3. Selecciona el plan **Free** y continúa.
4. Apunta los nameservers de tu registrador a los que Cloudflare te indique.

### Paso 3 — Crear registro CNAME en Cloudflare
En tu zona DNS de Cloudflare, agrega:

| Tipo | Nombre | Destino | Proxy |
|---|---|---|---|
| `CNAME` | `consulta` | `consulta-query-dashboard.onrender.com` | ✅ Proxy activo |

### Paso 4 — Configurar dominio personalizado en Render
1. En Render, ve a tu servicio → **"Settings" → "Custom Domains"**.
2. Agrega tu dominio (ej. `consulta.miempresa.com`).
3. Render verificará el CNAME y habilitará HTTPS automáticamente.

---

## 🔧 Personalización

### Cambiar el nombre del archivo de datos
Edita `NOMBRES_ARCHIVO_DATOS` en `utils/carga.py`.

### Cambiar la hoja de Excel usada
Edita `HOJA_EXCEL_DEFECTO` en `utils/carga.py` (por defecto: `0` = primera hoja).

### Cambiar columnas del archivo
Edita `COLUMNAS_REQUERIDAS` en `utils/carga.py` y los nombres usados en `app.py` dentro de `obtenerValorColumna(...)`.

### Agregar nuevos campos al dashboard
1. Agrega el encabezado a `COLUMNAS_REQUERIDAS` en `utils/carga.py`.
2. En `app.py`, agrega una llamada a `renderizarFila(...)` dentro del bloque correspondiente.

### Cambiar paleta de colores
Edita las variables CSS al inicio de `app.py` (bloque `:root { ... }`) y los colores en `.streamlit/config.toml`.

---

## 🛡️ Consideraciones de Seguridad

- El archivo `data/baseConsulta.xlsx` **debe subirse al repo** para que el deploy en Render funcione.
- Si los datos son confidenciales y no deben estar en el repo, considera usar **Render Disk** (volumen persistente) o una fuente de datos externa (base de datos, API).
- Para versión productiva con datos muy sensibles, evalúa Streamlit Cloud con **Secrets Management** o variables de entorno.

---

## 📦 Dependencias

| Librería | Uso |
|---|---|
| `streamlit` | Framework de UI web |
| `pandas` | Manejo y procesamiento de datos |
| `openpyxl` | Lectura de archivos `.xlsx` |
| `xlrd` | Lectura de archivos `.xls` legados |

---

*Dashboard Ejecutivo de Cobranza — v1.1.0*
