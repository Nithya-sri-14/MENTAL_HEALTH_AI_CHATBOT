from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import APP_NAME, APP_TAGLINE, ROLES, SAFE_GUARDRAILS, PATIENT_COLUMNS
from .database import init_db, get_db_connection, hash_password
from .auth import verify_password, get_password_hash, create_access_token, get_current_user_payload
from .governance import redact_sensitive_text, detect_high_risk, moderation_check, audit_event, should_escalate, detect_emotion
from .orchestrator import score_answers, risk_from_text, recommendations, build_report, psychometric_walkthrough
from .gemini_service import generate_chat_reply, is_gemini_configured, get_api_key
from .rag import build_default_rag_store, KnowledgeItem, load_document_text
from .voice import transcribe_audio_bytes, synthesize_speech, tts_language_code, tune_tamil_tts_text
from .storage import save_bytes, ARTIFACTS_DIR, KB_DIR
from .retention_service import predict_retention

app = FastAPI(title=APP_NAME, description=APP_TAGLINE, version="1.0.0")

# Enable CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global RAG store instance
rag_store = build_default_rag_store()


@app.on_event("startup")
def on_startup():
    init_db()
    # Reload local files into RAG store
    rag_store.load_local_files()


# Pydantic Schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str
    full_name: str
    email: str | None = None


class PatientCreate(BaseModel):
    patient_id: str | None = None
    name: str
    age: int
    language: str
    primary_concern: str
    engagement: int = 70
    missed_sessions: int = 0
    last_score: int = 0
    risk_level: str = "Low"
    notes: str = ""


class AppointmentCreate(BaseModel):
    patient_id: str
    patient_name: str
    date: str
    time: str
    clinician: str
    channel: str
    note: str = ""


class SessionCreate(BaseModel):
    patient_name: str
    date: str
    risk_level: str
    score: int
    transcript: str
    summary: str
    recommendations: list[str]


class ChatRequest(BaseModel):
    patient_name: str
    message: str
    language: str
    role: str


class VoiceChatRequest(BaseModel):
    patient_name: str
    message: str
    language: str
    role: str
    session_id: str | None = None


class ReportSaveRequest(BaseModel):
    patient_name: str
    report_text: str
    risk_level: str


class AuditLogCreate(BaseModel):
    actor: str
    role: str
    action: str
    subject: str
    severity: str = "info"


# Endpoints

# 1. AUTHENTICATION

