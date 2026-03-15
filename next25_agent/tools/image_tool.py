"""Imagen slide generation + Gemini Pro vision analysis.

Flow:
1. Imagen 4.0 Fast generates a keynote slide image
2. Gemini 2.5 Pro (vision) analyzes the generated image
3. The analysis text is returned to Alex (short, fits in 32K context)
4. The actual image is stored in session state for the WebSocket handler
   to forward to the client — bypasses the model context entirely

Three models working together:
- Imagen creates the visual
- Gemini Pro sees and describes it
- Gemini Flash (Alex) speaks about it
"""

import base64
import logging
import os
import queue

from google import genai
from google.adk.tools import ToolContext
from google.genai import types
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


def _analyze_image(image_bytes: bytes, topic: str) -> str:
    """Use Gemini 2.5 Pro (vision) to analyze the generated slide.

    Returns a concise description of what's actually on the slide —
    text, diagrams, visual elements, layout. This is what Alex will
    narrate from, so it must be accurate and descriptive.
    """
    try:
        client = _get_client()
        analysis_prompt = (
            f"You are a slide analyst for a keynote presenter. "
            f"Describe this presentation slide in 2-3 sentences. "
            f"Focus on: the title text, key visual elements, "
            f"diagrams or icons shown, and the overall message. "
            f"The topic is '{topic}'. Be specific about what you "
            f"actually see — colors, layout, text content. "
            f"Keep it under 60 words."
        )
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type="image/png",
                        ),
                        types.Part(text=analysis_prompt),
                    ],
                    role="user",
                )
            ],
        )
        analysis = response.text.strip()
        logger.info("Slide analysis for '%s': %s", topic, analysis[:100])
        return analysis
    except Exception as e:
        logger.error("Slide analysis failed: %s", e)
        return f"A presentation slide about {topic}."


def generate_slide(topic: str, key_points: str, tool_context: ToolContext) -> dict:
    """Generate a presentation slide and analyze what's on it.

    Creates a professional keynote slide using Imagen, then uses Gemini Pro
    vision to analyze the generated image. The actual image is sent to the
    audience's screen automatically. You receive a description of what the
    slide shows so you can narrate about it naturally.

    Args:
        topic: The slide title. Example: "Agent Development Kit (ADK)"
        key_points: 2-3 key concepts to visualize, comma-separated.
            Example: "Open source framework, Model agnostic, Build agents in minutes"

    Returns:
        A description of what's actually shown on the slide. Use this to
        narrate — describe what the audience is seeing on screen.
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

        # Step 2: Gemini Pro vision analyzes the generated slide
        slide_description = _analyze_image(image_bytes, topic)

        # Push image to the global slide queue for the WebSocket handler
        # The model NEVER sees the base64 — only the text description
        slide_queue.put({
            "image": image_b64,
            "topic": topic,
        })

        return {
            "status": "success",
            "topic": topic,
            "what_the_slide_shows": slide_description,
        }

    except Exception as e:
        logger.error("Slide generation failed: %s", e)
        return {
            "status": "error",
            "topic": topic,
            "what_the_slide_shows": f"The slide for '{topic}' is being prepared. Continue presenting.",
        }
