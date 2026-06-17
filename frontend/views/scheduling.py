from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from api_client import get_patients, create_appointment, get_appointments


def render_scheduling() -> None:
    st.subheader("Appointment Scheduling Agent")
    st.caption("Manage patient booking queues and preview automated notifications.")

    role = st.session_state.get("user_role")

    # 1. Fetch Patients
    patients = get_patients()
    patient_names = [p["name"] for p in patients]

    if role == "Patient":
        active_patient = st.session_state.get("username")
        if active_patient not in patient_names:
            st.warning("You do not have an active patient record. Please contact an administrator.")
            return
        active_patient_id = next((p["patient_id"] for p in patients if p["name"] == active_patient), "PT-UNKNOWN")
    else:
        patient_options = ["(none)"] + patient_names
        selected = st.session_state.get("active_patient") or "(none)"
        if selected not in patient_options:
            selected = "(none)"
            
        chosen = st.selectbox("Scheduling Patient Context", patient_options, index=patient_options.index(selected))
        if chosen == "(none)":
            st.warning("Please select a patient in the dropdown or sidebar to schedule appointments.")
            return
        active_patient = chosen
        st.session_state.active_patient = chosen
        active_patient_id = next((p["patient_id"] for p in patients if p["name"] == active_patient), "PT-UNKNOWN")

    st.markdown("---")

    # 2. Scheduling Form (Restricted to Clinicians/Assistants/Admins)
    if role in {"Admin", "Psychologist", "Assistant"}:
        st.markdown("### Create Clinical Appointment")
        with st.form("scheduling_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                date = st.date_input("Appointment Date", value=datetime.now().date() + timedelta(days=1))
                time = st.time_input("Appointment Time", value=datetime.now().time().replace(second=0, microsecond=0))
            with col2:
                clinician = st.selectbox("Assigned Clinician", ["Dr. Sarah Paul", "Dr. Arjun Mehta", "Dr. Priya Sen"])
                channel = st.selectbox("Interaction Channel", ["In-person Clinic", "Secure Video Call", "Tele-health Phone Session"])
                
            note = st.text_input("Consultation Notes / Topic", value="Regular follow-up screening review")
            
            submit = st.form_submit_button("Book Appointment")
            
        if submit:
            app_data = {
                "patient_id": active_patient_id,
                "patient_name": active_patient,
                "date": str(date),
                "time": str(time)[:5],
                "clinician": clinician,
                "channel": channel,
                "note": note
            }
            res = create_appointment(app_data)
            if res:
                st.success("Appointment successfully created in clinical registry!")
                
                # Render WhatsApp notification preview
                st.write("")
                st.markdown("#### WhatsApp Automated Alert Preview")
                whatsapp_msg = res.get("whatsapp_preview", "")
                
                st.markdown(
                    f'<div class="whatsapp-frame">'
                    f'<div class="whatsapp-header">💬 WhatsApp Notification Preview</div>'
                    f'<div class="whatsapp-message">{whatsapp_msg}'
                    f'<div class="whatsapp-time">{datetime.now().strftime("%I:%M %p")}</div>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            else:
                st.error("Failed to schedule appointment. Verify backend connectivity.")
    else:
        st.info("Note: Appointment booking forms are restricted to clinic staff and administrator accounts.")

    # 3. Appointments List
    st.write("")
    st.subheader("Your Appointment Registry")
    appts = get_appointments()
    if appts:
        df = pd.DataFrame(appts)
        display_df = df[["id", "patient_name", "date", "time", "clinician", "channel", "note"]].copy()
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No appointments currently scheduled.")
