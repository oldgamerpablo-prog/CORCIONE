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

st.set_page_config(page_title="Colectivo Kalma - Accesos", page_icon="🎫", layout="wide")

EVENTOS_HEADERS = ["id_evento", "nombre", "fecha", "hora", "lugar", "capacidad", "creado_en"]
ENTRADAS_HEADERS = ["codigo", "evento", "nombre_asistente", "email", "tipo", "estado", "fecha_emision", "fecha_ingreso"]


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
    return client.open_by_key(st.secrets["SHEET_ID"].strip())


def obtener_hoja(sh, nombre_pestana, headers):
    try:
        ws = sh.worksheet(nombre_pestana)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=nombre_pestana, rows=1000, cols=len(headers))
    if not ws.row_values(1):
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
    msg.add_attachment(qr_bytes, maintype="image", subtype="png", filename=f"entrada_{codigo}.png")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(remitente, clave)
        smtp.send_message(msg)


st.title("COLECTIVO KALMA")
st.caption("Gestión de eventos, emisión de entradas QR y control de acceso en Google Sheets")

try:
    sh = conectar_google_sheets()
    ws_eventos = obtener_hoja(sh, "eventos", EVENTOS_HEADERS)
    ws_entradas = obtener_hoja(sh, "entradas", ENTRADAS_HEADERS)
except Exception as e:
    st.error("No se pudo conectar con Google Sheets. Verifica permisos de Editor y Secrets.")
    st.exception(e)
    st.stop()

df_eventos = leer_dataframe(ws_eventos, EVENTOS_HEADERS)
df_entradas = leer_dataframe(ws_entradas, ENTRADAS_HEADERS)

tab_emitir, tab_validar, tab_eventos, tab_db = st.tabs(["🎟️ Emitir Entrada", "✅ Validar Acceso", "📅 Eventos", "📊 Base de Datos"])

with tab_emitir:
    st.subheader("Generar y enviar entrada")
    if df_eventos.empty:
        st.info("Primero crea al menos un evento en la pestaña '📅 Eventos'.")
    else:
        opciones_eventos = df_eventos["nombre"].tolist()
        with st.form("form_emitir_entrada", clear_on_submit=True):
            evento_sel = st.selectbox("Evento", opciones_eventos)
            col1, col2 = st.columns(2)
            with col1:
                nombre_asistente = st.text_input("Nombre del asistente")
                email_asistente = st.text_input("Correo electrónico")
            with col2:
                tipo_entrada = st.selectbox("Tipo de entrada", ["General", "Preventa", "Cortesía", "Staff"])
                enviar_mail = st.checkbox("Enviar entrada con QR por correo", value=True)
            submitted = st.form_submit_button("Generar entrada")

        if submitted:
            if not nombre_asistente.strip():
                st.warning("Ingresa el nombre del asistente.")
            elif enviar_mail and not email_asistente.strip():
                st.warning("Ingresa un correo electrónico o desmarca el envío por correo.")
            else:
                codigo = f"KALMA-{uuid.uuid4().hex[:8].upper()}"
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                fila_evento = df_eventos[df_eventos["nombre"] == evento_sel].iloc[0]

                nueva_fila = [
                    codigo,
                    evento_sel,
                    nombre_asistente.strip(),
                    email_asistente.strip(),
                    tipo_entrada,
                    "PENDIENTE",
                    ahora,
                    "",
                ]
                ws_entradas.append_row(nueva_fila)
                qr_bytes = generar_qr_bytes(codigo)

                st.success(f"Entrada registrada en Google Sheets con código: **{codigo}**")
                st.image(qr_bytes, caption=f"Código: {codigo}", width=220)
                st.download_button("Descargar QR en PNG", data=qr_bytes, file_name=f"{codigo}.png", mime="image/png")

                if enviar_mail and email_asistente.strip():
                    try:
                        enviar_correo_entrada(
                            destinatario=email_asistente.strip(),
                            nombre=nombre_asistente.strip(),
                            evento=evento_sel,
                            fecha_ev=f"{fila_evento['fecha']} {fila_evento['hora']}",
                            lugar_ev=fila_evento["lugar"],
                            codigo=codigo,
                            qr_bytes=qr_bytes,
                        )
                        st.info(f"Correo enviado correctamente a {email_asistente.strip()}.")
                    except Exception as mail_err:
                        st.warning(f"La entrada quedó guardada en Sheets, pero falló el envío del correo: {mail_err}")

