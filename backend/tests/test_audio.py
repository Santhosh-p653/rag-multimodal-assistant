# ruff: noqa: E402

from unittest.mock import MagicMock, patch
import sys
import os
import asyncio
import subprocess
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Ensure mock modules exist in sys.modules even if run standalone without conftest.py
if "faster_whisper" not in sys.modules:
    sys.modules["faster_whisper"] = MagicMock()
if "edge_tts" not in sys.modules:
    sys.modules["edge_tts"] = MagicMock()

from app.services.audio import (
    speak_text,
    transcribe_audio,
    clean_text_for_speech,
    detect_script_language,
    detect_language,
    truncate_text,
    convert_to_wav,
    get_whisper_model,
)


def _create_mock_edge_communicate(expected_bytes: bytes = b"mp3_bytes"):
    mock_inst = MagicMock()

    async def mock_save(path):
        with open(path, "wb") as f:
            f.write(expected_bytes)

    mock_inst.save = mock_save
    mock_comm = MagicMock(return_value=mock_inst)
    return mock_comm


def test_voice_tts_generation():
    async def run_test():
        mock_comm = _create_mock_edge_communicate(b"mp3_bytes")
        with patch("app.services.audio.edge_tts.Communicate", mock_comm):
            audio_bytes, mime = await speak_text(
                "Hello, please check the system tray.",
                "en",
            )

            assert audio_bytes == b"mp3_bytes"
            assert mime == "audio/mpeg"
            mock_comm.assert_called_once()

    asyncio.run(run_test())


def test_voice_tts_empty_fallback():
    async def run_test():
        mock_comm = _create_mock_edge_communicate(b"fallback_mp3_bytes")
        with patch("app.services.audio.edge_tts.Communicate", mock_comm):
            audio_bytes, mime = await speak_text("", "en")
            assert audio_bytes == b"fallback_mp3_bytes"
            assert mime == "audio/mpeg"
            mock_comm.assert_called_once()

    asyncio.run(run_test())


def test_multilingual_script_detection_and_cleaning():
    raw_text = "**Step 1:** Check [J4 connector](http://link) `code_val` [Source: manual.pdf | Page: 4]."
    cleaned = clean_text_for_speech(raw_text)
    assert "**" not in cleaned
    assert "`" not in cleaned
    assert "code_val" not in cleaned
    assert "Source:" not in cleaned
    assert "Step 1: Check J4 connector." in cleaned

    assert detect_script_language("नमस्ते, आपका फ्रिज ठीक है।") == "hi"
    assert detect_script_language("வணக்கம், குளிர்சாதன பெட்டி") == "ta"
    assert detect_script_language("నమస్కారం, ఫ్రిజ్ బాగుందా") == "te"
    assert detect_script_language("ನಮಸ್ಕಾರ, ಫ್ರಿಜ್ ಚೆನ್ನಾಗಿದೆಯೇ") == "kn"
    assert detect_script_language("നമസ്കാരം, ഫ്രിഡ്ജ് ശരിയാണോ") == "ml"
    assert detect_script_language("নমস্কার, ফ্রিজ ভালো আছে") == "bn"
    assert detect_script_language("નમસ્તે, ફ્રિજ સારું છે") == "gu"
    assert detect_script_language("ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ, ਫਰਿੱਜ ਠੀਕ ਹੈ") == "pa"
    assert detect_script_language("Hello, how are you?") is None

    assert detect_language("नमस्ते", hint_language="auto") == "hi"
    assert detect_language("Hello world", hint_language="en") == "en"
    assert detect_language("வணக்கம்", hint_language=None) == "ta"


def test_truncate_text():
    text = "First sentence. Second sentence! Third sentence? Fourth sentence."
    truncated = truncate_text(text, max_sentences=3)
    assert truncated == "First sentence. Second sentence! Third sentence?"

    indic_text = "पहला वाक्य। दूसरा वाक्य। तीसरा वाक्य। चौथा वाक्य।"
    truncated_indic = truncate_text(indic_text, max_sentences=2)
    assert truncated_indic == "पहला वाक्य। दूसरा वाक्य।"


def test_sarvam_indic_tts_generation():
    import base64

    async def run_test():
        with patch("app.services.audio.SARVAM_API_KEY", "mock_sarvam_key"), \
             patch("httpx.AsyncClient.post") as mock_post:
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


