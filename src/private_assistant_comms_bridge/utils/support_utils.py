import asyncio

import aiomqtt as mqtt
import openwakeword

from private_assistant_comms_bridge.utils import (
    config,
    silero_vad,
)


class SupportUtils:
    def __init__(self) -> None:
        self._config_obj: config.Config | None = None
        self._wakeword_model: openwakeword.Model | None = None
        self._mqtt_client: mqtt.Client | None = None
        self.mqtt_subscription_to_queue: dict[str, asyncio.Queue[str]] = {}
        self.websocket_connected: bool = False
        self.vad_model: silero_vad.SileroVad = silero_vad.SileroVad(0.6, 1)

    @property
    def config_obj(self) -> config.Config:
        if self._config_obj is None:
            raise ValueError("Config object is not set")
        return self._config_obj

    @config_obj.setter
    def config_obj(self, value: config.Config) -> None:
        self._config_obj = value

    @property
    def wakeword_model(self) -> openwakeword.Model:
        if self._wakeword_model is None:
            raise ValueError("Wakeword model is not set")
        return self._wakeword_model

    @wakeword_model.setter
    def wakeword_model(self, value: openwakeword.Model) -> None:
        self._wakeword_model = value

    @property
    def mqtt_client(self) -> mqtt.Client:
        if self._mqtt_client is None:
            raise ValueError("MQTT client is not set")
        return self._mqtt_client

    @mqtt_client.setter
    def mqtt_client(self, value: mqtt.Client) -> None:
        self._mqtt_client = value
