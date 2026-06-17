from __future__ import annotations

import requests
import streamlit as st
from typing import Any

API_BASE_URL = "http://127.0.0.1:8000"


def get_headers() -> dict[str, str]:
    headers = {}
    token = st.session_state.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def login(username: str, password: str) -> dict[str, Any] | None:
    try:
        response = requests.post(f"{API_BASE_URL}/api/auth/login", json={"username": username, "password": password})
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            st.session_state.username = data["username"]
            st.session_state.user_role = data["role"]
            st.session_state.full_name = data["full_name"]
            st.session_state.email = data.get("email")
            st.session_state.logged_in = True
            
            # Log audit
            log_audit(f"Logged in successfully", username, "info")
            return data
        return None
    except Exception:
        return None


def register(username: str, password: str, role: str, full_name: str, email: str | None = None) -> bool:
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/auth/register",
            json={
                "username": username,
                "password": password,
                "role": role,
                "full_name": full_name,
                "email": email
            }
        )
        return response.status_code == 200
    except Exception:
        return False


def logout() -> None:
    username = st.session_state.get("username", "Unknown")
    log_audit("Logged out", username, "info")
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.full_name = None
    st.session_state.email = None
    st.session_state.logged_in = False
    st.session_state.active_patient = None


def log_audit(action: str, subject: str, severity: str = "info") -> None:
    try:
        actor = st.session_state.get("username", "System")
        role = st.session_state.get("user_role", "System")
        requests.post(
            f"{API_BASE_URL}/api/admin/audit",
            headers=get_headers(),
            json={
                "actor": actor,
                "role": role,
                "action": action,
                "subject": subject,
                "severity": severity
            }
        )
    except Exception:
        pass


def get_patients() -> list[dict[str, Any]]:
    try:
        response = requests.get(f"{API_BASE_URL}/api/patients", headers=get_headers())
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def create_patient(data: dict[str, Any]) -> dict[str, Any] | None:
    try:
        response = requests.post(f"{API_BASE_URL}/api/patients", headers=get_headers(), json=data)
        if response.status_code == 200:
            log_audit("Created patient record", data["name"], "info")
            return response.json()
        return None
    except Exception:
        return None


def update_patient(name: str, data: dict[str, Any]) -> bool:
    try:
        response = requests.put(f"{API_BASE_URL}/api/patients/{name}", headers=get_headers(), json=data)
        if response.status_code == 200:
            # Check if risk escalated
            severity = "warning" if data.get("risk_level") in {"High", "Critical"} else "info"
            log_audit(f"Updated patient details (Risk: {data.get('risk_level')})", name, severity)
            return True
        return False
    except Exception:
        return False


def get_appointments() -> list[dict[str, Any]]:
    try:
        response = requests.get(f"{API_BASE_URL}/api/appointments", headers=get_headers())
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def create_appointment(data: dict[str, Any]) -> dict[str, Any] | None:
    try:
        response = requests.post(f"{API_BASE_URL}/api/appointments", headers=get_headers(), json=data)
        if response.status_code == 200:
            log_audit(f"Scheduled appointment for {data['patient_name']}", data["clinician"], "info")
            return response.json()
        return None
    except Exception:
        return None


def send_chat(patient_name: str, message: str, language: str, role: str) -> dict[str, Any] | None:
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/chat",
            headers=get_headers(),
            json={
                "patient_name": patient_name,
                "message": message,
                "language": language,
                "role": role
            }
        )
        if response.status_code == 200:
            res_data = response.json()
            severity = "warning" if res_data.get("risk") == "high" else "info"
            log_audit(f"Exchanged chat message (Risk: {res_data.get('risk')})", patient_name, severity)
            return res_data
        return None
    except Exception:
        return None


