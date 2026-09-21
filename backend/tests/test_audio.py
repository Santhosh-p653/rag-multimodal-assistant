# ruff: noqa: E402

from unittest.mock import MagicMock, patch
import sys
import os
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Retrieve globally mocked modules from sys.modules
mock_fw = sys.modules["faster_whisper"]
mock_edge = sys.modules["edge_tts"]

from app.services.audio import speak_text, transcribe_audio


def test_voice_tts_generation():
    async def run_test():
        # Overwrite edge_tts Communicate instantiation
        mock_inst = MagicMock()

        async def mock_save(path):
            with open(path, "wb") as f:
                f.write(b"mp3_bytes")

        mock_inst.save = mock_save
        mock_edge.Communicate.return_value = mock_inst

        audio_bytes, mime = await speak_text(
            "Hello, please check the system tray.",
            "en",
        )

        assert audio_bytes == b"mp3_bytes"
        assert mime == "audio/mpeg"

    asyncio.run(run_test())


def test_multilingual_script_detection_and_cleaning():
    from app.services.audio import clean_text_for_speech, detect_script_language, detect_language

    raw_text = "**Step 1:** Check [J4 connector](http://link) [Source: manual.pdf | Page: 4]."
    cleaned = clean_text_for_speech(raw_text)
    assert "**" not in cleaned
    assert "Source:" not in cleaned
    assert "Step 1: Check J4 connector." in cleaned

    assert detect_script_language("नमस्ते, आपका फ्रिज ठीक है।") == "hi"
    assert detect_script_language("வணக்கம், குளிர்சாதன பெட்டி") == "ta"
    assert detect_script_language("నమస్కారం, ఫ్రిజ్ బాగుందా") == "te"

    assert detect_language("नमस्ते", hint_language="auto") == "hi"
    assert detect_language("Hello world", hint_language="en") == "en"


def test_sarvam_indic_tts_generation():
    import base64
    async def run_test():
        with patch("httpx.AsyncClient.post") as mock_post:
            fake_wav = b"RIFF_test_wav_content"
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "audios": [base64.b64encode(fake_wav).decode("utf-8")]
            }
            mock_post.return_value = mock_resp

            audio_bytes, mime = await speak_text("नमस्ते, फ्रिज चालू है।", "hi")
            assert audio_bytes == fake_wav
            assert mime == "audio/wav"

    asyncio.run(run_test())




@patch("app.services.audio.os.remove")
@patch("app.services.audio.convert_to_wav")
@patch("app.services.audio.os.path.exists", return_value=True)
@patch("app.services.audio.subprocess.run")
def test_local_stt_transcription(
    mock_sub,
    mock_exists,
    mock_convert,
    mock_remove,
):
    # Mock convert_to_wav to just pass through
    mock_convert.return_value = "fake_temp.wav"

    # Mock local Whisper transcribe
    mock_model = MagicMock()

    mock_segment = MagicMock()
    mock_segment.text = "Hello world transcription"

    mock_info = MagicMock()
    mock_info.language = "en"

    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    mock_fw.WhisperModel.return_value = mock_model

    async def run_test():
        res = await transcribe_audio("fake_temp.wav", "en")

        assert res["text"] == "Hello world transcription"
        assert res["detected_language"] == "en"

    asyncio.run(run_test())