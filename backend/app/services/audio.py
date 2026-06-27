"""
audio.py — Audio processing service.
Provides hybrid speech-to-text (STT) via faster-whisper (local) and Sarvam AI (API),
and text-to-speech (TTS) via edge-tts (local Microsoft Neural Voices).
"""
import os
import re
import tempfile
import subprocess
import httpx
import edge_tts
from langdetect import detect
from app.config import SARVAM_API_KEY

# Voice mapping for edge-tts Microsoft Neural voices (Female by default)
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

# Language mapping for Sarvam AI Saaras v3 STT
SARVAM_LANG_MAP = {
    "en": "en-IN",
    "hi": "hi-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "bn": "bn-IN",
    "mr": "mr-IN",
    "auto": "unknown",
}

# Lazy load local faster-whisper model
_whisper_model = None


def get_whisper_model():
    """Singleton for local Whisper Model on CPU."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        print("[Audio] Loading local faster-whisper ('small', int8, CPU)...")
        # Pre-cache during docker build installs model in default Hugging Face cache
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        print("[Audio] local faster-whisper model ready.")
    return _whisper_model


def convert_to_wav(input_path: str) -> str:
    """
    Transcode uploaded audio file to standard 16kHz mono WAV using FFmpeg.
    Ensures compatibility with both Whisper and Sarvam AI.
    """
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, f"transcoded_{os.path.basename(input_path)}.wav")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        output_path
    ]
    try:
        # Run conversion silently
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode("utf-8", errors="ignore")
        print(f"[Audio] FFmpeg transcoding failed: {err_msg}")
        raise RuntimeError(f"Audio transcoding failed: {err_msg}")


async def transcribe_audio(file_path: str, hint_lang: str) -> dict:
    """
    Transcribe audio file using the hybrid engine routing logic:
      - hint_lang == "en" -> faster-whisper (local)
      - anything else -> Sarvam AI Saaras v3 API
    """
    # 1. Transcode input audio to 16kHz mono WAV PCM
    transcoded_path = convert_to_wav(file_path)

    try:
        if hint_lang == "en":
            # Engine A: Local English Transcription
            print("[Audio] Routing transcription to Local faster-whisper...")
            model = get_whisper_model()
            segments, info = model.transcribe(transcoded_path, beam_size=5)
            text = " ".join([segment.text for segment in segments]).strip()
            return {
                "text": text,
                "detected_language": info.language
            }
        else:
            # Engine B: Sarvam AI Indic/Automatic Translation & Transcription
            print(f"[Audio] Routing transcription to Sarvam AI (hint: {hint_lang})...")
            if not SARVAM_API_KEY:
                raise RuntimeError("SARVAM_API_KEY is not configured in backend/.env")

            sarvam_lang = SARVAM_LANG_MAP.get(hint_lang, "unknown")
            
            async with httpx.AsyncClient() as client:
                with open(transcoded_path, "rb") as audio_file:
                    files = {"file": (os.path.basename(transcoded_path), audio_file, "audio/wav")}
                    data = {
                        "model": "saaras:v3",
                        "mode": "transcribe",
                        "language_code": sarvam_lang,
                    }
                    headers = {
                        "api-subscription-key": SARVAM_API_KEY
                    }
                    response = await client.post(
                        "https://api.sarvam.ai/speech-to-text",
                        files=files,
                        data=data,
                        headers=headers,
                        timeout=30.0
                    )
                
                if response.status_code != 200:
                    raise RuntimeError(f"Sarvam API error ({response.status_code}): {response.text}")
                
                res_data = response.json()
                transcript = res_data.get("transcript", "")
                
                # Detect language if auto was requested
                detected_lang = hint_lang
                if hint_lang == "auto" and transcript:
                    try:
                        detected_lang = detect(transcript)
                    except Exception:
                        detected_lang = "unknown"
                        
                return {
                    "text": transcript.strip(),
                    "detected_language": detected_lang
                }
    finally:
        # Cleanup transcoded temp file
        if os.path.exists(transcoded_path):
            os.remove(transcoded_path)


def truncate_text(text: str, max_sentences: int = 3) -> str:
    """Truncate text to first N sentences to minimize TTS generation latency."""
    # Split text by punctuation marks (., !, ?, and Indian danda |)
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    trimmed = " ".join(sentences[:max_sentences])
    return trimmed


def detect_language(text: str) -> str:
    """Lightweight local language detection fallback."""
    try:
        return detect(text)
    except Exception:
        return "en"


async def speak_text(text: str, language: str = None) -> bytes:
    """
    Generate MP3 speech stream from text using edge-tts.
    Truncates text and detects language to match Microsoft Neural voices.
    """
    # 1. Truncate text to first 2-3 sentences to reduce CPU delay
    truncated = truncate_text(text, max_sentences=3)
    if not truncated:
        truncated = "No response text to read."

    # 2. Pick/Resolve language code
    if not language or language == "auto" or language == "unknown":
        language = detect_language(truncated)

    # Extract base language code (e.g. "hi-IN" -> "hi")
    lang_key = language.split("-")[0].lower()
    voice = VOICE_TABLE.get(lang_key, "en-IN-NeerjaNeural")

    print(f"[Audio] Generating TTS using voice '{voice}' for language key '{lang_key}'")

    # 3. Stream from edge-tts
    communicate = edge_tts.Communicate(truncated, voice)
    
    # Save to a temporary file first, then read into memory
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            mp3_data = f.read()
        return mp3_data
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
