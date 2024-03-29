#!/usr/bin/env python3

import logging
import os
import pathlib
import queue
import sys
import threading
from typing import Annotated

import numpy as np
import openwakeword  # type: ignore
import paho.mqtt.client as mqtt
import sounddevice as sd  # type: ignore
import typer

from private_assistant_comms_bridge.utils import (
    config,
    mqtt_utils,
    playing_sound,
    processing_sound,
)

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

input_passive_queue: queue.Queue = queue.Queue()
input_active_queue: queue.Queue = queue.Queue()
output_queue: queue.Queue = queue.Queue()
played_message: threading.Event = threading.Event()
active_listening: threading.Event = threading.Event()


app = typer.Typer()


def callback(
    indata: np.ndarray, outdata: np.ndarray, frames: int, time, status: sd.CallbackFlags
):
    """This is called (from a separate thread) for each audio block."""
    if status:
        logger.info("%s", status)
    if active_listening.is_set():
        input_active_queue.put(indata)
    else:
        input_passive_queue.put(indata)
    outdata.fill(
        0
    )  # important otherwise it will keep sound from the previous cycle if new_frames is smaller than blocksize
    try:
        new_frames: np.ndarray = output_queue.get_nowait()
        outdata[: new_frames.shape[0]] = new_frames
    except queue.Empty:
        played_message.set()


@app.command()
def start_comms_bridge(config_path: Annotated[pathlib.Path, typer.Argument()]):
    config_obj = config.load_config(config_path)
    openwakeword.utils.download_models(model_names=["alexa"])
    wakeword_model = openwakeword.Model(
        wakeword_models=["alexa"],
        enable_speex_noise_suppression=True,
    )

    mqttc = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=config_obj.client_id
    )
    mqttc.on_connect, mqttc.on_message = mqtt_utils.get_mqtt_event_functions(
        config_obj=config_obj, output_queue=output_queue
    )
    mqttc.connect(config_obj.mqtt_server_host, config_obj.mqtt_server_port, 60)
    mqttc.loop_start()
    with sd.Stream(
        samplerate=config_obj.sounddevice_input_samplerate,
        blocksize=config_obj.blocksize,
        device=(config_obj.voice_input_device, config_obj.voice_output_device),
        dtype=np.int16,
        channels=1,
        callback=callback,
    ):
        while True:
            wakeword_detected = False
            raw_audio_data = input_passive_queue.get()
            prediction = wakeword_model.predict(
                raw_audio_data.flatten(),
                debounce_time=1.0,
                threshold={"alexa": config_obj.wakework_detection_threshold},
            )
            if prediction["alexa"] >= config_obj.wakework_detection_threshold:
                logger.info("Wakeword detected.")
                wakeword_detected = True
                playing_sound.add_start_stop_message_to_output(
                    start=True, config_obj=config_obj, output_queue=output_queue
                )
                played_message.clear()
            if wakeword_detected is True:
                played_message.wait(timeout=5.0)
                active_listening.set()
                processing_sound.processing_spoken_commands(
                    config_obj=config_obj,
                    output_queue=output_queue,
                    mqtt_client=mqttc,
                    input_active_queue=input_active_queue,
                    active_listening=active_listening,
                )


if __name__ == "__main__":
    start_comms_bridge(config_path=pathlib.Path("./template.yaml"))
