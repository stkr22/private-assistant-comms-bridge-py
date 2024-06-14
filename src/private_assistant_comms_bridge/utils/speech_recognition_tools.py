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


def numpy_array_to_base64(audio_data: np.ndarray):
    """Convert a numpy array to a base64 encoded string."""
    audio_bytes = audio_data.tobytes()
    base64_bytes = base64.b64encode(audio_bytes)
    base64_string = base64_bytes.decode("utf-8")
    return base64_string


def int2float(sound: np.ndarray):
    abs_max = np.abs(sound).max()
    sound = sound.astype(np.float32)
    if abs_max > 0:
        sound *= 1 / 32768
    sound = sound.squeeze()  # depends on the use case
    return sound


def format_audio_and_speech_prob(
    audio_frames: np.ndarray, input_samplerate: int
) -> tuple[int, np.ndarray]:
    audio_float32 = int2float(audio_frames)
    speech_prob = vad_model(torch.from_numpy(audio_float32), input_samplerate).item()
    return speech_prob, audio_float32


async def send_audio_to_stt_api(
    audio_base64: str, dtype: str, config_obj: config.Config
) -> dict | None:
    """Send the recorded audio to the FastAPI server."""
    url = config_obj.speech_transcription_api
    payload = {
        "audio_base64": audio_base64,
        "dtype": dtype,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
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


async def send_text_to_tts_api(
    text: str, config_obj: config.Config, input_samplerate: int
) -> np.ndarray | None:
    json_data = {
        "samplerate": input_samplerate,
        "text": text,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
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
