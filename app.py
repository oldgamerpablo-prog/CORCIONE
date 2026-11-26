import streamlit as st
import sqlite3
import uuid
import pandas as pd
import qrcode
import zxingcpp
from PIL import Image
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Colectivo Kalma - Control QR", page_icon="🎵", layout="centered")

# ==========================================
# 🔐 CONFIGURACIÓN DE USUARIOS Y CONTRASEÑAS
# ==========================================
# Acceso general (Portada / Puerta)
USUARIOS_ACCESO = {
    "Colectivo.kalma": "Kalma.0720",
    "puerta": "1234"
}

# Acceso administrador (Pestañas 2 y 3 con historial de creador)
USUARIOS_ADMIN = {
    "Javi.martinez": "Colectivo2026",
    "Eric.brito": "Colectivo2026",
    "Piero.corci": "Colectivo2026"
}

# --- ESTADOS DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""
if "admin_usuario" not in st.session_state:
    st.session_state.admin_usuario = None

# ==========================================
# 🚪 PORTADA DE INICIO DE SESIÓN
# ==========================================
if not st.session_state.autenticado:
    st.title("🎵 Colectivo Kalma - Control de Acceso")
    st.subheader("🔐 Iniciar Sesión")

    with st.form("form_login"):
        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

        if entrar:
            if usuario in USUARIOS_ACCESO and USUARIOS_ACCESO[usuario] == clave:
                st.session_state.autenticado = True
                st.session_state.usuario_actual = usuario
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")

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
    # Si ya existía una tabla anterior sin la columna 'creado_por', la agrega automáticamente
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
    """Pide usuario y contraseña de administrador para desbloquear Pestañas 2 y 3."""
    if st.session_state.admin_usuario is not None:
        return True

    st.warning("🔒 Esta sección requiere acceso de administrador.")
    with st.form(f"form_admin_{id_pestana}"):
        admin_user = st.text_input("Usuario administrador")
        admin_pass = st.text_input("Contraseña", type="password")
        desbloquear = st.form_submit_button("Desbloquear sección", type="primary")
        if desbloquear:
            if admin_user in USUARIOS_ADMIN and USUARIOS_ADMIN[admin_user] == admin_pass:
                st.session_state.admin_usuario = admin_user
                st.rerun()
            else:
                st.error("Usuario o contraseña de administrador incorrectos.")
    return False

# --- BARRA SUPERIOR ---
col_tit, col_salir = st.columns([3, 1])
with col_tit:
    st.title("🎵 Colectivo Kalma")
with col_salir:
    st.write("")
    if st.button("Cerrar sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.usuario_actual = ""
        st.session_state.admin_usuario = None
        st.rerun()

st.caption(f"Sesión general: **{st.session_state.usuario_actual}**")

tab1, tab2, tab3 = st.tabs(["📷 Validar en Puerta", "🔒 Generar Entrada", "🔒 Lista y Respaldo"])

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
        c.execute("SELECT codigo, nombre, rut, tipo, estado, fecha_ingreso, creado_por FROM entradas WHERE codigo = ?", (codigo_leido,))
        entrada = c.fetchone()

        if not entrada:
            st.error(f"❌ ENTRADA INVÁLIDA: El código `{codigo_leido}` no existe en el sistema.")
        else:
            cod, nombre, rut, tipo, estado, fecha_ing, creado_por = entrada
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
                **✍️ Generada por:** {creado_por if creado_por else 'Sin registro'}
                """)
                if st.button("✅ Confirmar Ingreso (Quemar QR)", type="primary", use_container_width=True):
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("UPDATE entradas SET estado = 'USADA', fecha_ingreso = ? WHERE codigo = ?", (ahora, cod))
                    conn.commit()
                    st.toast(f"Ingreso confirmado para {nombre}")
                    st.rerun()

# ==========================================
# PESTAÑA 2: GENERAR ENTRADA (CON USUARIO ADMIN)
# ==========================================
with tab2:
    if pedir_acceso_admin("tab2"):
        st.info(f"👤 Generando entradas como: **{st.session_state.admin_usuario}**")
        st.subheader("Crear nueva entrada nominativa")
        with st.form("form_crear", clear_on_submit=True):
            nombre = st.text_input("Nombre Completo")
            rut = st.text_input("RUT / Carnet (ej: 12.345.678-9)")
            tipo = st.selectbox("Tipo de Entrada", ["General", "Preventa", "VIP", "Lista / Cortesía"])
            crear = st.form_submit_button("🎟️ Generar Entrada y QR", type="primary")

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
                st.success(f"Entrada creada para **{nombre.strip()}** (`{codigo_unico}`) por **{creador}**")
            else:
                st.error("Debes completar el Nombre y el RUT.")

        if "ultimo_qr" in st.session_state:
            cod, nom, rt, tp, cr = st.session_state["ultimo_qr"]
            qr_bytes = generar_imagen_qr(cod)
            st.divider()
            st.write(f"**Último QR generado:** {nom} ({rt}) — {tp} | *Creado por: {cr}*")
            st.image(qr_bytes, width=250)
            st.download_button(
                label="📥 Descargar imagen QR para enviar",
                data=qr_bytes,
                file_name=f"QR_{nom.replace(' ', '_')}_{cod}.png",
                mime="image/png"
            )

# ==========================================
# PESTAÑA 3: LISTA Y RESPALDO (CON USUARIO ADMIN)
# ==========================================
with tab3:
    if pedir_acceso_admin("tab3"):
        st.info(f"👤 Administrador activo: **{st.session_state.admin_usuario}**")
        df = pd.read_sql_query("SELECT * FROM entradas ORDER BY fecha_creacion DESC", conn)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Entradas", len(df))
        col2.metric("Ingresados", len(df[df["estado"] == "USADA"]))
        col3.metric("Pendientes", len(df[df["estado"] == "DISPONIBLE"]))

        busqueda = st.text_input("🔍 Buscar por Nombre, RUT o Creador:")
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
                    creador_csv = row["creado_por"] if "creado_por" in df_nuevo.columns else ""
                    c.execute(
                        "INSERT OR REPLACE INTO entradas VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (row["codigo"], row["nombre"], row["rut"], row["tipo"], row["estado"], row["fecha_creacion"], row["fecha_ingreso"], creador_csv)
                    )
                conn.commit()
                st.success("Base de datos restaurada correctamente.")
                st.rerun()

        st.divider()
        if st.button("🔒 Cerrar sesión de administrador (bloquear pestañas 2 y 3)"):
            st.session_state.admin_usuario = None
            st.rerun()
