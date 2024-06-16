import logging
import uuid

import numpy as np
import paho.mqtt.client as mqtt
from fastapi import WebSocket
from private_assistant_commons import messages

from private_assistant_comms_bridge.sounds import sounds
from private_assistant_comms_bridge.utils import (
    client_config,
    config,
    speech_recognition_tools,
)

logger = logging.getLogger(__name__)


async def processing_spoken_commands(
    websocket: WebSocket,
    config_obj: config.Config,
    mqtt_client: mqtt.Client,
    client_conf: client_config.ClientConfig,
) -> None:
    silence_packages = 0
    previous_frame = np.empty(shape=[client_conf.chunk_size, 1], dtype=np.int16)
    max_frames = config_obj.max_command_input_seconds * client_conf.samplerate
    max_silent_packages = (
        client_conf.samplerate
        / client_conf.chunk_size
        * config_obj.max_length_speech_pause
    )
    audio_frames = None
    active_listening = True
    client_ready = False
    while not client_ready:
        message = await websocket.receive()
        if "text" in message:
            text_data = message["text"]
            if text_data == "ready":
                logger.info(
                    "Received %s from client, starting active listening", text_data
                )
                client_ready = True
        else:
            continue
    while active_listening:
        audio_bytes = await websocket.receive_bytes()
        raw_audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
        speech_prob, data = speech_recognition_tools.format_audio_and_speech_prob(
            raw_audio_data, input_samplerate=client_conf.samplerate
        )
        if speech_prob > config_obj.vad_threshold:
            silence_packages = 0
            if audio_frames is None:
                audio_frames = np.concatenate((previous_frame, data), axis=0)
            else:
                audio_frames = np.concatenate((audio_frames, data), axis=0)
            logger.debug("Received voice...")
        else:
            if audio_frames is not None:
                audio_frames = np.concatenate((audio_frames, data), axis=0)
                silence_packages += 1
            previous_frame = data
            logger.debug("No voice...")
        if audio_frames is not None and (
            audio_frames.shape[0] > max_frames
            or silence_packages >= max_silent_packages
        ):
            active_listening = False
            notification_sound = np.int16(sounds.stop_recording * 32767)
            await websocket.send_bytes(notification_sound.tobytes())
            audio_base64 = speech_recognition_tools.numpy_array_to_base64(audio_frames)
            logger.debug("Requested transcription...")
            response = await speech_recognition_tools.send_audio_to_stt_api(
                audio_base64, audio_frames.dtype.name, config_obj=config_obj
            )
            logger.debug("Received result...%s", response)
            if response is not None:
                mqtt_client.publish(
                    config_obj.input_topic,
                    messages.ClientRequest(
                        id=uuid.uuid4(),
                        text=response["text"],
                        room=client_conf.room,
                        output_topic=client_conf.output_topic,
                    ).model_dump_json(),
                    qos=1,
                )
                logger.debug("Published result text to MQTT.")
