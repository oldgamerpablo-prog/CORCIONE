import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import uuid
import os
import re
import time as pytime
import smtplib
from email.message import EmailMessage
import pandas as pd
import qrcode
import zxingcpp
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

st.set_page_config(page_title="COLECTIVO KALMA // ACCESS", page_icon="⚡", layout="centered")

USUARIOS_PRODUCCION_CONOCIDOS = {"Javi.martinez", "Eric.brito", "Piero.corci"}

# --- HORA LOCAL CHILE ---
def ahora_chile():
    try:
        return datetime.now(ZoneInfo("America/Santiago")).replace(tzinfo=None)
    except Exception:
        return datetime.now()

def limpiar_nombre_archivo(texto):
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "_", str(texto).strip())
    return limpio.strip("_") or "evento"

def correo_valido(correo):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$", str(correo).strip()))

def parece_fecha_hora(valor):
    texto = str(valor or "").strip()
    if not texto:
        return False
    return bool(
        re.match(r"^\d{4}-\d{2}-\d{2}(\s+\d{1,2}:\d{2}(:\d{2})?)?$", texto)
        or re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}(\s+\d{1,2}:\d{2}(:\d{2})?)?$", texto)
    )

def parsear_fecha_excel(valor, fecha_defecto):
    if valor is None or str(valor).strip() == "" or pd.isna(valor):
        return fecha_defecto
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    dt_parsed = pd.to_datetime(texto, errors="coerce", dayfirst=True)
    if pd.notna(dt_parsed):
        return dt_parsed.date()
    return fecha_defecto

def parsear_hora_excel(valor, hora_defecto):
    if valor is None or str(valor).strip() == "" or pd.isna(valor):
        return hora_defecto
    if isinstance(valor, datetime):
        return valor.time().replace(second=0, microsecond=0)
    if isinstance(valor, time):
        return valor.replace(second=0, microsecond=0)
    texto = str(valor).strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(texto, fmt).time().replace(second=0, microsecond=0)
        except ValueError:
            continue
    dt_parsed = pd.to_datetime(texto, errors="coerce")
    if pd.notna(dt_parsed):
        return dt_parsed.time().replace(second=0, microsecond=0)
    return hora_defecto

def normalizar_dataframe_por_encabezado(df_in):
    alias_encabezados = {
        "codigo": "codigo",
        "id": "codigo",
        "nombre": "nombre",
        "nombre_completo": "nombre",
        "asistente": "nombre",
        "rut": "rut",
        "carnet": "rut",
        "dni": "rut",
        "tipo": "tipo",
        "tipo_de_pase": "tipo",
        "tipo_pase": "tipo",
        "pase": "tipo",
        "estado": "estado",
        "fecha_creacion": "fecha_creacion",
        "creacion": "fecha_creacion",
        "fecha_ingreso": "fecha_ingreso",
        "ingreso": "fecha_ingreso",
        "creado_por": "creado_por",
        "productor": "creado_por",
        "evento": "evento",
        "nombre_del_evento": "evento",
        "nombre_evento": "evento",
        "caducidad": "caducidad",
        "fecha_caducidad": "caducidad",
        "correo": "correo",
        "email": "correo",
        "correo_electronico": "correo",
        "nota_renominacion": "nota_renominacion",
        "renominacion": "nota_renominacion",
    }
    renombres = {}
    for col in df_in.columns:
        clave = re.sub(r"[^a-z0-9]+", "_", str(col).strip().lower()).strip("_")
        if clave in alias_encabezados:
            renombres[col] = alias_encabezados[clave]
    df_mapeado = df_in.rename(columns=renombres).copy()

    columnas_esperadas = [
        "codigo", "nombre", "rut", "tipo", "estado",
        "fecha_creacion", "fecha_ingreso", "creado_por",
        "evento", "caducidad", "correo", "nota_renominacion"
    ]
    for col_esp in columnas_esperadas:
        if col_esp not in df_mapeado.columns:
            df_mapeado[col_esp] = ""

    return df_mapeado[columnas_esperadas].fillna("")

