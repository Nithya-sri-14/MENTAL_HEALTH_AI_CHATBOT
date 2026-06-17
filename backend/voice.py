from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile


def normalize_voice_language(language: str) -> str:
    value = (language or "").strip().lower()
    if value in {"tamil", "ta", "ta-in", "தமிழ்"}:
        return "ta-IN"
    return "en-US"


def tts_language_code(language: str) -> str:
    return "ta" if normalize_voice_language(language).startswith("ta") else "en"


def transcribe_audio_file(path: Path, language: str = "en-US") -> tuple[str, str]:
    """
    Optional voice input helper.
    Returns (transcript, engine_name). Falls back gracefully when libraries are absent.
    """
    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        with sr.AudioFile(str(path)) as source:
            audio = recognizer.record(source)
        transcript = recognizer.recognize_google(audio, language=normalize_voice_language(language))
        return transcript, "speech_recognition"
    except Exception:
        return "", "unavailable"


def transcribe_audio_bytes(audio_bytes: bytes, suffix: str = ".wav", language: str = "en-US") -> tuple[str, str]:
    try:
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            return transcribe_audio_file(Path(tmp.name), language=language)
    except Exception:
        return "", "unavailable"


def synthesize_speech(text: str, output_path: Path, lang: str = "en") -> Path | None:
    try:
        from gtts import gTTS

        tts = gTTS(text=text, lang=lang)
        tts.save(str(output_path))
        return output_path
    except Exception:
        return None


def tune_tamil_tts_text(text: str) -> str:
    """
    Keep Tamil output short and speech-friendly.
    """
    cleaned = " ".join(text.split())
    cleaned = cleaned.replace("՝", ",").replace(";", ",")
    if len(cleaned) > 220:
        cleaned = cleaned[:217].rstrip() + "..."
    return cleaned
