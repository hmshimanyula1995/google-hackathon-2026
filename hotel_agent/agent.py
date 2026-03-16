"""A2A Hotel Agent — searches for real hotels near Las Vegas Convention Center.

Uses google_search grounding tool from ADK to find real hotel options.
Designed to be consumed via A2A protocol by the ConciergeAgent.
"""

import logging

from google.adk.agents import LlmAgent
from google.adk.tools import google_search
from google.genai import types

logger = logging.getLogger(__name__)

hotel_agent = LlmAgent(
    name="hotel_agent",
    model="gemini-2.5-flash",
    description=(
        "Searches for real hotels near the Las Vegas Convention Center for "
        "Google Cloud Next 2026 (April 22-24, 2026). Uses Google Search to "
        "find current hotel options with pricing, ratings, and distances."
    ),
    tools=[google_search],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=2048,
    ),
    instruction="""You are a hotel search specialist for Google Cloud Next 2026.

When asked for hotels near the Las Vegas Convention Center for Google Cloud Next 2026 (April 22-24, 2026), use google_search to find real hotels with real pricing, ratings, and distances.

<output_format>
You MUST return COMPLETE, DETAILED, STRUCTURED results. Do NOT truncate, abbreviate, or cut short your response.
ALWAYS list at least 3 hotel options. For EACH hotel, include ALL of the following details:
- Hotel name (full official name)
- Address (full street address)
- Distance from Las Vegas Convention Center (in miles)
- Price per night (estimated nightly rate in USD)
- Star rating (out of 5)
- Key amenities (pool, gym, shuttle, restaurant, spa, free WiFi, parking, etc.)
- A one-sentence summary of why this hotel is a good option

Present options ranging from budget to premium. Use clear numbered formatting (1., 2., 3., etc.).
Do NOT stop mid-sentence. Do NOT omit any fields. Every hotel entry must have ALL fields filled in.
</output_format>

Always search for current, real hotel options.
If the user has preferences (budget, amenities, distance), prioritize those in your search and results.

Keep responses factual. Do not fabricate hotel names, prices, or ratings.""",
)
