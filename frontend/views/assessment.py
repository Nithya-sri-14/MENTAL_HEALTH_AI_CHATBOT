from __future__ import annotations

import streamlit as st
from api_client import get_questions, submit_assessment, get_patients


def render_assessment() -> None:
    st.subheader("Psychological Assessment Agent")
    st.caption("This screening tool scores patient symptoms over the last 7 days without formulating a medical diagnosis.")
    
    # Check role features
    role = st.session_state.get("user_role")
    
    # Setup active patient selection
    patients = get_patients()
    patient_names = [p["name"] for p in patients]
    
    if role == "Patient":
        # Patients are locked to themselves
        active_patient = st.session_state.get("username")
        if active_patient not in patient_names:
            st.warning("You do not have an active patient record. Please contact an administrator.")
            return
    else:
        patient_options = ["(none)"] + patient_names
        selected = st.session_state.get("active_patient") or "(none)"
        if selected not in patient_options:
            selected = "(none)"
            
        chosen = st.selectbox("Select Patient to Screen", patient_options, index=patient_options.index(selected))
        if chosen == "(none)":
            st.warning("Please select a patient in the dropdown or sidebar to start the screening.")
            return
        active_patient = chosen
        st.session_state.active_patient = chosen

    # Check consent
    if not st.session_state.get("consent"):
        st.warning("⚠️ Warning: Clinical consent must be recorded in the sidebar before starting the screening.")
        return

    st.markdown("---")
    language = st.session_state.get("active_language", "English")
    questions = get_questions(language)
    
    if not questions:
        st.error("Could not fetch screening questions from backend.")
        return

    # Render questions one by one or as a list. A list is much cleaner in a web form context!
    answers = {}
    st.markdown("### Respond to the following questions:")
    for q in questions:
        # Check if we have a previous answer in session state
        prev_ans = st.session_state.get(f"ans_{q['id']}", 2)
        ans = st.slider(
            q["prompt"],
            min_value=0,
            max_value=4,
            value=int(prev_ans),
            key=f"ans_{q['id']}",
            help="0 = Not at all, 1 = Several days, 2 = More than half the days, 3 = Nearly every day, 4 = Severe impact"
        )
        answers[q["id"]] = ans
        
    st.write("")
    clinical_notes = st.text_area(
        "Clinical Intake/Session Notes",
        value="",
        placeholder="Enter patient transcript or clinical observations here. The backend NLP engine will analyze this text for risk factors.",
        height=140
    )

    if st.button("Submit Assessment & Calculate Scores"):
        with st.spinner("Processing clinical metrics..."):
            res = submit_assessment(active_patient, answers, clinical_notes, language)
            
        if res:
            st.success("Assessment completed successfully!")
            
            scorecard = res["scorecard"]
            text_risk = res["text_risk"]
            recs = res["recommendations"]
            summary = res["summary"]
            escalated = res["escalated"]
            
            # Show results cards
            st.markdown("### Screening Results")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(
                    f'<div class="compact-card">'
                    f'<h4>Symptom Scorecard</h4>'
                    f'<p><b>Stress weight score:</b> {scorecard["stress"]}/12</p>'
                    f'<p><b>Sleep weight score:</b> {scorecard["sleep"]}/8</p>'
                    f'<p><b>Anxiety weight score:</b> {scorecard["anxiety"]}/12</p>'
                    f'<p><b>Mood weight score:</b> {scorecard["mood"]}/12</p>'
                    f'<p><b>Function weight score:</b> {scorecard["function"]}/8</p>'
                    f'<h3 style="margin-top:1rem;">Total Score: {scorecard["total"]}/48</h3>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with c2:
                # Severity-specific color
                color = "#22c55e" if scorecard["risk_level"] == "Low" else (
                    "#eab308" if scorecard["risk_level"] == "Moderate" else (
                        "#f97316" if scorecard["risk_level"] == "High" else "#ef4444"
                    )
                )
                st.markdown(
                    f'<div class="compact-card">'
                    f'<h4>Clinical Safety Assessment</h4>'
                    f'<p><b>Calculated Risk Level:</b> <span style="color:{color}; font-weight:700;">{scorecard["risk_level"]}</span></p>'
                    f'<p><b>NLP Risk Score:</b> {text_risk["score"]}% ({text_risk["risk_level"]} Risk)</p>'
                    f'<p><b>Risk Signals:</b> {", ".join(text_risk["signals"]) if text_risk["signals"] else "None detected"}</p>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                
            if escalated:
                st.error("🚨 CRITICAL ALERT: Clinical safety threshold exceeded. Case flagged for supervisor review.")

            st.write("")
            st.markdown("### Session Summary & Coping Steps")
            st.write(summary)
            
            st.write("")
            st.markdown("### Treatment Recommendations")
            for r in recs:
                st.markdown(f"- {r}")

            if res.get("multi_agent_trace"):
                st.write("")
                with st.expander("🧠 CrewAI / LangGraph Multi-Agent Clinical Team Trace"):
                    for msg in res["multi_agent_trace"]:
                        st.markdown(
                            f'<div class="compact-card" style="border-left: 4px solid #a78bfa; margin-bottom: 0.8rem;">'
                            f'<b>Agent:</b> {msg["agent_name"]} ({msg["role"]})<br/>'
                            f'<b>Thought:</b> {msg["thought"]}<br/>'
                            f'<b>Action:</b> <code>{msg["action"]}</code><br/>'
                            f'<b>Output:</b> {msg["result"]}'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                
            # Clear answer state cache
            for q in questions:
                if f"ans_{q['id']}" in st.session_state:
                    del st.session_state[f"ans_{q['id']}"]
        else:
            st.error("Failed to submit screening. Please verify backend connectivity.")
