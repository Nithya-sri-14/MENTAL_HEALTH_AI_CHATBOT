from __future__ import annotations

import streamlit as st
import pandas as pd

try:
    import plotly.express as px
except Exception:
    px = None

from api_client import get_patients, get_sessions


def render_line_chart(df: pd.DataFrame, x: str, y: str, color: str | None = None, title: str = "") -> None:
    if px is not None:
        fig = px.line(df, x=x, y=y, color=color, markers=True, title=title, template="plotly_dark")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
        return
    st.subheader(title)
    st.line_chart(df.set_index(x)[y])


def render_progress() -> None:
    st.subheader("Patient Progress & Assessment Trends")
    st.caption("Track patient recovery rates, engagement histories, and screening trajectories.")

    role = st.session_state.get("user_role")

    # 1. Select Patient
    patients = get_patients()
    patient_names = [p["name"] for p in patients]
    
    if role == "Patient":
        active_patient = st.session_state.get("username")
        if active_patient not in patient_names:
            st.warning("You do not have an active patient record. Please contact an administrator.")
            return
    else:
        patient_options = ["(none)"] + patient_names
        selected = st.session_state.get("active_patient") or "(none)"
        if selected not in patient_options:
            selected = "(none)"
            
        chosen = st.selectbox("Select Patient to Analyze", patient_options, index=patient_options.index(selected))
        if chosen == "(none)":
            st.warning("Please select a patient in the dropdown or sidebar to view progress logs.")
            return
        active_patient = chosen
        st.session_state.active_patient = chosen

    # Fetch patient profile details
    patient = next((p for p in patients if p["name"] == active_patient), None)
    if not patient:
        st.error("Patient profile not found.")
        return

    st.markdown("---")

    # Display profile summary cards
    st.markdown("### Profile Summary")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<div class="compact-card">'
            f'<b>Patient ID:</b> {patient.get("patient_id", "N/A")}<br/>'
            f'<b>Name:</b> {patient["name"]}<br/>'
            f'<b>Age:</b> {patient["age"]}<br/>'
            f'<b>Preferred Language:</b> {patient["language"]}'
            f'</div>',
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f'<div class="compact-card">'
            f'<b>Primary Concern:</b> {patient["primary_concern"]}<br/>'
            f'<b>Clinical Risk Level:</b> {patient["risk_level"]}<br/>'
            f'<b>Engagement Index:</b> {patient["engagement"]}%<br/>'
            f'<b>Missed Sessions:</b> {patient["missed_sessions"]}'
            f'</div>',
            unsafe_allow_html=True
        )
    with c3:
        # Simple retention prediction metric
        from views.dashboard import retention_probability
        ret_risk = int(retention_probability(patient) * 100)
        color = "#10b981" if ret_risk < 30 else ("#f59e0b" if ret_risk < 60 else "#ef4444")
        st.markdown(
            f'<div class="compact-card" style="text-align:center;">'
            f'<b>Predictive Retention Dropout Risk</b>'
            f'<h2 style="color:{color}; margin-top:0.4rem;">{ret_risk}%</h2>'
            f'<div style="font-size:0.8rem; color:#94a3b8; margin-top:0.3rem;">💡 Detailed forecast available in Retention Insights</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    # 2. Render Trends Line Graph
    sessions = get_sessions(active_patient)
    if sessions:
        st.write("")
        st.markdown("### Assessment Score Trend Line")
        df = pd.DataFrame(sessions)
        
        # Sort by date ascending for trend line graph
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        
        render_line_chart(df, x="date", y="score", color=None, title=f"Symptom Index Timeline ({active_patient})")
        
        st.write("")
        st.markdown("### Historical Screening Timeline Logs")
        display_df = df[["id", "date", "risk_level", "score", "summary"]].copy()
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No historical screening records found for this patient context.")
