from __future__ import annotations

import os
from .gemini_service import run_gemini_call, is_gemini_configured


def predict_retention(patient: dict, chat_history: list[dict] | None = None) -> dict:
    name = patient.get("name", "Unknown")
    age = patient.get("age", 30)
    concern = patient.get("primary_concern", "None")
    engagement = patient.get("engagement", 70)
    missed_sessions = patient.get("missed_sessions", 0)
    risk_level = patient.get("risk_level", "Low")
    notes = patient.get("notes", "")

    # 1. Rule-based calculation of retention probability
    # Base probability
    prob = 0.88
    risk_factors = []

    # Penalty for missed sessions
    if missed_sessions > 0:
        penalty = min(missed_sessions * 0.14, 0.45)
        prob -= penalty
        risk_factors.append(f"Missed sessions: {missed_sessions} session(s) absent")

    # Penalty/bonus for engagement
    if engagement < 50:
        prob -= 0.25
        risk_factors.append(f"Low engagement index: {engagement}%")
    elif engagement < 70:
        prob -= 0.10
        risk_factors.append(f"Moderate engagement index: {engagement}%")
    elif engagement > 85:
        prob += 0.05

    # Penalty for clinical risk
    if risk_level == "Critical":
        prob -= 0.20
        risk_factors.append("Critical clinical risk status")
    elif risk_level == "High":
        prob -= 0.12
        risk_factors.append("High clinical risk status")
    elif risk_level == "Moderate":
        prob -= 0.05

    # Check chat history sentiment if present
    sentiment_factor = 0.0
    recent_chat_neg = False
    if chat_history:
        # Check last 5 messages for negative sentiment signals
        neg_count = 0
        for turn in chat_history[-5:]:
            msg = (turn.get("message") or "").lower()
            reply = (turn.get("reply") or "").lower()
            text_to_scan = f"{msg} {reply}"
            if any(w in text_to_scan for w in ["hopeless", "sad", "useless", "frustrated", "don't want", "stop", "cancel", "useless"]):
                neg_count += 1
        if neg_count >= 2:
            sentiment_factor = 0.08
            recent_chat_neg = True
            prob -= sentiment_factor
            risk_factors.append("Negative sentiment detected in recent chat transcripts")

    # Clamp probability
    prob = round(max(0.05, min(0.98, prob)), 2)

    # Determine churn risk level
    if prob >= 0.75:
        churn_level = "Low"
    elif prob >= 0.45:
        churn_level = "Moderate"
    else:
        churn_level = "High"

    # Generate recommendations
    recs = []
    if missed_sessions >= 2:
        recs.append("Conduct a proactive checkout call to address scheduling conflicts or transportation barriers.")
    if engagement < 60:
        recs.append("Simplify homework worksheets and introduce short 5-minute self-guided micro-sessions.")
    if risk_level in {"High", "Critical"}:
        recs.append("Trigger priority clinical review and discuss crisis plan accessibility.")
    if recent_chat_neg:
        recs.append("Directly address session frustration or perceived stagnation in the next therapy session.")
    if len(recs) == 0:
        recs.append("Continue current support structure; schedule next routine appointment.")
        recs.append("Provide monthly progress reports to build patient self-efficacy.")

    # 2. Generate analysis narrative using Gemini if active, otherwise fallback
    narrative = ""
    if is_gemini_configured():
        system_instruction = (
            "You are an expert mental health clinic retention agent. Your job is to analyze "
            "clinical metadata (engagement index, missed sessions, risk level, primary concerns) "
            "and write a professional, concise, actionable predictive retention narrative. "
            "Include an analysis of why the patient might drop out and how the therapist can intervene."
        )

        prompt = (
            f"Patient Profile:\n"
            f"- Name: {name}\n"
            f"- Age: {age}\n"
            f"- Primary Concern: {concern}\n"
            f"- Engagement level: {engagement}%\n"
            f"- Missed sessions: {missed_sessions}\n"
            f"- Clinical Risk: {risk_level}\n"
            f"- Notes: {notes}\n"
            f"- Calculated Retention Probability: {prob * 100}%\n"
            f"- Identified Risk Factors: {', '.join(risk_factors) if risk_factors else 'None'}\n\n"
            f"Please generate a short, professional, 1-2 paragraph retention forecast and intervention analysis."
        )

        reply = run_gemini_call(prompt, system_instruction=system_instruction)
        if reply:
            narrative = reply

    if not narrative:
        # Offline rule-based fallback
        if churn_level == "High":
            narrative = (
                f"Warning: {name} is at a high risk of dropping out from treatment. The combination of "
                f"{missed_sessions} missed sessions and an engagement rating of {engagement}% indicates "
                f"substantial friction or detachment from the therapeutic process. Immediate clinical "
                f"outreach is highly recommended to understand barriers to attendance and restore alignment."
            )
        elif churn_level == "Moderate":
            narrative = (
                f"{name} displays moderate retention risk. While they remain somewhat engaged, "
                f"specific markers such as missed sessions or shifting engagement metrics suggest "
                f"a need for intervention. It is advised to review their treatment goals in the next "
                f"session and confirm their feedback on the therapy pace."
            )
        else:
            narrative = (
                f"{name} maintains strong retention metrics. With an engagement level of {engagement}% "
                f"and minimal missed sessions, they demonstrate high adherence to the treatment plan. "
                f"Maintain the current supportive framework and continue reinforcing their positive progress."
            )

    return {
        "patient_name": name,
        "retention_probability": prob,
        "churn_risk_level": churn_level,
        "risk_factors": risk_factors,
        "analysis_narrative": narrative,
        "recommendations": recs
    }
