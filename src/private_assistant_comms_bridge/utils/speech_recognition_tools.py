import logging

import httpx
import numpy as np
import numpy.typing as np_typing
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


def int2float(sound: np_typing.NDArray[np.int16]) -> np_typing.NDArray[np.float32]:
    abs_max = np.abs(sound).max()
    sound_32: np_typing.NDArray[np.float32] = sound.astype(np.float32)
    if abs_max > 0:
        sound_32 *= 1 / 32768
    sound_32 = sound_32.squeeze()  # depends on the use case
    return sound_32


def format_audio_and_speech_prob(
    audio_frames: np_typing.NDArray[np.int16], input_samplerate: int
) -> tuple[int, np_typing.NDArray[np.float32]]:
    audio_float32 = int2float(audio_frames)
    # Calculate the number of full chunks of size 512
    num_chunks = len(audio_float32) // 512
    # Split the audio frames into chunks of size 512
    chunks = np.array_split(audio_float32[: num_chunks * 512], num_chunks)
    speech_probs = [
        vad_model(torch.from_numpy(chunk), input_samplerate).item() for chunk in chunks
    ]

    # Return the maximum probability and the processed audio
    max_speech_prob = max(speech_probs) if speech_probs else 0.0
    return round(max_speech_prob, 1), audio_float32


async def send_audio_to_stt_api(
    audio_data: np_typing.NDArray[np.float32], config_obj: config.Config
) -> dict | None:
    """Send the recorded audio to the stt batch api server."""
    files = {"file": ("audio.raw", audio_data.tobytes())}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config_obj.speech_transcription_api,
                files=files,
                headers={"user-token": config_obj.speech_transcription_api_token or ""},
                timeout=10.0,
            )
            response.raise_for_status()
        return response.json()
    except httpx.HTTPError as errh:
        logger.error("Http Error: %s", errh)
    return None


async def send_text_to_tts_api(
    text: str, config_obj: config.Config
) -> np_typing.NDArray[np.int16] | None:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config_obj.speech_synthesis_api,
                json={"text": text},  # Use form data to send the text
                headers={"user-token": config_obj.speech_synthesis_api_token or ""},
                timeout=10.0,
            )
            response.raise_for_status()

            # Read the streaming response content
            audio_bytes = b""
            async for chunk in response.aiter_bytes():
                audio_bytes += chunk

            # Convert the binary audio data to a NumPy array
            return np.frombuffer(audio_bytes, dtype=np.int16)  # Adjust dtype as needed
    except httpx.HTTPError as errh:
        logger.error("HTTP Error: %s", errh)
    return None
