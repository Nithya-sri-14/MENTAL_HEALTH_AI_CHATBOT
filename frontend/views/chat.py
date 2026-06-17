from __future__ import annotations

import streamlit as st
import pandas as pd
import requests
from api_client import get_patients, send_chat, get_chat_history, API_BASE_URL


def render_chat() -> None:
    st.subheader("💬 Multi-Language Conversation Agent")
    st.caption("Empathetic assistant support for patients. Clinicians can review histories or participate in mock sessions.")
    
    role = st.session_state.get("user_role")
    language = st.session_state.get("active_language", "English")
    
    # 1. Select Active Patient
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
            
        chosen = st.selectbox("Conversation Patient Context", patient_options, index=patient_options.index(selected))
        if chosen == "(none)":
            st.warning("Please select a patient in the dropdown or sidebar to start the chat.")
            return
        active_patient = chosen
        st.session_state.active_patient = chosen

    st.markdown("---")
    
    # Options and Voice Input Panel in columns
    col_settings, col_audio = st.columns([1, 1.5])
    
    auto_speak = True
    with col_settings:
        st.write("⚙️ **Chat Settings**")
        auto_speak = st.checkbox("Auto-speak reply (Audio Synthesis)", value=True)
        st.markdown(f"**Preferred Language:** `{language}`")
        st.markdown(f"**User Role:** `{role}`")
        
    with col_audio:
        st.write("🎙️ **Voice Message Input (Optional)**")
        audio_file = st.file_uploader("Upload audio recording to transcribe", type=["wav", "mp3", "flac"], key="chat_voice_uploader")
        
        if audio_file is not None:
            if st.button("Transcribe and Send Voice Msg"):
                with st.spinner("Decoding audio and transcribing..."):
                    try:
                        files = {"file": (audio_file.name, audio_file.getvalue(), "audio/wav")}
                        data = {"patient_name": active_patient, "language": language}
                        headers = {}
                        token = st.session_state.get("token")
                        if token:
                            headers["Authorization"] = f"Bearer {token}"
                        res = requests.post(f"{API_BASE_URL}/api/voice", headers=headers, files=files, data=data)
                        if res.status_code == 200:
                            res_data = res.json()
                            transcribed_text = res_data.get("transcript", "")
                            
                            # Send transcribed text as chat message
                            if transcribed_text.strip():
                                chat_res = send_chat(active_patient, transcribed_text, language, role)
                                if chat_res:
                                    st.success(f"Voice message sent: \"{transcribed_text}\"")
                                    if auto_speak and chat_res.get("audio_file"):
                                        st.audio(f"{API_BASE_URL}/api/voice/audio/{chat_res['audio_file']}")
                                    st.rerun()
                            else:
                                st.warning("Audio transcribed to empty text.")
                        else:
                            st.error("Audio transcription failed at the backend server.")
                    except Exception as e:
                        st.error(f"Error during audio upload: {e}")

    st.markdown("### Chat History Timeline")
    
    # Fetch chat history
    history = get_chat_history(active_patient)
    
    # Render chat bubbles in chronological order
    if history:
        for chat in reversed(history[:20]):
            with st.chat_message("user", avatar="👤"):
                st.markdown(chat.get("message"))
                
            if chat.get("reply"):
                with st.chat_message("assistant", avatar="🧠"):
                    st.markdown(chat.get("reply"))
                    
                    # Sentiment/Risk metadata flags
                    meta_signals = []
                    if chat.get("risk_level") == "high":
                        meta_signals.append("🚨 **Escalated Risk**")
                    if meta_signals:
                        st.caption(" | ".join(meta_signals))
    else:
        st.info("No prior conversation history found for this patient context. Start typing below to begin.")

    # Chat input at the bottom
    if prompt := st.chat_input("Ask a question or type a message..."):
        # Instantly render user message
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
            
        with st.spinner("Generating clinical-grade response..."):
            res = send_chat(active_patient, prompt, language, role)
            
        if res:
            # Render assistant message
            with st.chat_message("assistant", avatar="🧠"):
                st.markdown(res["reply"])
                
                # Show sentiment and risk alerts if any
                if res.get("emotion"):
                    st.caption(f"🎭 **Detected Sentiment:** {res['emotion']}")
                if res.get("risk") == "high":
                    st.error("🚨 CRITICAL WARNING: Self-harm or crisis patterns detected. Escalation triggered.")
                    
                if auto_speak and res.get("audio_file"):
                    st.audio(f"{API_BASE_URL}/api/voice/audio/{res['audio_file']}")
            
            st.rerun()
