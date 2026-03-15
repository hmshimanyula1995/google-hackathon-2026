"""A2A search tool — calls the remote search agent via A2A protocol.

This tool wraps an A2A JSON-RPC call to the standalone search agent service,
making it usable as a FunctionTool in the live/BIDI root agent.

Why a tool wrapper instead of RemoteA2aAgent sub-agent?
RemoteA2aAgent._run_live_impl is not implemented in ADK, so it cannot be
used as a sub-agent in BIDI streaming mode. Wrapping the A2A call as a
synchronous tool function sidesteps this limitation while still demonstrating
the A2A protocol: Alex calls the search agent over A2A JSON-RPC.

The A2A search agent URL is configurable via the A2A_SEARCH_URL env var.
Default: http://localhost:8001 (for local development).
"""

import logging
import os
import uuid

import httpx

logger = logging.getLogger(__name__)

A2A_SEARCH_URL = os.environ.get("A2A_SEARCH_URL", "http://localhost:8001")

# Module-level sync client (reused across calls)
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """Get or create a reusable HTTP client."""
    global _client
    if _client is None:
        _client = httpx.Client(timeout=30.0)
    return _client


def search_next25_sessions(query: str, top_k: int = 5) -> dict:
    """Search the Next '25 knowledge base via the A2A search agent.

    Sends a natural language query to the remote search agent over the
    Agent-to-Agent (A2A) protocol. The search agent performs vector
    similarity search against Firestore session transcripts and returns
    relevant session content with metadata.

    Args:
        query: Natural language question or topic to search for.
        top_k: Number of results to return. Use 5 for general questions,
               8 for questions spanning multiple topics.

    Returns:
        A dictionary with the search agent's response text and status.
    """
    try:
        logger.info(
            "A2A search request: '%s' (top_k=%d) -> %s",
            query,
            top_k,
            A2A_SEARCH_URL,
        )

        # Build the A2A JSON-RPC request
        message_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        search_query = f"{query} (return up to {top_k} results)"

        a2a_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "messageId": message_id,
                    "role": "user",
                    "parts": [
                        {
                            "kind": "text",
                            "text": search_query,
                        }
                    ],
                }
            },
        }

        client = _get_client()
        response = client.post(
            f"{A2A_SEARCH_URL.rstrip('/')}/",
            json=a2a_request,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        result = response.json()

        # Extract the response text from the A2A response
        # The response is either a Task or a Message depending on the server
        if "result" in result:
            a2a_result = result["result"]

            # Handle Task response (has status.message.parts)
            if "status" in a2a_result and "message" in a2a_result.get(
                "status", {}
            ):
                parts = (
                    a2a_result.get("status", {})
                    .get("message", {})
                    .get("parts", [])
                )
                text_parts = [
                    p.get("text", "") for p in parts if p.get("kind") == "text"
                ]
                response_text = "\n".join(text_parts)
            # Handle direct Message response (has parts)
            elif "parts" in a2a_result:
                parts = a2a_result.get("parts", [])
                text_parts = [
                    p.get("text", "") for p in parts if p.get("kind") == "text"
                ]
                response_text = "\n".join(text_parts)
            # Handle artifacts (has artifacts[].parts)
            elif "artifacts" in a2a_result:
                all_text = []
                for artifact in a2a_result.get("artifacts", []):
                    for p in artifact.get("parts", []):
                        if p.get("kind") == "text":
                            all_text.append(p.get("text", ""))
                response_text = "\n".join(all_text)
            else:
                response_text = str(a2a_result)

            logger.info(
                "A2A search returned %d chars for: '%s'",
                len(response_text),
                query,
            )

            return {
                "status": "success",
                "query": query,
                "response": response_text,
                "source": "a2a_search_agent",
            }

        elif "error" in result:
            error = result["error"]
            logger.warning("A2A search error: %s", error)
            return {
                "status": "error",
                "query": query,
                "response": "",
                "message": f"A2A error: {error.get('message', str(error))}",
            }

        else:
            logger.warning("Unexpected A2A response format: %s", result)
            return {
                "status": "error",
                "query": query,
                "response": "",
                "message": "Unexpected response format from search agent",
            }

    except httpx.ConnectError:
        logger.error(
            "Cannot connect to A2A search agent at %s. "
            "Is the search agent server running?",
            A2A_SEARCH_URL,
        )
        return {
            "status": "error",
            "query": query,
            "response": "",
            "message": (
                f"Search agent unavailable at {A2A_SEARCH_URL}. "
                "Start it with: python -m a2a_search_agent.server"
            ),
        }
    except Exception as e:
        logger.error("A2A search failed: %s", e)
        return {
            "status": "error",
            "query": query,
            "response": "",
            "message": f"A2A search failed: {str(e)}",
        }
