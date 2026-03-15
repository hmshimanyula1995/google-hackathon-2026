"""Imagen slide generation tool for the Next Live agent.

Generates presentation slides using Imagen on Vertex AI.
The image is stored in session state for the WebSocket handler to forward
to the client. Only a short text description is returned to the model
to avoid overflowing the 32K context window.
"""

import base64
import logging
import os

from google import genai
from google.adk.tools import ToolContext
from google.genai.types import GenerateImagesConfig

logger = logging.getLogger(__name__)

_genai_client: genai.Client | None = None


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
    """Generate a presentation slide image for the current topic.

    Creates a professional keynote-style slide using Google's Imagen model.
    The slide image is stored in session state for the client to display.
    Only a short description is returned to you — the audience sees the
    full visual on their screen.

    Args:
        topic: The slide title. Example: "Agent Development Kit (ADK)"
        key_points: 2-3 key bullet points to visualize. Example:
            "Open source framework, Model agnostic, Build agents in minutes"

    Returns:
        A short description of the slide. The actual image is sent to the audience automatically.
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

        # Store image in session state for the WebSocket handler to pick up
        # DO NOT return base64 to the model — it would overflow the 32K context window
        tool_context.state["temp:slide_image"] = image_b64
        tool_context.state["temp:slide_topic"] = topic

        # Return only a SHORT description to the model
        return {
            "status": "success",
            "topic": topic,
            "description": f"Slide displayed: '{topic}' showing {key_points}",
        }

    except Exception as e:
        logger.error("Slide generation failed: %s", e)
        return {
            "status": "error",
            "topic": topic,
            "description": f"Slide generation failed, continuing without visual.",
        }
