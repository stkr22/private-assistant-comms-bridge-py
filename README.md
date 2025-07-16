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

Comms Bridge is an open-source voice assistant communication bridge designed to facilitate speech interaction within smart home systems. It consists of a WebSocket-based server that processes audio streams and a client that handles local audio capture and playback.

### Architecture

The system follows a client-server architecture with the following components:

**Server (`app/main.py`):**
- FastAPI-based WebSocket server that accepts single client connections
- Integrates OpenWakeWord for wake word detection
- Uses Silero VAD for voice activity detection
- Handles speech-to-text (STT) and text-to-speech (TTS) API calls
- Communicates with MQTT broker for assistant integration
- Supports multiple wake word models (hey_loona, hey_nohvah, hey_nova)

**Client (`examples/client.py`):**
- PyAudio-based audio capture and playback
- WebSocket client that streams audio to server
- Handles sound effects for user feedback
- Configurable audio parameters and device selection

### Key Features

- **Wake Word Detection**: Uses OpenWakeWord with configurable models and thresholds
- **Voice Activity Detection**: Silero VAD for accurate speech detection
- **Real-time Audio Processing**: Continuous audio streaming with low-latency processing
- **MQTT Integration**: Publishes requests and receives responses via MQTT
- **Audio Feedback**: Plays sound effects and TTS responses to user
- **Room-based Routing**: Supports multiple rooms with topic-based message routing

### Performance Characteristics

The system is designed for low-latency voice interaction but may experience latency increases over time due to:
- Continuous audio buffering without proper cleanup
- WebSocket connection management overhead
- MQTT message queuing and processing delays
- External API call latencies for STT/TTS services

### Configuration

- Server configuration via YAML files with speech API endpoints and MQTT settings
- Client configuration for audio devices, sample rates, and WebSocket connection
- Support for environment-based configuration overrides
