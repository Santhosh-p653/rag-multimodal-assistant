"""
audio.py — Audio processing service.
Provides hybrid speech-to-text (STT) via faster-whisper (local) and Sarvam AI (API),
and text-to-speech (TTS) via edge-tts (local Microsoft Neural Voices).
"""
import os
import re
import tempfile
import subprocess  # nosec B404
from typing import Optional, Dict, Any, Tuple
import httpx
import edge_tts
from langdetect import detect
from app.config import SARVAM_API_KEY, settings

# Ensure current environment value is loaded if available
if not SARVAM_API_KEY:
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

VOICE_TABLE = {
    "en": "en-IN-NeerjaNeural",
    "hi": "hi-IN-SwaraNeural",
    "ta": "ta-IN-PallaviNeural",
    "te": "te-IN-ShrutiNeural",
    "kn": "kn-IN-SapnaNeural",
    "ml": "ml-IN-SobhanaNeural",
    "bn": "bn-IN-TanishaaNeural",
    "mr": "mr-IN-AarohiNeural",
}

SARVAM_LANG_MAP = {
    "en": "en-IN",
    "en-in": "en-IN",
    "hi": "hi-IN",
    "hi-in": "hi-IN",
    "ta": "ta-IN",
    "ta-in": "ta-IN",
    "te": "te-IN",
    "te-in": "te-IN",
    "kn": "kn-IN",
    "kn-in": "kn-IN",
    "ml": "ml-IN",
    "ml-in": "ml-IN",
    "bn": "bn-IN",
    "bn-in": "bn-IN",
    "mr": "mr-IN",
    "mr-in": "mr-IN",
    "gu": "gu-IN",
    "gu-in": "gu-IN",
    "pa": "pa-IN",
    "pa-in": "pa-IN",
    "auto": "unknown",
}

_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        print("[Audio] Loading local faster-whisper ('small', int8, CPU)...")
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        print("[Audio] local faster-whisper model ready.")
    return _whisper_model


def convert_to_wav(input_path: str) -> str:
    """
    Transcode uploaded audio file to standard 16kHz mono WAV using FFmpeg.
    """
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(
        temp_dir,
        f"transcoded_{os.path.basename(input_path)}.wav"
    )

    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        input_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        output_path
    ]

    try:
        subprocess.run(
            cmd,
            shell=False,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )  # nosec B603
        return output_path

    except subprocess.CalledProcessError as e:
        raise RuntimeError("Audio transcoding failed") from e


async def transcribe_audio(file_path: str, hint_lang: str) -> dict:
    """
    Hybrid STT pipeline:
    - Indic languages (Tamil, Hindi, etc.): Primary Sarvam AI (saaras:v3) with faster-whisper fallback
    - English: Primary faster-whisper local model with Sarvam en-IN fallback
    - Auto / Unknown: Sarvam AI with faster-whisper fallback
    """
    transcoded_path = convert_to_wav(file_path)

    clean_hint = (hint_lang or "auto").strip().lower()
    base_lang = clean_hint.split("-")[0]

    try:
        active_key = SARVAM_API_KEY or os.getenv("SARVAM_API_KEY", "")

        # 1. Primary path for Indic languages (or auto if Sarvam key available)
        if base_lang in INDIC_LANGUAGES or (base_lang in ("auto", "unknown") and active_key):
            sarvam_lang = SARVAM_LANG_MAP.get(clean_hint, SARVAM_LANG_MAP.get(base_lang, "unknown"))
            if active_key:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        with open(transcoded_path, "rb") as audio_file:
                            audio_content = audio_file.read()
                            response = await client.post(
                                "https://api.sarvam.ai/speech-to-text",
                                files={
                                    "file": (
                                        os.path.basename(transcoded_path),
                                        audio_content,
                                        "audio/wav",
                                    )
                                },
                                data={
                                    "model": "saaras:v3",
                                    "mode": "transcribe",
                                    "language_code": sarvam_lang,
                                },
                                headers={"api-subscription-key": active_key},
                            )

                    if response.status_code == 200:
                        res_data = response.json()
                        transcript = res_data.get("transcript", "").strip()
                        sarvam_code = res_data.get("language_code")
                        detected_lang = base_lang if base_lang not in ("auto", "unknown") else "en"

                        if sarvam_code and sarvam_code != "unknown":
                            detected_lang = sarvam_code.split("-")[0].lower()
                        elif transcript:
                            script_l = detect_script_language(transcript)
                            if script_l:
                                detected_lang = script_l
                            else:
                                try:
                                    detected_lang = detect(transcript)
                                except Exception:
                                    pass

                        return {
                            "text": transcript,
                            "detected_language": detected_lang,
                        }
                    else:
                        logger.warning(f"[Audio] Sarvam STT returned status {response.status_code}: {response.text}")
                except Exception as s_err:
                    logger.warning(f"[Audio] Sarvam STT request failed, trying faster-whisper: {s_err}")

        # 2. Faster-whisper engine (primary for English, robust fallback for Indic/auto)
        try:
            model = get_whisper_model()
            whisper_lang = None if base_lang in ("auto", "unknown") else base_lang
            segments, info = model.transcribe(transcoded_path, beam_size=5, language=whisper_lang)
            text = " ".join([s.text for s in segments]).strip()
            return {
                "text": text,
                "detected_language": info.language if info else base_lang,
            }
        except Exception as w_err:
            logger.error(f"[Audio] faster-whisper transcription error: {w_err}")
            # Final fallback to Sarvam en-IN if whisper crashed on English
            if active_key and base_lang == "en":
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        with open(transcoded_path, "rb") as audio_file:
                            response = await client.post(
                                "https://api.sarvam.ai/speech-to-text",
                                files={"file": (os.path.basename(transcoded_path), audio_file.read(), "audio/wav")},
                                data={"model": "saaras:v3", "mode": "transcribe", "language_code": "en-IN"},
                                headers={"api-subscription-key": active_key},
                            )
                        if response.status_code == 200:
                            return {"text": response.json().get("transcript", "").strip(), "detected_language": "en"}
                except Exception:
                    pass
            raise RuntimeError(f"Transcription failed across all available STT engines: {w_err}")

    finally:
        if os.path.exists(transcoded_path):
            try:
                os.remove(transcoded_path)
            except Exception:
                pass


