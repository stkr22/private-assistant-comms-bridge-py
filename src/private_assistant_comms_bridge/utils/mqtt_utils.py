import logging
import queue
from collections.abc import Callable

import paho.mqtt.client as mqtt

from private_assistant_comms_bridge.utils import (
    config,
)

logger = logging.getLogger(__name__)


def get_mqtt_event_functions(
    config_obj: config.Config, output_queue: queue.Queue
) -> tuple[Callable, Callable]:
    def on_message(client, user_data, msg):
        output_queue.put(msg.payload.decode("utf-8"))

    def on_connect(client: mqtt.Client, user_data, flags, reason_code, properties):
        logger.info(f"Connected to MQTT server with result code {reason_code}")
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(config_obj.output_topic, options=mqtt.SubscribeOptions(qos=1))

    return on_connect, on_message
