import numpy as np
from private_assistant_comms_bridge.utils.speech_recognition_tools import int2float


def test_int2float():
    # Test case 1: Normal case
    int_sound = np.array([0, 16384, -16384], dtype=np.int16)
    expected_float_sound = np.array([0.0, 0.5, -0.5], dtype=np.float32)
    np.testing.assert_allclose(int2float(int_sound), expected_float_sound, rtol=1e-4, atol=1e-6)

    # Test case 2: Maximum and minimum int16 values
    int_sound = np.array([32767, -32768], dtype=np.int16)
    expected_float_sound = np.array([1.0, -1.0], dtype=np.float32)
    np.testing.assert_allclose(int2float(int_sound), expected_float_sound, rtol=1e-4, atol=1e-6)

    # Test case 3: All zeros
    int_sound = np.array([0, 0, 0], dtype=np.int16)
    expected_float_sound = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    np.testing.assert_allclose(int2float(int_sound), expected_float_sound, rtol=1e-4, atol=1e-6)

    # Test case 4: Single value
    int_sound = np.array([16384], dtype=np.int16)
    expected_float_sound = np.array([0.5], dtype=np.float32)
    np.testing.assert_allclose(int2float(int_sound), expected_float_sound, rtol=1e-4, atol=1e-6)
