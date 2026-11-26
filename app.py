import streamlit as st
import sqlite3
import uuid
import os
import re
import smtplib
from email.message import EmailMessage
import pandas as pd
import qrcode
import zxingcpp
from PIL import Image, ImageDraw, ImageFont
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

def limpiar_nombre_archivo(texto):
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "_", texto.strip())
    return limpio.strip("_") or "evento"

def correo_valido(correo):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$", correo.strip()))

def generar_excel_bytes(df_data):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_data.to_excel(writer, index=False, sheet_name="Entradas")
    return buf.getvalue()

def cargar_fuente(tamano, bold=False):
    candidatos = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for ruta in candidatos:
        if os.path.exists(ruta):
            try:
                return ImageFont.truetype(ruta, tamano)
            except Exception:
                pass
    return ImageFont.load_default()

def generar_tarjeta_qr_bytes(codigo, nombre, rut, tipo, evento, caducidad):
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(codigo)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#09090b", back_color="#ffffff").convert("RGB")
    qr_size = 260
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.NEAREST)

    ancho, alto = 560, 760
    tarjeta = Image.new("RGB", (ancho, alto), "#0d0a14")
    draw = ImageDraw.Draw(tarjeta)

    draw.rounded_rectangle([14, 14, ancho - 14, alto - 14], radius=24, outline="#9333ea", width=3)
    draw.rounded_rectangle([22, 22, ancho - 22, 120], radius=18, fill="#1b102b", outline="#22d3ee", width=2)

    f_titulo = cargar_fuente(28, bold=True)
    f_sub = cargar_fuente(13, bold=True)
    f_evento = cargar_fuente(20, bold=True)
    f_dato = cargar_fuente(15, bold=False)
    f_dato_bold = cargar_fuente(15, bold=True)
    f_cod = cargar_fuente(14, bold=True)

    logo_colocado = False
    if os.path.exists("logo.png"):
        try:
            logo_img = Image.open("logo.png").convert("RGBA")
            max_w, max_h = 340, 76
            logo_img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            lx = (ancho - logo_img.width) // 2
            ly = 22 + (98 - logo_img.height) // 2
            tarjeta.paste(logo_img, (lx, ly), logo_img)
            logo_colocado = True
        except Exception:
            logo_colocado = False

    if not logo_colocado:
        draw.text((ancho // 2, 54), "COLECTIVO KALMA", fill="#ffffff", font=f_titulo, anchor="mm")
        draw.text((ancho // 2, 88), "ELECTRONIC MUSIC // OFFICIAL E-TICKET", fill="#22d3ee", font=f_sub, anchor="mm")

    draw.text((ancho // 2, 152), evento.upper(), fill="#22d3ee", font=f_evento, anchor="mm")
    draw.text((ancho // 2, 182), f"PASE: {tipo.upper()}", fill="#d8b4fe", font=f_sub, anchor="mm")

    qr_box_x0 = (ancho - (qr_size + 28)) // 2
    qr_box_y0 = 205
    qr_box_x1 = qr_box_x0 + qr_size + 28
    qr_box_y1 = qr_box_y0 + qr_size + 28
    draw.rounded_rectangle([qr_box_x0, qr_box_y0, qr_box_x1, qr_box_y1], radius=18, fill="#ffffff", outline="#22d3ee", width=3)
    tarjeta.paste(qr_img, (qr_box_x0 + 14, qr_box_y0 + 14))

    draw.text((ancho // 2, qr_box_y1 + 24), f"ID: {codigo}", fill="#22d3ee", font=f_cod, anchor="mm")

    info_y = qr_box_y1 + 54
    draw.rounded_rectangle([42, info_y, ancho - 42, alto - 42], radius=16, fill="#14121d", outline="#3f3f46", width=1)

    lineas = [
        ("ASISTENTE:", nombre),
        ("RUT:", rut),
        ("VÁLIDO HASTA:", caducidad or "Sin límite"),
    ]
    y_actual = info_y + 22
    for etiqueta, valor in lineas:
        draw.text((64, y_actual), etiqueta, fill="#a1a1aa", font=f_dato_bold)
        draw.text((205, y_actual), str(valor)[:32], fill="#ffffff", font=f_dato)
        y_actual += 34

    draw.text((ancho // 2, alto - 62), "Presenta este E-Ticket y tu carnet en puerta", fill="#22d3ee", font=f_sub, anchor="mm")

    buf = BytesIO()
    tarjeta.save(buf, format="PNG")
    return buf.getvalue()

def enviar_qr_por_correo(destinatario, nombre, rut, tipo, evento, caducidad, codigo, ticket_bytes):
    remitente = st.secrets.get("SMTP_EMAIL", "").strip()
    clave_app = st.secrets.get("SMTP_APP_PASSWORD", "").strip()
    if not remitente or not clave_app:
        return False, "Falta configurar SMTP_EMAIL y SMTP_APP_PASSWORD en Streamlit Secrets."

    msg = EmailMessage()
    msg["Subject"] = f"¡Bienvenido a {evento}! Tu E-Ticket QR — Colectivo Kalma"
    msg["From"] = remitente
    msg["To"] = destinatario

    texto_plano = (
        f"¡Bienvenido/a {nombre} a Colectivo Kalma!\n\n"
        f"Tu entrada para {evento} está lista.\n"
        f"• Nombre: {nombre}\n"
        f"• RUT: {rut}\n"
        f"• Tipo de pase: {tipo}\n"
        f"• Código: {codigo}\n"
        f"• Válido hasta: {caducidad}\n\n"
        f"Presenta el E-Ticket adjunto y tu carnet en el acceso."
    )
    msg.set_content(texto_plano)

    logo_html = ""
    logo_bytes = None
    if os.path.exists("logo.png"):
        try:
            with open("logo.png", "rb") as f_logo:
                logo_bytes = f_logo.read()
            logo_html = '<img src="cid:logo_kalma" alt="Colectivo Kalma" style="max-width:220px; height:auto; display:block; margin:0 auto 10px auto;" />'
        except Exception:
            logo_bytes = None

    if not logo_html:
        logo_html = '<div style="font-size:24px; font-weight:800; letter-spacing:3px; color:#ffffff; margin-bottom:6px;">COLECTIVO KALMA</div>'

    html_cuerpo = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0; padding:24px; background-color:#09090b; font-family:Arial, Helvetica, sans-serif; color:#f4f4f5;">
      <div style="max-width:560px; margin:0 auto; background:linear-gradient(160deg,#181026 0%,#10131f 100%); border:1px solid #9333ea; border-radius:16px; overflow:hidden; box-shadow:0 0 25px rgba(147,51,234,0.25);">
        <div style="padding:24px 24px 18px 24px; text-align:center; background-color:#130c1f; border-bottom:1px solid #2e1065;">
          {logo_html}
          <div style="font-size:11px; letter-spacing:3px; color:#22d3ee; text-transform:uppercase; font-weight:bold;">
            ELECTRONIC MUSIC // OFFICIAL E-TICKET
          </div>
        </div>

        <div style="padding:24px;">
          <h2 style="margin:0 0 8px 0; font-size:22px; color:#ffffff;">¡Hola, {nombre}! 👋</h2>
          <p style="margin:0 0 18px 0; font-size:14px; line-height:1.6; color:#d4d4d8;">
            ¡Qué alegría tenerte con nosotros! Te damos la bienvenida a <strong style="color:#22d3ee;">{evento}</strong>.
            Aquí tienes tu pase QR oficial para ingresar al evento.
          </p>

          <div style="background-color:#0d0e16; border:1px solid #3f3f46; border-radius:12px; padding:14px 16px; margin-bottom:20px; font-size:13px; line-height:1.7;">
            <div><strong style="color:#a855f7;">Evento:</strong> <span style="color:#ffffff;">{evento}</span></div>
            <div><strong style="color:#a855f7;">Asistente:</strong> <span style="color:#ffffff;">{nombre}</span></div>
            <div><strong style="color:#a855f7;">RUT:</strong> <span style="color:#ffffff;">{rut}</span></div>
            <div><strong style="color:#a855f7;">Tipo de pase:</strong> <span style="color:#22d3ee; font-weight:bold;">{tipo}</span></div>
            <div><strong style="color:#a855f7;">Válido hasta:</strong> <span style="color:#ffffff;">{caducidad}</span></div>
            <div><strong style="color:#a855f7;">Código ID:</strong> <span style="color:#e4e4e7;">{codigo}</span></div>
          </div>

          <div style="text-align:center; background-color:#14121d; border:1px solid #22d3ee; border-radius:14px; padding:16px;">
            <div style="font-size:12px; letter-spacing:2px; color:#22d3ee; font-weight:bold; margin-bottom:12px;">
              TU PASE QR DE ACCESO
            </div>
            <img src="cid:qr_ticket" alt="E-Ticket QR" style="max-width:100%; width:320px; height:auto; border-radius:10px; display:block; margin:0 auto;" />
          </div>

          <p style="margin:18px 0 0 0; font-size:12px; line-height:1.5; color:#a1a1aa; text-align:center;">
            Recuerda llevar tu <strong style="color:#ffffff;">carnet de identidad</strong> y tener el brillo de tu pantalla alto al llegar a la puerta.
            Este código es personal e intransferible y caduca automáticamente en la fecha y hora indicadas.
          </p>
        </div>

        <div style="padding:14px 24px; background-color:#0b0b10; border-top:1px solid #27272a; text-align:center; font-size:11px; color:#71717a;">
          Colectivo Kalma • Control de Acceso Oficial
        </div>
      </div>
    </body>
    </html>
    """
    msg.add_alternative(html_cuerpo, subtype="html")

    if logo_bytes:
        msg.get_payload()[1].add_related(logo_bytes, maintype="image", subtype="png", cid="<logo_kalma>")

    msg.get_payload()[1].add_related(ticket_bytes, maintype="image", subtype="png", cid="<qr_ticket>")
    msg.add_attachment(
        ticket_bytes,
        maintype="image",
        subtype="png",
        filename=f"ETICKET_KALMA_{limpiar_nombre_archivo(evento)}_{codigo}.png"
    )

    ultimo_error = None
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(remitente, clave_app)
            smtp.send_message(msg)
        return True, f"E-Ticket enviado automáticamente a {destinatario}."
    except Exception as exc:
        ultimo_error = exc

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(remitente, clave_app)
            smtp.send_message(msg)
        return True, f"E-Ticket enviado automáticamente a {destinatario}."
    except Exception as exc2:
        return False, f"No se pudo enviar el correo ({exc2 or ultimo_error})."

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
    [data-testid="stFileUploader"] section {
        background-color: #121217 !important;
        border: 1px dashed #9333ea !important;
        border-radius: 10px !important;
        color: #ffffff !important;
    }
    [data-testid="stFileUploader"] section span,
    [data-testid="stFileUploader"] section small,
    [data-testid="stFileUploader"] section div {
        color: #e4e4e7 !important;
    }
    [data-testid="stFileUploader"] section button {
        background-color: #2e1065 !important;
        color: #ffffff !important;
        border: 1px solid #9333ea !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
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
    .backup-box {
        background-color: #121217;
        border: 1px solid #3f3f46;
        border-radius: 10px;
        padding: 16px;
        margin-top: 10px;
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
if "borrador_qr" not in st.session_state:
    st.session_state.borrador_qr = None

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
            correo TEXT,
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
    if "correo" not in columnas:
        c.execute("ALTER TABLE entradas ADD COLUMN correo TEXT DEFAULT ''")
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
        st.session_state.borrador_qr = None
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
            "SELECT codigo, nombre, rut, correo, tipo, estado, fecha_ingreso, creado_por, evento, caducidad FROM entradas WHERE codigo = ?",
            (codigo_leido,)
        )
        entrada = c.fetchone()

        if not entrada:
            st.error(f"❌ ACCESO DENEGADO: El código `{codigo_leido}` no existe.")
        else:
            cod, nombre, rut, correo, tipo, estado, fecha_ing, creado_por, ev_qr, cad_qr = entrada

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
                    <p style="margin:0; font-size:14px;"><b>✉️ CORREO:</b> {correo if correo else 'No registrado'} &nbsp;|&nbsp; <b>🎟️ PASE:</b> {tipo}</p>
                    <p style="margin:4px 0 0 0; font-size:14px;"><b>🎧 EVENTO:</b> {ev_qr if ev_qr else 'General'} &nbsp;|&nbsp; <b>🔑 ID:</b> {cod}</p>
                    <p style="margin:4px 0 0 0; font-size:13px; color:#f4f4f5 !important;"><b>⌛ Válido hasta:</b> {cad_qr if cad_qr else 'Sin límite'}</p>
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

            with st.form("form_crear"):
                nombre = st.text_input("Nombre Completo")
                rut = st.text_input("RUT / Carnet (ej: 12.345.678-9)")
                correo = st.text_input("Correo Electrónico (ej: nombre@correo.com)")
                tipo = st.selectbox("Tipo de Pase", ["Early Bird", "Preventa 1", "Preventa 2", "General", "VIP / Backstage", "Lista / Cortesía"])
                crear = st.form_submit_button("⚡ GENERAR E-TICKET QR", type="primary", use_container_width=True)

            if crear:
                if not nombre.strip() or not rut.strip():
                    st.error("Debes completar el Nombre y el RUT.")
                elif correo.strip() and not correo_valido(correo.strip()):
                    st.error(f"El correo `{correo.strip()}` no tiene un formato válido. Revísalo antes de continuar.")
                else:
                    caducidad_final = f"{fecha_qr.strftime('%Y-%m-%d')} {hora_qr.strftime('%H:%M')}"
                    st.session_state.borrador_qr = {
                        "nombre": nombre.strip(),
                        "rut": rut.strip(),
                        "correo": correo.strip(),
                        "tipo": tipo,
                        "evento": evento_elegido,
                        "caducidad": caducidad_final,
                    }
                    st.rerun()

            if st.session_state.borrador_qr is not None:
                b = st.session_state.borrador_qr
                st.warning("❓ **¿Estás seguro de los datos?** Al confirmar se generará el QR y, si ingresaste correo, se enviará automáticamente.")
                st.markdown(
                    f"**• Evento:** {b['evento']}  \n"
                    f"**• Nombre:** {b['nombre']}  \n"
                    f"**• RUT:** {b['rut']}  \n"
                    f"**• Correo:** {b['correo'] or 'Sin correo'}  \n"
                    f"**• Tipo de Pase:** {b['tipo']}  \n"
                    f"**• Válido hasta:** {b['caducidad']}"
                )
                col_ok, col_cancel = st.columns(2)
                with col_ok:
                    if st.button("✅ SÍ, GENERAR Y ENVIAR", type="primary", use_container_width=True):
                        codigo_unico = f"KLM-{uuid.uuid4().hex[:8].upper()}"
                        ahora_str = ahora_chile().strftime("%Y-%m-%d %H:%M:%S")
                        creador = st.session_state.admin_usuario
                        c = conn.cursor()
                        c.execute(
                            "INSERT INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (codigo_unico, b["nombre"], b["rut"], b["correo"], b["tipo"], "DISPONIBLE", ahora_str, "", creador, b["evento"], b["caducidad"])
                        )
                        conn.commit()
                        ticket_bytes = generar_tarjeta_qr_bytes(codigo_unico, b["nombre"], b["rut"], b["tipo"], b["evento"], b["caducidad"])
                        st.session_state["ultimo_qr"] = (codigo_unico, b["nombre"], b["rut"], b["correo"], b["tipo"], creador, b["evento"], b["caducidad"])
                        st.session_state.borrador_qr = None

                        msg_envio = ""
                        error_envio = ""
                        if b["correo"]:
                            ok_mail, detalle_mail = enviar_qr_por_correo(
                                b["correo"], b["nombre"], b["rut"], b["tipo"], b["evento"], b["caducidad"], codigo_unico, ticket_bytes
                            )
                            if ok_mail:
                                msg_envio = f" | {detalle_mail}"
                            else:
                                error_envio = detalle_mail

                        st.success(f"E-Ticket emitido para **{b['nombre']}** (`{codigo_unico}`){msg_envio}")
                        if error_envio:
                            st.error(error_envio)
                        st.rerun()
                with col_cancel:
                    if st.button("✏️ CORREGIR DATOS", use_container_width=True):
                        st.session_state.borrador_qr = None
                        st.rerun()

        ultimo = st.session_state.get("ultimo_qr")
        if isinstance(ultimo, (list, tuple)) and len(ultimo) == 8:
            cod, nom, rt, cor, tp, cr, ev, cad = ultimo
            ticket_bytes = generar_tarjeta_qr_bytes(cod, nom, rt, tp, ev, cad)
            st.divider()
            st.write(f"**Último E-Ticket:** {nom} ({rt}) — {cor or 'Sin correo'} | **{ev}** ({tp}) | *Válido hasta: {cad}*")
            st.image(ticket_bytes, width=320)
            st.download_button(
                label="📥 DESCARGAR E-TICKET",
                data=ticket_bytes,
                file_name=f"ETICKET_KALMA_{limpiar_nombre_archivo(ev)}_{limpiar_nombre_archivo(nom)}_{cod}.png",
                mime="image/png",
                use_container_width=True
            )
        elif "ultimo_qr" in st.session_state:
            del st.session_state["ultimo_qr"]

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
            busqueda = st.text_input("🔍 Buscar por Nombre, RUT, Correo o Productor:")

        df_mostrar = df.copy()
        if filtro_ev != "Todos":
            df_mostrar = df_mostrar[df_mostrar["evento"] == filtro_ev]
        if busqueda:
            df_mostrar = df_mostrar[
                df_mostrar["nombre"].str.contains(busqueda, case=False, na=False) |
                df_mostrar["rut"].str.contains(busqueda, case=False, na=False) |
                df_mostrar["correo"].str.contains(busqueda, case=False, na=False) |
                df_mostrar["creado_por"].str.contains(busqueda, case=False, na=False)
            ]

        col1, col2, col3 = st.columns(3)
        col1.metric("EMITIDAS", len(df_mostrar))
        col2.metric("ADENTRO", len(df_mostrar[df_mostrar["estado"] == "USADA"]))
        col3.metric("POR LLEGAR", len(df_mostrar[df_mostrar["estado"] == "DISPONIBLE"]))

        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

        st.divider()
        nombre_etiqueta = "todos_eventos" if filtro_ev == "Todos" else limpiar_nombre_archivo(filtro_ev)
        etiqueta_visible = "TODOS LOS EVENTOS" if filtro_ev == "Todos" else filtro_ev

        st.markdown("### 📊 HISTORIAL EXCEL Y RESPALDO")
        st.markdown('<div class="backup-box">', unsafe_allow_html=True)
        st.markdown(f"**1. Descargar Excel ({etiqueta_visible})**")
        excel_bytes = generar_excel_bytes(df_mostrar)
        st.download_button(
            f"📥 DESCARGAR EXCEL (.XLSX) — {etiqueta_visible}",
            data=excel_bytes,
            file_name=f"kalma_{nombre_etiqueta}_{ahora_chile().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        st.divider()
        st.markdown("**2. Restaurar registros desde Excel (.xlsx) o CSV**")
        archivo_subido = st.file_uploader("Selecciona un archivo de respaldo", type=["xlsx", "csv"], label_visibility="collapsed")
        if archivo_subido is not None:
            if st.button("📤 CARGAR ENTRADAS DEL ARCHIVO", type="primary", use_container_width=True):
                if archivo_subido.name.lower().endswith(".xlsx"):
                    df_nuevo = pd.read_excel(archivo_subido).fillna("")
                else:
                    df_nuevo = pd.read_csv(archivo_subido).fillna("")
                c = conn.cursor()
                for _, row in df_nuevo.iterrows():
                    correo_csv = row["correo"] if "correo" in df_nuevo.columns else ""
                    creador_csv = row["creado_por"] if "creado_por" in df_nuevo.columns else ""
                    evento_csv = row["evento"] if "evento" in df_nuevo.columns else ""
                    cad_csv = row["caducidad"] if "caducidad" in df_nuevo.columns else ""
                    c.execute(
                        "INSERT OR REPLACE INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (row["codigo"], row["nombre"], row["rut"], correo_csv, row["tipo"], row["estado"], row["fecha_creacion"], row["fecha_ingreso"], creador_csv, evento_csv, cad_csv)
                    )
                    if evento_csv:
                        c.execute("INSERT OR IGNORE INTO eventos VALUES (?, ?)", (evento_csv, cad_csv))
                conn.commit()
                st.success("Base de datos restaurada correctamente.")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        if st.button("🔒 BLOQUEAR ZONA DE PRODUCCIÓN", use_container_width=True):
            st.session_state.admin_usuario = None
            st.rerun()
