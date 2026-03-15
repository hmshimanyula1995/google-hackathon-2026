"""A2A Search Agent Server — exposes the search agent via A2A protocol.

Wraps the search agent as a Starlette ASGI application using ADK's to_a2a()
utility. Serves on port 8001 by default.

The agent card is auto-generated and available at:
  GET /.well-known/agent.json

Usage:
    # Direct run
    python -m a2a_search_agent.server

    # Or via uvicorn
    uvicorn a2a_search_agent.server:app --host 0.0.0.0 --port 8001
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .agent import search_agent

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)

HOST = os.environ.get("A2A_SEARCH_HOST", "0.0.0.0")
PORT = int(os.environ.get("A2A_SEARCH_PORT", "8001"))

# to_a2a() returns a Starlette app with:
#   - POST / — A2A JSON-RPC endpoint
#   - GET /.well-known/agent.json — auto-generated agent card
app = to_a2a(
    search_agent,
    host=HOST,
    port=PORT,
    protocol="http",
)

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting A2A Search Agent on %s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT)
