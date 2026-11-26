import streamlit as st
import sqlite3
import uuid
import os
import pandas as pd
import qrcode
import zxingcpp
from PIL import Image
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="COLECTIVO KALMA // ACCESS", page_icon="⚡", layout="centered")

# ==========================================
# 🎨 ESTILO VISUAL: EVENTO ELECTRÓNICO (VIOLETA Y CIAN)
# ==========================================
st.markdown("""
<style>
    /* Fondo general oscuro */
    .stApp {
        background: radial-gradient(circle at top, #1a1025 0%, #09090b 65%);
        color: #ffffff !important;
    }
    /* Forzar visibilidad de textos, etiquetas y opciones */
    .stApp p, .stApp label, [data-testid="stWidgetLabel"] p,
    [data-testid="stRadio"] p, [data-testid="stCaptionContainer"] p,
    [data-testid="stMetricLabel"] p {
        color: #f4f4f5 !important;
    }
    [data-testid="stWidgetLabel"] p {
        font-weight: 600 !important;
        letter-spacing: 0.5px;
    }
    /* Títulos con estilo club/electrónica */
    h1, h2, h3 {
        color: #ffffff !important;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }
    h1 {
        text-shadow: 0 0 12px rgba(168, 85, 247, 0.7);
    }
    /* Botones principales y botón de cámara (Take Photo) */
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button,
    [data-testid="stCameraInputButton"] {
        background: linear-gradient(90deg, #9333ea 0%, #06b6d4 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        letter-spacing: 1px;
        text-transform: uppercase;
        box-shadow: 0 0 15px rgba(147, 51, 234, 0.4);
        transition: all 0.2s ease-in-out;
    }
    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button:hover,
    [data-testid="stCameraInputButton"]:hover {
        box-shadow: 0 0 22px rgba(6, 182, 212, 0.75);
        transform: scale(1.01);
    }
    /* Botones secundarios */
    .stButton > button, .stDownloadButton > button {
        background-color: #18181b !important;
        color: #ffffff !important;
        border: 1px solid #52525b !important;
        border-radius: 8px !important;
    }
    /* Inputs y formularios */
    .stTextInput > div > div > input, .stSelectbox > div > div {
        background-color: #18181b !important;
        color: #ffffff !important;
        border: 1px solid #7e22ce !important;
        border-radius: 8px !important;
    }
    /* Pestañas (activas e inactivas bien visibles) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #121217;
        padding: 6px;
        border-radius: 10px;
        border: 1px solid #3f3f46;
    }
    .stTabs [data-baseweb="tab"] p {
        color: #d4d4d8 !important;
        font-weight: 600 !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2e1065 !important;
        border: 1px solid #9333ea !important;
        border-radius: 6px;
    }
    .stTabs [aria-selected="true"] p {
        color: #22d3ee !important;
    }
    /* Tarjeta de pase válido */
    .ticket-card {
        background: linear-gradient(135deg, #18181b 0%, #1e1b4b 100%);
        border: 2px solid #22d3ee;
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 0 20px rgba(34, 211, 238, 0.25);
    }
    /* Métricas */
    [data-testid="stMetricValue"] {
        color: #22d3ee !important;
        text-shadow: 0 0 10px rgba(34, 211, 238, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 CONFIGURACIÓN DE USUARIOS Y CONTRASEÑAS
# ==========================================
USUARIOS_ACCESO = {
    "Colectivo.kalma": "Kalma.0720",
    "puerta": "1234"
}

USUARIOS_ADMIN = {
    "Javi.martinez": "Colectivo2026",
    "Eric.brito": "Colectivo2026",
    "Piero.corci": "Colectivo2026"
}

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""
if "admin_usuario" not in st.session_state:
    st.session_state.admin_usuario = None

# ==========================================
# 🚪 PORTADA DE INICIO DE SESIÓN CON LOGO
# ==========================================
if not st.session_state.autenticado:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("<h1 style='text-align: center;'>⚡ COLECTIVO KALMA</h1>", unsafe_allow_html=True)

    st.markdown("<p style='text-align: center; color: #22d3ee !important; letter-spacing: 3px; font-size: 14px;'>ELECTRONIC MUSIC // ACCESS CONTROL</p>", unsafe_allow_html=True)
    st.divider()

    with st.form("form_login"):
        usuario = st.text_input("USUARIO")
        clave = st.text_input("CONTRASEÑA", type="password")
        entrar = st.form_submit_button("INGRESAR AL SISTEMA", type="primary", use_container_width=True)

        if entrar:
            if usuario in USUARIOS_ACCESO and USUARIOS_ACCESO[usuario] == clave:
                st.session_state.autenticado = True
                st.session_state.usuario_actual = usuario
                st.rerun()
            else:
                st.error("Acceso denegado. Usuario o contraseña incorrectos.")

    st.stop()

# --- BASE DE DATOS LOCAL (SQLite) ---
def init_db():
    conn = sqlite3.connect("entradas.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS entradas (
            codigo TEXT PRIMARY KEY,
            nombre TEXT,
            rut TEXT,
            tipo TEXT,
            estado TEXT,
            fecha_creacion TEXT,
            fecha_ingreso TEXT,
            creado_por TEXT
        )
    """)
    c.execute("PRAGMA table_info(entradas)")
    columnas = [col[1] for col in c.fetchall()]
    if "creado_por" not in columnas:
        c.execute("ALTER TABLE entradas ADD COLUMN creado_por TEXT DEFAULT ''")
    conn.commit()
    return conn

