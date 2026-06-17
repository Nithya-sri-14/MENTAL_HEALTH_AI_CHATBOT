from __future__ import annotations

import json
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any

from .storage import DATA_DIR, ensure_directories

DB_PATH = DATA_DIR / "mental_health.db"
JSON_STATE_PATH = DATA_DIR / "state" / "app_state.json"


def get_db_connection() -> sqlite3.Connection:
    ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    # Secure SHA-256 hashing for local enterprise staging
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # Create patients table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        language TEXT NOT NULL,
        primary_concern TEXT,
        engagement INTEGER DEFAULT 70,
        missed_sessions INTEGER DEFAULT 0,
        last_score INTEGER DEFAULT 0,
        risk_level TEXT DEFAULT 'Low',
        notes TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # Create appointments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        patient_name TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        clinician TEXT NOT NULL,
        channel TEXT NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
    )
    """)

    # Create documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        size_kb REAL NOT NULL,
        saved_path TEXT NOT NULL,
        uploaded_at TEXT NOT NULL
    )
    """)

    # Create sessions/assessments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_name TEXT NOT NULL,
        date TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        score INTEGER NOT NULL,
        transcript TEXT,
        summary TEXT,
        recommendations TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # Create chat history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_name TEXT NOT NULL,
        speaker TEXT NOT NULL,
        message TEXT NOT NULL,
        reply TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        mode TEXT NOT NULL,
        session_id TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # Create voice sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voice_sessions (
        session_id TEXT PRIMARY KEY,
        patient_name TEXT NOT NULL,
        language TEXT NOT NULL,
        status TEXT NOT NULL,
        continuous_mode INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # Create voice turns table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voice_turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        speaker TEXT NOT NULL,
        text TEXT NOT NULL,
        language TEXT NOT NULL,
        engine TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES voice_sessions(session_id)
    )
    """)

    # Create escalations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS escalations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_name TEXT NOT NULL,
        reason TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL,
        resolved_at TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # Create reports table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_name TEXT NOT NULL,
        report_text TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # Create audit logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        actor TEXT NOT NULL,
        role TEXT NOT NULL,
        action TEXT NOT NULL,
        subject TEXT NOT NULL,
        severity TEXT NOT NULL
    )
    """)

    # Check if default users exist, seed them if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        default_users = [
            ("admin", hash_password("admin123"), "Admin", "System Admin", "admin@clinic.com"),
            ("psychologist", hash_password("psy123"), "Psychologist", "Dr. Sarah Paul", "sarah@clinic.com"),
            ("assistant", hash_password("asst123"), "Assistant", "James Cooper", "james@clinic.com"),
            ("patient", hash_password("patient123"), "Patient", "John Doe", "john.doe@email.com"),
        ]
        cursor.executemany(
            "INSERT INTO users (username, password_hash, role, full_name, email, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [(u[0], u[1], u[2], u[3], u[4], now_str) for u in default_users]
        )
        conn.commit()

    conn.commit()
    conn.close()

    # Trigger data migration from JSON if it exists
    migrate_from_json()


