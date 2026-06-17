from __future__ import annotations

import streamlit as st
import pandas as pd
from pathlib import Path
import csv
import io

from api_client import (
    login,
    register,
    logout,
    get_patients,
    create_patient,
    ingest_document,
    get_documents,
    log_audit
)

# Import sub-views
from views.dashboard import render_dashboard
from views.assessment import render_assessment
from views.chat import render_chat
from views.voice_chat import render_voice_chat
from views.rag_assistant import render_rag_assistant
from views.scheduling import render_scheduling
from views.reports import render_reports
from views.progress import render_progress
from views.admin import render_admin
from views.retention import render_retention

# Page Config
st.set_page_config(
    page_title="Mental Health Agentic Chatbot",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load CSS
CSS_PATH = Path(__file__).resolve().parent / "style.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def init_session():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "token" not in st.session_state:
        st.session_state.token = None
    if "username" not in st.session_state:
        st.session_state.username = None
    if "user_role" not in st.session_state:
        st.session_state.user_role = None
    if "full_name" not in st.session_state:
        st.session_state.full_name = None
    if "active_language" not in st.session_state:
        st.session_state.active_language = "English"
    if "active_patient" not in st.session_state:
        st.session_state.active_patient = None
    if "consent" not in st.session_state:
        st.session_state.consent = False


def render_login_page():
    with st.container(border=True):
        st.markdown('<div class="login-logo">🧠</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Mental Health Agentic Chatbot</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 1.15rem; font-weight: 600; color: #cbd5e1; margin-bottom: 0.5rem; letter-spacing: 0.5px;">Enterprise Portal Login</div>', unsafe_allow_html=True)
        st.markdown('<p style="color:#64748b; margin-bottom: 2rem; font-size: 0.9rem;">Secure Clinical Portal Gate</p>', unsafe_allow_html=True)

        mode = st.radio("Choose Mode", ["Log In", "Register Account"], horizontal=True, label_visibility="collapsed")
        
        if mode == "Log In":
            user = st.text_input("Username / Patient ID", placeholder="Enter username", key="login_user")
            pwd = st.text_input("Password", type="password", placeholder="Enter password", key="login_pass")
            
            if st.button("Access Portal", use_container_width=True):
                if not user or not pwd:
                    st.error("Please enter credentials.")
                else:
                    data = login(user.strip(), pwd.strip())
                    if data:
                        st.success("Access Granted! Loading session...")
                        st.rerun()
                    else:
                        st.error("Authentication failed. Invalid username or password.")
                        
            # Demo Credentials Expander
            with st.expander("🔑 Review Demo Accounts & Credentials"):
                st.markdown(
                    """
                    | Username | Password | Role | Description |
                    | :--- | :--- | :--- | :--- |
                    | **admin** | admin123 | **Admin** | System Configuration & Auditing |
                    | **psychologist** | psy123 | **Psychologist** | Full Clinical Dashboard Access |
                    | **assistant** | asst123 | **Assistant** | Scheduling & Basic Onboarding |
                    | **patient** | patient123 | **Patient** | Restricted Personal Chat & Assessment |
                    """
                )
                
        else:
            st.write("")
            reg_user = st.text_input("New Username", placeholder="e.g. john.doe", key="reg_user")
            reg_pwd = st.text_input("Password", type="password", placeholder="Enter secure password", key="reg_pwd")
            reg_name = st.text_input("Full Name", placeholder="e.g. John Doe", key="reg_name")
            reg_email = st.text_input("Email (Optional)", placeholder="john@email.com", key="reg_email")
            reg_role = st.selectbox("Role", ["Patient", "Psychologist", "Assistant"])
            
            if st.button("Submit Registration", use_container_width=True):
                if not reg_user.strip() or not reg_pwd.strip() or not reg_name.strip():
                    st.error("Username, password, and full name are required.")
                else:
                    success = register(reg_user.strip(), reg_pwd.strip(), reg_role, reg_name.strip(), reg_email.strip() or None)
                    if success:
                        st.success("Account created successfully! You can now log in.")
                    else:
                        st.error("Registration failed. Username may already be taken.")


def parse_patient_registry_csv(uploaded_file) -> list[dict] | None:
    try:
        raw_text = uploaded_file.getvalue().decode("utf-8-sig", errors="replace")
        buffer = io.StringIO(raw_text)
        df = pd.read_csv(buffer)
        required = {"name", "age", "language", "primary_concern"}
        if not required.issubset(df.columns):
            return None
        return df.to_dict(orient="records")
    except Exception:
        return None


def render_onboarding():
    st.subheader("Patient Intake & Onboarding")
    st.caption("Register new patient profiles individually or upload bulk clinical registries via CSV.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Individual Patient Intake")
        with st.form("new_patient_form", clear_on_submit=True):
            patient_id = st.text_input("Custom Patient ID (leave blank to auto-generate)")
            name = st.text_input("Patient Full Name", placeholder="John Doe")
            age = st.number_input("Patient Age", min_value=0, max_value=120, value=30)
            language = st.selectbox("Preferred Language", ["English", "Tamil"])
            concern = st.text_input("Primary Intake Concern", placeholder="Stress, anxiety, sleep issues")
            engagement = st.slider("Engagement Level (%)", 0, 100, 75)
            missed_sessions = st.number_input("Missed Sessions Count", min_value=0, value=0)
            risk_level = st.selectbox("Intake Risk Level", ["Low", "Moderate", "High", "Critical"])
            notes = st.text_area("Clinical Intake Notes")
            
            submit = st.form_submit_button("Register Patient Profile")
            
        if submit:
            if not name.strip():
                st.warning("Patient name is required.")
            else:
                p_data = {
                    "patient_id": patient_id.strip() if patient_id.strip() else None,
                    "name": name.strip(),
                    "age": age,
                    "language": language,
                    "primary_concern": concern.strip(),
                    "engagement": engagement,
                    "missed_sessions": missed_sessions,
                    "risk_level": risk_level,
                    "notes": notes.strip()
                }
                res = create_patient(p_data)
                if res:
                    st.success(f"Patient profile successfully created with ID: {res['patient_id']}")
                    st.session_state.active_patient = name.strip()
                else:
                    st.error("Failed to create patient profile. Check backend connection.")

    with col2:
        st.markdown("### Bulk CSV Registry Import")
        st.write("Upload a CSV file containing columns: `name`, `age`, `language`, `primary_concern`, `engagement`, `missed_sessions`, `notes`.")
        csv_file = st.file_uploader("Upload Patient CSV file", type=["csv"])
        
        if csv_file is not None:
            if st.button("Ingest CSV Registry"):
                records = parse_patient_registry_csv(csv_file)
                if records:
                    success_count = 0
                    for r in records:
                        p_data = {
                            "name": r.get("name"),
                            "age": int(r.get("age", 30)),
                            "language": r.get("language", "English"),
                            "primary_concern": r.get("primary_concern", ""),
                            "engagement": int(r.get("engagement", 70)),
                            "missed_sessions": int(r.get("missed_sessions", 0)),
                            "notes": r.get("notes", "")
                        }
                        res = create_patient(p_data)
                        if res:
                            success_count += 1
                    
                    if success_count > 0:
                        st.success(f"Successfully imported {success_count} patient profiles!")
                        log_audit("Imported patient CSV registry", csv_file.name, "info")
                    else:
                        st.error("All rows in CSV failed validation or exist.")
                else:
                    st.error("Invalid CSV format. Check column headers.")


def render_documents():
    st.subheader("Secure Document Management")
    st.caption("Upload and manage clinical protocols, treatment worksheets, and safety sheets.")
    
    files = st.file_uploader("Select files to upload", type=["txt", "md", "pdf", "docx"], accept_multiple_files=True)
    if files:
        success_count = 0
        for f in files:
            success = ingest_document(f.getvalue(), f.name)
            if success:
                success_count += 1
        if success_count > 0:
            st.success(f"Successfully uploaded and indexed {success_count} documents!")
            st.rerun()
            
    st.write("")
    st.markdown("### Indexed Guideline Documents")
    docs = get_documents()
    if docs:
        df = pd.DataFrame(docs)
        st.dataframe(df[["id", "name", "size_kb", "uploaded_at"]], use_container_width=True)
    else:
        st.info("No documents uploaded yet.")


def main():
    init_session()

    # Router Gate
    if not st.session_state.logged_in:
        render_login_page()
        return

    # User Profile Header
    role = st.session_state.user_role
    full_name = st.session_state.full_name
    
    # Glassmorphism header banner
    st.markdown(
        f'<div class="hero">'
        f'<h1>Mental Health Agentic Chatbot</h1>'
        f'<p>Enterprise Portal | <b>Staff:</b> {full_name} ({role}) | '
        f'<b>Context:</b> Language: {st.session_state.active_language} | '
        f'Patient: {st.session_state.active_patient or "None"}</p>'
        f'</div>',
        unsafe_allow_html=True
    )

    # 2. Sidebar Controls
    st.sidebar.header("Global Workspace Settings")
    st.session_state.active_language = st.sidebar.selectbox("Active Language Context", ["English", "Tamil"])
    
    # Select Patient Context
    patients = get_patients()
    patient_names = [p["name"] for p in patients]
    
    if role == "Patient":
        st.session_state.active_patient = st.session_state.username
    else:
        patient_options = ["(none)"] + patient_names
        selected_patient = st.session_state.get("active_patient") or "(none)"
        if selected_patient not in patient_options:
            selected_patient = "(none)"
            
        chosen_patient = st.sidebar.selectbox(
            "Selected Patient",
            patient_options,
            index=patient_options.index(selected_patient)
        )
        st.session_state.active_patient = None if chosen_patient == "(none)" else chosen_patient

    # Consent Check
    st.session_state.consent = st.sidebar.checkbox(
        "Consent Recorded",
        value=st.session_state.consent,
        help="Required before screening workflows are executed."
    )

    st.sidebar.markdown("---")
    st.sidebar.header("Portal Modules")

    # Define menu options based on Roles
    if role == "Patient":
        menu = {
            "Dashboard": render_dashboard,
            "Take Screening": render_assessment,
            "Chat Support": render_chat,
            "Appointments": render_scheduling
        }
    elif role == "Assistant":
        menu = {
            "Dashboard": render_dashboard,
            "Patient Onboarding": render_onboarding,
            "Appointments": render_scheduling,
            "Upload Documents": render_documents
        }
    elif role == "Psychologist":
        menu = {
            "Dashboard": render_dashboard,
            "Psychometric Screening": render_assessment,
            "Chat Agent": render_chat,
            "Voice Dialogue": render_voice_chat,
            "RAG Search": render_rag_assistant,
            "Scheduling": render_scheduling,
            "Clinical Reports": render_reports,
            "Progress Tracking": render_progress,
            "Retention Insights": render_retention
        }
    else:  # Admin
        menu = {
            "Dashboard": render_dashboard,
            "Patient Onboarding": render_onboarding,
            "Appointments": render_scheduling,
            "Psychometric Screening": render_assessment,
            "Chat Agent": render_chat,
            "Voice Dialogue": render_voice_chat,
            "RAG Search": render_rag_assistant,
            "Clinical Reports": render_reports,
            "Progress Tracking": render_progress,
            "Upload Documents": render_documents,
            "Retention Insights": render_retention,
            "Admin Panel": render_admin
        }

    # Sidebar Navigation radio selector
    page = st.sidebar.radio("Navigate", list(menu.keys()), label_visibility="collapsed")

    st.sidebar.markdown("---")
    if st.sidebar.button("Logout of Portal", use_container_width=True):
        logout()
        st.rerun()

    # Render Active Page view
    menu[page]()

    st.markdown("---")
    st.caption("🔒 HIPAA Staging Compliance. Clinical decision helper only, not a diagnostics utility.")


if __name__ == "__main__":
    main()