conn = init_db()

def generar_imagen_qr(texto):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def pedir_acceso_admin(id_pestana):
    if st.session_state.admin_usuario is not None:
        return True

    st.warning("🔒 ZONA RESTRINGIDA — SOLO PRODUCCIÓN")
    with st.form(f"form_admin_{id_pestana}"):
        admin_user = st.text_input("Usuario producción")
        admin_pass = st.text_input("Contraseña", type="password")
        desbloquear = st.form_submit_button("DESBLOQUEAR", type="primary", use_container_width=True)
        if desbloquear:
            if admin_user in USUARIOS_ADMIN and USUARIOS_ADMIN[admin_user] == admin_pass:
                st.session_state.admin_usuario = admin_user
                st.rerun()
            else:
                st.error("Credenciales de producción incorrectas.")
    return False

# --- BARRA SUPERIOR ---
col_tit, col_salir = st.columns([3, 1])
with col_tit:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=220)
    else:
        st.markdown("## ⚡ COLECTIVO KALMA")
with col_salir:
    st.write("")
    if st.button("SALIR", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.usuario_actual = ""
        st.session_state.admin_usuario = None
        st.rerun()

st.caption(f"🟢 EN LÍNEA: **{st.session_state.usuario_actual}**")

tab1, tab2, tab3 = st.tabs(["📷 PUERTA / SCAN", "🔒 GENERAR QR", "🔒 LISTA & BACKUP"])

# ==========================================
# PESTAÑA 1: VALIDAR EN PUERTA
# ==========================================
with tab1:
    st.subheader("CHECK-IN DE ACCESO")
    metodo = st.radio("Modo de lectura:", ["Cámara", "Código Manual / Pistola"], horizontal=True)
    codigo_leido = None

    if metodo == "Cámara":
        img_file = st.camera_input("Escanea el QR del asistente")
        if img_file is not None:
            img = Image.open(img_file)
            resultados = zxingcpp.read_barcodes(img)
            if resultados:
                codigo_leido = resultados[0].text.strip()
            else:
                st.warning("No se detectó ningún QR. Acerca la cámara o sube el brillo del celular.")
    else:
        codigo_leido = st.text_input("Ingresa o escanea el código:").strip()

    if codigo_leido:
        c = conn.cursor()
        c.execute("SELECT codigo, nombre, rut, tipo, estado, fecha_ingreso, creado_por FROM entradas WHERE codigo = ?", (codigo_leido,))
        entrada = c.fetchone()

        if not entrada:
            st.error(f"❌ ACCESO DENEGADO: El código `{codigo_leido}` no existe.")
        else:
            cod, nombre, rut, tipo, estado, fecha_ing, creado_por = entrada
            if estado == "USADA":
                st.error("⛔ ENTRADA YA QUEMADA / UTILIZADA")
                st.warning(f"**Titular:** {nombre} | **RUT:** {rut}\n\n**Ingresó el:** {fecha_ing}")
            else:
                st.markdown(f"""
                <div class="ticket-card">
                    <p style="color:#22d3ee !important; font-weight:bold; margin:0; letter-spacing:2px;">✅ ACCESO VÁLIDO — VERIFICAR CARNET</p>
                    <h2 style="margin:8px 0 4px 0;">👤 {nombre}</h2>
                    <h3 style="color:#a855f7 !important; margin:0 0 12px 0;">🪪 RUT: {rut}</h3>
                    <p style="margin:0; font-size:14px;"><b>🎟️ PASE:</b> {tipo} &nbsp;|&nbsp; <b>🔑 ID:</b> {cod}</p>
                    <p style="margin:4px 0 0 0; font-size:12px; color:#d4d4d8 !important;">Generado por: {creado_por if creado_por else 'Sin registro'}</p>
                </div>
                """, unsafe_allow_html=True)

                if st.button("✅ CONFIRMAR INGRESO (QUEMAR QR)", type="primary", use_container_width=True):
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("UPDATE entradas SET estado = 'USADA', fecha_ingreso = ? WHERE codigo = ?", (ahora, cod))
                    conn.commit()
                    st.toast(f"Ingreso confirmado: {nombre}")
                    st.rerun()

# ==========================================
# PESTAÑA 2: GENERAR ENTRADA (ADMIN)
# ==========================================
with tab2:
    if pedir_acceso_admin("tab2"):
        st.info(f"⚡ Producción activa: **{st.session_state.admin_usuario}**")
        st.subheader("EMITIR NUEVO E-TICKET")
        with st.form("form_crear", clear_on_submit=True):
            nombre = st.text_input("Nombre Completo")
            rut = st.text_input("RUT / Carnet (ej: 12.345.678-9)")
            tipo = st.selectbox("Tipo de Pase", ["Early Bird", "Preventa 1", "Preventa 2", "General", "VIP / Backstage", "Lista / Cortesía"])
            crear = st.form_submit_button("⚡ GENERAR E-TICKET QR", type="primary", use_container_width=True)

        if crear:
            if nombre.strip() and rut.strip():
                codigo_unico = f"KLM-{uuid.uuid4().hex[:8].upper()}"
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                creador = st.session_state.admin_usuario
                c = conn.cursor()
                c.execute(
                    "INSERT INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (codigo_unico, nombre.strip(), rut.strip(), tipo, "DISPONIBLE", ahora, "", creador)
                )
                conn.commit()
                st.session_state["ultimo_qr"] = (codigo_unico, nombre.strip(), rut.strip(), tipo, creador)
                st.success(f"E-Ticket emitido para **{nombre.strip()}** (`{codigo_unico}`)")
            else:
                st.error("Debes completar el Nombre y el RUT.")

        if "ultimo_qr" in st.session_state:
            cod, nom, rt, tp, cr = st.session_state["ultimo_qr"]
            qr_bytes = generar_imagen_qr(cod)
            st.divider()
            st.write(f"**Último E-Ticket:** {nom} ({rt}) — **{tp}** | *Por: {cr}*")
            st.image(qr_bytes, width=250)
            st.download_button(
                label="📥 DESCARGAR QR PARA WHATSAPP",
                data=qr_bytes,
                file_name=f"KALMA_QR_{nom.replace(' ', '_')}_{cod}.png",
                mime="image/png",
                use_container_width=True
            )

# ==========================================
# PESTAÑA 3: LISTA Y RESPALDO (ADMIN)
# ==========================================
with tab3:
    if pedir_acceso_admin("tab3"):
        st.info(f"⚡ Producción activa: **{st.session_state.admin_usuario}**")
        df = pd.read_sql_query("SELECT * FROM entradas ORDER BY fecha_creacion DESC", conn)

        col1, col2, col3 = st.columns(3)
        col1.metric("EMITIDAS", len(df))
        col2.metric("ADENTRO", len(df[df["estado"] == "USADA"]))
        col3.metric("POR LLEGAR", len(df[df["estado"] == "DISPONIBLE"]))

        busqueda = st.text_input("🔍 Buscar por Nombre, RUT o Productor:")
        if busqueda:
            df_mostrar = df[
                df["nombre"].str.contains(busqueda, case=False, na=False) |
                df["rut"].str.contains(busqueda, case=False, na=False) |
                df["creado_por"].str.contains(busqueda, case=False, na=False)
            ]
        else:
            df_mostrar = df

        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("**💾 BACKUP DE SEGURIDAD** *(Descarga siempre tu lista antes de abrir puertas)*")
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 DESCARGAR BASE DE DATOS (CSV)",
            data=csv,
            file_name=f"kalma_respaldo_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

        archivo_subido = st.file_uploader("📤 Restaurar base de datos desde CSV", type=["csv"])
        if archivo_subido is not None:
            if st.button("CARGAR ENTRADAS DEL ARCHIVO", use_container_width=True):
                df_nuevo = pd.read_csv(archivo_subido).fillna("")
                c = conn.cursor()
                for _, row in df_nuevo.iterrows():
                    creador_csv = row["creado_por"] if "creado_por" in df_nuevo.columns else ""
                    c.execute(
                        "INSERT OR REPLACE INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (row["codigo"], row["nombre"], row["rut"], row["tipo"], row["estado"], row["fecha_creacion"], row["fecha_ingreso"], creador_csv)
                    )
                conn.commit()
                st.success("Base de datos restaurada correctamente.")
                st.rerun()

        st.divider()
        if st.button("🔒 BLOQUEAR ZONA DE PRODUCCIÓN", use_container_width=True):
            st.session_state.admin_usuario = None
            st.rerun()
