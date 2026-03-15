"""A2A slide tool — calls the remote Slide Operator agent via A2A protocol.

Alex says "Next slide" → this tool calls the SlideOperator over A2A JSON-RPC →
SlideOperator generates the slide with Imagen → returns image + description →
Alex narrates about what's on the slide.

The A2A slide agent URL is configurable via A2A_SLIDE_URL env var.
Default: http://localhost:8002 (for local development).
"""

import logging
import os
import uuid

import httpx

logger = logging.getLogger(__name__)

A2A_SLIDE_URL = os.environ.get("A2A_SLIDE_URL", "http://localhost:8002")

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        # Short timeout — if slide agent is slow, Alex keeps presenting
        _client = httpx.Client(timeout=15.0)
    return _client


def next_slide(topic: str, key_points: str) -> dict:
    """Request the next presentation slide from the Slide Operator.

    Sends a slide request to the Slide Operator agent over A2A protocol.
    The Slide Operator generates a professional keynote slide using Imagen
    and returns both the image and a description of what the slide shows.

    Use the slide_description in your narration — describe what the audience
    is seeing on screen. The image is automatically displayed in the client.

    Args:
        topic: The slide title. Example: "Agent Development Kit (ADK)"
        key_points: Key concepts to visualize, comma-separated.
            Example: "Open source, Model agnostic, Production ready"

    Returns:
        Dictionary with slide_description (narrate this), image data, and status.
    """
    try:
        logger.info("A2A slide request: '%s' -> %s", topic, A2A_SLIDE_URL)

        message_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        slide_request = (
            f"Generate a keynote slide with title '{topic}' "
            f"and key points: {key_points}"
        )

        a2a_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "messageId": message_id,
                    "role": "user",
                    "parts": [{"kind": "text", "text": slide_request}],
                }
            },
        }

        client = _get_client()
        response = client.post(
            f"{A2A_SLIDE_URL.rstrip('/')}/",
            json=a2a_request,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        result = response.json()

        if "result" in result:
            a2a_result = result["result"]

            # Extract text response
            response_text = ""
            if "status" in a2a_result and "message" in a2a_result.get("status", {}):
                parts = a2a_result["status"]["message"].get("parts", [])
                text_parts = [p.get("text", "") for p in parts if p.get("kind") == "text"]
                response_text = "\n".join(text_parts)
            elif "parts" in a2a_result:
                text_parts = [p.get("text", "") for p in a2a_result["parts"] if p.get("kind") == "text"]
                response_text = "\n".join(text_parts)

            logger.info("A2A slide response received for: '%s'", topic)

            return {
                "status": "success",
                "topic": topic,
                "slide_description": response_text or f"Slide showing '{topic}' with key concepts: {key_points}",
                "source": "a2a_slide_operator",
            }

        elif "error" in result:
            error = result["error"]
            logger.warning("A2A slide error: %s", error)
            return {
                "status": "error",
                "topic": topic,
                "slide_description": f"Slide for '{topic}' is being prepared.",
                "message": f"A2A error: {error.get('message', str(error))}",
            }

        else:
            return {
                "status": "error",
                "topic": topic,
                "slide_description": f"Slide for '{topic}' is being prepared.",
                "message": "Unexpected response from slide operator",
            }

    except httpx.ConnectError:
        logger.error("Cannot connect to Slide Operator at %s", A2A_SLIDE_URL)
        return {
            "status": "error",
            "topic": topic,
            "slide_description": f"The slide for '{topic}' shows {key_points}.",
            "message": f"Slide operator unavailable at {A2A_SLIDE_URL}. Start with: python -m slide_agent.server",
        }
    except Exception as e:
        logger.error("A2A slide request failed: %s", e)
        return {
            "status": "error",
            "topic": topic,
            "slide_description": f"The slide for '{topic}' shows {key_points}.",
            "message": f"Slide request failed: {str(e)}",
        }