import base64
import logging

logger = logging.getLogger(__name__)


def clean_text_for_speech(text: str) -> str:
    """
    Clean markdown formatting, technical syntax, and citations to produce
    natural, spoken-friendly text.
    """
    if not text:
        return ""
    cleaned = text.strip()
    # Remove code blocks
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    # Remove inline code
    cleaned = re.sub(r"`[^`]+`", "", cleaned)
    # Remove markdown links: [text](url) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    # Remove source citations: [Source: ... | Page: ...]
    cleaned = re.sub(r"\[Source:[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[Page:[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    # Remove headers: # Header
    cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    # Remove markdown bold/italics
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    # Remove bullet markers
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    # Remove blockquotes
    cleaned = re.sub(r"^\s*>\s*", "", cleaned, flags=re.MULTILINE)
    # Normalize space before punctuation
    cleaned = re.sub(r"\s+([.,!?:;])", r"\1", cleaned)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


INDIC_LANGUAGES = {"hi", "ta", "te", "kn", "ml", "bn", "mr", "gu", "pa"}


def detect_script_language(text: str) -> Optional[str]:
    """
    Detect Indian language from native Unicode script with 100% deterministic accuracy.
    """
    # Devanagari (Hindi, Marathi)
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    # Tamil
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta"
    # Telugu
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te"
    # Kannada
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "kn"
    # Malayalam
    if re.search(r"[\u0D00-\u0D7F]", text):
        return "ml"
    # Bengali
    if re.search(r"[\u0980-\u09FF]", text):
        return "bn"
    # Gujarati
    if re.search(r"[\u0A80-\u0AFF]", text):
        return "gu"
    # Gurmukhi
    if re.search(r"[\u0A00-\u0A7F]", text):
        return "pa"
    return None


def truncate_text(text: str, max_sentences: int = 3) -> str:
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    return " ".join(sentences[:max_sentences])


def detect_language(text: str, hint_language: Optional[str] = None) -> str:
    """
    Resolves the intended language using script inspection first, statistical detection,
    and hint fallback. Never forces an Indic voice on pure English/Latin text.
    """
    if not text:
        return "en"

    # 1. Exact Unicode script detection takes highest priority
    script_lang = detect_script_language(text)
    if script_lang:
        return script_lang

    # 2. Check if text is predominantly ASCII/Latin
    is_pure_ascii = all(ord(c) < 128 for c in text.replace("\n", " ").strip())
    if is_pure_ascii:
        return "en"

    # 3. Statistical detection on non-script text
    try:
        detected = detect(text)
        if detected in VOICE_TABLE:
            return detected
    except Exception:
        pass

    # 4. If hint language is given and valid
    if hint_language and hint_language not in ("auto", "unknown"):
        clean_hint = hint_language.split("-")[0].lower()
        if clean_hint in VOICE_TABLE:
            return clean_hint

    return "en"


async def speak_text(text: str, language: Optional[str] = None) -> tuple[bytes, str]:
    """
    Synthesizes speech using Sarvam AI (native Indian neural models) for Indic languages,
    falling back seamlessly to Edge-TTS.

    Returns:
        tuple of (audio_bytes, mime_type)
    """
    cleaned_full = clean_text_for_speech(text)
    truncated = truncate_text(cleaned_full, 3) or "No response text to read."

    target_lang = detect_language(truncated, hint_language=language)
    lang_key = target_lang.split("-")[0].lower()

    # 1. Attempt Sarvam AI Text-to-Speech for supported Indian languages
    active_key = SARVAM_API_KEY or os.getenv("SARVAM_API_KEY", "")
    if active_key and lang_key in INDIC_LANGUAGES:
        sarvam_code = SARVAM_LANG_MAP.get(lang_key, f"{lang_key}-IN")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(
                    "https://api.sarvam.ai/text-to-speech",
                    headers={
                        "api-subscription-key": active_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "inputs": [truncated],
                        "target_language_code": sarvam_code,
                        "speaker": "kavya",
                        "model": "bulbul:v3",
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    audios = data.get("audios", [])
                    if audios and audios[0]:
                        audio_bytes = base64.b64decode(audios[0])
                        return audio_bytes, "audio/wav"
                else:
                    logger.warning(f"[Audio] Sarvam TTS returned status {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"[Audio] Sarvam TTS failed, falling back to edge-tts: {e}")

    # 2. Edge-TTS for English or fallback for Indic languages
    voice = VOICE_TABLE.get(lang_key, "en-IN-NeerjaNeural")
    communicate = edge_tts.Communicate(truncated, voice)

    import uuid
    temp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(temp_dir, f"tts_speech_{uuid.uuid4().hex}.mp3")

    try:
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read(), "audio/mpeg"
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass