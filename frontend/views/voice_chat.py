from __future__ import annotations

import streamlit as st
import pandas as pd
import requests
from api_client import (
    get_patients,
    get_voice_sessions,
    get_voice_turns,
    start_voice_session,
    send_voice,
    API_BASE_URL
)


def render_voice_chat() -> None:
    st.subheader("Voice Chat Support")
    st.caption("Audio transcription and spoken response flow for clinical dialogue verification.")

    role = st.session_state.get("user_role")
    language = st.session_state.get("active_language", "English")

    # 1. Select Patient Context
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
            
        chosen = st.selectbox("Voice Session Patient Context", patient_options, index=patient_options.index(selected))
        if chosen == "(none)":
            st.warning("Please select a patient in the dropdown or sidebar to start voice chat.")
            return
        active_patient = chosen
        st.session_state.active_patient = chosen

    st.markdown("---")

    # Voice session management
    col_a, col_b = st.columns([2, 1])
    with col_a:
        continuous_mode = st.toggle(
            "Continuous session tracking",
            value=st.session_state.get("voice_continuous_mode", True),
            key="voice_continuous_mode"
        )
    with col_b:
        if st.button("Start New Voice Session"):
            session_id = start_voice_session(active_patient, language, continuous_mode)
            if session_id:
                st.session_state.active_voice_session_id = session_id
                st.success(f"Started session {session_id}")
                st.rerun()

    # Fetch and list voice sessions
    sessions = get_voice_sessions(active_patient)
    active_session_id = st.session_state.get("active_voice_session_id")
    
    if sessions:
        session_labels = [f"{s['session_id']} | {s['patient_name']} | {s['language']} | {s['status']}" for s in sessions]
        
        # Determine index of active session
        active_idx = 0
        if active_session_id:
            for i, s in enumerate(sessions):
                if s["session_id"] == active_session_id:
                    active_idx = i
                    break
        else:
            # Set first session as active
            st.session_state.active_voice_session_id = sessions[0]["session_id"]
            active_session_id = sessions[0]["session_id"]

        chosen_label = st.selectbox("Select Active Voice Session", session_labels, index=active_idx)
        selected_session = sessions[session_labels.index(chosen_label)]
        st.session_state.active_voice_session_id = selected_session["session_id"]
        active_session_id = selected_session["session_id"]
    else:
        st.info("No active voice sessions. Click 'Start New Voice Session' above to begin.")
        return

    # Display session dialogue timeline
    turns = get_voice_turns(active_session_id)
    if turns:
        st.markdown("### Session Dialogue History")
        for turn in turns:
            align = "left" if turn["speaker"] == "patient" else "right"
            color = "#a78bfa" if turn["speaker"] == "patient" else "#38bdf8"
            speaker_name = "Patient" if turn["speaker"] == "patient" else "Bot Assistant"
            
            st.markdown(
                f'<div class="compact-card" style="border-left: 4px solid {color}; margin-bottom: 0.8rem;">'
                f'<div style="font-size:0.75rem; color:#94a3b8; font-weight:600; margin-bottom:0.25rem;">'
                f'{speaker_name} | {turn["timestamp"]}</div>'
                f'<div style="font-size:0.95rem;">{turn["text"]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            
    # Audio capture tools
    st.write("")
    st.markdown("### record or Upload audio")
    
    auto_speak = st.checkbox("Auto-speak reply", value=True, key="voice_autospeak")
    
    # Check for streamlit's native audio_input
    recorded_audio = None
    if hasattr(st, "audio_input"):
        recorded_audio = st.audio_input("Record your voice")

    fallback_audio = st.file_uploader("Or upload WAV/MP3 recording", type=["wav", "mp3"])
    
    active_audio_bytes = None
    filename = "input.wav"
    
    if recorded_audio is not None:
        active_audio_bytes = recorded_audio.getvalue()
        filename = "recording.wav"
    elif fallback_audio is not None:
        active_audio_bytes = fallback_audio.getvalue()
        filename = fallback_audio.name

    if st.button("Send Audio Message") and active_audio_bytes:
        with st.spinner("Uploading and transcribing spoken audio..."):
            res = send_voice(active_audio_bytes, filename, active_patient, language, active_session_id)
            
        if res:
            st.success("Dialogue processed successfully.")
            st.markdown(f"**Your Speech Transcript:** \"{res['transcript']}\"")
            st.markdown(f"**Bot Reply:** {res['reply']}")
            
            if res.get("emotion"):
                st.info(f"🎭 **Voice Sentiment Profile:** `{res['emotion']}`")
                
            if res.get("risk") == "high":
                st.error("🚨 CRITICAL ALERT: High-risk keywords identified. Crisis routing triggered.")
                
            if auto_speak and res.get("audio_file"):
                st.audio(f"{API_BASE_URL}/api/voice/audio/{res['audio_file']}")
                
            # Rerun to refresh dialogue turns timeline
            st.rerun()
        else:
            st.error("Audio processing failed at the backend server.")
