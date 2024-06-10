import base64

import numpy as np
from private_assistant_comms_bridge.utils import speech_recognition_tools


def test_numpy_array_to_base64():
    # Create a sample NumPy array
    samplerate = 16000  # Sample rate in Hz
    duration = 1  # Duration in seconds
    frequency = 440  # Frequency in Hz (A4 note)
    t = np.linspace(
        0, duration, int(samplerate * duration), endpoint=False
    )  # Time array
    audio_data = np.sin(2 * np.pi * frequency * t).astype(np.float32)  # Sine wave

    # Manually encode the array to base64 for comparison
    expected_base64 = base64.b64encode(audio_data.tobytes()).decode("utf-8")

    # Call the function
    result_base64 = speech_recognition_tools.numpy_array_to_base64(audio_data)

    # Assert the function's output matches the expected base64 string
    assert (
        result_base64 == expected_base64
    ), f"Expected {expected_base64}, got {result_base64}"
