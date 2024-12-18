import logging
import uuid

import numpy as np
from fastapi import WebSocket
from private_assistant_commons import messages

from private_assistant_comms_bridge.utils import (
    client_config,
    config,
    speech_recognition_tools,
    support_utils,
)

logger = logging.getLogger(__name__)


async def processing_spoken_commands(
    websocket: WebSocket,
    sup_util: support_utils.SupportUtils,
    config_obj: config.Config,
    client_conf: client_config.ClientConfig,
) -> None:
    silence_packages = 0
    max_frames = config_obj.max_command_input_seconds * client_conf.samplerate
    max_silent_packages = client_conf.samplerate / client_conf.chunk_size * config_obj.max_length_speech_pause
    audio_frames = None
    active_listening = True
    while active_listening:
        audio_bytes = await websocket.receive_bytes()
        speech_prob = sup_util.vad_model(audio_bytes)
        raw_audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
        data = speech_recognition_tools.int2float(raw_audio_data)
        if speech_prob > config_obj.vad_threshold:
            silence_packages = 0
            if audio_frames is None:
                audio_frames = data
            else:
                audio_frames = np.concatenate((audio_frames, data), axis=0)
            logger.debug("Received voice...")
        else:
            if audio_frames is not None:
                audio_frames = np.concatenate((audio_frames, data), axis=0)
                silence_packages += 1
            logger.debug("No voice...")
        if audio_frames is not None and (audio_frames.shape[0] > max_frames or silence_packages >= max_silent_packages):
            active_listening = False
            await websocket.send_text("stop_listening")
            logger.info("Requested transcription...")
            response = await speech_recognition_tools.send_audio_to_stt_api(audio_frames, config_obj=config_obj)
            logger.info("Received result...")
            logger.debug("Response...%s", response)
            if response is not None:
                await sup_util.mqtt_client.publish(
                    config_obj.input_topic,
                    messages.ClientRequest(
                        id=uuid.uuid4(),
                        text=response["text"],
                        room=client_conf.room,
                        output_topic=client_conf.output_topic,
                    ).model_dump_json(),
                    qos=1,
                )
                logger.info("Published result text to MQTT.")
