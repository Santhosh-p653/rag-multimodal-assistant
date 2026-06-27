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

        audio_bytes = await speak_text(
            "Hello, please check the system tray.",
            "en",
        )

        assert audio_bytes == b"mp3_bytes"

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