@app.post("/api/auth/login")
def login(req: LoginRequest):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (req.username,)).fetchone()
    conn.close()

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    access_token = create_access_token(data={"sub": user["username"], "role": user["role"]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
        "email": user["email"]
    }


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if req.role not in ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role. Must be one of: {ROLES}")

    conn = get_db_connection()
    existing = conn.execute("SELECT * FROM users WHERE username = ?", (req.username,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hashed = get_password_hash(req.password)
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name, email, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (req.username, hashed, req.role, req.full_name, req.email, now_str)
        )
        conn.commit()
    except Exception as exc:
        conn.close()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {exc}")
    
    conn.close()
    return {"message": "User registered successfully"}


# 2. PATIENTS

@app.get("/api/patients")
def get_patients(current_user: dict = Depends(get_current_user_payload)):
    # Standard RBAC check
    if current_user["role"] == "Patient":
        # Patients can only see themselves (matched by username)
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM patients WHERE name = ?", (current_user["sub"],)).fetchone()
        conn.close()
        return [dict(row)] if row else []

    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM patients ORDER BY name ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/patients")
def create_patient(req: PatientCreate, current_user: dict = Depends(get_current_user_payload)):
    if current_user["role"] not in {"Admin", "Psychologist", "Assistant"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    conn = get_db_connection()
    pid = req.patient_id or f"PT-{hash(req.name) % 10000:04d}"
    
    # Check duplicate name
    existing = conn.execute("SELECT * FROM patients WHERE name = ?", (req.name,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Patient with this name already exists")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        INSERT INTO patients (patient_id, name, age, language, primary_concern, engagement, missed_sessions, last_score, risk_level, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (pid, req.name, req.age, req.language, req.primary_concern, req.engagement, req.missed_sessions, req.last_score, req.risk_level, req.notes, now_str)
    )
    # Log Audit
    conn.execute(
        "INSERT INTO audit_logs (timestamp, actor, role, action, subject, severity) VALUES (?, ?, ?, ?, ?, ?)",
        (now_str, current_user["sub"], current_user["role"], "Created patient record", req.name, "info")
    )
    conn.commit()
    conn.close()
    return {"message": "Patient created successfully", "patient_id": pid}


@app.put("/api/patients/{name}")
def update_patient(name: str, req: PatientCreate, current_user: dict = Depends(get_current_user_payload)):
    if current_user["role"] not in {"Admin", "Psychologist", "Assistant"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    conn = get_db_connection()
    existing = conn.execute("SELECT * FROM patients WHERE name = ?", (name,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    conn.execute(
        """
        UPDATE patients 
        SET age = ?, language = ?, primary_concern = ?, engagement = ?, missed_sessions = ?, last_score = ?, risk_level = ?, notes = ?
        WHERE name = ?
        """,
        (req.age, req.language, req.primary_concern, req.engagement, req.missed_sessions, req.last_score, req.risk_level, req.notes, name)
    )
    
    # Check if risk escalation triggers
    escalated = False
    if req.risk_level in {"High", "Critical"}:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO escalations (patient_name, reason, severity, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, f"Risk level set to {req.risk_level}", req.risk_level.lower(), "active", now_str)
        )
        escalated = True
        
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO audit_logs (timestamp, actor, role, action, subject, severity) VALUES (?, ?, ?, ?, ?, ?)",
        (now_str, current_user["sub"], current_user["role"], "Updated patient record", name, "warning" if escalated else "info")
    )
    conn.commit()
    conn.close()
    return {"message": "Patient updated successfully"}


# 3. APPOINTMENTS

@app.get("/api/appointments")
def get_appointments(current_user: dict = Depends(get_current_user_payload)):
    conn = get_db_connection()
    if current_user["role"] == "Patient":
        rows = conn.execute("SELECT * FROM appointments WHERE patient_name = ? ORDER BY date DESC, time DESC", (current_user["sub"],)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM appointments ORDER BY date DESC, time DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/appointments")
def create_appointment(req: AppointmentCreate, current_user: dict = Depends(get_current_user_payload)):
    if current_user["role"] not in {"Admin", "Psychologist", "Assistant"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        INSERT INTO appointments (patient_id, patient_name, date, time, clinician, channel, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (req.patient_id, req.patient_name, req.date, req.time, req.clinician, req.channel, req.note, now_str)
    )
    conn.execute(
        "INSERT INTO audit_logs (timestamp, actor, role, action, subject, severity) VALUES (?, ?, ?, ?, ?, ?)",
        (now_str, current_user["sub"], current_user["role"], "Scheduled appointment", req.patient_name, "info")
    )
    conn.commit()
    conn.close()
    
    whatsapp_preview = f"Hello {req.patient_name}, your appointment is on {req.date} at {req.time} with {req.clinician}."
    return {"message": "Appointment created", "whatsapp_preview": whatsapp_preview}


# 4. CHAT

@app.post("/api/chat")
def post_chat(req: ChatRequest, current_user: dict = Depends(get_current_user_payload)):
    # Moderation check
    mod = moderation_check(req.message)
    if not mod["allowed"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message blocked by moderation rules.")

    # Sensitive redaction
    redacted_msg = redact_sensitive_text(req.message)
    
    # Risk detection
    risk = detect_high_risk(req.message)
    
    # Retrieve notes from database to provide context
    conn = get_db_connection()
    patient = conn.execute("SELECT notes FROM patients WHERE name = ?", (req.patient_name,)).fetchone()
    patient_notes = patient["notes"] if patient else ""

    if risk["high_risk"]:
        reply = (
            "This sounds urgent. Please contact a licensed clinician or local emergency support immediately. "
            "If there is immediate danger, call emergency services now."
        )
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO escalations (patient_name, reason, severity, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (req.patient_name, "High risk phrases detected in chat support", "critical", "active", now_str)
        )
        conn.execute(
            "INSERT INTO audit_logs (timestamp, actor, role, action, subject, severity) VALUES (?, ?, ?, ?, ?, ?)",
            (now_str, current_user["sub"], current_user["role"], "Triggered critical risk escalation", req.patient_name, "critical")
        )
    else:
        # Generate reply using Gemini (with fallback)
        reply = generate_chat_reply(patient_notes, redacted_msg, req.language)
        
    # Save chat history
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        INSERT INTO chat_history (patient_name, speaker, message, reply, risk_level, mode, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (req.patient_name, "patient", redacted_msg, reply, "high" if risk["high_risk"] else "normal", "chat", now_str)
    )
    conn.commit()
    conn.close()

    # Synthesize reply to speech
    tts_filename = f"chat_reply_{hash(reply) % 10000}.mp3"
    tts_path = ARTIFACTS_DIR / tts_filename
    tts_lang = tts_language_code(req.language)
    spoken_reply = tune_tamil_tts_text(reply) if tts_lang == "ta" else reply
    synthesize_speech(spoken_reply, tts_path, lang=tts_lang)

    return {
        "reply": reply,
        "risk": "high" if risk["high_risk"] else "normal",
        "redacted_message": redacted_msg,
        "audio_file": tts_filename,
        "emotion": detect_emotion(req.message)["primary"]
    }


@app.get("/api/chat/history")
def get_chat_history(patient_name: str, current_user: dict = Depends(get_current_user_payload)):
    if current_user["role"] == "Patient" and current_user["sub"] != patient_name:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM chat_history WHERE patient_name = ? ORDER BY created_at DESC", (patient_name,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# 5. VOICE

@app.post("/api/voice")
def post_voice(
    file: UploadFile = File(...),
    patient_name: str = Form(...),
    language: str = Form(...),
    session_id: str = Form(None),
    current_user: dict = Depends(get_current_user_payload)
):
    try:
        audio_bytes = file.file.read()
        transcript, engine = transcribe_audio_bytes(audio_bytes, suffix=Path(file.filename).suffix, language=language)
        if not transcript:
            raise HTTPException(status_code=400, detail="Voice transcription failed or unavailable in this environment.")
            
        # Standard chat reply flow
        mod = moderation_check(transcript)
        if not mod["allowed"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message blocked by moderation rules.")
            
        redacted_transcript = redact_sensitive_text(transcript)
        risk = detect_high_risk(transcript)
        
        conn = get_db_connection()
        patient = conn.execute("SELECT notes FROM patients WHERE name = ?", (patient_name,)).fetchone()
        patient_notes = patient["notes"] if patient else ""

        if risk["high_risk"]:
            reply = (
                "This sounds urgent. Please contact a licensed clinician or local emergency support immediately. "
                "If there is immediate danger, call emergency services now."
            )
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO escalations (patient_name, reason, severity, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (patient_name, "High risk phrases detected in voice transcription", "critical", "active", now_str)
            )
        else:
            reply = generate_chat_reply(patient_notes, redacted_transcript, language)

        # Synthesize reply to speech
        tts_filename = f"voice_reply_{hash(reply) % 1000}.mp3"
        tts_path = ARTIFACTS_DIR / tts_filename
        tts_lang = tts_language_code(language)
        spoken_reply = tune_tamil_tts_text(reply) if tts_lang == "ta" else reply
        synthesize_speech(spoken_reply, tts_path, lang=tts_lang)

        # Save to voice session
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if session_id:
            # Append turns
            conn.execute(
                "INSERT INTO voice_turns (session_id, speaker, text, language, engine, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, "patient", redacted_transcript, language, engine, now_str)
            )
            conn.execute(
                "INSERT INTO voice_turns (session_id, speaker, text, language, engine, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, "assistant", reply, language, "gtts", now_str)
            )
            conn.execute(
                "UPDATE voice_sessions SET updated_at = ? WHERE session_id = ?",
                (now_str, session_id)
            )
            
        conn.commit()
        conn.close()

        return {
            "transcript": redacted_transcript,
            "reply": reply,
            "engine": engine,
            "audio_file": tts_filename,
            "risk": "high" if risk["high_risk"] else "normal",
            "emotion": detect_emotion(transcript)["primary"]
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/voice/audio/{filename}")
def get_voice_audio(filename: str):
    path = ARTIFACTS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(str(path), media_type="audio/mp3")


@app.get("/api/voice/sessions")
def get_voice_sessions(patient_name: str | None = None, current_user: dict = Depends(get_current_user_payload)):
    conn = get_db_connection()
    if current_user["role"] == "Patient":
        rows = conn.execute("SELECT * FROM voice_sessions WHERE patient_name = ? ORDER BY updated_at DESC", (current_user["sub"],)).fetchall()
    elif patient_name:
        rows = conn.execute("SELECT * FROM voice_sessions WHERE patient_name = ? ORDER BY updated_at DESC", (patient_name,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM voice_sessions ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/api/voice/sessions/{session_id}/turns")
def get_voice_turns(session_id: str):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM voice_turns WHERE session_id = ? ORDER BY timestamp ASC", (session_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/voice/sessions")
def start_voice_session(req: dict, current_user: dict = Depends(get_current_user_payload)):
    patient_name = req.get("patient_name", "Unassigned")
    language = req.get("language", "English")
    continuous = req.get("continuous_mode", True)
    
    conn = get_db_connection()
    session_count = conn.execute("SELECT COUNT(*) FROM voice_sessions").fetchone()[0]
    session_id = f"V-{session_count + 1:04d}"
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        INSERT INTO voice_sessions (session_id, patient_name, language, status, continuous_mode, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, patient_name, language, "active", 1 if continuous else 0, now_str, now_str)
    )
    conn.commit()
    conn.close()
    return {"session_id": session_id}


# 6. RAG KNOWLEDGE BASE

@app.get("/api/rag/search")
def search_rag(q: str):
    answer_text, sources = rag_store.answer(q)
    return {
        "answer": answer_text,
        "sources": sources
    }


@app.post("/api/rag/ingest")
def ingest_rag(file: UploadFile = File(...), current_user: dict = Depends(get_current_user_payload)):
    if current_user["role"] not in {"Admin", "Psychologist", "Assistant"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    content = file.file.read()
    # Save to knowledge directory
    saved_path = save_bytes(file.filename, content, subdir="knowledge_base")
    text = load_document_text(saved_path)
    
    if not text.strip():
        raise HTTPException(status_code=400, detail="Uploaded document contains no readable text.")

    # Ingest into vector store
    rag_store.add_items([KnowledgeItem(title=file.filename, text=text, source=str(saved_path))])
    
    # Save document meta to DB
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO documents (name, size_kb, saved_path, uploaded_at) VALUES (?, ?, ?, ?)",
        (file.filename, round(len(content) / 1024, 2), str(saved_path), now_str)
    )
    conn.execute(
        "INSERT INTO audit_logs (timestamp, actor, role, action, subject, severity) VALUES (?, ?, ?, ?, ?, ?)",
        (now_str, current_user["sub"], current_user["role"], "Ingested document into RAG", file.filename, "info")
    )
    conn.commit()
    conn.close()
    
    return {"message": f"Successfully ingested {file.filename} into RAG."}


@app.get("/api/documents")
def get_documents():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


# 7. ASSESSMENTS / CLINICAL SCREENINGS

@app.get("/api/assessment/questions")
def get_questions(language: str):
    return psychometric_walkthrough(language, {})


@app.post("/api/assessment/submit")
def submit_assessment(req: dict, current_user: dict = Depends(get_current_user_payload)):
    patient_name = req.get("patient_name")
    language = req.get("language", "English")
    answers = req.get("answers", {})
    notes = req.get("notes", "")

    # Retrieve patient details
    conn = get_db_connection()
    patient_row = conn.execute("SELECT * FROM patients WHERE name = ?", (patient_name,)).fetchone()
    patient = dict(patient_row) if patient_row else {
        "name": patient_name, "age": 30, "language": language, "primary_concern": "", "engagement": 70, "missed_sessions": 0
    }
    conn.close()

    # Run Multi-Agent Orchestration Team
    from .multi_agent import run_clinical_multi_agent_team
    agent_result = run_clinical_multi_agent_team(patient, answers, notes)
    
    scorecard = agent_result.final_output["scorecard"]
    text_risk = agent_result.final_output["text_risk"]
    recs = agent_result.final_output["recommendations"]
    escalated = agent_result.final_output["escalate"]

    # Summarize notes
    summary = notes.strip()
    if is_gemini_configured():
        from .gemini_service import generate_session_summary
        summary = generate_session_summary(notes)
    else:
        # Fallback summary
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", notes.strip()) if s.strip()]
        if sentences:
            summary = "\n".join(f"- {s}" for s in sentences[:3])

    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Insert session
    conn.execute(
        """
        INSERT INTO sessions (patient_name, date, risk_level, score, transcript, summary, recommendations, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (patient_name, datetime.now().strftime("%Y-%m-%d"), scorecard["risk_level"], scorecard["total"], notes, summary, "\n".join(recs), now_str)
    )

    # Update patient's latest score
    conn.execute(
        "UPDATE patients SET last_score = ?, risk_level = ? WHERE name = ?",
        (scorecard["total"], scorecard["risk_level"], patient_name)
    )

    # Check escalation rules
    if escalated:
        # Check if active escalation already exists
        active_esc = conn.execute("SELECT * FROM escalations WHERE patient_name = ? AND status = 'active'", (patient_name,)).fetchone()
        if not active_esc:
            conn.execute(
                "INSERT INTO escalations (patient_name, reason, severity, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (patient_name, "Clinical screening threshold reached", scorecard["risk_level"].lower(), "active", now_str)
            )

    # Audit log
    conn.execute(
        "INSERT INTO audit_logs (timestamp, actor, role, action, subject, severity) VALUES (?, ?, ?, ?, ?, ?)",
        (now_str, current_user["sub"], current_user["role"], "Completed patient assessment", patient_name, "warning" if escalated else "info")
    )
    
    conn.commit()
    conn.close()

    serialized_trace = [
        {
            "agent_name": msg.agent_name,
            "role": msg.role,
            "thought": msg.thought,
            "action": msg.action,
            "result": msg.result
        }
        for msg in agent_result.trace
    ]

    return {
        "scorecard": scorecard,
        "text_risk": text_risk,
        "recommendations": recs,
        "summary": summary,
        "escalated": escalated,
        "multi_agent_trace": serialized_trace
    }


@app.get("/api/sessions")
def get_sessions(patient_name: str | None = None, current_user: dict = Depends(get_current_user_payload)):
    conn = get_db_connection()
    if current_user["role"] == "Patient":
        rows = conn.execute("SELECT * FROM sessions WHERE patient_name = ? ORDER BY date DESC", (current_user["sub"],)).fetchall()
    elif patient_name:
        rows = conn.execute("SELECT * FROM sessions WHERE patient_name = ? ORDER BY date DESC", (patient_name,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM sessions ORDER BY date DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


# 8. CLINICAL REPORTS

@app.get("/api/reports")
def get_reports(patient_name: str | None = None, current_user: dict = Depends(get_current_user_payload)):
    conn = get_db_connection()
    if current_user["role"] == "Patient":
        rows = conn.execute("SELECT * FROM reports WHERE patient_name = ? ORDER BY created_at DESC", (current_user["sub"],)).fetchall()
    elif patient_name:
        rows = conn.execute("SELECT * FROM reports WHERE patient_name = ? ORDER BY created_at DESC", (patient_name,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM reports ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/reports")
def save_report(req: ReportSaveRequest, current_user: dict = Depends(get_current_user_payload)):
    if current_user["role"] not in {"Admin", "Psychologist"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO reports (patient_name, report_text, risk_level, created_at) VALUES (?, ?, ?, ?)",
        (req.patient_name, req.report_text, req.risk_level, now_str)
    )
    conn.execute(
        "INSERT INTO audit_logs (timestamp, actor, role, action, subject, severity) VALUES (?, ?, ?, ?, ?, ?)",
        (now_str, current_user["sub"], current_user["role"], "Saved clinical report", req.patient_name, "info")
    )
    conn.commit()
    conn.close()
    return {"message": "Report saved successfully"}


# 9. ADMIN METRICS & CONTROLS

@app.get("/api/admin/metrics")
def get_admin_metrics(current_user: dict = Depends(get_current_user_payload)):
    if current_user["role"] not in {"Admin", "Psychologist"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    conn = get_db_connection()
    patient_count = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    high_risk_count = conn.execute("SELECT COUNT(*) FROM patients WHERE risk_level IN ('High', 'Critical')").fetchone()[0]
    appt_count = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    audit_count = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    
    audit_logs = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 50").fetchall()
    escalations = conn.execute("SELECT * FROM escalations ORDER BY created_at DESC LIMIT 50").fetchall()
    
    conn.close()
    return {
        "metrics": {
            "patients": patient_count,
            "high_risk": high_risk_count,
            "appointments": appt_count,
            "audit_logs": audit_count
        },
        "audit_logs": [dict(r) for r in audit_logs],
        "escalations": [dict(r) for r in escalations],
        "governance": SAFE_GUARDRAILS,
        "gemini_active": is_gemini_configured()
    }


@app.post("/api/admin/audit")
def post_audit(req: AuditLogCreate, current_user: dict = Depends(get_current_user_payload)):
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO audit_logs (timestamp, actor, role, action, subject, severity) VALUES (?, ?, ?, ?, ?, ?)",
        (now_str, req.actor, req.role, req.action, req.subject, req.severity)
    )
    conn.commit()
    conn.close()
    return {"message": "Audit event recorded"}


class ConfigUpdateRequest(BaseModel):
    gemini_api_key: str


class EscalationResolveRequest(BaseModel):
    escalation_id: int
    notes: str


@app.post("/api/admin/config")
def update_config(req: ConfigUpdateRequest, current_user: dict = Depends(get_current_user_payload)):
    if current_user["role"] != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    env_path = Path(__file__).resolve().parents[1] / ".env"
    env_path.write_text(f"GEMINI_API_KEY={req.gemini_api_key}\n", encoding="utf-8")
    os.environ["GEMINI_API_KEY"] = req.gemini_api_key
    from .gemini_service import init_gemini
    init_gemini()
    return {"message": "API key updated successfully"}


@app.post("/api/admin/escalation/resolve")
def resolve_escalation(req: EscalationResolveRequest, current_user: dict = Depends(get_current_user_payload)):
    if current_user["role"] not in {"Admin", "Psychologist"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE escalations SET status = 'resolved', resolved_at = ? WHERE id = ?", (now_str, req.escalation_id))
    esc = conn.execute("SELECT patient_name FROM escalations WHERE id = ?", (req.escalation_id,)).fetchone()
    p_name = esc["patient_name"] if esc else "Unknown"
    conn.execute(
        "INSERT INTO audit_logs (timestamp, actor, role, action, subject, severity) VALUES (?, ?, ?, ?, ?, ?)",
        (now_str, current_user["sub"], current_user["role"], f"Resolved escalation: {req.notes}", p_name, "info")
    )
    conn.commit()
    conn.close()
    return {"message": "Escalation resolved successfully"}


@app.get("/api/patients/{name}/retention")
def get_patient_retention(name: str, current_user: dict = Depends(get_current_user_payload)):
    if current_user["role"] not in {"Admin", "Psychologist"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    
    conn = get_db_connection()
    patient = conn.execute("SELECT * FROM patients WHERE name = ?", (name,)).fetchone()
    if not patient:
        conn.close()
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Fetch recent chat transcripts to check sentiment
    chat_rows = conn.execute(
        "SELECT * FROM chat_history WHERE patient_name = ? ORDER BY id DESC LIMIT 5",
        (name,)
    ).fetchall()
    conn.close()
    
    chat_list = [dict(c) for c in chat_rows]
    insights = predict_retention(dict(patient), chat_list)
    return insights

