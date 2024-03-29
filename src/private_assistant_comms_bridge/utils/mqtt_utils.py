import logging
import queue
from collections.abc import Callable

from private_assistant_comms_bridge.utils import (
    config,
    playing_sound,
    speech_recognition_tools,
)

logger = logging.getLogger(__name__)


def get_mqtt_event_functions(
    config_obj: config.Config, output_queue: queue.Queue
) -> tuple[Callable, Callable]:
    def on_message(client, userdata, msg):
        audio_np = speech_recognition_tools.send_text_to_tts_api(
            msg.payload.decode("utf-8"), config_obj
        )
        if audio_np is not None:
            for block in playing_sound.split_array_into_blocks(
                audio_np, config_obj.blocksize
            ):
                block = block.reshape(-1, 1)
                output_queue.put(block)

    def on_connect(client, userdata, flags, reason_code, properties):
        logger.info(f"Connected to MQTT server with result code {reason_code}")
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(config_obj.output_topic)

    return on_connect, on_message
