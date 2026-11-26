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

                            nuevo_reset = st.session_state.ren_reset_id + 1
                            st.session_state.ren_reset_id = nuevo_reset
                            for pref in ("ren_nom_", "ren_rut_", "ren_cor_", "ren_obs_"):
                                clave_ant = f"{pref}{codigo_sel}_{reset_id}"
                                clave_nue = f"{pref}{codigo_sel}_{nuevo_reset}"
                                st.session_state.pop(clave_ant, None)
                                st.session_state[clave_nue] = ""

                            st.session_state["ren_msg_exito"] = (
                                f"Entrada `{codigo_sel}` renombrada bajo el folio **{codigo_ren}** a **{nuevo_nombre.strip()}** ({nuevo_rut.strip()}) para **{evento_ticket}**."
                            )
                            st.rerun()
