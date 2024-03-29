import queue

import numpy as np

from private_assistant_comms_bridge.sounds import sounds
from private_assistant_comms_bridge.utils import config


def split_array_into_blocks(arr: np.ndarray, block_size: int):
    """Yield successive block_size chunks from arr."""
    for i in range(0, len(arr), block_size):
        yield arr[i : i + block_size]


def add_start_stop_message_to_output(
    start: bool, config_obj: config.Config, output_queue: queue.Queue
) -> None:
    if start is True:
        notification_sound = np.int16(sounds.start_recording * 32767)
    else:
        notification_sound = np.int16(sounds.stop_recording * 32767)
    for block in split_array_into_blocks(notification_sound, config_obj.blocksize):
        block = block.reshape(-1, 1)
        output_queue.put(block)
