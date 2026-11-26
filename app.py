import streamlit as st
import cv2
import numpy as np
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Gestor de Pallets - Lector QR", page_icon="📦", layout="centered")

st.title("📦 Gestor de Pallets - Lector QR")

if "registros" not in st.session_state:
    st.session_state.registros = []

def agregar_registro(codigo, metodo):
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.registros.insert(0, {
        "Fecha y Hora": ahora,
        "Código QR": codigo,
        "Método": metodo
    })

tab1, tab2 = st.tabs(["📷 Escanear con Cámara", "⌨️ Lector USB / Manual"])

with tab1:
    img_file = st.camera_input("Apunta al código QR y toma la foto")
    if img_file is not None:
        bytes_data = img_file.getvalue()
        np_arr = np.frombuffer(bytes_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)

        if data:
            st.success(f"QR detectado: **{data}**")
            if st.button("✅ Guardar en el registro", type="primary"):
                agregar_registro(data, "Cámara")
                st.toast("Registro guardado")
        else:
            st.warning("No se detectó ningún código QR. Intenta enfocar mejor o acercar la cámara.")

with tab2:
    with st.form("form_manual", clear_on_submit=True):
        codigo_manual = st.text_input("Escanea con pistola QR o escribe el código y presiona Enter:")
        enviado = st.form_submit_button("Registrar código")
        if enviado and codigo_manual.strip():
            agregar_registro(codigo_manual.strip(), "Manual / Pistola")
            st.success(f"Registrado: {codigo_manual.strip()}")

st.divider()

st.subheader("📋 Registro de lecturas")

if st.session_state.registros:
    df = pd.DataFrame(st.session_state.registros)
    st.dataframe(df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 Descargar registro (CSV / Excel)",
            data=csv,
            file_name=f"registro_pallets_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col2:
        if st.button("🗑️ Limpiar registro", use_container_width=True):
            st.session_state.registros = []
            st.rerun()
else:
    st.info("Aún no hay códigos QR registrados.")
