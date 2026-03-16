"""Next Live — Production BIDI Streaming Server

3-Stage Journey: Invitation → Travel Concierge → Keynote
Based on google/adk-samples/bidi-demo pattern.
Custom WebSocket handler with full RunConfig control for optimal interruption handling.
"""

import asyncio
import json
import logging
import os
import queue

from dotenv import load_dotenv

load_dotenv()  # Load .env BEFORE any Google imports

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from next25_agent.agent import root_agent
from next25_agent.tools import image_tool
from concierge_agent.agent import concierge_agent, itinerary_queues
from concierge_tools.invitation_tool import generate_invitation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Next Live")

logger.info("=" * 60)
logger.info("NEXT LIVE — 3-Stage Journey Server Starting")
logger.info("=" * 60)

# ---------------------------------------------------------------------------
# A2A Agents — in-process runners for hotel/flight search
# The concierge tools call these via A2A JSON-RPC at /a2a/hotel/ and /a2a/flight/
# We create dedicated runners and handle JSON-RPC ourselves for reliable routing.
# ---------------------------------------------------------------------------
from hotel_agent.agent import hotel_agent
from flight_agent.agent import flight_agent

logger.info("[INIT] Creating A2A agent runners...")

# Separate session services for A2A agents (isolated from main agents)
_hotel_session_svc = InMemorySessionService()
_flight_session_svc = InMemorySessionService()

hotel_runner = Runner(
    app_name="hotel_agent",
    agent=hotel_agent,
    session_service=_hotel_session_svc,
)
flight_runner = Runner(
    app_name="flight_agent",
    agent=flight_agent,
    session_service=_flight_session_svc,
)
logger.info("[INIT] A2A agent runners created: hotel_agent, flight_agent")


# ---------------------------------------------------------------------------
# A2A JSON-RPC endpoint handler — runs an ADK agent synchronously
# ---------------------------------------------------------------------------
import uuid as _uuid


async def _run_a2a_agent(runner: Runner, session_svc: InMemorySessionService, app_name: str, request_body: dict) -> dict:
    """Execute an A2A JSON-RPC message/send request against an ADK agent runner."""
    request_id = request_body.get("id", str(_uuid.uuid4()))
    params = request_body.get("params", {})
    message = params.get("message", {})
    parts = message.get("parts", [])

    # Extract text from the A2A message
    user_text = ""
    for p in parts:
        if p.get("kind") == "text":
            user_text += p.get("text", "")

    if not user_text:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "No text in message"}}

    logger.info("[A2A:%s] Received query: '%s'", app_name, user_text[:100])

    # Create a one-shot session for this A2A request
    session_id = str(_uuid.uuid4())
    await session_svc.create_session(app_name=app_name, user_id="a2a", session_id=session_id)

    # Run the agent
    response_text = ""
    try:
        content = types.Content(parts=[types.Part(text=user_text)], role="user")
        async for event in runner.run_async(
            user_id="a2a",
            session_id=session_id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text
    except Exception as e:
        logger.error("[A2A:%s] Agent execution error: %s", app_name, e, exc_info=True)
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(e)}}

    logger.info("[A2A:%s] Response: %d chars", app_name, len(response_text))
    logger.info("[A2A:%s] Response preview: %s", app_name, response_text[:200])

    # Return A2A Task response
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "id": session_id,
            "status": {
                "state": "completed",
                "message": {
                    "kind": "message",
                    "messageId": str(_uuid.uuid4()),
                    "role": "agent",
                    "parts": [{"kind": "text", "text": response_text}],
                },
            },
        },
    }


@app.post("/a2a/hotel/")
async def a2a_hotel_endpoint(request: Request):
    """A2A JSON-RPC endpoint for HotelAgent."""
    body = await request.json()
    logger.info("[A2A:hotel] JSON-RPC method: %s", body.get("method"))
    result = await _run_a2a_agent(hotel_runner, _hotel_session_svc, "hotel_agent", body)
    return result


@app.post("/a2a/flight/")
async def a2a_flight_endpoint(request: Request):
    """A2A JSON-RPC endpoint for FlightAgent."""
    body = await request.json()
    logger.info("[A2A:flight] JSON-RPC method: %s", body.get("method"))
    result = await _run_a2a_agent(flight_runner, _flight_session_svc, "flight_agent", body)
    return result


@app.get("/a2a/hotel/.well-known/agent-card.json")
async def a2a_hotel_card():
    """Agent card for HotelAgent (A2A discovery)."""
    return {
        "name": "hotel_agent",
        "description": hotel_agent.description,
        "url": "/a2a/hotel/",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "skills": [{"id": "hotel_search", "name": "Hotel Search", "description": "Search for hotels near Las Vegas Convention Center"}],
    }


@app.get("/a2a/flight/.well-known/agent-card.json")
async def a2a_flight_card():
    """Agent card for FlightAgent (A2A discovery)."""
    return {
        "name": "flight_agent",
        "description": flight_agent.description,
        "url": "/a2a/flight/",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "skills": [{"id": "flight_search", "name": "Flight Search", "description": "Search for flights to Las Vegas"}],
    }


