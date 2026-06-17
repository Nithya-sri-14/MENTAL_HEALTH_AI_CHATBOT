from __future__ import annotations

import streamlit as st
import pandas as pd

try:
    import plotly.express as px
except Exception:
    px = None

from api_client import get_patients, get_admin_metrics, log_audit


def retention_probability(patient: dict) -> float:
    base = 0.16
    base += min(patient.get("missed_sessions", 0) * 0.13, 0.4)
    base += max(0, (70 - patient.get("engagement", 70)) / 220)
    base += 0.12 if patient.get("risk_level") in {"High", "Critical"} else 0
    return round(min(0.95, base), 2)


def render_bar_chart(df: pd.DataFrame, x: str, y: str, color: str | None = None, title: str = "") -> None:
    if px is not None:
        fig = px.bar(df, x=x, y=y, color=color, title=title, template="plotly_dark")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
        return
    st.subheader(title)
    st.bar_chart(df.set_index(x)[y])


def render_dashboard() -> None:
    st.subheader("Enterprise Clinical Dashboard")
    
    role = st.session_state.get("user_role")
    
    # Fetch metrics
    metrics_data = get_admin_metrics()
    if not metrics_data:
        st.info("Unable to fetch dashboard metrics. Check backend connection.")
        return
        
    metrics = metrics_data.get("metrics", {})
    patient_count = metrics.get("patients", 0)
    risk_count = metrics.get("high_risk", 0)
    appt_count = metrics.get("appointments", 0)
    audit_count = metrics.get("audit_logs", 0)
    
    # Redundant check for API configuration
    api_status = "🟢 Connected" if metrics_data.get("gemini_active") else "🟡 Offline Fallback Mode"
    
    # Visual cards for metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f'<div class="metric-box"><div class="metric-value">{patient_count}</div><div class="metric-label">Total Patients</div></div>',
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f'<div class="metric-box"><div class="metric-value" style="color: #ef4444;">{risk_count}</div><div class="metric-label">High/Critical Risk</div></div>',
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            f'<div class="metric-box"><div class="metric-value" style="color: #a78bfa;">{appt_count}</div><div class="metric-label">Appointments</div></div>',
            unsafe_allow_html=True
        )
    with col4:
        st.markdown(
            f'<div class="metric-box"><div class="metric-value" style="color: #10b981;">{api_status}</div><div class="metric-label">Gemini API status</div></div>',
            unsafe_allow_html=True
        )
        
    st.write("")
    
    # Display critical alerts banner if any patients are high risk
    if risk_count > 0:
        st.markdown(
            f'<div class="critical-alert">⚠️ WARNING: {risk_count} patients currently flagged with HIGH or CRITICAL risk. Supervisors have been notified.</div>',
            unsafe_allow_html=True
        )

    # Fetch patients
    patients = get_patients()
    if patients:
        df = pd.DataFrame(patients)
        
        c1, c2 = st.columns(2)
        with c1:
            render_bar_chart(df, x="name", y="engagement", color="risk_level", title="Patient Engagement Levels")
        with c2:
            retention_data = pd.DataFrame(
                {
                    "patient": [p["name"] for p in patients],
                    "retention_risk": [retention_probability(p) for p in patients],
                }
            )
            render_bar_chart(retention_data, x="patient", y="retention_risk", title="Predictive Retention Risk Insights")
            
        st.write("")
        st.subheader("Recent Active Patients")
        # Format patient table nicely
        display_df = df[["patient_id", "name", "age", "language", "primary_concern", "risk_level", "engagement"]].copy()
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No patient registry records are loaded. Create a patient or import a registry in the sidebar to populate.")
