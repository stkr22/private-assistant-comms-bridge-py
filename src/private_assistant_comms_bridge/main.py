#!/usr/bin/env python3

import logging
import os
import pathlib
import queue
import sys
from contextlib import asynccontextmanager

import numpy as np
import openwakeword
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
    sup_util.config_obj = config.load_config(
        pathlib.Path(os.getenv("PRIVATE_ASSISTANT_API_CONFIG_PATH", "local_config.yaml"))
    )
    openwakeword.utils.download_models(model_names=["alexa"])
    sup_util.wakeword_model = openwakeword.Model(
        wakeword_models=[sup_util.config_obj.path_or_name_wakeword_model],
        enable_speex_noise_suppression=True,
        vad_threshold=sup_util.config_obj.vad_threshold,
    )
    mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=sup_util.config_obj.client_id,
        protocol=mqtt.MQTTv5,
    )
    mqtt_client.on_connect, mqtt_client.on_message = mqtt_utils.get_mqtt_event_functions(sup_util=sup_util)
    mqtt_client.connect(
        sup_util.config_obj.mqtt_server_host,
        sup_util.config_obj.mqtt_server_port,
        60,
    )
    mqtt_client.loop_start()
    sup_util.mqtt_client = mqtt_client
    yield
    print(1)


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}


@app.get("/acceptsConnections")
async def accepts_connection():
    """Endpoint to check if the app can accept a new WebSocket connection."""
    if sup_util.websocket_connected:
        return {"status": "busy"}, 503
    return {"status": "ready"}


@app.websocket("/client_control")
async def websocket_endpoint(websocket: WebSocket):
    if sup_util.websocket_connected:
        await websocket.close(code=1001, reason="Server busy")
        return

    sup_util.websocket_connected = True  # Mark WebSocket as connected
    await websocket.accept()
    try:
        client_config_raw = await websocket.receive_json()
        client_conf = client_config.ClientConfig.model_validate(client_config_raw)
        output_queue: queue.Queue[str] = queue.Queue()
        output_topic = f"assistant/{client_conf.room}/output"
        client_conf.output_topic = output_topic
        sup_util.mqtt_subscription_to_queue[output_topic] = output_queue
        sup_util.mqtt_client.subscribe(output_topic, options=mqtt.SubscribeOptions(qos=1))
        sup_util.mqtt_subscription_to_queue[sup_util.config_obj.broadcast_topic] = output_queue
        sup_util.mqtt_client.subscribe(sup_util.config_obj.broadcast_topic, options=mqtt.SubscribeOptions(qos=1))

        while True:
            await process_output_queue(websocket, output_queue, sup_util.config_obj)
            message = await websocket.receive()

            if "bytes" in message:
                await handle_audio_message(websocket, message["bytes"], client_conf, sup_util)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        await websocket.close(code=1002)
    except Exception as e:
        logger.exception("Unexpected error occurred: %s", e)
        await websocket.close(code=1011)
    finally:
        sup_util.websocket_connected = False  # Reset connection status on disconnect or error


async def process_output_queue(websocket: WebSocket, output_queue: queue.Queue[str], config_obj: config.Config):
    try:
        output_text = output_queue.get_nowait()
        audio_np = await speech_recognition_tools.send_text_to_tts_api(output_text, config_obj)
        if audio_np is not None:
            await websocket.send_bytes(audio_np.tobytes())
    except queue.Empty:
        logger.debug("Queue is empty, no message to process.")


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
        threshold={sup_util.config_obj.name_wakeword_model: sup_util.config_obj.wakework_detection_threshold},
    )
    wakeword_prediction = prediction[sup_util.config_obj.name_wakeword_model]
    logger.debug(
        "Wakeword probability: %s, Threshold check: %s",
        wakeword_prediction,
        wakeword_prediction >= sup_util.config_obj.wakework_detection_threshold,
    )

    if wakeword_prediction >= sup_util.config_obj.wakework_detection_threshold:
        logger.info("Wakeword detected, sending start listening signal.")
        await websocket.send_text("start_listening")
        await processing_sound.processing_spoken_commands(
            websocket=websocket,
            config_obj=sup_util.config_obj,
            mqtt_client=sup_util.mqtt_client,
            client_conf=client_conf,
        )