with tab_validar:
    st.subheader("Control de puerta (Check-in)")
    codigo_buscar = st.text_input("Ingresa o escanea el código de la entrada (ej. KALMA-1A2B3C4D)").strip().upper()

    if codigo_buscar:
        coincidencias = df_entradas[df_entradas["codigo"].str.upper() == codigo_buscar]
        if coincidencias.empty:
            st.error("❌ Código no encontrado en la base de datos.")
        else:
            reg = coincidencias.iloc[0]
            st.write(f"**Asistente:** {reg['nombre_asistente']}")
            st.write(f"**Evento:** {reg['evento']} | **Tipo:** {reg['tipo']}")
            st.write(f"**Estado actual:** `{reg['estado']}`")

            if reg["estado"] == "USADA":
                st.warning(f"⚠️ Esta entrada ya fue utilizada el {reg['fecha_ingreso']}.")
            else:
                if st.button("✅ Confirmar ingreso ahora", type="primary"):
                    celda = ws_entradas.find(reg["codigo"], in_column=1)
                    hora_ingreso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ws_entradas.update_cell(celda.row, 6, "USADA")
                    ws_entradas.update_cell(celda.row, 8, hora_ingreso)
                    st.success(f"Ingreso registrado a las {hora_ingreso}.")
                    st.rerun()

with tab_eventos:
    st.subheader("Crear nuevo evento")
    with st.form("form_crear_evento", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre_ev = st.text_input("Nombre del evento")
            fecha_ev = st.date_input("Fecha")
            hora_ev = st.time_input("Hora")
        with c2:
            lugar_ev = st.text_input("Lugar / Dirección")
            capacidad_ev = st.number_input("Capacidad", min_value=1, value=100, step=10)
        crear_ev = st.form_submit_button("Guardar evento")

    if crear_ev:
        if not nombre_ev.strip():
            st.warning("Escribe un nombre para el evento.")
        else:
            id_ev = f"EV-{uuid.uuid4().hex[:6].upper()}"
            creado_en = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ws_eventos.append_row([
                id_ev,
                nombre_ev.strip(),
                str(fecha_ev),
                hora_ev.strftime("%H:%M"),
                lugar_ev.strip(),
                str(capacidad_ev),
                creado_en,
            ])
            st.success(f"Evento '{nombre_ev.strip()}' guardado en Google Sheets.")
            st.rerun()

    st.divider()
    st.subheader("Eventos registrados")
    st.dataframe(df_eventos, use_container_width=True)

with tab_db:
    st.subheader("Resumen de entradas en tiempo real")
    total = len(df_entradas)
    usadas = int((df_entradas["estado"] == "USADA").sum()) if not df_entradas.empty else 0
    pendientes = total - usadas

    m1, m2, m3 = st.columns(3)
    m1.metric("Total emitidas", total)
    m2.metric("Ingresadas", usadas)
    m3.metric("Pendientes", pendientes)

    if not df_entradas.empty:
        eventos_filtro = ["Todos"] + sorted(df_entradas["evento"].unique().tolist())
        filtro = st.selectbox("Filtrar por evento", eventos_filtro)
        df_vista = df_entradas if filtro == "Todos" else df_entradas[df_entradas["evento"] == filtro]
        st.dataframe(df_vista, use_container_width=True)

        csv_bytes = df_vista.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar listado CSV", data=csv_bytes, file_name="entradas_colectivo_kalma.csv", mime="text/csv")
    else:
        st.info("Aún no hay entradas registradas en la hoja.")
