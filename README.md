# Private Assistant Comms Bridge

Owner: stkr22

## Comms Bridge: Speech Processing for Edge Devices

Comms Bridge is an open-source endpoint designed to facilitate speech interaction within smart assistant systems, optimized for operation on edge devices. It utilizes Voice Activity Detection (VAD) and OpenWakeWord for efficient speech and wake word detection, enabling the device to listen and respond to verbal commands accurately.

Key functionalities include:

- **Speech Recognition**: Captures audio upon wake word detection, converting speech to text using a speech-to-text API, and forwards the text to an MQTT server for processing.
- **Voice Feedback**: Receives text from the MQTT server and converts it into speech with a text-to-speech API, providing an audible response to the user.
- **Audio Handling**: Leverages the sounddevice library for high-quality audio recording and playback, ensuring seamless voice capture and output.

Comms Bridge's architecture is designed for low-latency communication and privacy preservation, making it suitable for various applications, from smart homes to personal devices. Its modular design and open-source nature allow for customization and integration into existing smart systems.