def generar_excel_bytes(df_data):
    df_ordenado = normalizar_dataframe_por_encabezado(df_data)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_ordenado.to_excel(writer, index=False, sheet_name="Entradas")
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

    draw.text((ancho // 2, 152), str(evento).upper(), fill="#22d3ee", font=f_evento, anchor="mm")
    draw.text((ancho // 2, 182), f"PASE: {str(tipo).upper()}", fill="#d8b4fe", font=f_sub, anchor="mm")

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

def forzar_camara_trasera():
    components.html(
        """
        <script>
        (function() {
            try {
                const targetWin = window.parent || window;
                const md = targetWin.navigator && targetWin.navigator.mediaDevices;
                if (!md || typeof md.getUserMedia !== "function" || md.__kalmaBackCamPatched) {
                    return;
                }
                const origGetUserMedia = md.getUserMedia.bind(md);
                md.getUserMedia = function(constraints) {
                    if (constraints && constraints.video) {
                        const baseVideo = typeof constraints.video === "object" ? { ...constraints.video } : {};
                        delete baseVideo.deviceId;
                        baseVideo.facingMode = { ideal: "environment" };
                        const nextConstraints = { ...constraints, video: baseVideo };
                        return origGetUserMedia(nextConstraints).catch(function() {
                            return origGetUserMedia(constraints);
                        });
                    }
                    return origGetUserMedia(constraints);
                };
                md.__kalmaBackCamPatched = true;
            } catch (e) {}
        })();
        </script>
        """,
        height=0,
    )

def enviar_qr_por_correo(destinatario, nombre, rut, tipo, evento, caducidad, codigo, ticket_bytes):
    remitente = st.secrets.get("SMTP_EMAIL", "").strip()
    clave_app = st.secrets.get("SMTP_APP_PASSWORD", "").strip()
    if not remitente or not clave_app:
        return False, "Falta configurar SMTP_EMAIL y SMTP_APP_PASSWORD en Streamlit Secrets."

    destino_individual = str(destinatario).strip()
    if not destino_individual:
        return False, "Correo de destino vacío."

    msg = EmailMessage()
    msg["Subject"] = f"¡Bienvenido a {evento}! Tu E-Ticket QR — Colectivo Kalma"
    msg["From"] = remitente
    msg["To"] = destino_individual

    texto_plano = (
        f"¡Bienvenido/a {nombre} a Colectivo Kalma!\n\n"
        f"Tu entrada para {evento} está lista.\n"
        f"• Nombre: {nombre}\n"
        f"• RUT: {rut}\n"
        f"• Tipo de pase: {tipo}\n"
        f"• Código: {codigo}\n"
        f"• Válido hasta: {caducidad}\n\n"
        f"Presenta el E-Ticket adjunto y tu carnet en el acceso.\n\n"
        f"RENOMINACIÓN (CESIÓN O REVENTA):\n"
        f"Si no podrás asistir y transfieres o revendes tu entrada, NO reenvíes el QR sin avisar. "
        f"Escríbenos indicando el código del ticket ({codigo}), nombre, RUT y correo del nuevo asistente, "
        f"junto con el motivo (cesión o reventa). El QR seguirá asociado al titular registrado en el sistema "
        f"hasta que producción actualice los datos, y en puerta se pedirá carnet acorde al registro vigente."
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

          <div style="margin-top:18px; background-color:#14111f; border:1px solid #7e22ce; border-radius:12px; padding:14px 16px; font-size:12px; line-height:1.6; color:#e4e4e7;">
            <div style="color:#22d3ee; font-weight:bold; letter-spacing:1px; margin-bottom:6px; text-transform:uppercase;">
              🔄 Renominación (Cesión o Reventa)
            </div>
            <p style="margin:0 0 6px 0;">
              Si no podrás asistir y transfieres o revendes tu entrada, <strong>no reenvíes el QR sin avisar</strong>.
              Escríbenos indicando el código del ticket (<strong>{codigo}</strong>), <strong>nombre</strong>, <strong>RUT</strong> y <strong>correo</strong> del nuevo asistente,
              junto con el motivo (<strong>cesión</strong> o <strong>reventa</strong>).
            </p>
            <p style="margin:0; color:#d4d4d8;">
              El QR seguirá asociado al titular registrado en el sistema hasta que producción actualice los datos, y en el acceso se pedirá carnet acorde al registro vigente.
            </p>
          </div>

          <p style="margin:14px 0 0 0; font-size:12px; line-height:1.5; color:#a1a1aa; text-align:center;">
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
        return True, f"E-Ticket enviado individualmente a {destino_individual}."
    except Exception as exc:
        ultimo_error = exc

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(remitente, clave_app)
            smtp.send_message(msg)
        return True, f"E-Ticket enviado individualmente a {destino_individual}."
    except Exception as exc2:
        return False, f"No se pudo enviar a {destino_individual} ({exc2 or ultimo_error})."

def normalizar_excel_masivo(archivo, evento_defecto, fecha_defecto, hora_defecto):
    if archivo.name.lower().endswith(".xlsx"):
        df_raw = pd.read_excel(archivo)
    else:
        df_raw = pd.read_csv(archivo)

    mapa_cols = {}
    for col in df_raw.columns:
        clave = re.sub(r"[^a-z0-9]+", "_", str(col).strip().lower()).strip("_")
        if clave in {"nombre", "nombre_completo", "asistente", "name"}:
            mapa_cols[col] = "nombre"
        elif clave in {"rut", "carnet", "dni", "run"}:
            mapa_cols[col] = "rut"
        elif clave in {"correo", "email", "e_mail", "mail", "correo_electronico"}:
            mapa_cols[col] = "correo"
        elif clave in {"tipo", "tipo_de_pase", "tipo_pase", "pase", "entrada", "ticket"}:
            mapa_cols[col] = "tipo"
        elif clave in {"nombre_del_evento", "nombre_evento", "evento", "fiesta"}:
            mapa_cols[col] = "evento"
        elif clave in {"fecha_caducidad", "fecha_de_caducidad", "fecha_limite", "fecha", "caducidad_fecha"}:
            mapa_cols[col] = "fecha_caducidad"
        elif clave in {"hora_limite", "hora_de_caducidad", "hora_caducidad", "hora", "limite_hora"}:
            mapa_cols[col] = "hora_limite"

    df_norm = df_raw.rename(columns=mapa_cols)
    for req in ["nombre", "rut", "correo"]:
        if req not in df_norm.columns:
            return None, f"Falta la columna obligatoria `{req}` en el archivo."
    if "tipo" not in df_norm.columns:
        df_norm["tipo"] = "General"
    if "evento" not in df_norm.columns:
        df_norm["evento"] = evento_defecto
    if "fecha_caducidad" not in df_norm.columns:
        df_norm["fecha_caducidad"] = fecha_defecto
    if "hora_limite" not in df_norm.columns:
        df_norm["hora_limite"] = hora_defecto

    registros = []
    advertencias = []
    for idx, row in df_norm.iterrows():
        val_nom = "" if pd.isna(row["nombre"]) else str(row["nombre"]).strip()
        val_rut = "" if pd.isna(row["rut"]) else str(row["rut"]).strip()
        val_cor = "" if pd.isna(row["correo"]) else str(row["correo"]).strip()
        val_tp = "" if pd.isna(row["tipo"]) else str(row["tipo"]).strip()
        val_ev = "" if pd.isna(row["evento"]) else str(row["evento"]).strip()

        if not val_nom and not val_rut and not val_cor:
            continue
        if not val_nom or not val_rut:
            advertencias.append(f"Fila {idx + 2}: omitida por faltar nombre o RUT.")
            continue

        tp = val_tp or "General"
        ev = val_ev or evento_defecto
        fec_obj = parsear_fecha_excel(row["fecha_caducidad"], fecha_defecto)
        hor_obj = parsear_hora_excel(row["hora_limite"], hora_defecto)
        cad_str = f"{fec_obj.strftime('%Y-%m-%d')} {hor_obj.strftime('%H:%M')}"

        cor_limpio = val_cor
        if cor_limpio and not correo_valido(cor_limpio):
            advertencias.append(f"Fila {idx + 2} ({val_nom}): correo `{cor_limpio}` con formato inválido (no se enviará correo).")
            cor_limpio = ""

        registros.append({
            "nombre": val_nom,
            "rut": val_rut,
            "correo": cor_limpio,
            "tipo": tp,
            "evento": ev,
            "caducidad": cad_str,
        })

    if not registros:
        return None, "No se encontraron filas válidas con nombre y RUT en el archivo."
    return {"registros": registros, "advertencias": advertencias}, None

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

if "rol_sesion" not in st.session_state:
    st.session_state.rol_sesion = None
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""
if "modo_login_portada" not in st.session_state:
    st.session_state.modo_login_portada = None
if "vista_admin" not in st.session_state:
    st.session_state.vista_admin = "generar"
if "borrador_qr" not in st.session_state:
    st.session_state.borrador_qr = None
if "borrador_masivo" not in st.session_state:
    st.session_state.borrador_masivo = None

def reparar_filas_desplazadas(conn):
    c = conn.cursor()
    c.execute("SELECT rowid, codigo, correo, creado_por, evento, caducidad FROM entradas")
    filas = c.fetchall()
    cambios = 0
    for rowid, codigo, correo, creado_por, evento, caducidad in filas:
        cor_s = str(correo or "").strip()
        prod_s = str(creado_por or "").strip()
        ev_s = str(evento or "").strip()
        cad_s = str(caducidad or "").strip()

        nuevo_cor = cor_s
        nuevo_prod = prod_s
        nuevo_ev = ev_s
        nuevo_cad = cad_s

        if parece_fecha_hora(cor_s) and not parece_fecha_hora(cad_s):
            nuevo_cad = cor_s
            nuevo_cor = ""
        if parece_fecha_hora(cad_s) and parece_fecha_hora(cor_s):
            nuevo_cor = ""
        if ev_s in USUARIOS_PRODUCCION_CONOCIDOS:
            if not nuevo_prod:
                nuevo_prod = ev_s
            if cad_s and not parece_fecha_hora(cad_s):
                nuevo_ev = cad_s
                nuevo_cad = ""
            else:
                nuevo_ev = ""

        if (nuevo_cor, nuevo_prod, nuevo_ev, nuevo_cad) != (cor_s, prod_s, ev_s, cad_s):
            c.execute(
                "UPDATE entradas SET correo = ?, creado_por = ?, evento = ?, caducidad = ? WHERE rowid = ?",
                (nuevo_cor, nuevo_prod, nuevo_ev, nuevo_cad, rowid)
            )
            cambios += 1
    if cambios:
        conn.commit()

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
            caducidad TEXT,
            nota_renominacion TEXT
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
    if "nota_renominacion" not in columnas:
        c.execute("ALTER TABLE entradas ADD COLUMN nota_renominacion TEXT DEFAULT ''")
    conn.commit()
    reparar_filas_desplazadas(conn)
    return conn

conn = init_db()

def obtener_eventos():
    c = conn.cursor()
    c.execute("SELECT nombre, caducidad FROM eventos ORDER BY nombre ASC")
    return dict(c.fetchall())

def siguiente_codigo_ren(conn):
    c = conn.cursor()
    c.execute("SELECT nota_renominacion FROM entradas WHERE nota_renominacion LIKE '%REN-%'")
    max_num = 0
    for (nota,) in c.fetchall():
        if nota:
            for match in re.findall(r"REN-(\d+)", str(nota)):
                val = int(match)
                if val > max_num:
                    max_num = val
    return f"REN-{max_num + 1:03d}"

def fecha_caducidad_pasada(caducidad_str, eventos_dict, evento_nombre):
    referencia = (caducidad_str or "").strip() or eventos_dict.get(evento_nombre, "").strip()
    if not referencia:
        return False, ""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
        try:
            dt_ref = datetime.strptime(referencia, fmt)
            if fmt == "%Y-%m-%d":
                dt_ref = datetime.combine(dt_ref.date(), time(23, 59))
            return ahora_chile() > dt_ref, referencia
        except ValueError:
            continue
    return False, referencia

# ==========================================
# 🚪 PORTADA DE INICIO DE SESIÓN SEPARADA
# ==========================================
if st.session_state.rol_sesion is None:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("<h1 style='text-align: center;'>⚡ COLECTIVO KALMA</h1>", unsafe_allow_html=True)

    st.markdown(
        "<p style='text-align: center; color: #22d3ee !important; letter-spacing: 3px; font-size: 14px;'>"
        "ELECTRONIC MUSIC // ACCESS CONTROL</p>",
        unsafe_allow_html=True
    )
    st.divider()

    st.markdown(
        "<p style='text-align: center; font-size: 15px; margin-bottom: 14px;'>"
        "Selecciona el tipo de acceso para continuar:</p>",
        unsafe_allow_html=True
    )

    col_btn_puerta, col_btn_prod = st.columns(2)
    with col_btn_puerta:
        if st.button("📷 ACCESO PUERTA / SCAN", type="primary", use_container_width=True):
            st.session_state.modo_login_portada = "puerta"
            st.rerun()
    with col_btn_prod:
        if st.button("🔒 ACCESO PRODUCCIÓN", use_container_width=True):
            st.session_state.modo_login_portada = "admin"
            st.rerun()

    if st.session_state.modo_login_portada == "puerta":
        st.divider()
        st.subheader("📷 INGRESO EQUIPO DE PUERTA")
        with st.form("form_login_puerta"):
            usuario = st.text_input("Usuario de puerta")
            clave = st.text_input("Contraseña", type="password")
            entrar = st.form_submit_button("ENTRAR A PUERTA / SCAN", type="primary", use_container_width=True)

            if entrar:
                if usuario in USUARIOS_ACCESO and USUARIOS_ACCESO[usuario] == clave:
                    st.session_state.rol_sesion = "puerta"
                    st.session_state.usuario_actual = usuario
                    st.session_state.modo_login_portada = None
                    st.rerun()
                else:
                    st.error("Acceso de puerta denegado. Usuario o contraseña incorrectos.")

    elif st.session_state.modo_login_portada == "admin":
        st.divider()
        st.subheader("🔒 INGRESO PRODUCCIÓN / ADMIN")
        with st.form("form_login_admin"):
            usuario = st.text_input("Usuario producción")
            clave = st.text_input("Contraseña", type="password")
            entrar = st.form_submit_button("ENTRAR A PRODUCCIÓN", type="primary", use_container_width=True)

            if entrar:
                if usuario in USUARIOS_ADMIN and USUARIOS_ADMIN[usuario] == clave:
                    st.session_state.rol_sesion = "admin"
                    st.session_state.usuario_actual = usuario
                    st.session_state.modo_login_portada = None
                    st.session_state.vista_admin = "generar"
                    st.rerun()
                else:
                    st.error("Credenciales de producción incorrectas.")

    st.stop()

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
        st.session_state.rol_sesion = None
        st.session_state.usuario_actual = ""
        st.session_state.modo_login_portada = None
        st.session_state.borrador_qr = None
        st.session_state.borrador_masivo = None
        st.rerun()

etiqueta_rol = "PUERTA / SCAN" if st.session_state.rol_sesion == "puerta" else "PRODUCCIÓN"
st.caption(f"🟢 {etiqueta_rol}: **{st.session_state.usuario_actual}** | 🕒 Hora Chile: {ahora_chile().strftime('%d/%m/%Y %H:%M')}")

# ==========================================
# VISTA EXCLUSIVA PUERTA / SCAN
# ==========================================
if st.session_state.rol_sesion == "puerta":
    st.subheader("📷 CHECK-IN DE ACCESO EN PUERTA")

    eventos_dict = obtener_eventos()
    opciones_puerta = ["Todos los eventos"] + list(eventos_dict.keys())
    evento_activo = st.selectbox("🎧 Evento activo en puerta (filtro):", opciones_puerta)

    metodo = st.radio("Modo de lectura:", ["Cámara Trasera", "Código Manual / Pistola"], horizontal=True)
    codigo_leido = None

    if metodo == "Cámara Trasera":
        forzar_camara_trasera()
        st.caption("📷 Priorizando cámara trasera. Si el navegador muestra selector de cámara, elige la trasera.")
        img_file = st.camera_input("Escanea el QR con la cámara trasera")
        if img_file is not None:
            img = Image.open(img_file)
            resultados = zxingcpp.read_barcodes(img)
            if resultados:
                codigo_leido = resultados[0].text.strip()
            else:
                st.warning("No se detectó ningún QR. Acerca la cámara trasera o sube el brillo del celular.")
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
# VISTA PRODUCCIÓN / ADMIN (BOTONES SIN PESTAÑAS)
# ==========================================
elif st.session_state.rol_sesion == "admin":
    col_nav1, col_nav2, col_nav3 = st.columns(3)
    with col_nav1:
        if st.button(
            "⚡ GENERAR QR",
            type="primary" if st.session_state.vista_admin == "generar" else "secondary",
            use_container_width=True
        ):
            st.session_state.vista_admin = "generar"
            st.rerun()
    with col_nav2:
        if st.button(
            "🔄 RENOMINAR",
            type="primary" if st.session_state.vista_admin == "renominar" else "secondary",
            use_container_width=True
        ):
            st.session_state.vista_admin = "renominar"
            st.rerun()
    with col_nav3:
        if st.button(
            "📊 LISTA & BACKUP",
            type="primary" if st.session_state.vista_admin == "lista" else "secondary",
            use_container_width=True
        ):
            st.session_state.vista_admin = "lista"
            st.rerun()

    st.divider()

    if st.session_state.vista_admin == "generar":
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
            evento_defecto_masivo = "KALMA"
            fecha_defecto_masivo = ahora_chile().date()
            hora_defecto_masivo = time(6, 0)
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
            caducidad_final = f"{fecha_qr.strftime('%Y-%m-%d')} {hora_qr.strftime('%H:%M')}"
            evento_defecto_masivo = evento_elegido
            fecha_defecto_masivo = fecha_qr
            hora_defecto_masivo = hora_qr

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
                        creador = st.session_state.usuario_actual
                        c = conn.cursor()
                        c.execute(
                            "INSERT INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (codigo_unico, b["nombre"], b["rut"], b["correo"], b["tipo"], "DISPONIBLE", ahora_str, "", creador, b["evento"], b["caducidad"], "")
                        )
                        conn.commit()
                        ticket_bytes = generar_tarjeta_qr_bytes(codigo_unico, b["nombre"], b["rut"], b["tipo"], b["evento"], b["caducidad"])
                        st.session_state["ultimo_qr"] = (codigo_unico, b["nombre"], b["rut"], b["correo"], b["tipo"], creador, b["evento"], b["caducidad"])
                        st.session_state.borrador_qr = None

                        msg_envio = ""
                        error_envio = ""
                        correo_unificado = str(b["correo"]).strip()
                        if correo_unificado:
                            ok_mail, detalle_mail = enviar_qr_por_correo(
                                correo_unificado, b["nombre"], b["rut"], b["tipo"], b["evento"], b["caducidad"], codigo_unico, ticket_bytes
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

        st.divider()
        with st.expander("📦 CARGA MASIVA DE QR DESDE EXCEL"):
            st.caption(
                "Columnas en el Excel: `nombre`, `rut`, `correo`, `tipo` (o `tipo de pase`), "
                "**`Nombre del Evento`**, **`Fecha caducidad`** y **`Hora límite`**. "
                "Cada fila se envía únicamente al correo asignado en esa misma fila."
            )
            archivo_masivo = st.file_uploader("Sube tu archivo Excel (.xlsx) o CSV", type=["xlsx", "csv"], key="uploader_masivo")

            if archivo_masivo is not None:
                if st.button("📋 REVISAR LISTADO ANTES DE ENVIAR", type="primary", use_container_width=True):
                    resultado, err_masivo = normalizar_excel_masivo(
                        archivo_masivo, evento_defecto_masivo, fecha_defecto_masivo, hora_defecto_masivo
                    )
                    if err_masivo:
                        st.error(err_masivo)
                    else:
                        st.session_state.borrador_masivo = {
                            "registros": resultado["registros"],
                            "advertencias": resultado["advertencias"],
                        }
                        st.rerun()

            if st.session_state.borrador_masivo is not None:
                bm = st.session_state.borrador_masivo
                total_regs = len(bm["registros"])
                con_correo = sum(1 for r in bm["registros"] if r["correo"])
                st.warning(
                    f"❓ **¿Estás seguro de generar y enviar {total_regs} E-Tickets de forma individual?** "
                    f"({con_correo} filas enviarán su QR solo a su propio correo asignado)."
                )
                st.dataframe(pd.DataFrame(bm["registros"]), use_container_width=True, hide_index=True)

                for adv in bm["advertencias"]:
                    st.caption(f"⚠️ {adv}")

                col_m_ok, col_m_no = st.columns(2)
                with col_m_ok:
                    if st.button("🚀 SÍ, GENERAR Y ENVIAR TODOS", type="primary", use_container_width=True):
                        c = conn.cursor()
                        creador = st.session_state.usuario_actual
                        ahora_str = ahora_chile().strftime("%Y-%m-%d %H:%M:%S")
                        enviados_ok = 0
                        enviados_err = 0
                        errores_detalle = []
                        barra = st.progress(0)
                        estado_txt = st.empty()

                        for i, reg in enumerate(bm["registros"]):
                            nom_fila = str(reg["nombre"]).strip()
                            rut_fila = str(reg["rut"]).strip()
                            cor_fila = str(reg["correo"]).strip()
                            tp_fila = str(reg["tipo"]).strip()
                            ev_fila = str(reg["evento"]).strip()
                            cad_fila = str(reg["caducidad"]).strip()

                            estado_txt.text(f"Procesando {i + 1}/{total_regs}: {nom_fila} -> {cor_fila or 'sin correo'}...")
                            codigo_fila = f"KLM-{uuid.uuid4().hex[:8].upper()}"
                            if ev_fila:
                                c.execute("INSERT OR IGNORE INTO eventos VALUES (?, ?)", (ev_fila, cad_fila))
                            c.execute(
                                "INSERT INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (codigo_fila, nom_fila, rut_fila, cor_fila, tp_fila, "DISPONIBLE", ahora_str, "", creador, ev_fila, cad_fila, "")
                            )
                            if cor_fila:
                                qr_fila_bytes = generar_tarjeta_qr_bytes(codigo_fila, nom_fila, rut_fila, tp_fila, ev_fila, cad_fila)
                                ok_m, detalle_m = enviar_qr_por_correo(
                                    cor_fila, nom_fila, rut_fila, tp_fila, ev_fila, cad_fila, codigo_fila, qr_fila_bytes
                                )
                                if ok_m:
                                    enviados_ok += 1
                                else:
                                    enviados_err += 1
                                    errores_detalle.append(detalle_m)
                                pytime.sleep(0.25)
                            barra.progress((i + 1) / total_regs)

                        conn.commit()
                        st.session_state.borrador_masivo = None
                        estado_txt.empty()
                        st.success(f"Carga masiva lista: {total_regs} QR generados | {enviados_ok} correos individuales enviados | {enviados_err} con error.")
                        for err_item in errores_detalle:
                            st.error(err_item)
                with col_m_no:
                    if st.button("❌ CANCELAR LOTE", use_container_width=True):
                        st.session_state.borrador_masivo = None
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

    elif st.session_state.vista_admin == "renominar":
        st.subheader("🔄 RENOMINAR ENTRADA (CESIÓN O REVENTA)")
        st.caption("Busca con la lupa en todos los eventos o filtra por un evento generado, y actualiza los datos manteniendo el mismo QR y el folio correlativo (REN-001).")

        reparar_filas_desplazadas(conn)
        eventos_dict_ren = obtener_eventos()
        df_ren_raw = pd.read_sql_query("SELECT * FROM entradas ORDER BY fecha_creacion DESC", conn)
        df_ren = normalizar_dataframe_por_encabezado(df_ren_raw)

        if df_ren.empty:
            st.info("No hay entradas registradas aún para renombrar.")
        else:
            eventos_generados = sorted(list(eventos_dict_ren.keys()))
            eventos_en_entradas = sorted([str(e).strip() for e in df_ren["evento"].dropna().unique() if str(e).strip() != ""])
            eventos_unicos = sorted(list(set(eventos_generados + eventos_en_entradas)))
            opciones_evento_filtro = ["Todos los eventos"] + eventos_unicos

            evento_filtro_sel = st.selectbox("🎧 Filtrar por evento (opcional):", opciones_evento_filtro, key="sel_evento_filtro_ren")
            filtro_ren = st.text_input("🔍 Buscar por código, RUT, nombre o evento:").strip()

            df_filtrado_ren = df_ren.copy()
            if evento_filtro_sel != "Todos los eventos":
                df_filtrado_ren = df_filtrado_ren[df_filtrado_ren["evento"] == evento_filtro_sel]
            if filtro_ren:
                df_filtrado_ren = df_filtrado_ren[
                    df_filtrado_ren["codigo"].str.contains(filtro_ren, case=False, na=False) |
                    df_filtrado_ren["rut"].str.contains(filtro_ren, case=False, na=False) |
                    df_filtrado_ren["nombre"].str.contains(filtro_ren, case=False, na=False) |
                    df_filtrado_ren["evento"].str.contains(filtro_ren, case=False, na=False)
                ]

            if df_filtrado_ren.empty:
                st.warning("No se encontraron entradas con ese criterio de búsqueda o evento.")
            else:
                st.caption(f"Entradas encontradas: {len(df_filtrado_ren)}")
                opciones_ren = [
                    f"{r['codigo']} — {r['nombre']} ({r['rut']}) | {r['evento'] or 'Sin evento'} [{r['estado'] or 'DISPONIBLE'}]"
                    for _, r in df_filtrado_ren.iterrows()
                ]
                seleccion_ren = st.selectbox("Selecciona la entrada a renombrar:", opciones_ren)
                codigo_sel = seleccion_ren.split(" — ", 1)[0].strip()
                fila_actual = df_ren[df_ren["codigo"] == codigo_sel].iloc[0]

                evento_ticket = str(fila_actual["evento"] or "").strip()
                caducidad_ticket = str(fila_actual["caducidad"] or eventos_dict_ren.get(evento_ticket, "")).strip()
                evento_pasado, ref_cad = fecha_caducidad_pasada(caducidad_ticket, eventos_dict_ren, evento_ticket)

                st.markdown(
                    f"**Evento:** {evento_ticket or 'Sin evento'} | **Caducidad:** {ref_cad or 'Sin límite'}  \n"
                    f"**Titular actual:** {fila_actual['nombre']} | **RUT:** {fila_actual['rut']} | "
                    f"**Correo:** {fila_actual['correo'] or 'Sin correo'} | **Pase:** {fila_actual['tipo']}"
                )
                if fila_actual["nota_renominacion"]:
                    st.caption(f"📝 Historial anterior: {fila_actual['nota_renominacion']}")

                if evento_pasado:
                    st.error(
                        f"⛔ **Renominación bloqueada:** El evento **{evento_ticket or 'registrado'}** ya pasó de la fecha/hora límite (`{ref_cad}`). "
                        f"No se pueden generar renominaciones para eventos ya pasados."
                    )
                else:
                    if fila_actual["estado"] == "USADA":
                        st.warning("⚠️ Esta entrada ya figura como **USADA** en puerta.")

                    tipos_pase = ["Early Bird", "Preventa 1", "Preventa 2", "General", "VIP / Backstage", "Lista / Cortesía"]
                    idx_tipo = tipos_pase.index(fila_actual["tipo"]) if fila_actual["tipo"] in tipos_pase else 3

                    with st.form("form_renominar"):
                        nuevo_nombre = st.text_input("Nombre Completo nuevo asistente", value=str(fila_actual["nombre"]))
                        nuevo_rut = st.text_input("RUT / Carnet nuevo asistente", value=str(fila_actual["rut"]))
                        nuevo_correo = st.text_input("Correo Electrónico nuevo asistente", value=str(fila_actual["correo"]))
                        nuevo_tipo = st.selectbox("Tipo de Pase", tipos_pase, index=idx_tipo)
                        motivo_ren = st.selectbox("Motivo de renominación", ["Cesión", "Reventa"])
                        detalle_ren = st.text_input("Observación adicional (opcional)", placeholder="Ej: Solicitado por correo")
                        guardar_ren = st.form_submit_button("💾 GUARDAR RENOMINACIÓN", type="primary", use_container_width=True)

                    if guardar_ren:
                        evento_vencido_ahora, ref_cad_ahora = fecha_caducidad_pasada(caducidad_ticket, eventos_dict_ren, evento_ticket)
                        if evento_vencido_ahora:
                            st.error(f"⛔ Este evento ya pasó (`{ref_cad_ahora}`). No se puede guardar la renominación.")
                        elif not nuevo_nombre.strip() or not nuevo_rut.strip():
                            st.error("Debes completar el Nombre y el RUT del nuevo asistente.")
                        elif nuevo_correo.strip() and not correo_valido(nuevo_correo.strip()):
                            st.error(f"El correo `{nuevo_correo.strip()}` no tiene un formato válido.")
                        else:
                            codigo_ren = siguiente_codigo_ren(conn)
                            fecha_ren = ahora_chile().strftime("%d/%m/%Y %H:%M")
                            anterior_txt = (
                                f"ANTERIOR [{codigo_ren}]: {fila_actual['nombre']} | RUT: {fila_actual['rut']} | "
                                f"Correo: {fila_actual['correo'] or 'Sin correo'} | Pase: {fila_actual['tipo']}"
                            )
                            nuevo_txt = (
                                f"NUEVO [{codigo_ren}]: {nuevo_nombre.strip()} | RUT: {nuevo_rut.strip()} | "
                                f"Correo: {nuevo_correo.strip() or 'Sin correo'} | Pase: {nuevo_tipo}"
                            )
                            marca_cambio = (
                                f"[{codigo_ren} - RENOMINADA] {fecha_ren} | Evento: '{evento_ticket}' | Motivo: {motivo_ren} | "
                                f"{anterior_txt} ==> {nuevo_txt} | Por: {st.session_state.usuario_actual}"
                            )
                            if detalle_ren.strip():
                                marca_cambio += f" | Obs: {detalle_ren.strip()}"
                            nota_acumulada = (
                                f"{fila_actual['nota_renominacion']} || {marca_cambio}"
                                if fila_actual["nota_renominacion"]
                                else marca_cambio
                            )
                            c = conn.cursor()
                            c.execute(
                                "UPDATE entradas SET nombre = ?, rut = ?, correo = ?, tipo = ?, nota_renominacion = ? WHERE codigo = ?",
                                (nuevo_nombre.strip(), nuevo_rut.strip(), nuevo_correo.strip(), nuevo_tipo, nota_acumulada, codigo_sel)
                            )
                            conn.commit()
                            st.success(
                                f"Entrada `{codigo_sel}` renombrada bajo el folio **{codigo_ren}** a **{nuevo_nombre.strip()}** ({nuevo_rut.strip()}) para **{evento_ticket}**."
                            )
                            st.rerun()

    elif st.session_state.vista_admin == "lista":
        reparar_filas_desplazadas(conn)
        df_raw = pd.read_sql_query("SELECT * FROM entradas ORDER BY fecha_creacion DESC", conn)
        df = normalizar_dataframe_por_encabezado(df_raw)

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
                    df_nuevo_raw = pd.read_excel(archivo_subido)
                else:
                    df_nuevo_raw = pd.read_csv(archivo_subido)
                df_nuevo = normalizar_dataframe_por_encabezado(df_nuevo_raw)
                c = conn.cursor()
                for _, row in df_nuevo.iterrows():
                    c.execute(
                        "INSERT OR REPLACE INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            row["codigo"], row["nombre"], row["rut"], row["correo"],
                            row["tipo"], row["estado"], row["fecha_creacion"], row["fecha_ingreso"],
                            row["creado_por"], row["evento"], row["caducidad"], row["nota_renominacion"]
                        )
                    )
                    if row["evento"]:
                        c.execute("INSERT OR IGNORE INTO eventos VALUES (?, ?)", (row["evento"], row["caducidad"]))
                conn.commit()
                reparar_filas_desplazadas(conn)
                st.success("Base de datos restaurada correctamente.")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        with st.expander("🧹 LIMPIADOR DE EVENTOS Y REGISTROS"):
            st.caption("Usa estas herramientas con cuidado para borrar eventos o registros de prueba/detalle.")

            eventos_limpiar = list(obtener_eventos().keys())
            if eventos_limpiar:
                st.markdown("**A. Borrar evento guardado**")
                ev_borrar = st.selectbox("Selecciona evento a borrar:", eventos_limpiar, key="sel_ev_borrar")
                borrar_entradas_ev = st.checkbox("Borrar también todas las entradas asociadas a este evento", key="chk_borrar_entradas_ev")
                confirmar_ev = st.checkbox("Confirmo que deseo eliminar este evento", key="chk_conf_ev")
                if st.button("🗑️ ELIMINAR EVENTO", use_container_width=True):
                    if not confirmar_ev:
                        st.warning("Marca la casilla de confirmación antes de eliminar el evento.")
                    else:
                        c = conn.cursor()
                        c.execute("DELETE FROM eventos WHERE nombre = ?", (ev_borrar,))
                        if borrar_entradas_ev:
                            c.execute("DELETE FROM entradas WHERE evento = ?", (ev_borrar,))
                        conn.commit()
                        st.success(f"Evento **{ev_borrar}** eliminado.")
                        st.rerun()
            else:
                st.caption("No hay eventos guardados para borrar.")

            st.divider()
            st.markdown("**B. Borrar una entrada específica (detalle)**")
            if not df.empty:
                opciones_detalle = [
                    f"{r['codigo']} — {r['nombre']} ({r['rut']}) | {r['evento']}"
                    for _, r in df.iterrows()
                ]
                sel_detalle = st.selectbox("Selecciona una entrada puntual:", opciones_detalle, key="sel_detalle_borrar")
                confirmar_det = st.checkbox("Confirmo eliminar esta entrada específica", key="chk_conf_det")
                if st.button("🗑️ BORRAR ENTRADA SELECCIONADA", use_container_width=True):
                    if not confirmar_det:
                        st.warning("Marca la casilla de confirmación antes de borrar la entrada.")
                    else:
                        cod_borrar = sel_detalle.split(" — ", 1)[0].strip()
                        c = conn.cursor()
                        c.execute("DELETE FROM entradas WHERE codigo = ?", (cod_borrar,))
                        conn.commit()
                        st.success(f"Entrada `{cod_borrar}` eliminada.")
                        st.rerun()

            st.divider()
            st.markdown("**C. Limpiar todo el historial de entradas**")
            confirmar_todo = st.checkbox("Confirmo que ya respaldé en Excel y deseo borrar TODAS las entradas", key="chk_conf_todo")
            if st.button("💣 VACIAR TODAS LAS ENTRADAS", use_container_width=True):
                if not confirmar_todo:
                    st.warning("Marca la casilla de confirmación para vaciar la tabla de entradas.")
                else:
                    c = conn.cursor()
                    c.execute("DELETE FROM entradas")
                    conn.commit()
                    st.success("Todas las entradas han sido eliminadas.")
                    st.rerun()
