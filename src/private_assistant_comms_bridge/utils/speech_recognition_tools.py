import base64
import logging

import httpx
import numpy as np
import torch

from private_assistant_comms_bridge.utils import (
    config,
)

logger = logging.getLogger(__name__)


torch.set_num_threads(1)
vad_model, utils = torch.hub.load(
    repo_or_dir="snakers4/silero-vad",
    model="silero_vad",
    force_reload=False,
    onnx=True,
)


def numpy_array_to_base64(audio_data):
    """Convert a numpy array to a base64 encoded string."""
    audio_bytes = audio_data.tobytes()
    base64_bytes = base64.b64encode(audio_bytes)
    base64_string = base64_bytes.decode("utf-8")
    return base64_string


def format_audio_and_speech_prob(
    audio_frames: np.ndarray, config_obj: config.Config
) -> tuple[int, np.ndarray]:
    samplerate = config_obj.sounddevice_input_samplerate
    audio_data = audio_frames.flatten().astype(np.float32) / 32768.0
    speech_prob = vad_model(torch.from_numpy(audio_data.copy()), samplerate).item()
    return speech_prob, audio_data


def send_audio_to_stt_api(
    audio_base64, dtype, config_obj: config.Config
) -> dict | None:
    """Send the recorded audio to the FastAPI server."""
    url = config_obj.speech_transcription_api
    payload = {
        "audio_base64": audio_base64,
        "dtype": dtype,
    }
    try:
        with httpx.Client() as client:
            response = client.post(
                url,
                json=payload,
                headers={"user-token": config_obj.speech_transcription_api_token or ""},
                timeout=10.0,
            )
            response.raise_for_status()
        return response.json()
    except httpx.HTTPError as errh:
        logger.error("Http Error: %s", errh)
    return None


def send_text_to_tts_api(text: str, config_obj: config.Config) -> np.ndarray | None:
    json_data = {
        "samplerate": config_obj.sounddevice_output_samplerate,
        "text": text,
    }
    try:
        with httpx.Client() as client:
            response = client.post(
                config_obj.speech_synthesis_api,
                json=json_data,
                headers={"user-token": config_obj.speech_synthesis_api_token or ""},
                timeout=10.0,
            )
            response.raise_for_status()
            response_json = response.json()
        audio_bytes = base64.b64decode(response_json["audio_base64"])
        return np.frombuffer(audio_bytes, dtype=response_json["dtype"])
    except httpx.HTTPError as errh:
        logger.error("Http Error: %s", errh)
    return None
