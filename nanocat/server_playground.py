import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from loguru import logger
from nanocat.pipeline.runner import PipelineRunner
from nanocat.playground.transport.network.fastapi_websocket import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)
from nanocat.serializers.protobuf import ProtobufFrameSerializer
from nanocat.audio.vad.silero import SileroVADAnalyzer
from nanocat.pipeline.pipeline import Pipeline
from nanocat.pipeline.task import PipelineTask, PipelineParams


load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

USE_DEEPGRAM = int(os.getenv("USE_DEEPGRAM", "0"))


app = FastAPI()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming audio data."""
    logger.info("WebSocket connection established")
    await websocket.accept()
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            serializer=ProtobufFrameSerializer(),
            audio_out_enabled=True,
            add_wav_header=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            session_timeout=60 * 3,  # 3 minutes
        ),
    )
    pipeline = Pipeline(
        [
            transport.input(),
            transport.output(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16_000,
            audio_out_sample_rate=16_000,
            allow_interruptions=True,
        ),
    )
    await PipelineRunner().run(task=task)
