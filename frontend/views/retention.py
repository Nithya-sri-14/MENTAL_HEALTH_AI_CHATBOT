from __future__ import annotations

import streamlit as st
import pandas as pd
from api_client import get_patients, get_patient_retention

try:
    import plotly.express as px
    import plotly.graph_objects as go
except Exception:
    px = None
    go = None


def render_gauge(probability: float, title: str = "Retention Probability") -> None:
    percentage = int(probability * 100)
    color = "#ef4444" if percentage < 45 else ("#f59e0b" if percentage < 75 else "#10b981")
    
    if go is not None:
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=percentage,
                domain={"x": [0, 1], "y": [0, 1]},
                title={"text": title, "font": {"size": 18, "color": "#f8fafc"}},
                number={"suffix": "%", "font": {"color": color, "size": 36}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#94a3b8"},
                    "bar": {"color": color},
                    "bgcolor": "rgba(30, 41, 59, 0.5)",
                    "borderwidth": 2,
                    "bordercolor": "#475569",
                    "steps": [
                        {"range": [0, 45], "color": "rgba(239, 68, 68, 0.1)"},
                        {"range": [45, 75], "color": "rgba(245, 158, 11, 0.1)"},
                        {"range": [75, 100], "color": "rgba(16, 185, 129, 0.1)"},
                    ],
                },
            )
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#f8fafc", "family": "Inter, sans-serif"},
            height=250,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        # Fallback if plotly not fully imported
        st.markdown(
            f'<div style="text-align:center; padding: 2rem; border-radius: 12px; background-color: rgba(30,41,59,0.4); border: 1px solid #334155;">'
            f'<div style="font-size: 1.1rem; color: #94a3b8; margin-bottom: 0.5rem;">{title}</div>'
            f'<div style="font-size: 3rem; font-weight: bold; color: {color};">{percentage}%</div>'
            f'</div>',
            unsafe_allow_html=True
        )


def simulate_retention_risk(engagement: int, missed: int, risk: str, negative_sentiment: bool) -> tuple[float, str, list[str]]:
    prob = 0.88
    factors = []
    
    if missed > 0:
        penalty = min(missed * 0.14, 0.45)
        prob -= penalty
        factors.append(f"Missed Sessions ({missed} missed)")
        
    if engagement < 50:
        prob -= 0.25
        factors.append(f"Low Engagement Index ({engagement}%)")
    elif engagement < 70:
        prob -= 0.10
        factors.append(f"Moderate Engagement Index ({engagement}%)")
    elif engagement > 85:
        prob += 0.05
        
    if risk == "Critical":
        prob -= 0.20
        factors.append("Critical Clinical Risk")
    elif risk == "High":
        prob -= 0.12
        factors.append("High Clinical Risk")
    elif risk == "Moderate":
        prob -= 0.05
        
    if negative_sentiment:
        prob -= 0.08
        factors.append("Negative Sentiment in Chat")
        
    prob = round(max(0.05, min(0.98, prob)), 2)
    
    if prob >= 0.75:
        level = "Low Churn Risk"
    elif prob >= 0.45:
        level = "Moderate Churn Risk"
    else:
        level = "High Churn Risk"
        
    return prob, level, factors


