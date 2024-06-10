import asyncio
import json
import logging
import os
import sys

import pyaudio
import websockets

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger()

# Configuration for audio capture and playback
config = {"samplerate": 16000, "channels": 1, "chunk_size": 2000, "room": "bedroom"}


async def send_audio_data(websocket, audio_data):
    try:
        await websocket.send(audio_data)
    except Exception as e:
        logger.error(f"Error sending audio data: {e}")


async def send_audio(websocket: websockets.WebSocketClientProtocol, stream_input):
    """Async function to send audio data to the server."""
    semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent send tasks
    while True:
        async with semaphore:
            # Read audio data from the stream
            audio_data = stream_input.read(
                config["chunk_size"], exception_on_overflow=False
            )
            asyncio.create_task(send_audio_data(websocket, audio_data))
        await asyncio.sleep(0)  # Yield control


async def receive_commands(
    websocket: websockets.WebSocketClientProtocol, stream_output
):
    """Async function to receive commands from the server."""
    while True:
        # Receive command from the server
        message = await websocket.recv()

        if isinstance(message, bytes):
            stream_output.write(message)

            # Notify server that playback is complete
            await websocket.send("ready")
            await asyncio.sleep(0)  # Yield control


async def send_receive_audio(uri, stream_input, stream_output):
    """Async function to handle audio sending and receiving."""
    async for websocket in websockets.connect(uri, ping_interval=10):
        try:
            await websocket.send(json.dumps(config))
            # Create tasks for sending and receiving
            await asyncio.gather(
                send_audio(websocket, stream_input),
                receive_commands(websocket, stream_output),
            )
        except websockets.ConnectionClosed:
            logger.warning("Connection closed, retrying...")
            continue


def main(uri="ws://192.168.178.20:8000/client_control"):
    """Function to handle audio input and output streams."""
    # Initialize PyAudio
    p = pyaudio.PyAudio()

    # Open audio input stream
    stream_input = p.open(
        format=pyaudio.paInt16,
        channels=config["channels"],
        rate=config["samplerate"],
        input=True,
        frames_per_buffer=config["chunk_size"],
    )

    # Open audio output stream
    stream_output = p.open(
        format=pyaudio.paInt16,
        channels=config["channels"],
        rate=config["samplerate"],
        output=True,
    )

    try:
        asyncio.run(send_receive_audio(uri, stream_input, stream_output))
    finally:
        stream_input.stop_stream()
        stream_output.stop_stream()
        stream_input.close()
        stream_output.close()
        p.terminate()


if __name__ == "__main__":
    main()