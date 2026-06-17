from __future__ import annotations

import streamlit as st
import pandas as pd
import requests
from api_client import get_admin_metrics, register, log_audit, API_BASE_URL


def render_admin() -> None:
    st.subheader("Admin Control & Auditing Panel")
    st.caption("Manage system configurations, user accounts, audit trails, and high-risk case escalations.")

    role = st.session_state.get("user_role")
    if role != "Admin":
        st.info("System configuration, user management, and audit logs are restricted to Admin accounts.")
        return

    # Fetch admin metrics data
    data = get_admin_metrics()
    if not data:
        st.error("Failed to load admin metrics. Verify backend connectivity.")
        return

    st.markdown("---")

    # Tabs for different admin tasks
    tab1, tab2, tab3, tab4 = st.tabs(["API Configurations", "Active Escalations", "Clinical Audit Logs", "User Accounts"])

    # 1. API Configurations
    with tab1:
        st.markdown("### LLM API Gateway Settings")
        st.write("Enable advanced clinical RAG, dialogue flows, and reporting summaries by adding your Gemini API key.")
        
        # Check current key configuration status
        is_active = data.get("gemini_active", False)
        status_text = "🟢 Active (Keys configured)" if is_active else "🔴 Inactive (Using Local Fallback Engine)"
        st.markdown(f"**Current Status:** {status_text}")
        
        # Form to update Gemini API Key
        new_key = st.text_input("Gemini API Key", type="password", help="Enters your GEMINI_API_KEY. It will be saved securely in the backend.")
        if st.button("Save API Configuration"):
            if not new_key.strip():
                st.warning("Key cannot be empty.")
            else:
                with st.spinner("Configuring API gateway..."):
                    try:
                        # Call backend to set key
                        res = requests.post(
                            f"{API_BASE_URL}/api/admin/config",
                            headers={"Authorization": f"Bearer {st.session_state.token}"},
                            json={"gemini_api_key": new_key.strip()}
                        )
                        if res.status_code == 200:
                            st.success("API Configuration successfully updated! Server reloaded.")
                            log_audit("Updated LLM API Configuration key", "GEMINI_API_KEY", "warning")
                            st.rerun()
                        else:
                            st.error("Failed to update key in backend server configuration.")
                    except Exception as e:
                        st.error(f"Error calling backend configuration: {e}")

    # 2. Active Escalations
    with tab2:
        st.markdown("### Pending Critical Escalations")
        st.write("The following patients have been flagged for supervisor/psychologist intervention due to high scoring or phrase analysis:")
        
        escalations = data.get("escalations", [])
        if escalations:
            df_esc = pd.DataFrame(escalations)
            display_esc = df_esc[["id", "patient_name", "reason", "severity", "status", "created_at"]].copy()
            st.dataframe(display_esc, use_container_width=True)
            
            # Resolve form
            st.write("")
            st.markdown("#### Resolve Case Escalation")
            esc_ids = [str(e["id"]) for e in escalations if e["status"] == "active"]
            if esc_ids:
                chosen_esc = st.selectbox("Select Case ID to Resolve", esc_ids)
                resolution_notes = st.text_input("Resolution Comments / Treatment Action Taken")
                if st.button("Mark Case as Resolved"):
                    try:
                        res = requests.post(
                            f"{API_BASE_URL}/api/admin/escalation/resolve",
                            headers={"Authorization": f"Bearer {st.session_state.token}"},
                            json={"escalation_id": int(chosen_esc), "notes": resolution_notes}
                        )
                        if res.status_code == 200:
                            st.success(f"Case Escalation {chosen_esc} resolved successfully.")
                            log_audit(f"Resolved clinical escalation case {chosen_esc}", resolution_notes, "info")
                            st.rerun()
                        else:
                            st.error("Failed to resolve escalation on backend.")
                    except Exception as e:
                        st.error(f"Error calling resolution: {e}")
            else:
                st.info("All escalation cases are resolved.")
        else:
            st.info("No active escalation cases found.")

    # 3. Clinical Audit Logs
    with tab3:
        st.markdown("### System Security & Audit Trails")
        st.write("Review immutable log entries of clinician actions, authentication logs, and data accesses:")
        
        audit_logs = data.get("audit_logs", [])
        if audit_logs:
            df_audit = pd.DataFrame(audit_logs)
            display_audit = df_audit[["id", "timestamp", "actor", "role", "action", "subject", "severity"]].copy()
            st.dataframe(display_audit, use_container_width=True)
        else:
            st.info("No audit logs recorded.")

    # 4. User Accounts
    with tab4:
        st.markdown("### User Account Management")
        st.write("Add new clinician, assistant, or patient accounts to the secure system registry:")
        
        # User creation form
        with st.form("create_user_form", clear_on_submit=True):
            username = st.text_input("Username / ID", placeholder="john.doe")
            password = st.text_input("Temporary Password", type="password", placeholder="••••••••")
            full_name = st.text_input("Full Name", placeholder="John Doe")
            email = st.text_input("Email Address", placeholder="john@clinic.com")
            user_role = st.selectbox("System Role", ["Psychologist", "Assistant", "Patient", "Admin"])
            
            submit = st.form_submit_button("Register Account")
            
        if submit:
            if not username.strip() or not password.strip() or not full_name.strip():
                st.warning("Username, password, and full name are required.")
            else:
                success = register(username.strip(), password.strip(), user_role, full_name.strip(), email.strip() or None)
                if success:
                    st.success(f"User account '{username}' successfully created!")
                    log_audit(f"Registered new user account: {username}", user_role, "warning")
                else:
                    st.error("Username already exists or database transaction failed.")
