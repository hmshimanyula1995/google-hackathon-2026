"""ConciergeAgent (Maya) — Live API voice agent for travel booking.

Handles Stage 2 of the 3-stage journey: flight + hotel booking for
Google Cloud Next 2026. Uses A2A protocol to call HotelAgent and FlightAgent.

Model: gemini-live-2.5-flash-native-audio (same as Alex)
Voice: Aoede (warm, distinct from Alex's Kore)
"""

import logging
import os
import queue

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import ToolContext
from google.genai import types

from concierge_tools.hotel_tool import search_hotels
from concierge_tools.flight_tool import search_flights

logger = logging.getLogger(__name__)

# Session-scoped itinerary queues — keyed by session_id
# Created in WebSocket handler, cleaned up on disconnect
itinerary_queues: dict[str, queue.Queue] = {}


def _send_itinerary_email(email: str, flight: str, hotel: str):
    """Send itinerary confirmation email via Gmail SMTP."""
    try:
        from concierge_tools.invitation_tool import _send_email_smtp

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f8f9fa;font-family:'Google Sans','Segoe UI',Roboto,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;padding:40px 20px;">
        <tr><td align="center">
            <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
                <tr><td style="background:linear-gradient(135deg,#34A853 0%,#188038 100%);padding:24px 32px;text-align:center;">
                    <span style="color:#fff;font-size:20px;font-weight:600;">Trip Confirmed!</span>
                </td></tr>
                <tr><td style="padding:28px 32px;">
                    <h1 style="margin:0 0 8px;font-size:24px;color:#202124;">Your Next '26 Itinerary</h1>
                    <p style="margin:0 0 24px;font-size:14px;color:#5f6368;line-height:1.6;">
                        Your trip to Google Cloud Next 2026 is booked! Here are your details:
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;border-radius:12px;margin-bottom:20px;">
                        <tr><td style="padding:16px 20px;border-bottom:1px solid #e8eaed;">
                            <p style="margin:0;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#9aa0a6;font-weight:600;">Flight</p>
                            <p style="margin:6px 0 0;font-size:15px;color:#202124;">{flight}</p>
                        </td></tr>
                        <tr><td style="padding:16px 20px;border-bottom:1px solid #e8eaed;">
                            <p style="margin:0;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#9aa0a6;font-weight:600;">Hotel</p>
                            <p style="margin:6px 0 0;font-size:15px;color:#202124;">{hotel}</p>
                        </td></tr>
                        <tr><td style="padding:16px 20px;border-bottom:1px solid #e8eaed;">
                            <p style="margin:0;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#9aa0a6;font-weight:600;">Event</p>
                            <p style="margin:6px 0 0;font-size:15px;color:#202124;">Google Cloud Next 2026 &middot; April 22-24, 2026</p>
                        </td></tr>
                        <tr><td style="padding:16px 20px;">
                            <p style="margin:0;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#9aa0a6;font-weight:600;">Venue</p>
                            <p style="margin:6px 0 0;font-size:15px;color:#202124;">Las Vegas Convention Center, Las Vegas NV</p>
                        </td></tr>
                    </table>
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr><td align="center">
                            <a href="https://next-live-agent-338756532561.us-central1.run.app/keynote" style="display:inline-block;padding:14px 40px;background:#34A853;color:#fff;text-decoration:none;border-radius:28px;font-size:16px;font-weight:600;">
                                Join the Keynote
                            </a>
                        </td></tr>
                    </table>
                </td></tr>
                <tr><td style="padding:20px 32px;border-top:1px solid #e8eaed;text-align:center;">
                    <p style="margin:0;font-size:11px;color:#9aa0a6;">Booked by Maya, your AI travel concierge &middot; Powered by Google ADK</p>
                </td></tr>
            </table>
        </td></tr>
    </table>
</body>
</html>"""

        sent = _send_email_smtp(
            to_email=email,
            subject="Trip Confirmed — Google Cloud Next 2026 Itinerary",
            html=html,
        )
        if sent:
            logger.info("[ITINERARY_EMAIL] Sent to %s", email)
        else:
            logger.warning("[ITINERARY_EMAIL] Skipped for %s — no Gmail password", email)

    except Exception as e:
        logger.error("[ITINERARY_EMAIL] Failed for %s: %s", email, e)


def confirm_booking(
    selected_flight: str,
    selected_hotel: str,
    traveler_email: str,
    tool_context: ToolContext,
) -> dict:
    """Confirm the trip booking and display the itinerary on screen.

    Args:
        selected_flight: Full description of the chosen flight
            (e.g. "United UA 1247, SFO to LAS, April 21, 8:30am-10:15am, $287 economy")
        selected_hotel: Full description of the chosen hotel
            (e.g. "Renaissance Las Vegas, 0.3 miles from venue, $189/night, 4.2 stars")
        traveler_email: The attendee's email address

    Returns:
        Confirmation message for the agent to speak.
    """
    session_id = tool_context.state.get("session_id", "")
    logger.info("[CONFIRM_BOOKING] session=%s, email=%s", session_id, traveler_email)
    logger.info("[CONFIRM_BOOKING] Flight: %s", selected_flight[:100])
    logger.info("[CONFIRM_BOOKING] Hotel: %s", selected_hotel[:100])

    itinerary = {
        "flight": {
            "description": selected_flight,
        },
        "hotel": {
            "description": selected_hotel,
        },
        "traveler_email": traveler_email,
        "event": "Google Cloud Next 2026",
        "event_dates": "April 22-24, 2026",
        "travel_dates": "April 21-25, 2026",
        "venue": "Las Vegas Convention Center",
    }

    # Push to session-scoped queue for WebSocket delivery
    if session_id and session_id in itinerary_queues:
        itinerary_queues[session_id].put(itinerary)
        logger.info("Itinerary queued for session: %s", session_id)
    else:
        logger.warning("No itinerary queue for session: %s", session_id)

    # Send itinerary confirmation email
    _send_itinerary_email(traveler_email, selected_flight, selected_hotel)

    return {
        "status": "confirmed",
        "message": (
            f"Trip confirmed for {traveler_email}. "
            f"Flight: {selected_flight}. "
            f"Hotel: {selected_hotel}. "
            f"The full itinerary is now on screen. A confirmation email has also been sent."
        ),
    }


# Model setup — same as Alex but with Aoede voice
_use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
CONCIERGE_MODEL_NAME = (
    "gemini-live-2.5-flash-native-audio"
    if _use_vertex
    else "gemini-2.5-flash-native-audio-preview-12-2025"
)

concierge_model = Gemini(
    model=CONCIERGE_MODEL_NAME,
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Aoede",
            )
        ),
    ),
)

concierge_agent = LlmAgent(
    name="concierge_agent",
    model=concierge_model,
    description="Maya — a friendly Google Cloud Next '26 travel concierge who helps book flights and hotels.",
    output_key="concierge_response",
    tools=[
        search_hotels,
        search_flights,
        confirm_booking,
    ],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.5,
        max_output_tokens=400,
    ),
    instruction="""<identity>
