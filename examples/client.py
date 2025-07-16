import asyncio
import json
import logging
import os
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Self

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
logger = logging.getLogger(__name__)


@dataclass
class AudioStreams:
    input: pyaudio.Stream
    output: pyaudio.Stream

    def cleanup(self) -> None:
        for stream in (self.input, self.output):
            stream.stop_stream()
            stream.close()


class Config(BaseModel):
    samplerate: int = Field(default=16000, description="Sample rate for audio")
    input_channels: int = Field(default=1, description="Number of input channels")
    output_channels: int = Field(default=1, description="Number of output channels")
    chunk_size: int = Field(default=1280, description="Audio chunk size in bytes")
    room: str = Field(default="livingroom", description="Room identifier")
    url: str = Field(default="ws://192.168.8.20:8000/client_control", description="WebSocket URL")
    output_device_index: int = Field(default=1, description="Output device index")
    input_device_index: int = Field(default=1, description="Input device index")
    start_listening_path: Path = Field(
        default=Path("sounds/start_listening.wav"), description="Path to start listening WAV file"
    )
    stop_listening_path: Path = Field(
        default=Path("sounds/stop_listening.wav"), description="Path to stop listening WAV file"
    )
    alert_default_path: Path = Field(
        default=Path("sounds/alert_default.wav"), description="Path to alert default WAV file"
    )

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> Self:
        if yaml_path.exists():
            try:
                with yaml_path.open("r") as yaml_file:
                    yaml_data = yaml.safe_load(yaml_file) or {}
                return cls.model_validate(yaml_data)
            except Exception as e:
                logger.error("Error loading YAML configuration: %s", e)
                sys.exit(1)
        logger.warning("YAML configuration file not found: %s. Using defaults.", yaml_path)
        return cls()


def load_wav_file(file_path: Path) -> bytes:
    with file_path.open("rb") as f, wave.open(f) as wf:
        return wf.readframes(wf.getnframes())  # type: ignore


class WebSocketManager:
    RECONNECT_DELAY: Final[float] = 1.0

    def __init__(self, config: Config, streams: AudioStreams, sounds: dict[str, bytes]) -> None:
        self.config = config
        self.streams = streams
        self.sounds = sounds
        self._running = True

    async def start(self) -> None:
        while self._running:
            try:
                async with websockets.connect(self.config.url) as ws:
                    await ws.send(self._get_config_json())
                    await self._handle_connection(ws)
            except websockets.ConnectionClosed:
                logger.warning("Connection closed, retrying...")
            except Exception as e:
                logger.error("Error: %s", e, exc_info=True)
            await asyncio.sleep(self.RECONNECT_DELAY)

    def stop(self) -> None:
        self._running = False
        self.streams.cleanup()

    async def _handle_connection(self, ws: websockets.asyncio.client.ClientConnection) -> None:
        await asyncio.gather(self._send_audio(ws), self._receive_commands(ws))

    async def _send_audio(self, ws: websockets.asyncio.client.ClientConnection) -> None:
        # AIDEV-NOTE: Removed artificial sleep delay to reduce latency
        while self._running:
            audio_data = self.streams.input.read(self.config.chunk_size, exception_on_overflow=False)
            await ws.send(audio_data)
            # Natural rate limiting from audio buffer read - no artificial delay needed

    async def _receive_commands(self, ws: websockets.asyncio.client.ClientConnection) -> None:
        # AIDEV-NOTE: Removed artificial sleep delay to reduce latency
        while self._running:
            message = await ws.recv()
            if isinstance(message, bytes):
                self.streams.output.write(message)
            elif sound := self.sounds.get(message):
                self.streams.output.write(sound)
            # WebSocket recv() is naturally blocking - no artificial delay needed

    def _get_config_json(self) -> str:
        return json.dumps(
            self.config.model_dump(include={"samplerate", "input_channels", "output_channels", "chunk_size", "room"})
        )


def setup_audio_streams(config: Config) -> AudioStreams:
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

    return AudioStreams(input=stream_input, output=stream_output)


def load_sound_effects(config: Config) -> dict[str, bytes]:
    return {
        "start_listening": load_wav_file(config.start_listening_path),
        "stop_listening": load_wav_file(config.stop_listening_path),
        "alert_default": load_wav_file(config.alert_default_path),
    }


def main(config_path: str = "config.yaml") -> None:
    config = Config.from_yaml(Path(config_path))
    streams = setup_audio_streams(config)
    sounds = load_sound_effects(config)

    ws_manager = WebSocketManager(config, streams, sounds)

    try:
        asyncio.run(ws_manager.start())
    except KeyboardInterrupt:
        pass
    finally:
        ws_manager.stop()


if __name__ == "__main__":
    main()
