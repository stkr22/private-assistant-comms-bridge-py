import pathlib

import pytest
import yaml
from pydantic import ValidationError

from app.utils.config import Config

# Sample invalid YAML configuration (missing required fields)
invalid_yaml = """
mqtt_server_host: "test_host"
mqtt_server_port: "invalid_port"  # invalid type
client_id: 12345  # invalid type
"""


def test_load_valid_config():
    data_directory = pathlib.Path(__file__).parent / "data" / "config.yaml"
    with data_directory.open("r") as file:
        config_data = yaml.safe_load(file)
    config = Config.model_validate(config_data)

    assert config.mqtt_server_host == "localhost"
    assert config.mqtt_server_port == 1884
    assert config.speech_transcription_api == "http://localhost/transcribe"
    assert config.speech_transcription_api_token == "DEBUG"
    assert config.speech_synthesis_api == "https://localhost/synthesizeSpeech"
    assert config.speech_synthesis_api_token == "DEBUG"


def test_load_invalid_config():
    config_data = yaml.safe_load(invalid_yaml)
    with pytest.raises(ValidationError):
        Config.model_validate(config_data)
