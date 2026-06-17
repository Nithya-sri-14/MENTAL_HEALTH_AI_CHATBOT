from __future__ import annotations

import os
import re
import google.generativeai as genai
from typing import Any

from .config import SAFE_GUARDRAILS


def get_api_key() -> str | None:
    # Check OS env first, then fall back to dotenv if loaded
    return os.environ.get("GEMINI_API_KEY")


def is_gemini_configured() -> bool:
    key = get_api_key()
    return bool(key and key.strip())


def init_gemini() -> bool:
    key = get_api_key()
    if key:
        try:
            genai.configure(api_key=key)
            return True
        except Exception:
            pass
    return False


def clean_text_for_prompt(text: str) -> str:
    # Strip dangerous HTML tags
    return re.sub(r"<[^>]*>", "", text)


def run_gemini_call(prompt: str, system_instruction: str | None = None) -> str | None:
    if not init_gemini():
        return None
    try:
        model_name = "gemini-2.5-flash"
        config = genai.GenerationConfig(temperature=0.3, max_output_tokens=1024)
        
        # Using newer SDK patterns or fallback
        if system_instruction:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction,
                generation_config=config
            )
        else:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=config
            )
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        # Fallback to gemini-1.5-flash if 2.5 is not yet enabled/supported in the region
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(f"{system_instruction}\n\n{prompt}" if system_instruction else prompt)
            return response.text.strip()
        except Exception:
            return None


def generate_chat_reply(patient_notes: str, user_message: str, language: str) -> str:
    user_message = clean_text_for_prompt(user_message)
    is_tamil = language.lower() == "tamil"
    
    # Check if Gemini API key is configured
    if is_gemini_configured():
        system_instruction = (
            "You are a supportive, safety-first clinical assistant in a mental health portal. "
            "Your tone is warm, professional, and empathetic. Do not diagnose or prescribe medication. "
            "Ensure you suggest a safety escalation or seeking a clinician if the user is in distress. "
            "Write the response strictly in the requested language."
        )
        
        prompt = (
            f"Active Language: {'Tamil' if is_tamil else 'English'}\n"
            f"Patient Context/Notes: {patient_notes}\n"
            f"Patient Message: {user_message}\n\n"
            f"Please generate a short 1-2 paragraph empathetic response."
        )
        
        reply = run_gemini_call(prompt, system_instruction=system_instruction)
        if reply:
            return reply

    # Fallback to local rule-based response if offline or key is missing
    lowered = user_message.lower()
    
    # Rule-based response selections
    if is_tamil:
        if any(word in lowered for word in ["தூக்கம்", "தூங்க", "sleep"]):
            return (
                "உங்கள் தூக்க சிக்கல்களைப் பகிர்ந்ததற்கு நன்றி. தூங்குவதற்கு முன் திரைகளைப் பார்ப்பதைத் தவிர்த்து, "
                "வெதுவெதுப்பான பால் அல்லது தியானத்தை முயற்சிக்கவும். தேவைப்பட்டால் உங்கள் மருத்துவரை அணுகவும்."
            )
        elif any(word in lowered for word in ["கவலை", "பயம்", "anxiety", "fear"]):
            return (
                "பதட்டமாக உணர்வது இயல்பானது. தயவுசெய்து உங்கள் கைகளை நெஞ்சில் வைத்துக்கொண்டு, மெதுவாக மூச்சை இழுத்து விடவும். "
                "உங்களைச் சுற்றியுள்ள ஐந்து பொருட்களைக் கவனியுங்கள்."
            )
        else:
            return (
                "நீங்கள் பகிர்ந்ததற்கு நன்றி. ஒரு சிறிய மூச்சுப் பயிற்சி செய்து, அடுத்த 10 நிமிடங்களுக்கு ஒரு சிறிய செயலில் "
                "கவனம் செலுத்துங்கள். இது தீவிரமாக இருந்தால் உடனே நிபுணர் உதவியைப் பெறுங்கள்."
            )
    else:
        if any(word in lowered for word in ["sleep", "insomnia", "tired"]):
            return (
                "Thank you for sharing. Sleep difficulties can heavily impact your well-being. Try establishing a screen-free "
                "wind-down routine 30 minutes before bed, keeping your room dark and cool. If sleep issues persist, consult a doctor."
            )
        elif any(word in lowered for word in ["anxious", "panic", "worry", "fear"]):
            return (
                "I hear how overwhelming this anxiety feels. Let's do a quick grounding exercise: name 5 things you can see, "
                "4 things you can touch, and take 3 deep, slow breaths. You are in a safe space right now."
            )
        elif any(word in lowered for word in ["depressed", "sad", "empty", "lonely"]):
            return (
                "Thank you for reaching out. Feeling low or empty is heavy to carry. Please consider connecting with a supportive "
                "family member or a licensed counselor. Remember to take things one small step at a time today."
            )
        else:
            return (
                "Thank you for sharing your thoughts. I encourage you to take a 2-minute grounding pause, focus on slow breathing, "
                "and identify one small, manageable task to focus on today. If this is urgent, please contact professional support."
            )


