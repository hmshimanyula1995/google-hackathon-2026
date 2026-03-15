"""Next Live — Production BIDI Streaming Server

Based on google/adk-samples/bidi-demo pattern.
Custom WebSocket handler with full RunConfig control for optimal interruption handling.
"""

import asyncio
import json
import logging
import os
import uuid

from dotenv import load_dotenv

load_dotenv()  # Load .env BEFORE any Google imports

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from next25_agent.agent import root_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Next Live")

# Mount static files for the custom frontend
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Session service — in-memory for development, Cloud SQL for production
session_service = InMemorySessionService()

# Runner
runner = Runner(
    app_name="next25_agent",
    agent=root_agent,
    session_service=session_service,
)

# Optimized RunConfig for fastest interruption response
RUN_CONFIG = RunConfig(
    streaming_mode=StreamingMode.BIDI,
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Kore",
            )
        ),
    ),
    realtime_input_config=types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            disabled=False,
            start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
            end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
            prefix_padding_ms=0,
            silence_duration_ms=100,
        )
    ),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    input_audio_transcription=types.AudioTranscriptionConfig(),
    session_resumption=types.SessionResumptionConfig(transparent=True),
)


@app.get("/")
async def root():
    """Serve the custom frontend."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok", "agent": root_agent.name}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """BIDI streaming WebSocket — handles audio in/out with instant interruption."""
    await websocket.accept()
    user_id = "user"

    # Create session
    session = await session_service.create_session(
        app_name="next25_agent",
        user_id=user_id,
        session_id=session_id,
    )
    logger.info("Session created: %s", session_id)

    # Create live request queue
    live_request_queue = LiveRequestQueue()

    async def upstream_task():
        """Client → Server: receive audio and text from browser."""
        try:
            while True:
                message = await websocket.receive()

                if "bytes" in message:
                    # Binary audio data (PCM 16kHz)
                    live_request_queue.send_realtime(
                        types.Blob(
                            mime_type="audio/pcm;rate=16000",
                            data=message["bytes"],
                        )
                    )
                elif "text" in message:
                    data = json.loads(message["text"])

                    if "text" in data:
                        # Text message from user
                        live_request_queue.send_content(
                            types.Content(
                                parts=[types.Part(text=data["text"])],
                                role="user",
                            )
                        )
                    elif "image" in data:
                        # Base64 image data
                        import base64
                        image_bytes = base64.b64decode(data["image"])
                        live_request_queue.send_content(
                            types.Content(
                                parts=[
                                    types.Part(
                                        inline_data=types.Blob(
                                            mime_type=data.get("mime_type", "image/jpeg"),
                                            data=image_bytes,
                                        )
                                    )
                                ],
                                role="user",
                            )
                        )
        except WebSocketDisconnect:
            logger.info("Client disconnected (upstream): %s", session_id)
        except Exception as e:
            logger.error("Upstream error: %s", e)

    async def downstream_task():
        """Server → Client: send audio and events to browser."""
        try:
            async for event in runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=RUN_CONFIG,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.inline_data and part.inline_data.data:
                            # Send audio as binary frame (no base64 overhead)
                            await websocket.send_bytes(part.inline_data.data)
                        elif part.function_response:
                            # Check for slide-related tool responses
                            fr = part.function_response
                            if fr.name in ("generate_slide", "next_slide", "create_slide") and fr.response:
                                resp = fr.response
                                # Direct Imagen response (has image_base64)
                                if resp.get("image_base64"):
                                    await websocket.send_text(
                                        json.dumps({
                                            "type": "slide",
                                            "image": resp["image_base64"],
                                            "topic": resp.get("topic", ""),
                                        })
                                    )
                                    logger.info("Slide sent to client: %s", resp.get("topic"))
                                # A2A response (has slide_description but no image)
                                elif resp.get("slide_description"):
                                    await websocket.send_text(
                                        json.dumps({
                                            "type": "slide_text",
                                            "topic": resp.get("topic", ""),
                                            "description": resp.get("slide_description", ""),
                                        })
                                    )
                                    logger.info("Slide description sent: %s", resp.get("topic"))
                        elif part.text:
                            await websocket.send_text(
                                json.dumps({"type": "text", "text": part.text})
                            )

                # Send transcription events
                if hasattr(event, "output_transcription") and event.output_transcription:
                    text = getattr(event.output_transcription, "text", "")
                    if text:
                        await websocket.send_text(
                            json.dumps({"type": "transcript", "text": text})
                        )

                if hasattr(event, "input_transcription") and event.input_transcription:
                    text = getattr(event.input_transcription, "text", "")
                    if text:
                        await websocket.send_text(
                            json.dumps({"type": "user_transcript", "text": text})
                        )

                # Send interruption signal — client MUST clear audio buffer
                if hasattr(event, "interrupted") and event.interrupted:
                    await websocket.send_text(
                        json.dumps({"type": "interrupted"})
                    )

                # Turn complete signal
                if hasattr(event, "turn_complete") and event.turn_complete:
                    await websocket.send_text(
                        json.dumps({"type": "turn_complete"})
                    )

        except WebSocketDisconnect:
            logger.info("Client disconnected (downstream): %s", session_id)
        except Exception as e:
            logger.error("Downstream error: %s", e)

    try:
        await asyncio.gather(
            upstream_task(),
            downstream_task(),
        )
    finally:
        live_request_queue.close()
        logger.info("Session closed: %s", session_id)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )
