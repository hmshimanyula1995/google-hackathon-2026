"""A2A Search Agent — standalone agent exposing Next '25 search via A2A protocol.

This agent wraps the Firestore vector search capability as an A2A-compatible
service. It uses a text-only model (gemini-2.5-flash) since it handles
structured search queries, not voice.

The agent is designed to be consumed by Alex (the root voice agent) via
RemoteA2aAgent or a direct HTTP client wrapper, demonstrating the A2A
protocol in action: "Alex uses ADK, and Alex communicates with other agents
via A2A — the very protocol it describes."
"""

import logging

from google.adk.agents import LlmAgent
from google.genai import types

from next25_agent.tools.search_tool import search_next25_sessions

logger = logging.getLogger(__name__)

search_agent = LlmAgent(
    name="next25_search_agent",
    model="gemini-2.5-flash",
    description=(
        "Searches the Google Cloud Next '25 knowledge base. Accepts natural "
        "language queries about sessions, announcements, speakers, products, "
        "and demos from the conference. Returns relevant session chunks with "
        "titles, speakers, YouTube URLs, and transcript excerpts."
    ),
    tools=[search_next25_sessions],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=1024,
    ),
    instruction="""You are a search agent for Google Cloud Next '25 conference content.

When you receive a query:
1. Call search_next25_sessions with the user's query.
2. Return the search results as a clear, structured summary.
3. Include session titles, speakers, and key points from the transcript excerpts.
4. If no results are found, say so clearly.

Keep responses factual and concise. Do not embellish or fabricate information.
Only report what the search results contain.""",
)