def generate_rag_answer(query: str, contexts: list[dict]) -> str:
    query = clean_text_for_prompt(query)
    
    if not contexts:
        return "No local document matches found to answer your question."
        
    context_str = "\n\n".join(f"Source: {c['title']}\nContent: {c['excerpt']}" for c in contexts)
    
    if is_gemini_configured():
        system_instruction = (
            "You are an expert clinical RAG assistant. Answer the psychologist's query using only the provided context snippets. "
            "If the answer cannot be found in the context, clearly state that and summarize the available context. "
            "Provide citations of the source documents in your response."
        )
        
        prompt = (
            f"Therapist Query: {query}\n\n"
            f"Context Documents:\n{context_str}\n\n"
            f"Generate a professional, structured response."
        )
        
        reply = run_gemini_call(prompt, system_instruction=system_instruction)
        if reply:
            return reply

    # Fallback response
    top = contexts[0]
    return (
        f"[Offline Fallback Answer]\n"
        f"Based on the document '{top['title']}' (Score: {top['score']}):\n"
        f"\"{top['excerpt']}...\"\n\n"
        f"Other matching documents include: {', '.join(c['title'] for c in contexts[1:])}."
    )


def generate_session_summary(transcript: str) -> str:
    transcript = clean_text_for_prompt(transcript)
    if not transcript.strip():
        return "No transcript content provided to summarize."
        
    if is_gemini_configured():
        system_instruction = (
            "You are a clinical transcriber. Summarize this session transcript in a professional clinical format. "
            "Focus on the patient's symptoms, emotions, presenting concerns, and progress. Keep it under 3-4 bullet points."
        )
        prompt = f"Transcript:\n{transcript}"
        reply = run_gemini_call(prompt, system_instruction=system_instruction)
        if reply:
            return reply

    # Fallback to local rule summary
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", transcript.strip()) if s.strip()]
    if not sentences:
        return "Empty transcript."
    return "\n".join(f"- {s}" for s in sentences[:3])


def generate_clinical_report(patient: dict, scorecard: dict, risk_info: dict, summary: str, recs: list[str]) -> str:
    patient_name = patient.get("name", "Unknown")
    
    if is_gemini_configured():
        system_instruction = (
            "You are an expert clinical psychologist. Generate a structured clinical report based on the provided patient data, "
            "psychometric scorecard, risk analysis, and session summary. Use clear professional headings and format in Markdown."
        )
        
        prompt = (
            f"Patient Profile:\n"
            f"- Name: {patient_name}\n"
            f"- Age: {patient.get('age')}\n"
            f"- Language: {patient.get('language')}\n"
            f"- Concern: {patient.get('primary_concern')}\n\n"
            f"Assessment Scorecard: {scorecard}\n"
            f"Text Risk Assessment: {risk_info}\n"
            f"Session Summary: {summary}\n"
            f"Standard Recommendations: {recs}\n"
        )
        
        reply = run_gemini_call(prompt, system_instruction=system_instruction)
        if reply:
            return reply

    # Fallback structured markdown report
    report = [
        f"# Clinical Workflow Report - {patient_name}",
        "",
        f"- **Patient ID**: {patient.get('patient_id', 'N/A')}",
        f"- **Age**: {patient.get('age', 'N/A')}",
        f"- **Primary Concern**: {patient.get('primary_concern', 'N/A')}",
        f"- **Language**: {patient.get('language', 'English')}",
        f"- **Assessment Score**: {scorecard.get('total', 0)} ({scorecard.get('risk_level', 'Low')} Risk)",
        f"- **Language Risk Score**: {risk_info.get('score', 0)} ({risk_info.get('risk_level', 'Low')} Risk)",
        "",
        "## Clinical Session Summary",
        summary,
        "",
        "## Recommendations",
    ]
    report.extend(f"- {r}" for r in recs)
    report.extend([
        "",
        "## Safeguard Status",
        "CRITICAL ESCALATION TRIGGERED. Alerting supervisor for psychologist review." if risk_info.get("escalate") else "Patient metrics fall within regular parameters. Schedule standard follow-up."
    ])
    return "\n".join(report)


def analyze_risk_nlp(text: str) -> dict:
    lowered = text.lower()
    
    # Standard keywords
    suicide_keywords = ["suicide", "kill myself", "end my life", "want to die", "hanging", "overdose"]
    self_harm_keywords = ["self-harm", "harm myself", "cutting", "burning", "hurting myself"]
    moderate_keywords = ["hopeless", "panic", "worthless", "depressed", "anxious", "stress", "can't sleep", "cannot sleep", "overwhelmed"]
    
    hits = []
    score = 0
    
    # Calculate score
    for word in suicide_keywords:
        if word in lowered:
            score += 50
            hits.append(word)
    for word in self_harm_keywords:
        if word in lowered:
            score += 45
            hits.append(word)
    for word in moderate_keywords:
        if word in lowered:
            score += 12
            hits.append(word)
            
    if len(re.findall(r"\w+", lowered)) < 6 and score > 0:
        score += 8
        
    score = min(score, 100)
    
    if score >= 55:
        risk_level = "Critical"
    elif score >= 30:
        risk_level = "High"
    elif score >= 12:
        risk_level = "Moderate"
    else:
        risk_level = "Low"
        
    return {
        "score": score,
        "risk_level": risk_level,
        "signals": list(set(hits)),
        "escalate": risk_level in {"High", "Critical"}
    }
