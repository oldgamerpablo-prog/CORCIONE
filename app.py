import streamlit as st
import sqlite3
import uuid
import os
import pandas as pd
import qrcode
import zxingcpp
from PIL import Image
from io import BytesIO
from datetime import datetime, time
from zoneinfo import ZoneInfo

st.set_page_config(page_title="COLECTIVO KALMA // ACCESS", page_icon="⚡", layout="centered")

# --- HORA LOCAL CHILE ---
def ahora_chile():
    try:
        return datetime.now(ZoneInfo("America/Santiago")).replace(tzinfo=None)
    except Exception:
        return datetime.now()

# ==========================================
# 🎨 ESTILO VISUAL: EVENTO ELECTRÓNICO (VIOLETA Y CIAN)
# ==========================================
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at top, #1a1025 0%, #09090b 65%);
        color: #ffffff !important;
    }
    .stApp p, .stApp label, [data-testid="stWidgetLabel"] p,
    [data-testid="stRadio"] p, [data-testid="stCaptionContainer"] p,
    [data-testid="stMetricLabel"] p {
        color: #f4f4f5 !important;
    }
    [data-testid="stWidgetLabel"] p {
        font-weight: 600 !important;
        letter-spacing: 0.5px;
    }
    h1, h2, h3 {
        color: #ffffff !important;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }
    h1 {
        text-shadow: 0 0 12px rgba(168, 85, 247, 0.7);
    }
    [data-testid="stAlert"], [data-testid="stAlert"] > div {
        background-color: #18181b !important;
        color: #ffffff !important;
        border: 1px solid #7e22ce !important;
        border-radius: 8px !important;
    }
    [data-testid="stExpander"] {
        background-color: #121217 !important;
        border: 1px solid #7e22ce !important;
        border-radius: 8px !important;
    }
    [data-testid="stExpander"] summary, [data-testid="stExpander"] summary:hover {
        background-color: #1e1b4b !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    [data-testid="stExpander"] summary p {
        color: #22d3ee !important;
        font-weight: 700 !important;
    }
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
    .stButton > button, .stDownloadButton > button {
        background-color: #18181b !important;
        color: #ffffff !important;
        border: 1px solid #52525b !important;
        border-radius: 8px !important;
    }
    .stTextInput > div > div > input {
        background-color: #18181b !important;
        color: #ffffff !important;
        border: 1px solid #7e22ce !important;
        border-radius: 8px !important;
    }
    /* Selectbox: texto visible, fondo oscuro y menú desplegable legible */
    .stSelectbox [data-baseweb="select"] > div {
        background-color: #18181b !important;
        color: #ffffff !important;
        border: 1px solid #9333ea !important;
        border-radius: 8px !important;
    }
    .stSelectbox [data-baseweb="select"] span,
    .stSelectbox [data-baseweb="select"] div,
    .stSelectbox [data-baseweb="select"] input,
    .stSelectbox [data-baseweb="select"] svg {
        color: #ffffff !important;
        fill: #22d3ee !important;
    }
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"],
    [role="listbox"] {
        background-color: #18181b !important;
        color: #ffffff !important;
        border: 1px solid #9333ea !important;
    }
    [role="option"] {
        background-color: #18181b !important;
        color: #ffffff !important;
    }
    [role="option"]:hover,
    [aria-selected="true"][role="option"] {
        background-color: #2e1065 !important;
        color: #22d3ee !important;
    }
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
    .ticket-card {
        background: linear-gradient(135deg, #18181b 0%, #1e1b4b 100%);
        border: 2px solid #22d3ee;
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 0 20px rgba(34, 211, 238, 0.25);
    }
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
            creado_por TEXT,
            evento TEXT,
            caducidad TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            nombre TEXT PRIMARY KEY,
            caducidad TEXT
        )
    """)
    c.execute("PRAGMA table_info(entradas)")
    columnas = [col[1] for col in c.fetchall()]
    if "creado_por" not in columnas:
        c.execute("ALTER TABLE entradas ADD COLUMN creado_por TEXT DEFAULT ''")
    if "evento" not in columnas:
        c.execute("ALTER TABLE entradas ADD COLUMN evento TEXT DEFAULT ''")
    if "caducidad" not in columnas:
        c.execute("ALTER TABLE entradas ADD COLUMN caducidad TEXT DEFAULT ''")
    conn.commit()
    return conn

conn = init_db()

def obtener_eventos():
    c = conn.cursor()
    c.execute("SELECT nombre, caducidad FROM eventos ORDER BY nombre ASC")
    return dict(c.fetchall())

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

st.caption(f"🟢 EN LÍNEA: **{st.session_state.usuario_actual}** | 🕒 Hora Chile: {ahora_chile().strftime('%d/%m/%Y %H:%M')}")

tab1, tab2, tab3 = st.tabs(["📷 PUERTA / SCAN", "🔒 GENERAR QR", "🔒 LISTA & BACKUP"])

# ==========================================
# PESTAÑA 1: VALIDAR EN PUERTA
# ==========================================
with tab1:
    st.subheader("CHECK-IN DE ACCESO")

    eventos_dict = obtener_eventos()
    opciones_puerta = ["Todos los eventos"] + list(eventos_dict.keys())
    evento_activo = st.selectbox("🎧 Evento activo en puerta (filtro):", opciones_puerta)

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
        c.execute(
            "SELECT codigo, nombre, rut, tipo, estado, fecha_ingreso, creado_por, evento, caducidad FROM entradas WHERE codigo = ?",
            (codigo_leido,)
        )
        entrada = c.fetchone()

        if not entrada:
            st.error(f"❌ ACCESO DENEGADO: El código `{codigo_leido}` no existe.")
        else:
            cod, nombre, rut, tipo, estado, fecha_ing, creado_por, ev_qr, cad_qr = entrada

            caducada = False
            if cad_qr:
                try:
                    dt_cad = datetime.strptime(cad_qr, "%Y-%m-%d %H:%M")
                    if ahora_chile() > dt_cad:
                        caducada = True
                except ValueError:
                    pass

            if estado == "USADA":
                st.error("⛔ ENTRADA YA QUEMADA / UTILIZADA")
                st.warning(f"**Titular:** {nombre} | **RUT:** {rut}\n\n**Evento:** {ev_qr}\n\n**Ingresó el:** {fecha_ing}")
            elif evento_activo != "Todos los eventos" and ev_qr != evento_activo:
                st.error("🚫 ENTRADA DE OTRO EVENTO")
                st.warning(f"Este QR corresponde a **{ev_qr or 'Sin evento'}**, no a **{evento_activo}**.")
            elif caducada:
                st.error("⌛ ENTRADA CADUCADA")
                st.warning(f"**Titular:** {nombre} | **Evento:** {ev_qr}\n\n**Venció el:** {cad_qr}")
            else:
                st.markdown(f"""
                <div class="ticket-card">
                    <p style="color:#22d3ee !important; font-weight:bold; margin:0; letter-spacing:2px;">✅ ACCESO VÁLIDO — VERIFICAR CARNET</p>
                    <h2 style="margin:8px 0 4px 0;">👤 {nombre}</h2>
                    <h3 style="color:#a855f7 !important; margin:0 0 12px 0;">🪪 RUT: {rut}</h3>
                    <p style="margin:0; font-size:14px;"><b>🎧 EVENTO:</b> {ev_qr if ev_qr else 'General'} &nbsp;|&nbsp; <b>🎟️ PASE:</b> {tipo}</p>
                    <p style="margin:4px 0 0 0; font-size:13px; color:#f4f4f5 !important;"><b>⌛ Válido hasta:</b> {cad_qr if cad_qr else 'Sin límite'} &nbsp;|&nbsp; <b>🔑 ID:</b> {cod}</p>
                    <p style="margin:4px 0 0 0; font-size:12px; color:#a1a1aa !important;">Generado por: {creado_por if creado_por else 'Sin registro'}</p>
                </div>
                """, unsafe_allow_html=True)

                if st.button("✅ CONFIRMAR INGRESO (QUEMAR QR)", type="primary", use_container_width=True):
                    ahora_str = ahora_chile().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("UPDATE entradas SET estado = 'USADA', fecha_ingreso = ? WHERE codigo = ?", (ahora_str, cod))
                    conn.commit()
                    st.toast(f"Ingreso confirmado: {nombre}")
                    st.rerun()

# ==========================================
# PESTAÑA 2: GENERAR ENTRADA (ADMIN)
# ==========================================
with tab2:
    if pedir_acceso_admin("tab2"):
        st.info(f"⚡ Producción activa: **{st.session_state.admin_usuario}**")

        with st.expander("➕ CREAR O EDITAR EVENTO (QUEDA GUARDADO)", expanded=(len(obtener_eventos()) == 0)):
            with st.form("form_nuevo_evento", clear_on_submit=True):
                col_ev, col_fec, col_hor = st.columns([2, 1.2, 1])
                with col_ev:
                    nuevo_ev = st.text_input("Nombre del Evento", placeholder="Ej: KALMA VOL. 1")
                with col_fec:
                    fec_ev = st.date_input("Fecha caducidad", value=ahora_chile().date())
                with col_hor:
                    hor_ev = st.time_input("Hora límite", value=time(6, 0))

                guardar_ev = st.form_submit_button("💾 GUARDAR EVENTO", use_container_width=True)
                if guardar_ev:
                    if nuevo_ev.strip():
                        cad_str = f"{fec_ev.strftime('%Y-%m-%d')} {hor_ev.strftime('%H:%M')}"
                        c = conn.cursor()
                        c.execute("INSERT OR REPLACE INTO eventos VALUES (?, ?)", (nuevo_ev.strip(), cad_str))
                        conn.commit()
                        st.success(f"Evento **{nuevo_ev.strip()}** guardado (caduca: {cad_str}).")
                        st.rerun()
                    else:
                        st.error("Escribe un nombre para el evento.")

        st.subheader("EMITIR NUEVO E-TICKET")
        eventos_guardados = obtener_eventos()

        if not eventos_guardados:
            st.warning("Primero crea y guarda al menos un evento en el menú de arriba ⬆️.")
        else:
            col_sel_ev, col_sel_fec, col_sel_hor = st.columns([2, 1.2, 1])
            with col_sel_ev:
                evento_elegido = st.selectbox("🎧 Evento (selecciona o escribe para filtrar):", list(eventos_guardados.keys()))

            cad_guardada = eventos_guardados[evento_elegido]
            try:
                dt_def = datetime.strptime(cad_guardada, "%Y-%m-%d %H:%M")
                def_fecha, def_hora = dt_def.date(), dt_def.time()
            except ValueError:
                def_fecha, def_hora = ahora_chile().date(), time(6, 0)

            with col_sel_fec:
                fecha_qr = st.date_input("Fecha caducidad QR", value=def_fecha, key=f"fec_{evento_elegido}")
            with col_sel_hor:
                hora_qr = st.time_input("Hora límite QR", value=def_hora, key=f"hor_{evento_elegido}")

            with st.form("form_crear", clear_on_submit=True):
                nombre = st.text_input("Nombre Completo")
                rut = st.text_input("RUT / Carnet (ej: 12.345.678-9)")
                tipo = st.selectbox("Tipo de Pase", ["Early Bird", "Preventa 1", "Preventa 2", "General", "VIP / Backstage", "Lista / Cortesía"])
                crear = st.form_submit_button("⚡ GENERAR E-TICKET QR", type="primary", use_container_width=True)

            if crear:
                if nombre.strip() and rut.strip():
                    codigo_unico = f"KLM-{uuid.uuid4().hex[:8].upper()}"
                    ahora_str = ahora_chile().strftime("%Y-%m-%d %H:%M:%S")
                    caducidad_final = f"{fecha_qr.strftime('%Y-%m-%d')} {hora_qr.strftime('%H:%M')}"
                    creador = st.session_state.admin_usuario
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (codigo_unico, nombre.strip(), rut.strip(), tipo, "DISPONIBLE", ahora_str, "", creador, evento_elegido, caducidad_final)
                    )
                    conn.commit()
                    st.session_state["ultimo_qr"] = (codigo_unico, nombre.strip(), rut.strip(), tipo, creador, evento_elegido, caducidad_final)
                    st.success(f"E-Ticket emitido para **{nombre.strip()}** en **{evento_elegido}** (`{codigo_unico}`)")
                else:
                    st.error("Debes completar el Nombre y el RUT.")

        if "ultimo_qr" in st.session_state:
            cod, nom, rt, tp, cr, ev, cad = st.session_state["ultimo_qr"]
            qr_bytes = generar_imagen_qr(cod)
            st.divider()
            st.write(f"**Último E-Ticket:** {nom} ({rt}) — **{ev}** ({tp}) | *Válido hasta: {cad}*")
            st.image(qr_bytes, width=250)
            st.download_button(
                label="📥 DESCARGAR QR PARA WHATSAPP",
                data=qr_bytes,
                file_name=f"KALMA_{ev.replace(' ', '_')}_{nom.replace(' ', '_')}_{cod}.png",
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

        col_f1, col_f2 = st.columns([1.2, 1.8])
        with col_f1:
            lista_ev = ["Todos"] + sorted([e for e in df["evento"].dropna().unique() if e != ""])
            filtro_ev = st.selectbox("🎧 Filtrar por Evento:", lista_ev)
        with col_f2:
            busqueda = st.text_input("🔍 Buscar por Nombre, RUT o Productor:")

        df_mostrar = df.copy()
        if filtro_ev != "Todos":
            df_mostrar = df_mostrar[df_mostrar["evento"] == filtro_ev]
        if busqueda:
            df_mostrar = df_mostrar[
                df_mostrar["nombre"].str.contains(busqueda, case=False, na=False) |
                df_mostrar["rut"].str.contains(busqueda, case=False, na=False) |
                df_mostrar["creado_por"].str.contains(busqueda, case=False, na=False)
            ]

        col1, col2, col3 = st.columns(3)
        col1.metric("EMITIDAS", len(df_mostrar))
        col2.metric("ADENTRO", len(df_mostrar[df_mostrar["estado"] == "USADA"]))
        col3.metric("POR LLEGAR", len(df_mostrar[df_mostrar["estado"] == "DISPONIBLE"]))

        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("**💾 BACKUP DE SEGURIDAD** *(Descarga siempre tu lista antes de abrir puertas)*")
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 DESCARGAR BASE DE DATOS (CSV)",
            data=csv,
            file_name=f"kalma_respaldo_{ahora_chile().strftime('%Y%m%d_%H%M')}.csv",
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
                    evento_csv = row["evento"] if "evento" in df_nuevo.columns else ""
                    cad_csv = row["caducidad"] if "caducidad" in df_nuevo.columns else ""
                    c.execute(
                        "INSERT OR REPLACE INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (row["codigo"], row["nombre"], row["rut"], row["tipo"], row["estado"], row["fecha_creacion"], row["fecha_ingreso"], creador_csv, evento_csv, cad_csv)
                    )
                    if evento_csv:
                        c.execute("INSERT OR IGNORE INTO eventos VALUES (?, ?)", (evento_csv, cad_csv))
                conn.commit()
                st.success("Base de datos restaurada correctamente.")
                st.rerun()

        st.divider()
        if st.button("🔒 BLOQUEAR ZONA DE PRODUCCIÓN", use_container_width=True):
            st.session_state.admin_usuario = None
            st.rerun()
