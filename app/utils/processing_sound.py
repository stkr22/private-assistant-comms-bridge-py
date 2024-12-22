import logging
import uuid
from dataclasses import dataclass

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect
from private_assistant_commons import messages

from app.utils import (
    client_config,
    config,
    support_utils,
)
from app.utils import (
    speech_recognition_tools as srt,
)


@dataclass
class AudioConfig:
    max_frames: int
    max_silent_packages: int
    vad_threshold: float


class AudioProcessor:
    def __init__(
        self,
        websocket: WebSocket,
        sup_util: support_utils.SupportUtils,
        config_obj: config.Config,
        client_conf: client_config.ClientConfig,
        logger: logging.Logger,
    ) -> None:
        self.websocket = websocket
        self.sup_util = sup_util
        self.audio_config = AudioConfig(
            max_frames=config_obj.max_command_input_seconds * client_conf.samplerate,
            max_silent_packages=int(
                client_conf.samplerate / client_conf.chunk_size * config_obj.max_length_speech_pause
            ),
            vad_threshold=config_obj.vad_threshold,
        )
        self.config_obj = config_obj
        self.client_conf = client_conf
        self.audio_frames: np.ndarray | None = None
        self.silence_packages: int = 0
        self.logger = logger

    async def handle_voice_packet(self, data: np.ndarray) -> None:
        self.silence_packages = 0
        self.audio_frames = data if self.audio_frames is None else np.concatenate((self.audio_frames, data))
        self.logger.debug("Received voice...")

    async def handle_silence_packet(self, data: np.ndarray) -> None:
        if self.audio_frames is not None:
            self.audio_frames = np.concatenate((self.audio_frames, data))
            self.silence_packages += 1
        self.logger.debug("No voice...")

    async def process_complete_audio(self) -> None:
        if self.audio_frames is None:
            return

        try:
            await self.websocket.send_text("stop_listening")
            self.logger.info("Requested transcription...")

            response = await srt.send_audio_to_stt_api(self.audio_frames, config_obj=self.config_obj)
            if response is None:
                self.logger.error("Failed to get STT response")
                return

            self.logger.info("Received result...")
            self.logger.debug("Response: %s", response)

            request = messages.ClientRequest(
                id=uuid.uuid4(),
                text=response.text,
                room=self.client_conf.room,
                output_topic=self.client_conf.output_topic,
            )

            await self.sup_util.mqtt_client.publish(
                self.config_obj.input_topic,
                request.model_dump_json(),
                qos=1,
            )
            self.logger.info("Published result text to MQTT")

        except Exception as e:
            self.logger.error("Error processing audio: %s", str(e))
            raise

    async def process_audio_stream(self) -> None:
        try:
            while True:
                audio_bytes = await self.websocket.receive_bytes()
                speech_prob: float = self.sup_util.vad_model(audio_bytes)
                raw_audio: np.ndarray = np.frombuffer(audio_bytes, dtype=np.int16)
                data: np.ndarray = srt.int2float(raw_audio)

                if speech_prob > self.audio_config.vad_threshold:
                    await self.handle_voice_packet(data)
                else:
                    await self.handle_silence_packet(data)

                if self.should_process_audio():
                    await self.process_complete_audio()
                    break

        except WebSocketDisconnect:
            self.logger.info("WebSocket disconnected")
        except Exception as e:
            self.logger.error("Error in audio processing: %s", str(e))
            raise
        finally:
            await self.cleanup()

    def should_process_audio(self) -> bool:
        if self.audio_frames is None:
            return False
        return (
            self.audio_frames.shape[0] > self.audio_config.max_frames
            or self.silence_packages >= self.audio_config.max_silent_packages
        )

    async def cleanup(self) -> None:
        self.audio_frames = None
        self.silence_packages = 0


async def processing_spoken_commands(
    websocket: WebSocket,
    sup_util: support_utils.SupportUtils,
    config_obj: config.Config,
    client_conf: client_config.ClientConfig,
    logger: logging.Logger,
) -> None:
    processor = AudioProcessor(websocket, sup_util, config_obj, client_conf, logger=logger)
    await processor.process_audio_stream()
