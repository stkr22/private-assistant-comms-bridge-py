import logging
import queue
import threading
import uuid

import numpy as np
import paho.mqtt.client as mqtt
from private_assistant_commons import messages

from private_assistant_comms_bridge.utils import (
    config,
    playing_sound,
    speech_recognition_tools,
)

logger = logging.getLogger(__name__)


def processing_spoken_commands(
    config_obj: config.Config,
    output_queue: queue.Queue,
    mqtt_client: mqtt.Client,
    input_active_queue: queue.Queue,
    active_listening: threading.Event,
) -> None:
    silence_packages = 0
    # Window should correspond to the number/split parts of a second
    # one block corresponds to
    max_frames = (
        config_obj.max_command_input_seconds * config_obj.sounddevice_input_samplerate
    )
    previous_frame = np.empty(shape=[config_obj.blocksize, 1], dtype=np.int16)
    audio_frames = None
    while active_listening.is_set():
        raw_data = input_active_queue.get()
        speech_prob, data = speech_recognition_tools.format_audio_and_speech_prob(
            raw_data, config_obj=config_obj
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
            audio_frames.shape[0] > max_frames or silence_packages >= 2
        ):
            active_listening.clear()
            playing_sound.add_start_stop_message_to_output(
                start=False, config_obj=config_obj, output_queue=output_queue
            )
            audio_base64 = speech_recognition_tools.numpy_array_to_base64(audio_frames)
            logger.debug("Requested transcription...")
            response = speech_recognition_tools.send_audio_to_stt_api(
                audio_base64, audio_frames.dtype.name, config_obj=config_obj
            )
            logger.debug("Received result...%s", response)
            if response is not None:
                mqtt_client.publish(
                    config_obj.input_topic,
                    messages.ClientRequest(
                        id=uuid.uuid4(),
                        text=response["text"],
                        room=config_obj.virtual_assistant_room,
                        output_topic=config_obj.output_topic,
                    ).model_dump_json(),
                    qos=1,
                )
                logger.debug("Published result text to MQTT.")