You are Maya, a friendly and warm Google Cloud Next '26 travel concierge.
You help attendees plan their trip to Las Vegas for the conference.
Event: Google Cloud Next 2026, April 22-24, 2026, Las Vegas Convention Center.
</identity>

<critical_behavior>
BEFORE calling ANY tool, you MUST speak a brief acknowledgment first. This is non-negotiable.
The tools take a few seconds to search, and the user needs to know what is happening.

Examples of what to say BEFORE calling search_flights:
- "Indianapolis, great! Let me pull up some flights for you right now."
- "Love it! Let me search for the best flights from Chicago to Vegas."
- "Awesome, flying from New York! Give me just a moment to find some options."

Examples of what to say BEFORE calling search_hotels:
- "Perfect, let me find some great hotels near the Convention Center for you."
- "Got it! Let me search for hotels that match what you are looking for."

Examples of what to say BEFORE calling confirm_booking:
- "Alright, let me lock that in for you!"

You MUST say something warm and specific BEFORE every tool call. Never call a tool in silence.
</critical_behavior>

<flow>
1. Greet warmly. Tell them you are excited to help plan their trip to Next '26 in Las Vegas. Ask where they will be flying from.
2. Once they say their city, FIRST say something like "Great choice! Let me search for flights from [city] to Vegas right now." THEN call search_flights.
3. Present 2-3 flight options conversationally. Mention airline, price, departure times naturally. Ask which sounds good.
4. Once they pick a flight, ask about hotel preferences: budget range, must-have amenities, how close to the venue.
5. FIRST say "Perfect, let me find some hotels that match." THEN call search_hotels for the Las Vegas Convention Center area.
6. Present 2-3 hotel options. Mention name, price per night, distance from venue, rating. Ask which they prefer.
7. Once they pick a hotel, say "Let me lock that in!" then call confirm_booking with:
   - selected_flight: full description of their chosen flight (airline, times, price)
   - selected_hotel: full description of their chosen hotel (name, price, rating)
   - traveler_email: "hudsonshimanyula@gmail.com"
8. After confirmation, say something like: "Your trip is all set! Your full itinerary is on screen now. When you are ready, hit the Confirm and Join Keynote button. Alex will catch you up on what happened at last year's Next!"
</flow>

<tool_limits>
NEVER call the same tool more than once per topic. If you called search_flights and got results, present those results immediately. Do not call search_flights again. If you called search_hotels and got results, present those results immediately. Do not call search_hotels again. If results seem incomplete, work with what you have and present them to the user. Calling a tool a second time for the same request is strictly forbidden.
</tool_limits>

<vision>
When the user shares an image with you, analyze what you see and help them with their travel planning:
- If it is a hotel photo: identify the hotel if you can, describe what you see (pool, lobby, room, exterior), comment on whether it looks like a good fit for their Next trip, and offer to search for it or similar hotels near the Convention Center.
- If it is a screenshot of flight or hotel search results: read the prices and options visible in the image and help them compare or pick the best one.
- If it is something else travel-related (a map, a venue photo, a restaurant): describe what you see and relate it to their Las Vegas trip.
- Always acknowledge the image warmly: "Oh nice, let me take a look at that!" and then describe what you see before giving advice.
</vision>

<rules>
- 40-60 words per turn. Be conversational, warm, and interruptible.
- Use contractions. Be friendly and enthusiastic about the conference.
- Never use markdown, bold, bullet points, or formatting. Spoken audio only.
- All dates are fixed: fly in April 21, conference April 22-24, fly out April 25.
- For confirm_booking, always use traveler_email "hudsonshimanyula@gmail.com".
- If they ask something off-topic: "I am all about getting you to Next! What do you say we lock in this trip first?"
- If a tool returns an error, do NOT retry silently. Say "Hmm, that search did not come through. Let me try again." Then retry once. If it fails again, offer general options from your knowledge: "Based on what I know, there are usually direct flights from [city] on major carriers like United, Delta, and Southwest."
- Always keep the conversation flowing. Never go silent.
</rules>""",
)
