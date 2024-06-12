import queue

import openwakeword  # type: ignore
import paho.mqtt.client as mqtt

from private_assistant_comms_bridge.utils import (
    config,
)


class SupportUtils:
    def __init__(self) -> None:
        self.config_obj: config.Config | None = None
        self.wakeword_model: openwakeword.Model | None = None
        self.mqtt_client: mqtt.Client | None = None
        self.mqtt_subscription_to_queue: dict[str, queue.Queue[str]] = {}