def render_retention() -> None:
    st.subheader("Predictive Patient Retention Insights")
    st.caption("AI-driven retention forecasting engine analyzes engagement history, attendance metrics, clinical risk, and patient sentiment to calculate dropout probabilities and recommend preemptive interventions.")

    # 1. Fetch Patients
    patients = get_patients()
    if not patients:
        st.info("No patients registered. Please onboard patients to generate retention metrics.")
        return

    patient_names = [p["name"] for p in patients]

    # Sidebar / Top Patient Context Selector
    col_sel, col_stats = st.columns([1, 2])
    with col_sel:
        selected_name = st.selectbox("Select Patient to Analyze", ["(Select Patient)"] + patient_names)
    
    # Pre-calculated retention probability helper for overview
    def local_ret_prob(p: dict) -> float:
        base = 0.88
        base -= min(p.get("missed_sessions", 0) * 0.14, 0.45)
        base += 0.05 if p.get("engagement", 70) > 85 else ( -0.25 if p.get("engagement", 70) < 50 else (-0.10 if p.get("engagement", 70) < 70 else 0) )
        base -= 0.20 if p.get("risk_level") == "Critical" else (0.12 if p.get("risk_level") == "High" else (0.05 if p.get("risk_level") == "Moderate" else 0))
        return round(max(0.05, min(0.98, base)), 2)

    if selected_name == "(Select Patient)":
        # Render Cohort Overview
        st.markdown("### Cohort Retention Risk Overview")
        
        # Build DataFrame of patient risks
        cohort_data = []
        for p in patients:
            prob = local_ret_prob(p)
            dropout_risk = round((1 - prob) * 100, 0)
            status = "Low Churn Risk" if prob >= 0.75 else ("Moderate Churn Risk" if prob >= 0.45 else "High Churn Risk")
            cohort_data.append({
                "Patient ID": p.get("patient_id", "N/A"),
                "Name": p["name"],
                "Engagement": f"{p['engagement']}%",
                "Missed Sessions": p["missed_sessions"],
                "Clinical Risk": p["risk_level"],
                "Retention Probability": f"{int(prob * 100)}%",
                "Dropout Risk": f"{int(dropout_risk)}%",
                "Risk Level": status
            })
        
        df_cohort = pd.DataFrame(cohort_data)
        
        # Color coding rows using st.dataframe styling or display normally
        st.dataframe(df_cohort, use_container_width=True)
        
        # Show a summary chart
        if px is not None:
            # Prepare chart data
            chart_df = pd.DataFrame({
                "Name": [p["name"] for p in patients],
                "Retention Probability (%)": [int(local_ret_prob(p) * 100) for p in patients],
                "Risk Level": ["Low Churn Risk" if local_ret_prob(p) >= 0.75 else ("Moderate Churn Risk" if local_ret_prob(p) >= 0.45 else "High Churn Risk") for p in patients]
            })
            fig = px.bar(
                chart_df,
                x="Name",
                y="Retention Probability (%)",
                color="Risk Level",
                color_discrete_map={
                    "Low Churn Risk": "#10b981",
                    "Moderate Churn Risk": "#f59e0b",
                    "High Churn Risk": "#ef4444"
                },
                title="Cohort Retention Probabilities",
                template="plotly_dark"
            )
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            
        return

    # A patient is selected
    st.markdown("---")
    
    # Call backend for real predictive insights (using Gemini if active)
    with st.spinner(f"Analyzing retention models for {selected_name}..."):
        insights = get_patient_retention(selected_name)

    if not insights:
        st.error("Failed to generate retention insights from backend.")
        return

    prob = insights.get("retention_probability", 0.8)
    churn_level = insights.get("churn_risk_level", "Low")
    risk_factors = insights.get("risk_factors", [])
    narrative = insights.get("analysis_narrative", "")
    recommendations = insights.get("recommendations", [])

    c1, c2 = st.columns([1, 1.5])
    
    with c1:
        render_gauge(prob, f"Patient Retention Score ({selected_name})")
        
        # Status Card
        color = "#ef4444" if churn_level == "High" else ("#f59e0b" if churn_level == "Moderate" else "#10b981")
        st.markdown(
            f'<div class="compact-card" style="border-left: 5px solid {color}; margin-top: 1rem;">'
            f'<div style="font-size:0.9rem; color:#94a3b8;">SYSTEM STATUS</div>'
            f'<div style="font-size:1.6rem; font-weight:bold; color:{color};">{churn_level} Churn Risk</div>'
            f'<div style="font-size:0.95rem; color:#cbd5e1; margin-top:0.5rem;">Dropout Risk: <b>{int((1-prob)*100)}%</b></div>'
            f'</div>',
            unsafe_allow_html=True
        )

    with c2:
        st.markdown("### 🤖 Agentic Predictive Forecast")
        st.write(narrative)
        
        st.markdown("### 📋 Preemptive Action Plan")
        for rec in recommendations:
            st.markdown(f"- 🔸 {rec}")

    st.markdown("---")
    
    col_sim_controls, col_sim_output = st.columns([1, 1.2])
    
    with col_sim_controls:
        st.markdown("### 🎛️ Real-Time Retention Simulator")
        st.write("Simulate changes in clinical and engagement variables to assess dynamic risk fluctuations.")
        
        # Get active values for selected patient
        patient_obj = next((p for p in patients if p["name"] == selected_name), {})
        
        sim_engagement = st.slider("Simulated Engagement Index (%)", 0, 100, int(patient_obj.get("engagement", 70)))
        sim_missed = st.slider("Simulated Missed Sessions", 0, 10, int(patient_obj.get("missed_sessions", 0)))
        sim_risk = st.selectbox("Simulated Clinical Risk Level", ["Low", "Moderate", "High", "Critical"], index=["Low", "Moderate", "High", "Critical"].index(patient_obj.get("risk_level", "Low")))
        sim_sentiment = st.checkbox("Negative Sentiment Detected in Recent Transcripts", value=False)
        
    with col_sim_output:
        st.markdown("### 📊 Simulated Output Analysis")
        st.write("Calculated projection from the predictive risk models:")
        
        # Calculate simulated parameters
        sim_prob, sim_level, sim_factors = simulate_retention_risk(sim_engagement, sim_missed, sim_risk, sim_sentiment)
        
        # Simulated Gauge
        render_gauge(sim_prob, "Simulated Retention Score")
        
        sim_color = "#ef4444" if sim_level == "High Churn Risk" else ("#f59e0b" if sim_level == "Moderate Churn Risk" else "#10b981")
        st.markdown(
            f'<div style="text-align:center; font-size:1.3rem; font-weight:bold; color:{sim_color}; margin-top: 0.5rem;">'
            f'Status: {sim_level}'
            f'</div>',
            unsafe_allow_html=True
        )
        
        # Simulated Risk factors list
        st.markdown("**Identified Sim-Risk Markers:**")
        if sim_factors:
            for f in sim_factors:
                st.markdown(f"- ⚠️ {f}")
        else:
            st.markdown("- ✅ No significant risk factors identified.")
