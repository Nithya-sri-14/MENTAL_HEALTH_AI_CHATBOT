from __future__ import annotations

import re
from .config import DEFAULT_QUESTIONS, APP_NAME
from .gemini_service import analyze_risk_nlp, generate_clinical_report


def normalize_score(value: int) -> int:
    return max(0, min(4, int(value)))


def language_key(language: str) -> str:
    return "question_ta" if language == "Tamil" else "question_en"


def score_answers(answers: dict[str, int]) -> dict:
    stress = normalize_score(answers.get("q1", 0)) * 3
    sleep = normalize_score(answers.get("q2", 0)) * 2
    anxiety = normalize_score(answers.get("q3", 0)) * 3
    mood = normalize_score(answers.get("q4", 0)) * 3
    function = normalize_score(answers.get("q5", 0)) * 2

    total = stress + sleep + anxiety + mood + function
    
    if total >= 28:
        risk_level = "Critical"
    elif total >= 18:
        risk_level = "High"
    elif total >= 9:
        risk_level = "Moderate"
    else:
        risk_level = "Low"

    return {
        "stress": stress,
        "sleep": sleep,
        "anxiety": anxiety,
        "mood": mood,
        "function": function,
        "total": total,
        "risk_level": risk_level,
    }


def risk_from_text(text: str) -> dict:
    return analyze_risk_nlp(text)


def recommendations(scorecard: dict, text_risk: dict, engagement: int, missed_sessions: int) -> list[str]:
    recs = []
    if text_risk.get("escalate", False):
        recs.append("Escalate to a licensed psychologist for same-day review.")
    if scorecard.get("risk_level") in {"High", "Critical"}:
        recs.append("Pause automated advice and move to safety-first clinical assessment.")
    if scorecard.get("sleep", 0) >= 4:
        recs.append("Review sleep hygiene guidelines and recommend a nightly calming routine.")
    if scorecard.get("anxiety", 0) >= 5:
        recs.append("Apply daily mindfulness, paced breathing, and short symptom check-ins.")
    if engagement < 60 or missed_sessions >= 2:
        recs.append("Trigger a patient retention follow-up and reschedule missed sessions.")
    if not recs:
        recs.append("Continue the current mental well-being plan and monitor progress weekly.")
    return recs


def psychometric_walkthrough(language: str, answers: dict[str, int] | None = None) -> list[dict]:
    answers = answers or {}
    questions = []
    for item in DEFAULT_QUESTIONS:
        questions.append(
            {
                "id": item["id"],
                "domain": item["domain"],
                "prompt": item[language_key(language)],
                "answer": normalize_score(answers.get(item["id"], 0)),
            }
        )
    return questions


def build_report(patient: dict, scorecard: dict, text_risk: dict, summary: str, recs: list[str]) -> str:
    return generate_clinical_report(patient, scorecard, text_risk, summary, recs)
