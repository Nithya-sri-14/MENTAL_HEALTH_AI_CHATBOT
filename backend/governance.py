from __future__ import annotations

import re
from datetime import datetime

SENSITIVE_PATTERNS = [
    (re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?:\+?\d[\d\-\s]{7,}\d)\b"), "[REDACTED_PHONE]"),
    (re.compile(r"\b\d{12}\b"), "[REDACTED_ID]"),
]

HIGH_RISK_TRIGGERS = [
    "suicide",
    "kill myself",
    "end my life",
    "self-harm",
    "hurt myself",
    "cannot stay safe",
    "want to die",
]


def redact_sensitive_text(text: str) -> str:
    value = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def detect_high_risk(text: str) -> dict:
    lowered = text.lower()
    hits = [trigger for trigger in HIGH_RISK_TRIGGERS if trigger in lowered]
    return {
        "high_risk": bool(hits),
        "signals": hits,
        "severity": "critical" if hits else "normal",
    }


def moderation_check(text: str) -> dict:
    lowered = text.lower()
    banned = any(word in lowered for word in ["hack", "password dump", "ssn", "credit card"])
    return {
        "allowed": not banned,
        "reason": "Potential unsafe request" if banned else "ok",
    }


def audit_event(actor: str, action: str, subject: str, severity: str = "info") -> dict:
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "actor": actor,
        "action": action,
        "subject": redact_sensitive_text(subject),
        "severity": severity,
    }


def should_escalate(risk_level: str, text: str) -> bool:
    if risk_level in {"High", "Critical"}:
        return True
    return detect_high_risk(text)["high_risk"]


def detect_emotion(text: str) -> dict:
    lowered = text.lower()
    emotions = {
        "Anxious": ["anxious", "panic", "worry", "fear", "nervous", "scared", "dread", "terror"],
        "Depressed": ["sad", "depressed", "empty", "lonely", "crying", "down", "hopeless", "worthless"],
        "Stressed": ["stress", "overwhelmed", "busy", "pressure", "tired", "exhausted", "fatigue"],
        "Frustrated": ["angry", "mad", "annoyed", "hate", "frustrated", "upset", "irritated"],
        "Calm/Optimistic": ["happy", "good", "calm", "fine", "great", "positive", "better", "peaceful", "hopeful"]
    }
    detected = []
    for emotion, keywords in emotions.items():
        matches = [kw for kw in keywords if kw in lowered]
        if matches:
            detected.append((emotion, len(matches)))
    if not detected:
        return {"primary": "Neutral", "all": []}
    detected.sort(key=lambda x: x[1], reverse=True)
    return {
        "primary": detected[0][0],
        "all": [x[0] for x in detected]
    }
