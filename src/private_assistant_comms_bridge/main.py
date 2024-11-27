#!/usr/bin/env python3

import asyncio
import logging
import os
import pathlib
import sys
from contextlib import asynccontextmanager

import aiomqtt
import numpy as np
import openwakeword
import pydantic
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from private_assistant_commons import messages

from private_assistant_comms_bridge.utils import (
    client_config,
    config,
    processing_sound,
    silero_vad,
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


def decode_message_payload(payload) -> str | None:
    """Decode the message payload if it is a suitable type."""
    if isinstance(payload, bytes) or isinstance(payload, bytearray):
        return payload.decode("utf-8")
    elif isinstance(payload, str):
        return payload
    else:
        logger.warning("Unexpected payload type: %s", type(payload))
        return None


async def listen(client: aiomqtt.Client, sup_util: support_utils.SupportUtils):
    async for message in client.messages:
        topic_queue = sup_util.mqtt_subscription_to_queue.get(message.topic.value)
        logger.debug("Received message: %s", message)
        if topic_queue is None:
            logger.warning("%s seems to have no queue. Discarding message.", message.topic)
        else:
            payload_str = decode_message_payload(message.payload)
            if payload_str is not None:
                try:
                    await topic_queue.put(messages.Response.model_validate_json(payload_str))
                except pydantic.ValidationError:
                    logger.error("Message failed validation. %s", payload_str)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sup_util.config_obj = config.load_config(
        pathlib.Path(os.getenv("PRIVATE_ASSISTANT_API_CONFIG_PATH", "local_config.yaml"))
    )
    sup_util.wakeword_model = openwakeword.Model(
        wakeword_models=[sup_util.config_obj.path_or_name_wakeword_model],
        enable_speex_noise_suppression=True,
        vad_threshold=sup_util.config_obj.vad_threshold,
        inference_framework=sup_util.config_obj.openwakeword_inference_framework,
    )
    sup_util.vad_model = silero_vad.SileroVad(threshold=sup_util.config_obj.vad_threshold, trigger_level=1)
    # global client
    global client
    async with aiomqtt.Client(
        hostname=sup_util.config_obj.mqtt_server_host, port=sup_util.config_obj.mqtt_server_port
    ) as c:
        # Make client globally available
        sup_util.mqtt_client = c
        # Listen for MQTT messages in (unawaited) asyncio task
        await sup_util.mqtt_client.subscribe(sup_util.config_obj.broadcast_topic, qos=1)
        loop = asyncio.get_event_loop()
        task = loop.create_task(listen(sup_util.mqtt_client, sup_util=sup_util))
        yield
        # Cancel the task
        task.cancel()
        # Wait for the task to be cancelled
        try:
            await task
        except asyncio.CancelledError:
            pass


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
        output_queue: asyncio.Queue[messages.Response] = asyncio.Queue()
        output_topic = f"assistant/{client_conf.room}/output"
        client_conf.output_topic = output_topic
        sup_util.mqtt_subscription_to_queue[output_topic] = output_queue
        await sup_util.mqtt_client.subscribe(output_topic, qos=1)
        sup_util.mqtt_subscription_to_queue[sup_util.config_obj.broadcast_topic] = output_queue
        while True:
            await process_output_queue(websocket, output_queue, sup_util.config_obj)
            message = await websocket.receive()

            if "bytes" in message:
                audio_bytes: bytes = message["bytes"]
                await handle_audio_message(websocket, audio_bytes, client_conf, sup_util)

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


async def process_output_queue(
    websocket: WebSocket, output_queue: asyncio.Queue[messages.Response], config_obj: config.Config
):
    try:
        response = output_queue.get_nowait()
        audio_np = await speech_recognition_tools.send_text_to_tts_api(response.text, config_obj)
        if response.alert is not None and response.alert.play_before:
            await websocket.send_text("alert_default")
        if audio_np is not None:
            await websocket.send_bytes(audio_np.tobytes())
    except asyncio.QueueEmpty:
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
            sup_util=sup_util,
            config_obj=sup_util.config_obj,
            client_conf=client_conf,
        )