def migrate_from_json() -> None:
    if not JSON_STATE_PATH.exists():
        return

    try:
        data = json.loads(JSON_STATE_PATH.read_text(encoding="utf-8"))
        conn = get_db_connection()
        cursor = conn.cursor()

        # Migrate patients
        cursor.execute("SELECT COUNT(*) FROM patients")
        db_patient_count = cursor.fetchone()[0]
        if db_patient_count == 0 and "patients" in data:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for p in data["patients"]:
                pid = p.get("patient_id") or f"PT-{hash(p['name']) % 10000:04d}"
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO patients 
                    (patient_id, name, age, language, primary_concern, engagement, missed_sessions, last_score, risk_level, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        p.get("name"),
                        p.get("age", 30),
                        p.get("language", "English"),
                        p.get("primary_concern", ""),
                        p.get("engagement", 70),
                        p.get("missed_sessions", 0),
                        p.get("last_score", 0),
                        p.get("risk_level", "Low"),
                        p.get("notes", ""),
                        now_str
                    )
                )

        # Migrate appointments
        cursor.execute("SELECT COUNT(*) FROM appointments")
        if cursor.fetchone()[0] == 0 and "appointments" in data:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for a in data["appointments"]:
                p_name = a.get("patient")
                # Find patient_id
                cursor.execute("SELECT patient_id FROM patients WHERE name = ?", (p_name,))
                row = cursor.fetchone()
                pid = row["patient_id"] if row else "UNKNOWN"

                cursor.execute(
                    """
                    INSERT INTO appointments (patient_id, patient_name, date, time, clinician, channel, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        p_name,
                        a.get("date"),
                        a.get("time"),
                        a.get("clinician", "Unassigned"),
                        a.get("channel", "In-person"),
                        a.get("note", ""),
                        now_str
                    )
                )

        # Migrate documents
        cursor.execute("SELECT COUNT(*) FROM documents")
        if cursor.fetchone()[0] == 0 and "documents" in data:
            for d in data["documents"]:
                cursor.execute(
                    """
                    INSERT INTO documents (name, size_kb, saved_path, uploaded_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        d.get("name"),
                        d.get("size_kb", 0.0),
                        d.get("saved_path"),
                        d.get("uploaded_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                )

        # Migrate sessions
        cursor.execute("SELECT COUNT(*) FROM sessions")
        if cursor.fetchone()[0] == 0 and "sessions" in data:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for s in data["sessions"]:
                cursor.execute(
                    """
                    INSERT INTO sessions (patient_name, date, risk_level, score, transcript, summary, recommendations, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        s.get("patient"),
                        s.get("date"),
                        s.get("risk_level", "Low"),
                        s.get("score", 0),
                        "",
                        "",
                        "",
                        now_str
                    )
                )

        # Migrate chat history
        cursor.execute("SELECT COUNT(*) FROM chat_history")
        if cursor.fetchone()[0] == 0 and "chat_history" in data:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for c in data["chat_history"]:
                cursor.execute(
                    """
                    INSERT INTO chat_history (patient_name, speaker, message, reply, risk_level, mode, session_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c.get("patient"),
                        "patient",
                        c.get("message", ""),
                        c.get("reply", ""),
                        c.get("risk", "normal"),
                        c.get("mode", "chat"),
                        c.get("session_id", ""),
                        now_str
                    )
                )

        # Migrate voice sessions
        cursor.execute("SELECT COUNT(*) FROM voice_sessions")
        if cursor.fetchone()[0] == 0 and "voice_sessions" in data:
            for vs in data["voice_sessions"]:
                cursor.execute(
                    """
                    INSERT INTO voice_sessions (session_id, patient_name, language, status, continuous_mode, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        vs.get("session_id"),
                        vs.get("patient"),
                        vs.get("language", "English"),
                        vs.get("status", "active"),
                        1 if vs.get("continuous_mode", True) else 0,
                        vs.get("created_at"),
                        vs.get("updated_at")
                    )
                )
                # Migrate turns
                if "turns" in vs:
                    for t in vs["turns"]:
                        cursor.execute(
                            """
                            INSERT INTO voice_turns (session_id, speaker, text, language, engine, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                vs.get("session_id"),
                                t.get("speaker"),
                                t.get("text"),
                                t.get("language", "English"),
                                t.get("engine", "none"),
                                t.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            )
                        )

        # Migrate escalations
        cursor.execute("SELECT COUNT(*) FROM escalations")
        if cursor.fetchone()[0] == 0 and "escalations" in data:
            for esc in data["escalations"]:
                cursor.execute(
                    """
                    INSERT INTO escalations (patient_name, reason, severity, status, resolved_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        esc.get("patient"),
                        esc.get("reason", "Assessment threshold reached"),
                        "high",
                        "active",
                        None,
                        esc.get("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                )

        # Migrate audit logs
        cursor.execute("SELECT COUNT(*) FROM audit_logs")
        if cursor.fetchone()[0] == 0 and "audit_logs" in data:
            for l in data["audit_logs"]:
                cursor.execute(
                    """
                    INSERT INTO audit_logs (timestamp, actor, role, action, subject, severity)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        l.get("timestamp"),
                        l.get("actor", "System"),
                        "Psychologist",
                        l.get("action", "Action"),
                        l.get("subject", ""),
                        l.get("severity", "info")
                    )
                )

        # Migrate saved reports
        cursor.execute("SELECT COUNT(*) FROM reports")
        if cursor.fetchone()[0] == 0 and "saved_reports" in data:
            for rep in data["saved_reports"]:
                cursor.execute(
                    """
                    INSERT INTO reports (patient_name, report_text, risk_level, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        rep.get("patient"),
                        f"# Automated Report\nSaved at: {rep.get('time')}\nRisk level: {rep.get('risk')}",
                        rep.get("risk", "Low"),
                        rep.get("time")
                    )
                )

        conn.commit()
        conn.close()

        # Safely archive JSON file so migration doesn't run again
        archive_path = JSON_STATE_PATH.with_suffix(".json.bak")
        JSON_STATE_PATH.rename(archive_path)

    except Exception as exc:
        print(f"Error during JSON data migration: {exc}")
