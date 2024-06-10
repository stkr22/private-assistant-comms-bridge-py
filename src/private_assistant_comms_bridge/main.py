#!/usr/bin/env python3

import logging
import os
import pathlib
import queue
import sys
from contextlib import asynccontextmanager

import numpy as np
import openwakeword  # type: ignore
import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from private_assistant_comms_bridge.sounds import sounds
from private_assistant_comms_bridge.utils import (
    client_config,
    config,
    mqtt_utils,
    processing_sound,
    speech_recognition_tools,
)

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


class SupportUtils:
    def __init__(self) -> None:
        self.config_obj: config.Config | None = None
        self.wakeword_model: openwakeword.Model | None = None
        self.mqtt_client: mqtt.Client | None = None
        self.output_queue: queue.Queue[np.ndarray] | None = None


support_utils = SupportUtils()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    support_utils.config_obj = config.load_config(pathlib.Path("local_config.yaml"))
    openwakeword.utils.download_models(model_names=["alexa"])
    support_utils.wakeword_model = openwakeword.Model(
        wakeword_models=["alexa"],
    )
    support_utils.output_queue = queue.Queue()
    mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=support_utils.config_obj.client_id,
        protocol=mqtt.MQTTv5,
    )
    mqtt_client.on_connect, mqtt_client.on_message = (
        mqtt_utils.get_mqtt_event_functions(
            config_obj=support_utils.config_obj, output_queue=support_utils.output_queue
        )
    )
    mqtt_client.connect(
        support_utils.config_obj.mqtt_server_host,
        support_utils.config_obj.mqtt_server_port,
        60,
    )
    mqtt_client.loop_start()
    support_utils.mqtt_client = mqtt_client
    yield
    # Clean up the ML models and release the resources
    print(1)


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}


@app.websocket("/client_control")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections."""
    await websocket.accept()
    if (
        support_utils.config_obj is None
        or support_utils.mqtt_client is None
        or support_utils.output_queue is None
        or support_utils.wakeword_model is None
    ):
        raise ValueError
    try:
        client_config_raw = await websocket.receive_json()
        client_conf = client_config.ClientConfig.model_validate(client_config_raw)
        while True:
            try:
                output_text = support_utils.output_queue.get(block=False)
                audio_np = await speech_recognition_tools.send_text_to_tts_api(
                    output_text, support_utils.config_obj, client_conf.samplerate
                )
                if audio_np is not None:
                    await websocket.send_bytes(audio_np.tobytes())
            except queue.Empty:
                logger.info("Nothing in queue, continue.")
            message = await websocket.receive()
            if "text" in message:
                text_data = message["text"]
                if text_data == "ready":
                    logger.info("Client ready for next command")
                else:
                    logger.warning(f"Unexpected text message: {text_data}")
                    continue
            if "bytes" not in message:
                continue
            raw_audio_data = message["bytes"]
            audio_data = np.frombuffer(raw_audio_data, dtype=np.int16)
            prediction = support_utils.wakeword_model.predict(
                audio_data.flatten(),
                debounce_time=1.0,
                threshold={
                    "alexa": support_utils.config_obj.wakework_detection_threshold
                },
            )
            if (
                prediction["alexa"]
                >= support_utils.config_obj.wakework_detection_threshold
            ):
                logger.info("Wakeword detected.")
                notification_sound = np.int16(sounds.start_recording * 32767)
                await websocket.send_bytes(notification_sound.tobytes())
                await processing_sound.processing_spoken_commands(
                    websocket=websocket,
                    config_obj=support_utils.config_obj,
                    mqtt_client=support_utils.mqtt_client,
                    client_conf=client_conf,
                )
            else:
                logger.debug("No wake word detected")
    except WebSocketDisconnect:
        logger.info("Client disconnected")
