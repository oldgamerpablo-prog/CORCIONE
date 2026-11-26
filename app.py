import streamlit as st
import sqlite3
import uuid
import pandas as pd
import qrcode
import zxingcpp
from PIL import Image
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Control de Entradas QR", page_icon="🎵", layout="centered")

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
            fecha_ingreso TEXT
        )
    """)
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

st.title("🎵 Control de Acceso - Evento")

tab1, tab2, tab3 = st.tabs(["📷 Validar en Puerta", "🎟️ Generar Entrada", "📋 Lista y Respaldo"])

# ==========================================
# PESTAÑA 1: VALIDAR EN PUERTA
# ==========================================
with tab1:
    st.subheader("Escáner de Puerta")
    metodo = st.radio("Método de lectura:", ["Cámara", "Código Manual / Pistola"], horizontal=True)
    codigo_leido = None

    if metodo == "Cámara":
        img_file = st.camera_input("Apunta al QR de la entrada")
        if img_file is not None:
            img = Image.open(img_file)
            resultados = zxingcpp.read_barcodes(img)
            if resultados:
                codigo_leido = resultados[0].text.strip()
            else:
                st.warning("No se detectó ningún QR. Intenta acercar o enfocar mejor.")
    else:
        codigo_leido = st.text_input("Ingresa o escanea el código:").strip()

    if codigo_leido:
        c = conn.cursor()
        c.execute("SELECT codigo, nombre, rut, tipo, estado, fecha_ingreso FROM entradas WHERE codigo = ?", (codigo_leido,))
        entrada = c.fetchone()

        if not entrada:
            st.error(f"❌ ENTRADA INVÁLIDA: El código `{codigo_leido}` no existe en el sistema.")
        else:
            cod, nombre, rut, tipo, estado, fecha_ing = entrada
            if estado == "USADA":
                st.error("⚠️ ENTRADA YA UTILIZADA")
                st.warning(f"**Titular:** {nombre} | **RUT:** {rut}\n\n**Ingresó el:** {fecha_ing}")
            else:
                st.success("✅ ENTRADA VÁLIDA — VERIFICAR CARNET")
                st.markdown(f"""
                ### 👤 {nombre}
                ### 🪪 RUT: `{rut}`
                **🎟️ Tipo:** {tipo}  
                **🔑 Código:** `{cod}`
                """)
                if st.button("✅ Confirmar Ingreso (Quemar QR)", type="primary", use_container_width=True):
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("UPDATE entradas SET estado = 'USADA', fecha_ingreso = ? WHERE codigo = ?", (ahora, cod))
                    conn.commit()
                    st.toast(f"Ingreso confirmado para {nombre}")
                    st.rerun()

# ==========================================
# PESTAÑA 2: GENERAR ENTRADA Y QR ÚNICO
# ==========================================
with tab2:
    st.subheader("Crear nueva entrada nominativa")
    with st.form("form_crear", clear_on_submit=True):
        nombre = st.text_input("Nombre Completo")
        rut = st.text_input("RUT / Carnet (ej: 12.345.678-9)")
        tipo = st.selectbox("Tipo de Entrada", ["General", "Preventa", "VIP", "Lista / Cortesía"])
        crear = st.form_submit_button("🎟️ Generar Entrada y QR", type="primary")

    if crear:
        if nombre.strip() and rut.strip():
            codigo_unico = f"EVT-{uuid.uuid4().hex[:8].upper()}"
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c = conn.cursor()
            c.execute(
                "INSERT INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?)",
                (codigo_unico, nombre.strip(), rut.strip(), tipo, "DISPONIBLE", ahora, "")
            )
            conn.commit()
            st.session_state["ultimo_qr"] = (codigo_unico, nombre.strip(), rut.strip(), tipo)
            st.success(f"Entrada creada para **{nombre.strip()}** (`{codigo_unico}`)")
        else:
            st.error("Debes completar el Nombre y el RUT.")

    if "ultimo_qr" in st.session_state:
        cod, nom, rt, tp = st.session_state["ultimo_qr"]
        qr_bytes = generar_imagen_qr(cod)
        st.divider()
        st.write(f"**Último QR generado:** {nom} ({rt}) — {tp}")
        st.image(qr_bytes, width=250)
        st.download_button(
            label="📥 Descargar imagen QR para enviar",
            data=qr_bytes,
            file_name=f"QR_{nom.replace(' ', '_')}_{cod}.png",
            mime="image/png"
        )

# ==========================================
# PESTAÑA 3: LISTA DE ASISTENTES Y RESPALDO
# ==========================================
with tab3:
    df = pd.read_sql_query("SELECT * FROM entradas ORDER BY fecha_creacion DESC", conn)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Entradas", len(df))
    col2.metric("Ingresados", len(df[df["estado"] == "USADA"]))
    col3.metric("Pendientes", len(df[df["estado"] == "DISPONIBLE"]))

    busqueda = st.text_input("🔍 Buscar por Nombre o RUT:")
    if busqueda:
        df_mostrar = df[
            df["nombre"].str.contains(busqueda, case=False, na=False) |
            df["rut"].str.contains(busqueda, case=False, na=False)
        ]
    else:
        df_mostrar = df

    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**💾 Respaldo de Seguridad** *(Descarga siempre tu lista antes del evento)*")
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 Descargar base de datos (CSV)",
        data=csv,
        file_name=f"respaldo_entradas_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv"
    )

    archivo_subido = st.file_uploader("📤 Restaurar base de datos desde CSV", type=["csv"])
    if archivo_subido is not None:
        if st.button("Cargar entradas del archivo"):
            df_nuevo = pd.read_csv(archivo_subido).fillna("")
            c = conn.cursor()
            for _, row in df_nuevo.iterrows():
                c.execute(
                    "INSERT OR REPLACE INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row["codigo"], row["nombre"], row["rut"], row["tipo"], row["estado"], row["fecha_creacion"], row["fecha_ingreso"])
                )
            conn.commit()
            st.success("Base de datos restaurada correctamente.")
            st.rerun()
