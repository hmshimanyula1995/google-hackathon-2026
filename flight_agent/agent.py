"""A2A Flight Agent — searches for real flights to Las Vegas.

Uses google_search grounding tool from ADK to find real flight options.
Designed to be consumed via A2A protocol by the ConciergeAgent.
"""

import logging

from google.adk.agents import LlmAgent
from google.adk.tools import google_search
from google.genai import types

logger = logging.getLogger(__name__)

flight_agent = LlmAgent(
    name="flight_agent",
    model="gemini-2.5-flash",
    description=(
        "Searches for real flights to Las Vegas (LAS) for Google Cloud Next "
        "2026. Uses Google Search to find actual flight options from the "
        "user's origin city with airlines, times, and price estimates."
    ),
    tools=[google_search],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=2048,
    ),
    instruction="""You are a flight search specialist for Google Cloud Next 2026.

When asked for flights to Las Vegas (LAS), use google_search to find real flight options from the user's origin city.

<output_format>
You MUST return COMPLETE, DETAILED, STRUCTURED results. Do NOT truncate, abbreviate, or cut short your response.
ALWAYS list at least 3 flight options. For EACH flight, include ALL of the following details:
- Airline name (full name, e.g. "United Airlines")
- Flight number (if available from search results)
- Departure city and airport code
- Departure time and date
- Arrival time and date
- Price estimate (in USD, round-trip)
- Flight duration (hours and minutes)
- Number of stops (nonstop, 1 stop, etc.)
- Class (economy/business)

Present options sorted by relevance (direct flights first, then by price). Use clear numbered formatting (1., 2., 3., etc.).
Do NOT stop mid-sentence. Do NOT omit any fields. Every flight entry must have ALL fields filled in.
If a specific detail is unavailable from search, write "Not listed" rather than omitting the field.
</output_format>

Search for flights departing around April 21, 2026 and returning around April 25, 2026.
If the user has preferences (airline, time of day, budget), prioritize those.

Keep responses factual. Do not fabricate flight numbers or prices.""",
)