# Mount static files for the custom frontend
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
logger.info("[INIT] Static files mounted from %s", STATIC_DIR)

# ---------------------------------------------------------------------------
# Session service — shared between keynote and concierge (different app_name)
# ---------------------------------------------------------------------------
session_service = InMemorySessionService()
logger.info("[INIT] InMemorySessionService created")

# ---------------------------------------------------------------------------
# Keynote Runner (Alex)
# ---------------------------------------------------------------------------
logger.info("[INIT] Creating Keynote Runner (Alex, voice: Kore)...")
keynote_runner = Runner(
    app_name="next25_agent",
    agent=root_agent,
    session_service=session_service,
)

KEYNOTE_RUN_CONFIG = RunConfig(
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

# ---------------------------------------------------------------------------
# Concierge Runner (Maya)
# ---------------------------------------------------------------------------
logger.info("[INIT] Creating Concierge Runner (Maya, voice: Aoede)...")
concierge_runner = Runner(
    app_name="concierge_agent",
    agent=concierge_agent,
    session_service=session_service,
)

CONCIERGE_RUN_CONFIG = RunConfig(
    streaming_mode=StreamingMode.BIDI,
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Aoede",
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


logger.info("[INIT] All runners created successfully")
logger.info("[INIT] Endpoints: GET /, GET /health, POST /api/invitation")
logger.info("[INIT] WebSockets: /ws/keynote/{id}, /ws/concierge/{id}")
logger.info("[INIT] A2A: /a2a/hotel/, /a2a/flight/")
logger.info("=" * 60)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Serve the custom frontend."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
async def health():
    logger.info("[HEALTH] Health check requested")
    return {"status": "ok", "agents": ["alex", "concierge", "hotel", "flight"]}


@app.post("/api/invitation")
async def create_invitation(request: Request):
    """Generate an Imagen invitation card and send it via email."""
    # Accept email from request body, fallback to default
    try:
        body = await request.json()
        email = body.get("email", "").strip()
    except Exception:
        email = ""

    if not email:
        email = os.environ.get("INVITATION_EMAIL", "hudsonshimanyula@gmail.com")

    logger.info("[INVITATION] Generating invitation card for: %s", email)
    result = generate_invitation(email)
    logger.info("[INVITATION] Result status: %s, image size: %d KB, email_sent: %s",
                result.get("status"), len(result.get("image", "")) // 1024,
                result.get("email_sent"))
    return result


# ---------------------------------------------------------------------------
# Keynote WebSocket (Alex) — Stage 3
# ---------------------------------------------------------------------------

# Session-scoped slide queues (fixes cross-session leak)
slide_queues: dict[str, queue.Queue] = {}


@app.websocket("/ws/keynote/{session_id}")
async def keynote_websocket(websocket: WebSocket, session_id: str):
    """BIDI streaming WebSocket for Alex keynote — handles audio in/out."""
    await websocket.accept()
    user_id = "user"
    logger.info("[KEYNOTE] WebSocket accepted: %s", session_id)

    # Create session-scoped slide queue
    slide_queues[session_id] = queue.Queue()
    logger.info("[KEYNOTE] Slide queue created for session: %s", session_id)

    session = await session_service.create_session(
        app_name="next25_agent",
        user_id=user_id,
        session_id=session_id,
    )
    logger.info("[KEYNOTE] ADK session created: %s", session_id)

    live_request_queue = LiveRequestQueue()

    async def upstream_task():
        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message:
                    live_request_queue.send_realtime(
                        types.Blob(mime_type="audio/pcm;rate=16000", data=message["bytes"])
                    )
                elif "text" in message:
                    data = json.loads(message["text"])
                    if "text" in data:
                        live_request_queue.send_content(
                            types.Content(parts=[types.Part(text=data["text"])], role="user")
                        )
                    elif "image" in data:
                        import base64
                        image_bytes = base64.b64decode(data["image"])
                        live_request_queue.send_content(
                            types.Content(
                                parts=[types.Part(inline_data=types.Blob(
                                    mime_type=data.get("mime_type", "image/jpeg"),
                                    data=image_bytes,
                                ))],
                                role="user",
                            )
                        )
        except WebSocketDisconnect:
            logger.info("Client disconnected (upstream): %s", session_id)
        except Exception as e:
            logger.error("Upstream error: %s", e)

    async def downstream_task():
        try:
            async for event in keynote_runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=KEYNOTE_RUN_CONFIG,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.inline_data and part.inline_data.data:
                            await websocket.send_bytes(part.inline_data.data)
                        elif part.function_response:
                            pass
                        elif part.text:
                            await websocket.send_text(
                                json.dumps({"type": "text", "text": part.text})
                            )

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

                if hasattr(event, "interrupted") and event.interrupted:
                    await websocket.send_text(json.dumps({"type": "interrupted"}))

                if hasattr(event, "turn_complete") and event.turn_complete:
                    await websocket.send_text(json.dumps({"type": "turn_complete"}))

        except WebSocketDisconnect:
            logger.info("Client disconnected (downstream): %s", session_id)
        except Exception as e:
            logger.error("Downstream error: %s", e)

    async def slide_drainer_task():
        """Drain session-scoped slide queue and the global fallback."""
        try:
            while True:
                # Drain session-scoped queue
                session_queue = slide_queues.get(session_id)
                if session_queue:
                    while not session_queue.empty():
                        try:
                            slide_data = session_queue.get_nowait()
                        except queue.Empty:
                            break
                        try:
                            await websocket.send_text(json.dumps({
                                "type": "slide",
                                "image": slide_data["image"],
                                "topic": slide_data["topic"],
                            }))
                            logger.info("Slide delivered: '%s' (%d KB)", slide_data["topic"], len(slide_data["image"]) // 1024)
                        except Exception as e:
                            logger.error("Failed to send slide: %s", e)

                # Also drain the global slide_queue (backward compat — image_tool still uses it)
                while not image_tool.slide_queue.empty():
                    try:
                        slide_data = image_tool.slide_queue.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        await websocket.send_text(json.dumps({
                            "type": "slide",
                            "image": slide_data["image"],
                            "topic": slide_data["topic"],
                        }))
                        logger.info("Slide delivered (global): '%s'", slide_data["topic"])
                    except Exception as e:
                        logger.error("Failed to send slide: %s", e)

                await asyncio.sleep(0.3)
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Slide drainer error: %s", e)

    try:
        await asyncio.gather(upstream_task(), downstream_task(), slide_drainer_task())
    finally:
        live_request_queue.close()
        slide_queues.pop(session_id, None)
        logger.info("Keynote session closed: %s", session_id)


# ---------------------------------------------------------------------------
# Concierge WebSocket (Maya) — Stage 2
# ---------------------------------------------------------------------------

@app.websocket("/ws/concierge/{session_id}")
async def concierge_websocket(websocket: WebSocket, session_id: str):
    """BIDI streaming WebSocket for Maya travel concierge."""
    await websocket.accept()
    user_id = "user"
    logger.info("[CONCIERGE] WebSocket accepted: %s", session_id)

    # Create session-scoped itinerary queue
    itinerary_queues[session_id] = queue.Queue()
    logger.info("[CONCIERGE] Itinerary queue created for session: %s", session_id)

    # Get traveler email for confirm_booking tool
    traveler_email = os.environ.get("INVITATION_EMAIL", "hudsonshimanyula@gmail.com")
    logger.info("[CONCIERGE] Traveler email: %s", traveler_email)

    session = await session_service.create_session(
        app_name="concierge_agent",
        user_id=user_id,
        session_id=session_id,
        state={"session_id": session_id, "traveler_email": traveler_email},
    )
    logger.info("[CONCIERGE] ADK session created: %s (email=%s)", session_id, traveler_email)

    live_request_queue = LiveRequestQueue()

    async def upstream_task():
        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message:
                    live_request_queue.send_realtime(
                        types.Blob(mime_type="audio/pcm;rate=16000", data=message["bytes"])
                    )
                elif "text" in message:
                    data = json.loads(message["text"])
                    if "text" in data:
                        live_request_queue.send_content(
                            types.Content(parts=[types.Part(text=data["text"])], role="user")
                        )
        except WebSocketDisconnect:
            logger.info("Client disconnected (concierge upstream): %s", session_id)
        except Exception as e:
            logger.error("Concierge upstream error: %s", e)

    async def downstream_task():
        try:
            async for event in concierge_runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=CONCIERGE_RUN_CONFIG,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.inline_data and part.inline_data.data:
                            await websocket.send_bytes(part.inline_data.data)
                        elif part.function_response:
                            pass
                        elif part.text:
                            await websocket.send_text(
                                json.dumps({"type": "text", "text": part.text})
                            )

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

                if hasattr(event, "interrupted") and event.interrupted:
                    await websocket.send_text(json.dumps({"type": "interrupted"}))

                if hasattr(event, "turn_complete") and event.turn_complete:
                    await websocket.send_text(json.dumps({"type": "turn_complete"}))

        except WebSocketDisconnect:
            logger.info("Client disconnected (concierge downstream): %s", session_id)
        except Exception as e:
            logger.error("Concierge downstream error: %s", e)

    async def itinerary_drainer_task():
        """Drain itinerary queue — sends itinerary card data to client."""
        try:
            while True:
                itin_queue = itinerary_queues.get(session_id)
                if itin_queue:
                    while not itin_queue.empty():
                        try:
                            itinerary = itin_queue.get_nowait()
                        except queue.Empty:
                            break
                        try:
                            await websocket.send_text(json.dumps({
                                "type": "itinerary",
                                **itinerary,
                            }))
                            logger.info("Itinerary delivered to session: %s", session_id)
                        except Exception as e:
                            logger.error("Failed to send itinerary: %s", e)
                await asyncio.sleep(0.3)
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Itinerary drainer error: %s", e)

    try:
        await asyncio.gather(upstream_task(), downstream_task(), itinerary_drainer_task())
    finally:
        live_request_queue.close()
        itinerary_queues.pop(session_id, None)
        logger.info("Concierge session closed: %s", session_id)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info("[STARTUP] Starting uvicorn on 0.0.0.0:%d", port)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )
