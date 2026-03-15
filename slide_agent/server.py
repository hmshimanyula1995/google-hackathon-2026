"""Slide Operator A2A Server — exposes slide generation via A2A protocol.

Usage:
    uvicorn slide_agent.server:app --host 0.0.0.0 --port 8002
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .agent import slide_operator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

HOST = os.environ.get("A2A_SLIDE_HOST", "0.0.0.0")
PORT = int(os.environ.get("A2A_SLIDE_PORT", "8002"))

app = to_a2a(
    slide_operator,
    host=HOST,
    port=PORT,
    protocol="http",
)

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting A2A Slide Operator on %s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT)
