import logging
import socket
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class Config(BaseModel):
    wakework_detection_threshold: float = 0.5
    openwakeword_inference_framework: str = "onnx"
    path_or_name_wakeword_model: str = "/app/assets/hey_nova.onnx"
    name_wakeword_model: str = "hey_nova"
    speech_transcription_api: str = "http://localhost:8000/transcribe"
    speech_transcription_api_token: str | None = None
    speech_synthesis_api: str = "http://localhost:8080/synthesizeSpeech"
    speech_synthesis_api_token: str | None = None
    client_id: str = socket.gethostname()
    max_command_input_seconds: int = 30
    max_length_speech_pause: float = 0.5
    vad_threshold: float = 0.6
    mqtt_server_host: str = "localhost"
    mqtt_server_port: int = 1883
    broadcast_topic: str = "assistant/comms_bridge/broadcast"
    base_topic_overwrite: str | None = None
    input_topic_overwrite: str | None = None
    output_topic_overwrite: str | None = None

    @property
    def base_topic(self) -> str:
        return self.base_topic_overwrite or f"assistant/comms_bridge/all/{self.client_id}"

    @property
    def input_topic(self) -> str:
        return self.input_topic_overwrite or f"{self.base_topic}/input"

    @property
    def output_topic(self) -> str:
        return self.output_topic_overwrite or f"{self.base_topic}/output"


def load_config(config_path: Path) -> Config:
    try:
        with config_path.open("r") as file:
            config_data = yaml.safe_load(file)
        return Config.model_validate(config_data)
    except FileNotFoundError as err:
        logger.error("Config file not found: %s", config_path)
        raise err
    except ValidationError as err_v:
        logger.error("Validation error: %s", err_v)
        raise err_v
