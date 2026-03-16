"""A2A hotel tool — calls the HotelAgent via A2A JSON-RPC protocol.

Uses async httpx to avoid blocking the event loop (critical: the A2A
endpoint is on the SAME server, so sync HTTP would deadlock).
"""

import logging
import os
import uuid

import httpx

logger = logging.getLogger(__name__)


def _extract_response_text(result: dict) -> str:
    """Extract text from A2A JSON-RPC response (Task or Message format)."""
    a2a_result = result.get("result", {})

    if "status" in a2a_result and "message" in a2a_result.get("status", {}):
        parts = a2a_result["status"]["message"].get("parts", [])
        texts = [p.get("text", "") for p in parts if p.get("kind") == "text"]
        return "\n".join(texts)

    if "parts" in a2a_result:
        parts = a2a_result.get("parts", [])
        texts = [p.get("text", "") for p in parts if p.get("kind") == "text"]
        return "\n".join(texts)

    if "artifacts" in a2a_result:
        all_text = []
        for artifact in a2a_result.get("artifacts", []):
            for p in artifact.get("parts", []):
                if p.get("kind") == "text":
                    all_text.append(p.get("text", ""))
        return "\n".join(all_text)

    return str(a2a_result)


async def search_hotels(location: str, preferences: str) -> dict:
    """Search for hotels near the conference venue via the A2A Hotel Agent.

    Args:
        location: Area to search, e.g. "Las Vegas Convention Center"
        preferences: User preferences like "under $200/night", "with pool", "closest to venue"

    Returns:
        Dictionary with hotel search results from the A2A agent.
    """
    port = os.environ.get("PORT", "8000")
    url = f"http://localhost:{port}/a2a/hotel/"

    query = (
        f"Hotels near {location} for April 21-25, 2026 "
        f"(Google Cloud Next 2026 conference). Preferences: {preferences}"
    )

    a2a_request = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"kind": "text", "text": query}],
            }
        },
    }

    logger.info("[A2A_HOTEL_TOOL] Searching: '%s' -> %s", query[:80], url)

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, json=a2a_request, headers={"Content-Type": "application/json"})
            response.raise_for_status()

        result = response.json()

        if "result" in result:
            response_text = _extract_response_text(result)
            logger.info("[A2A_HOTEL_TOOL] Response: %d chars", len(response_text))
            return {
                "status": "success",
                "response": response_text,
                "source": "a2a_hotel_agent",
            }

        if "error" in result:
            error = result["error"]
            logger.warning("[A2A_HOTEL_TOOL] Error: %s", error)
            return {"status": "error", "response": "", "message": str(error)}

        return {"status": "error", "response": "", "message": "Unexpected response format"}

    except httpx.ConnectError:
        logger.error("[A2A_HOTEL_TOOL] Cannot connect to localhost:%s", port)
        return {"status": "error", "response": "", "message": "Hotel agent unavailable"}
    except Exception as e:
        logger.error("[A2A_HOTEL_TOOL] Failed: %s", e)
        return {"status": "error", "response": "", "message": str(e)}
