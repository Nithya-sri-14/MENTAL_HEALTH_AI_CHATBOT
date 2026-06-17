from __future__ import annotations

APP_NAME = "Mental Health Agentic Chatbot"
APP_TAGLINE = "An enterprise safety-first psychometric screening, RAG, and workflow automation platform."

LANGUAGES = ["English", "Tamil"]
ROLES = ["Admin", "Psychologist", "Assistant", "Patient"]

FEATURES = [
    "patient_onboarding",
    "psychological_assessment",
    "multilingual_conversation",
    "appointment_scheduling",
    "rag_knowledge_assistant",
    "automated_reports",
    "progress_tracking",
    "session_summarization",
    "secure_documents",
    "admin_dashboard",
    "rbac",
    "audit_logs",
    "analytics",
    "retention_prediction",
    "voice",
    "whatsapp_preview",
    "risk_escalation",
]

PATIENT_COLUMNS = [
    "patient_id",
    "name",
    "age",
    "language",
    "primary_concern",
    "engagement",
    "missed_sessions",
    "last_score",
    "risk_level",
    "notes",
]

DEFAULT_QUESTIONS = [
    {
        "id": "q1",
        "domain": "stress",
        "question_en": "In the last 7 days, how often have you felt overwhelmed by stress?",
        "question_ta": "கடந்த 7 நாட்களில், மன அழுத்தத்தால் அதிகமாக சோர்வடைந்ததாக எவ்வளவு அடிக்கடி உணர்ந்தீர்கள்?",
        "weight": 3,
    },
    {
        "id": "q2",
        "domain": "sleep",
        "question_en": "How often has sleep difficulty affected your daily functioning?",
        "question_ta": "தூக்க சிக்கல் உங்கள் அன்றாட செயல்பாட்டை எவ்வளவு அடிக்கடி பாதித்துள்ளது?",
        "weight": 2,
    },
    {
        "id": "q3",
        "domain": "anxiety",
        "question_en": "How often have you experienced persistent worry or panic sensations?",
        "question_ta": "தொடர்ச்சியான கவலை அல்லது பதட்ட உணர்வுகளை எவ்வளவு அடிக்கடி அனுபவித்தீர்கள்?",
        "weight": 3,
    },
    {
        "id": "q4",
        "domain": "mood",
        "question_en": "How often have you felt low, hopeless, or emotionally numb?",
        "question_ta": "மனச்சோர்வு, நம்பிக்கையற்ற தன்மை அல்லது உணர்வுகள் குறைந்ததாக எவ்வளவு அடிக்கடி உணர்ந்தீர்கள்?",
        "weight": 3,
    },
    {
        "id": "q5",
        "domain": "function",
        "question_en": "How much has this affected your work, study, or home routine?",
        "question_ta": "இது உங்கள் வேலை, படிப்பு, அல்லது வீட்டுப்பணிகளை எவ்வளவு பாதித்துள்ளது?",
        "weight": 2,
    },
]

PROMPT_TEMPLATE = """\
You are a safety-first psychological screening assistant.

Objective:
- Ask one short question at a time.
- Collect self-report screening answers.
- Do not diagnose.
- Do not claim to be a clinician.
- Explain that the exchange is a screening and not medical advice.
- Support English and Tamil.
- If the user mentions self-harm, suicide, immediate danger, abuse, or inability to stay safe:
  - stop the screening,
  - recommend emergency support and a licensed clinician,
  - mark the case for escalation.

Interaction style:
- Calm, concise, empathetic, and non-judgmental.
- Avoid jargon.
- Keep each turn under 2 short paragraphs.
- Prefer concrete response options where useful.

Return structure:
1. current_question
2. why_it_is_asked
3. response_options or free_text_instruction
4. risk_flags
5. next_step
"""

SAFE_GUARDRAILS = {
    "no_diagnosis": True,
    "no_medication_advice": True,
    "escalate_high_risk": True,
    "consent_required": True,
    "log_redaction": True,
    "document_allowlist": [".txt", ".md", ".pdf", ".docx"],
}

EMPTY_STATE_NOTICE = "No patient registry is loaded. Import a CSV or create a patient record to begin."
