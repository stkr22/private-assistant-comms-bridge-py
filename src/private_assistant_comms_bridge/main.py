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

from private_assistant_comms_bridge.utils import (
    client_config,
    config,
    mqtt_utils,
    processing_sound,
    speech_recognition_tools,
    support_utils,
)

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


sup_util = support_utils.SupportUtils()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    sup_util.config_obj = config.load_config(
        pathlib.Path(os.getenv("ASSISTANT_API_CONFIG_PATH", "local_config.yaml"))
    )
    openwakeword.utils.download_models(model_names=["alexa"])
    sup_util.wakeword_model = openwakeword.Model(
        wakeword_models=["alexa"],
        enable_speex_noise_suppression=True,
        vad_threshold=sup_util.config_obj.vad_threshold,
    )
    mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=sup_util.config_obj.client_id,
        protocol=mqtt.MQTTv5,
    )
    mqtt_client.on_connect, mqtt_client.on_message = (
        mqtt_utils.get_mqtt_event_functions(sup_util=sup_util)
    )
    mqtt_client.connect(
        sup_util.config_obj.mqtt_server_host,
        sup_util.config_obj.mqtt_server_port,
        60,
    )
    mqtt_client.loop_start()
    sup_util.mqtt_client = mqtt_client
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
    try:
        sup_util.config_obj
        sup_util.mqtt_client
        sup_util.wakeword_model
    except ValueError as e:
        logger.error(str(e))
        await websocket.close(code=1002)
        return
    try:
        client_config_raw = await websocket.receive_json()
        client_conf = client_config.ClientConfig.model_validate(client_config_raw)
        output_queue: queue.Queue[str] = queue.Queue()
        output_topic = f"assistant/{client_conf.room}/output"
        client_conf.output_topic = output_topic
        sup_util.mqtt_subscription_to_queue[output_topic] = output_queue
        sup_util.mqtt_client.subscribe(
            output_topic, options=mqtt.SubscribeOptions(qos=1)
        )

        while True:
            await process_output_queue(websocket, output_queue, sup_util.config_obj)
            message = await websocket.receive()

            if "bytes" in message:
                await handle_audio_message(
                    websocket, message["bytes"], client_conf, sup_util
                )

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        await websocket.close(code=1002)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        await websocket.close(code=1011)


async def process_output_queue(
    websocket: WebSocket, output_queue: queue.Queue[str], config_obj: config.Config
):
    try:
        output_text = output_queue.get_nowait()
        audio_np = await speech_recognition_tools.send_text_to_tts_api(
            output_text, config_obj
        )
        if audio_np is not None:
            await websocket.send_bytes(audio_np.tobytes())
    except queue.Empty:
        logger.debug("Nothing in queue, continue.")


async def handle_audio_message(
    websocket: WebSocket,
    audio_bytes: bytes,
    client_conf: client_config.ClientConfig,
    sup_util: support_utils.SupportUtils,
):
    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
    prediction = sup_util.wakeword_model.predict(
        audio_data,
        debounce_time=3.0,
        threshold={"alexa": sup_util.config_obj.wakework_detection_threshold},
    )
    alexa_prediction = prediction["alexa"]
    logger.debug(
        "Wakeword prob: %s. Above threshold %s",
        alexa_prediction,
        alexa_prediction >= sup_util.config_obj.wakework_detection_threshold,
    )

    if alexa_prediction >= sup_util.config_obj.wakework_detection_threshold:
        logger.info("Wakeword detected.")
        await websocket.send_text("start_listening")
        await processing_sound.processing_spoken_commands(
            websocket=websocket,
            config_obj=sup_util.config_obj,
            mqtt_client=sup_util.mqtt_client,
            client_conf=client_conf,
        )
