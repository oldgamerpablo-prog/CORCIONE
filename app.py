import io
import uuid
import smtplib
from datetime import datetime
from email.message import EmailMessage

import gspread
import pandas as pd
import qrcode
import streamlit as st
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Colectivo Kalma - Accesos",
    page_icon="🎫",
    layout="wide",
)

EVENTOS_HEADERS = [
    "id_evento",
    "nombre",
    "fecha",
    "hora",
    "lugar",
    "capacidad",
    "creado_en",
]

ENTRADAS_HEADERS = [
    "codigo",
    "evento",
    "nombre_asistente",
    "email",
    "tipo",
    "estado",
    "fecha_emision",
    "fecha_ingreso",
]


@st.cache_resource
def conectar_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["SHEET_ID"])


def obtener_hoja(sh, nombre_pestana, headers):
    try:
        ws = sh.worksheet(nombre_pestana)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=nombre_pestana, rows=1000, cols=len(headers))
    primera_fila = ws.row_values(1)
    if not primera_fila:
        ws.append_row(headers)
    return ws


def leer_dataframe(ws, headers):
    valores = ws.get_all_values()
    if len(valores) <= 1:
        return pd.DataFrame(columns=headers)
    return pd.DataFrame(valores[1:], columns=valores[0])


def generar_qr_bytes(texto_qr):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(texto_qr)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def enviar_correo_entrada(destinatario, nombre, evento, fecha_ev, lugar_ev, codigo, qr_bytes):
    remitente = st.secrets["SMTP_EMAIL"]
    clave = st.secrets["SMTP_APP_PASSWORD"]

    msg = EmailMessage()
    msg["Subject"] = f"Tu entrada para {evento} - Colectivo Kalma"
    msg["From"] = remitente
    msg["To"] = destinatario

    cuerpo = (
        f"Hola {nombre},\n\n"
        f"Aquí tienes tu entrada confirmada para {evento}.\n"
        f"Fecha: {fecha_ev}\n"
        f"Lugar: {lugar_ev}\n"
        f"Código de acceso: {codigo}\n\n"
        "Presenta el código QR adjunto en la entrada del evento.\n\n"
        "Nos vemos,\nColectivo Kalma"
    )
    msg.set_content(cuerpo)
    msg.add_attachment(
        qr_bytes,
        maintype="image",
        subtype="png",
        filename=f"entrada_{codigo}.png",
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(remitente, clave)
        smtp.send_message(msg)


# --- Encabezado ---
st.title("COLECTIVO KALMA")
st.caption("Gestión de eventos, emisión de entradas QR y control de acceso en Google Sheets")

try:
    sh = conectar_google_sheets()
    ws_eventos = obtener_hoja(sh, "eventos", EVENTOS_HEADERS)
    ws_entradas = obtener_hoja(sh, "entradas", ENTRADAS_HEADERS)
except Exception as e:
    st.error(
        "No se pudo conectar con Google Sheets. Verifica que la hoja esté compartida "
        "como Editor con la cuenta de servicio y que los Secrets estén guardados."
    )
    st.exception(e)
    st.stop()

df_eventos = leer_dataframe(ws_eventos, EVENTOS_HEADERS)
df_entradas = leer_dataframe(ws_entradas, ENTRADAS_HEADERS)

tab_emitir, tab_validar, tab_eventos, tab_db
