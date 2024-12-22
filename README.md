# Private Assistant Comms Bridge

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)
[![python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

Owner: stkr22

## Comms Bridge: Speech Processing for Edge Devices

Comms Bridge is an open-source endpoint designed to facilitate speech interaction within smart assistant systems, optimized for operation on edge devices. It utilizes Voice Activity Detection (VAD) and OpenWakeWord for efficient speech and wake word detection, enabling the device to listen and respond to verbal commands accurately.

Key functionalities include:

- **Speech Recognition**: Captures audio upon wake word detection, converting speech to text using a speech-to-text API, and forwards the text to an MQTT server for processing.
- **Voice Feedback**: Receives text from the MQTT server and converts it into speech with a text-to-speech API, providing an audible response to the user.
- **Audio Handling**: Leverages the sounddevice library for high-quality audio recording and playback, ensuring seamless voice capture and output.

Comms Bridge's architecture is designed for low-latency communication and privacy preservation, making it suitable for various applications, from smart homes to personal devices. Its modular design and open-source nature allow for customization and integration into existing smart systems.
