"""Slide Operator Agent — generates and manages presentation slides via A2A.

This agent acts as the "slide production team" in the keynote. When Alex
(the presenter) says "Next slide", this agent:
1. Receives the topic and key points
2. Generates a visual slide using Imagen 4.0 Fast
3. Returns the slide image AND a text description of what's on it

Alex then "looks at" the description and narrates about the slide content.
The actual image is sent to the client UI simultaneously.

Exposed via A2A protocol so Alex communicates with it as a separate service —
demonstrating multi-agent collaboration.
"""

import base64
import logging
import os

from google import genai
from google.adk.agents import LlmAgent
from google.genai import types as genai_types
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


def create_slide(topic: str, key_points: str, style: str = "modern tech keynote") -> dict:
    """Generate a presentation slide image for the given topic.

    Creates a professional keynote-style slide using Google's Imagen model.
    Returns both the image data and a text description of the slide content
    so the presenter can narrate about it.

    Args:
        topic: The slide title. Example: "Agent Development Kit (ADK)"
        key_points: Key concepts to visualize, comma-separated.
            Example: "Open source framework, Model agnostic, Build agents in minutes"
        style: Visual style hint. Default: "modern tech keynote"

    Returns:
        Dictionary with image_base64, mime_type, topic, and slide_description.
    """
    try:
        prompt = (
            f"A clean, professional keynote presentation slide. "
            f"Title text: '{topic}'. "
            f"Visual elements representing: {key_points}. "
            f"Style: {style} with Google Cloud colors (blue #4285F4, white background), "
            f"bold sans-serif typography, abstract geometric shapes and icons, "
            f"minimal and modern. 16:9 aspect ratio. No photographs of people. "
            f"Conference stage quality."
        )

        logger.info("SlideOperator generating: '%s'", topic)

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

        # Return image AND a description so the presenter can narrate
        slide_description = (
            f"The slide shows the title '{topic}' with visual elements "
            f"representing {key_points}. It uses Google Cloud blue branding "
            f"with modern geometric design."
        )

        return {
            "status": "success",
            "image_base64": image_b64,
            "mime_type": "image/png",
            "topic": topic,
            "slide_description": slide_description,
        }

    except Exception as e:
        logger.error("Slide generation failed: %s", e)
        return {
            "status": "error",
            "message": f"Slide generation failed: {str(e)}",
            "image_base64": "",
            "topic": topic,
            "slide_description": f"The slide for '{topic}' is being prepared.",
        }


# The Slide Operator agent
slide_operator = LlmAgent(
    name="slide_operator",
    model="gemini-2.5-flash",
    description=(
        "Slide production operator for a keynote presentation. "
        "When the presenter requests the next slide, this agent generates "
        "a professional keynote slide using Imagen and returns both the image "
        "and a description of what the slide shows. The presenter uses the "
        "description to narrate about the slide content."
    ),
    tools=[create_slide],
    generate_content_config=genai_types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=300,
    ),
    instruction="""You are the slide operator for a keynote presentation about Google Cloud Next '25.

When the presenter requests a slide:
1. Extract the topic and key points from their request.
2. Call create_slide with the topic and key points.
3. Return the result including the slide_description so the presenter knows what's on the slide.

You are behind the scenes. You do not speak to the audience. You only produce slides.
Keep your responses structured and factual — just the slide data.""",
)