def get_chat_history(patient_name: str) -> list[dict[str, Any]]:
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/chat/history",
            headers=get_headers(),
            params={"patient_name": patient_name}
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def send_voice(file_bytes: bytes, file_name: str, patient_name: str, language: str, session_id: str | None = None) -> dict[str, Any] | None:
    try:
        files = {"file": (file_name, file_bytes, "audio/wav")}
        data = {
            "patient_name": patient_name,
            "language": language,
        }
        if session_id:
            data["session_id"] = session_id

        response = requests.post(
            f"{API_BASE_URL}/api/voice",
            headers=get_headers(),
            files=files,
            data=data
        )
        if response.status_code == 200:
            res_data = response.json()
            severity = "warning" if res_data.get("risk") == "high" else "info"
            log_audit(f"Processed voice dialogue (Risk: {res_data.get('risk')})", patient_name, severity)
            return res_data
        return None
    except Exception:
        return None


def get_voice_sessions(patient_name: str | None = None) -> list[dict[str, Any]]:
    try:
        params = {}
        if patient_name:
            params["patient_name"] = patient_name
        response = requests.get(f"{API_BASE_URL}/api/voice/sessions", headers=get_headers(), params=params)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_voice_turns(session_id: str) -> list[dict[str, Any]]:
    try:
        response = requests.get(f"{API_BASE_URL}/api/voice/sessions/{session_id}/turns", headers=get_headers())
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def start_voice_session(patient_name: str, language: str, continuous_mode: bool = True) -> str | None:
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/voice/sessions",
            headers=get_headers(),
            json={
                "patient_name": patient_name,
                "language": language,
                "continuous_mode": continuous_mode
            }
        )
        if response.status_code == 200:
            return response.json().get("session_id")
        return None
    except Exception:
        return None


def query_rag(q: str) -> dict[str, Any] | None:
    try:
        response = requests.get(f"{API_BASE_URL}/api/rag/search", headers=get_headers(), params={"q": q})
        if response.status_code == 200:
            log_audit("Queried RAG knowledge assistant", q[:30], "info")
            return response.json()
        return None
    except Exception:
        return None


def ingest_document(file_bytes: bytes, file_name: str) -> bool:
    try:
        files = {"file": (file_name, file_bytes)}
        response = requests.post(f"{API_BASE_URL}/api/rag/ingest", headers=get_headers(), files=files)
        return response.status_code == 200
    except Exception:
        return False


def get_documents() -> list[dict[str, Any]]:
    try:
        response = requests.get(f"{API_BASE_URL}/api/documents", headers=get_headers())
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_questions(language: str) -> list[dict[str, Any]]:
    try:
        response = requests.get(f"{API_BASE_URL}/api/assessment/questions", params={"language": language})
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def submit_assessment(patient_name: str, answers: dict[str, int], notes: str, language: str) -> dict[str, Any] | None:
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/assessment/submit",
            headers=get_headers(),
            json={
                "patient_name": patient_name,
                "answers": answers,
                "notes": notes,
                "language": language
            }
        )
        if response.status_code == 200:
            res_data = response.json()
            severity = "warning" if res_data.get("escalated") else "info"
            log_audit(f"Submitted screening assessment (Escalated: {res_data.get('escalated')})", patient_name, severity)
            return res_data
        return None
    except Exception:
        return None


def get_sessions(patient_name: str | None = None) -> list[dict[str, Any]]:
    try:
        params = {}
        if patient_name:
            params["patient_name"] = patient_name
        response = requests.get(f"{API_BASE_URL}/api/sessions", headers=get_headers(), params=params)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_reports(patient_name: str | None = None) -> list[dict[str, Any]]:
    try:
        params = {}
        if patient_name:
            params["patient_name"] = patient_name
        response = requests.get(f"{API_BASE_URL}/api/reports", headers=get_headers(), params=params)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def save_report(patient_name: str, report_text: str, risk_level: str) -> bool:
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/reports",
            headers=get_headers(),
            json={
                "patient_name": patient_name,
                "report_text": report_text,
                "risk_level": risk_level
            }
        )
        return response.status_code == 200
    except Exception:
        return False


def get_admin_metrics() -> dict[str, Any] | None:
    try:
        response = requests.get(f"{API_BASE_URL}/api/admin/metrics", headers=get_headers())
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def get_patient_retention(name: str) -> dict[str, Any] | None:
    try:
        response = requests.get(f"{API_BASE_URL}/api/patients/{name}/retention", headers=get_headers())
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

