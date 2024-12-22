import logging

import httpx
import numpy as np
import numpy.typing as np_typing

from private_assistant_comms_bridge.utils import (
    config,
)

logger = logging.getLogger(__name__)


def int2float(sound: np_typing.NDArray[np.int16]) -> np_typing.NDArray[np.float32]:
    abs_max = np.abs(sound).max()
    sound_32: np_typing.NDArray[np.float32] = sound.astype(np.float32)
    if abs_max > 0:
        sound_32 *= 1 / 32768
    return sound_32.squeeze()


async def send_audio_to_stt_api(audio_data: np_typing.NDArray[np.float32], config_obj: config.Config) -> dict | None:
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


async def send_text_to_tts_api(text: str, config_obj: config.Config) -> np_typing.NDArray[np.int16] | None:
    """
    Send text to TTS API and receive audio data as numpy array.

    Args:
        text: Text to convert to speech
        config_obj: Configuration object containing API settings

    Returns:
        Numpy array of int16 audio samples or None if request failed
    """
    timeout = 10.0
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=config_obj.speech_synthesis_api,
                json={"text": text},
                headers={
                    "user-token": config_obj.speech_synthesis_api_token or "",
                    "accept": "audio/x-raw",
                },
                timeout=timeout,
            )
            response.raise_for_status()

            audio_bytes = response.content
            if len(audio_bytes) < 2:  # int16 = 2 bytes
                logger.error("Received insufficient audio data: %d bytes", len(audio_bytes))
                return None

            return np.frombuffer(audio_bytes, dtype=np.int16)

    except httpx.TimeoutException as e:
        logger.error("Request timed out after %.1f seconds: %s", timeout, e)
        return None

    except httpx.HTTPStatusError as e:
        logger.error("HTTP %d error for %s: %s", e.response.status_code, e.request.url, e.response.text)
        return None

    except httpx.RequestError as e:
        logger.error("Network/connection error: %s", e)
        return None

    except ValueError as e:
        logger.error("Error converting audio data to numpy array: %s", e)
        return None
