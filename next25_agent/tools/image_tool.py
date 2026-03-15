"""Imagen slide generation — fast path only.

Flow:
1. Imagen 4.0 Fast generates a keynote slide image (~2-3s)
2. The image is pushed to a global slide queue for the WebSocket handler
   to forward to the client — bypasses the model context entirely
3. A brief text description is returned to Alex so it can narrate

Single model, minimal latency — critical for Live API tool timeout window.
"""

import base64
import logging
import os
import queue

from google import genai
from google.adk.tools import ToolContext
from google.genai.types import GenerateImagesConfig

logger = logging.getLogger(__name__)

_genai_client: genai.Client | None = None

# Global slide queue — image_tool pushes, main.py WebSocket handler reads
slide_queue: queue.Queue = queue.Queue()


def _get_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(
            vertexai=os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true",
            project=os.environ.get("GOOGLE_CLOUD_PROJECT", "next-live-agent"),
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
    return _genai_client


def generate_slide(topic: str, key_points: str, tool_context: ToolContext) -> dict:
    """Generate a presentation slide and push it to the audience screen.

    Creates a professional keynote slide using Imagen. The actual image is
    sent to the audience's screen automatically via the slide queue. You
    receive the topic and key points back so you can narrate naturally.

    Args:
        topic: The slide title. Example: "Agent Development Kit (ADK)"
        key_points: 2-3 key concepts to visualize, comma-separated.
            Example: "Open source framework, Model agnostic, Build agents in minutes"

    Returns:
        Confirmation with topic and key points for narration.
    """
    try:
        prompt = (
            f"A clean, professional keynote presentation slide for a Google Cloud conference. "
            f"Title: '{topic}'. "
            f"Key concepts: {key_points}. "
            f"Style: modern tech conference slide with Google Cloud branding colors "
            f"(blue #4285F4, white background), minimal text, bold typography, "
            f"abstract geometric shapes representing AI and cloud technology. "
            f"16:9 aspect ratio. No photographs of people."
        )

        logger.info("Generating slide for: '%s'", topic)

        client = _get_client()
        response = client.models.generate_images(
            model="imagen-4.0-fast-generate-001",
            prompt=prompt,
            config=GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                person_generation="dont_allow",
                safety_filter_level="block_medium_and_above",
                add_watermark=False,
            ),
        )

        image_bytes = response.generated_images[0].image.image_bytes
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        logger.info("Slide generated: %d bytes for '%s'", len(image_bytes), topic)

        # Push image to the global slide queue for the WebSocket handler
        # The model NEVER sees the base64 — only the text description
        slide_queue.put({
            "image": image_b64,
            "topic": topic,
        })
        logger.info("Slide queued for delivery: '%s'", topic)

        return {
            "status": "success",
            "topic": topic,
            "what_the_slide_shows": (
                f"A presentation slide titled '{topic}' is now on screen. "
                f"Key concepts shown: {key_points}. "
                f"Describe what the audience is seeing based on these points."
            ),
        }

    except Exception as e:
        logger.error("Slide generation failed for '%s': %s", topic, e, exc_info=True)
        return {
            "status": "error",
            "topic": topic,
            "what_the_slide_shows": f"The slide for '{topic}' is being prepared. Continue presenting.",
        }
