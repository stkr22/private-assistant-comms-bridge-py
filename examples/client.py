import asyncio
import json
import logging
import os
import sys
import wave
from pathlib import Path

import pyaudio
import websockets
import websockets.asyncio
import websockets.asyncio.client
import yaml
from pydantic import BaseModel, Field

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger()

# Configuration for audio capture and playback
# chunk size should be 1/10 of samplerate otherwise silero vad might not work properly


class Config(BaseModel):
    samplerate: int = Field(16000, description="Sample rate for audio")
    input_channels: int = Field(1, description="Number of input channels")
    output_channels: int = Field(1, description="Number of output channels")
    chunk_size: int = Field(1280, description="Audio chunk size in bytes")
    room: str = Field("livingroom", description="Room identifier")
    url: str = Field("ws://192.168.178.20:8000/client_control", description="WebSocket URL")
    output_device_index: int = Field(1, description="Output device index")
    input_device_index: int = Field(1, description="Input device index")
    start_listening_path: Path = Field(
        Path("sounds/start_listening.wav"), description="Path to start listening WAV file"
    )
    stop_listening_path: Path = Field(Path("sounds/stop_listening.wav"), description="Path to stop listening WAV file")

    @classmethod
    def from_yaml(cls, yaml_path: Path):
        """Load configuration from a YAML file and validate using Pydantic."""
        if yaml_path.exists():
            try:
                with yaml_path.open("r") as yaml_file:
                    yaml_data = yaml.safe_load(yaml_file) or {}
                return cls.model_validate(yaml_data)
            except Exception as e:
                logger.error("Error loading YAML configuration: %s", e)
                sys.exit(1)
        else:
            logger.warning("YAML configuration file not found: %s. Using defaults.", yaml_path)
            return cls()


# Function to load WAV file into memory
def load_wav_file(file_path: Path):
    with file_path.open("rb") as f:
        wf = wave.open(f)
        audio_data = wf.readframes(wf.getnframes())
        wf.close()
    return audio_data


async def send_audio(websocket: websockets.asyncio.client.ClientConnection, stream_input, config: Config):
    """Async function to send audio data to the server."""
    while True:
        audio_data = stream_input.read(config.chunk_size, exception_on_overflow=False)
        await websocket.send(audio_data)
        await asyncio.sleep(0.01)


async def receive_commands(
    websocket: websockets.asyncio.client.ClientConnection,
    stream_output,
    start_listening_sound: bytes,
    stop_listening_sound: bytes,
):
    """Async function to receive commands from the server."""
    while True:
        message = await websocket.recv()

        if isinstance(message, bytes):
            stream_output.write(message)
        elif message == "start_listening":
            stream_output.write(start_listening_sound)
        elif message == "stop_listening":
            stream_output.write(stop_listening_sound)
        await asyncio.sleep(0.01)


async def send_receive_audio(
    config: Config,
    stream_input,
    stream_output,
    start_listening_sound: bytes,
    stop_listening_sound: bytes,
):
    """Async function to handle audio sending and receiving."""
    while True:
        try:
            async with websockets.connect(config.url) as websocket:
                await websocket.send(
                    json.dumps(
                        config.model_dump(
                            include=["samplerate", "input_channels", "output_channels", "chunk_size", "room"]
                        )
                    )
                )
                await asyncio.gather(
                    send_audio(websocket, stream_input, config),
                    receive_commands(websocket, stream_output, start_listening_sound, stop_listening_sound),
                )
        except websockets.ConnectionClosed:
            logger.warning("Connection closed, retrying...")
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
        await asyncio.sleep(1)  # Avoid tight reconnection loops


def main(config_path="config.yaml"):
    """Function to handle audio input and output streams."""
    config_path = Path(config_path)
    config = Config.from_yaml(config_path)
    start_listening_sound = load_wav_file(config.start_listening_path)
    stop_listening_sound = load_wav_file(config.stop_listening_path)

    p = pyaudio.PyAudio()

    stream_input = p.open(
        format=pyaudio.paInt16,
        channels=config.input_channels,
        rate=config.samplerate,
        input=True,
        frames_per_buffer=640,
        input_device_index=config.input_device_index,
    )

    stream_output = p.open(
        format=pyaudio.paInt16,
        channels=config.output_channels,
        rate=config.samplerate,
        output=True,
        frames_per_buffer=640,
        output_device_index=config.output_device_index,
    )

    try:
        asyncio.run(
            send_receive_audio(config, stream_input, stream_output, start_listening_sound, stop_listening_sound)
        )
    finally:
        stream_input.stop_stream()
        stream_output.stop_stream()
        stream_input.close()
        stream_output.close()
        p.terminate()


if __name__ == "__main__":
    main()