def test_sarvam_tts_fallback_to_edge_tts():
    async def run_test():
        mock_comm = _create_mock_edge_communicate(b"fallback_edge_mp3")

        # Case 1: Sarvam API returns non-200 error
        with patch("app.services.audio.SARVAM_API_KEY", "mock_sarvam_key"), \
             patch("httpx.AsyncClient.post") as mock_post, \
             patch("app.services.audio.edge_tts.Communicate", mock_comm):
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"
            mock_post.return_value = mock_resp

            audio_bytes, mime = await speak_text("नमस्ते, फ्रिज चालू है।", "hi")
            assert audio_bytes == b"fallback_edge_mp3"
            assert mime == "audio/mpeg"

        # Case 2: Sarvam API raises connection/timeout exception
        mock_comm_2 = _create_mock_edge_communicate(b"fallback_edge_mp3_2")
        with patch("app.services.audio.SARVAM_API_KEY", "mock_sarvam_key"), \
             patch("httpx.AsyncClient.post", side_effect=Exception("Connection error")), \
             patch("app.services.audio.edge_tts.Communicate", mock_comm_2):
            audio_bytes, mime = await speak_text("नमस्ते, फ्रिज चालू है।", "hi")
            assert audio_bytes == b"fallback_edge_mp3_2"
            assert mime == "audio/mpeg"

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
    mock_convert.return_value = "fake_temp.wav"

    mock_model = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "Hello world transcription"
    mock_info = MagicMock()
    mock_info.language = "en"

    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    with patch("app.services.audio.get_whisper_model", return_value=mock_model):
        async def run_test():
            res = await transcribe_audio("fake_temp.wav", "en")
            assert res["text"] == "Hello world transcription"
            assert res["detected_language"] == "en"

        asyncio.run(run_test())


def test_sarvam_indic_stt_transcription(tmp_path):
    fake_audio = tmp_path / "sample.wav"
    fake_audio.write_bytes(b"RIFF_test_audio")

    async def run_test():
        with patch("app.services.audio.convert_to_wav", return_value=str(fake_audio)), \
             patch("app.services.audio.SARVAM_API_KEY", "mock_sarvam_key"), \
             patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"transcript": "नमस्ते यह एक परीक्षण है"}
            mock_post.return_value = mock_resp

            res = await transcribe_audio(str(fake_audio), "hi")
            assert res["text"] == "नमस्ते यह एक परीक्षण है"
            assert res["detected_language"] == "hi"

    asyncio.run(run_test())


def test_sarvam_stt_auto_detect_language(tmp_path):
    fake_audio = tmp_path / "sample.wav"
    fake_audio.write_bytes(b"RIFF_test_audio")

    async def run_test():
        with patch("app.services.audio.convert_to_wav", return_value=str(fake_audio)), \
             patch("app.services.audio.SARVAM_API_KEY", "mock_sarvam_key"), \
             patch("httpx.AsyncClient.post") as mock_post, \
             patch("app.services.audio.detect", return_value="hi"):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"transcript": "नमस्ते"}
            mock_post.return_value = mock_resp

            res = await transcribe_audio(str(fake_audio), "auto")
            assert res["text"] == "नमस्ते"
            assert res["detected_language"] == "hi"

    asyncio.run(run_test())


def test_sarvam_stt_missing_api_key(tmp_path):
    fake_audio = tmp_path / "sample.wav"
    fake_audio.write_bytes(b"RIFF_test_audio")

    async def run_test():
        with patch("app.services.audio.convert_to_wav", return_value=str(fake_audio)), \
             patch("app.services.audio.SARVAM_API_KEY", ""):
            with pytest.raises(RuntimeError, match="SARVAM_API_KEY not configured"):
                await transcribe_audio(str(fake_audio), "hi")

    asyncio.run(run_test())


def test_sarvam_stt_api_error(tmp_path):
    fake_audio = tmp_path / "sample.wav"
    fake_audio.write_bytes(b"RIFF_test_audio")

    async def run_test():
        with patch("app.services.audio.convert_to_wav", return_value=str(fake_audio)), \
             patch("app.services.audio.SARVAM_API_KEY", "mock_key"), \
             patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_post.return_value = mock_resp

            with pytest.raises(RuntimeError, match="Sarvam API error: Unauthorized"):
                await transcribe_audio(str(fake_audio), "hi")

    asyncio.run(run_test())


def test_convert_to_wav():
    with patch("imageio_ffmpeg.get_ffmpeg_exe", return_value="ffmpeg.exe"), \
         patch("subprocess.run") as mock_sub:
        out_path = convert_to_wav("sample_input.mp3")
        assert out_path.endswith(".wav")
        mock_sub.assert_called_once()
        cmd = mock_sub.call_args[0][0]
        assert cmd[0] == "ffmpeg.exe"
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "-ac" in cmd
        assert "1" in cmd

    with patch("imageio_ffmpeg.get_ffmpeg_exe", return_value="ffmpeg.exe"), \
         patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg")):
        with pytest.raises(RuntimeError, match="Audio transcoding failed"):
            convert_to_wav("sample_input.mp3")


def test_get_whisper_model_singleton():
    import app.services.audio as audio_mod
    old_model = audio_mod._whisper_model
    try:
        audio_mod._whisper_model = None
        mock_instance = MagicMock()
        mock_fw_class = MagicMock(return_value=mock_instance)

        with patch.dict(sys.modules, {"faster_whisper": MagicMock(WhisperModel=mock_fw_class)}):
            m1 = get_whisper_model()
            m2 = get_whisper_model()
            assert m1 is mock_instance
            assert m2 is mock_instance
            assert m1 is m2
            assert mock_fw_class.call_count == 1
    finally:
        audio_mod._whisper_model = old_model


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main(["-v", __file__]))