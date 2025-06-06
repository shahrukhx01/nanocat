import os
import sys
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from loguru import logger
from nanocat.frames.frames import TTSSpeakFrame
from nanocat.transports.base_transport import BaseTransport
from nanocat.transports.network.fastapi_websocket import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)
from nanocat.serializers.protobuf import ProtobufFrameSerializer
from nanocat.audio.vad.silero import SileroVADAnalyzer
from nanocat.pipeline.pipeline import Pipeline
from nanocat.pipeline.task import PipelineTask, PipelineParams
from nanocat.services.deepgram.stt import DeepgramSTTService
from nanocat.services.openai.llm import (
    OpenAIContextAggregatorPair,
    OpenAILLMService,
    OpenAILLMContext,
)
from nanocat.services.azure.tts import AzureTTSService


load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


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
    first_message = "Hello, how are you?"

    stt_service = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
    )

    llm_service = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o-mini",
    )

    tts_service = AzureTTSService(
        api_key=os.getenv("AZURE_API_KEY"),
        region=os.getenv("AZURE_REGION"),
    )
    first_message_chat = [{"role": "assistant", "content": first_message}]
    llm_context = OpenAILLMContext(first_message_chat, tools=[])  # type: ignore
    context_aggregator: OpenAIContextAggregatorPair = (
        llm_service.create_context_aggregator(llm_context)
    )
    pipeline = Pipeline(
        [
            transport.input(),
            stt_service,
            context_aggregator.user(),
            llm_service,
            tts_service,
            transport.output(),
            context_aggregator.assistant(),
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

    @transport.event_handler("on_client_connected")  # type: ignore
    async def on_client_connected(transport: BaseTransport, client: Any) -> None:
        await task.queue_frames([TTSSpeakFrame(first_message)])

    await task.run()
