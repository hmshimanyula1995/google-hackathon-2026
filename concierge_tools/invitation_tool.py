"""Invitation tool — generates a premium Imagen invitation card and sends it via email.

Generates the card with Imagen 4.0 Fast, returns base64 for the UI,
and sends the same image as a beautiful HTML email via Gmail SMTP.
"""

import base64
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

from google import genai
from google.genai.types import GenerateImagesConfig

logger = logging.getLogger(__name__)

_genai_client: genai.Client | None = None
_gmail_password: str | None = None


def _get_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(
            vertexai=os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true",
            project=os.environ.get("GOOGLE_CLOUD_PROJECT", "next-live-agent"),
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
    return _genai_client


def _get_gmail_password() -> str | None:
    """Get Gmail app password from env or Secret Manager."""
    global _gmail_password
    if _gmail_password:
        return _gmail_password

    _gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not _gmail_password:
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            project = os.environ.get("GOOGLE_CLOUD_PROJECT", "next-live-agent")
            name = f"projects/{project}/secrets/GMAIL_APP_PASSWORD/versions/latest"
            response = client.access_secret_version(request={"name": name})
            _gmail_password = response.payload.data.decode("UTF-8")
            logger.info("[GMAIL] App password loaded from Secret Manager")
        except Exception as e:
            logger.warning("[GMAIL] Could not load password: %s", e)

    return _gmail_password


GMAIL_SENDER = "hudsonshimanyula@gmail.com"


def _send_email_smtp(to_email: str, subject: str, html: str, image_bytes: bytes | None = None) -> bool:
    """Send an HTML email via Gmail SMTP. Attaches invitation image if provided."""
    password = _get_gmail_password()
    if not password or password == "PLACEHOLDER":
        logger.warning("[GMAIL] No app password configured — skipping email")
        return False

    try:
        msg = MIMEMultipart("related")
        msg["From"] = f"Next Live <{GMAIL_SENDER}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # HTML body
        html_part = MIMEText(html, "html")
        msg.attach(html_part)

        # Attach invitation image inline (referenced as cid:invitation-card)
        if image_bytes:
            img_part = MIMEImage(image_bytes, _subtype="png")
            img_part.add_header("Content-ID", "<invitation-card>")
            img_part.add_header("Content-Disposition", "inline", filename="invitation.png")
            msg.attach(img_part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, password)
            server.sendmail(GMAIL_SENDER, to_email, msg.as_string())

        logger.info("[GMAIL] Email sent to %s", to_email)
        return True

    except Exception as e:
        logger.error("[GMAIL] Failed to send to %s: %s", to_email, e, exc_info=True)
        return False


def _send_invitation_email(email: str, image_b64: str) -> bool:
    """Send the invitation card as a beautiful HTML email."""
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f8f9fa;font-family:'Google Sans','Segoe UI',Roboto,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;padding:40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
                    <tr>
                        <td style="background:linear-gradient(135deg,#4285F4 0%,#1a73e8 100%);padding:24px 32px;text-align:center;">
                            <span style="color:#ffffff;font-size:20px;font-weight:600;letter-spacing:0.5px;">Next Live</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:24px 24px 0;">
                            <img src="cid:invitation-card" alt="Google Cloud Next 2026 Invitation" style="width:100%;border-radius:12px;display:block;" />
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:28px 32px;">
                            <h1 style="margin:0 0 8px;font-size:26px;color:#202124;font-weight:700;">You're Invited!</h1>
                            <p style="margin:0 0 20px;font-size:15px;color:#5f6368;line-height:1.7;">
                                You've been personally invited to <strong style="color:#202124;">Google Cloud Next 2026</strong> — the biggest Google Cloud event of the year.
                            </p>
                            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;border-radius:12px;padding:20px;margin-bottom:24px;">
                                <tr><td style="padding:8px 20px;">
                                    <p style="margin:0;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#9aa0a6;font-weight:600;">When</p>
                                    <p style="margin:4px 0 0;font-size:15px;color:#202124;font-weight:500;">April 22-24, 2026</p>
                                </td></tr>
                                <tr><td style="padding:8px 20px;">
                                    <p style="margin:0;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#9aa0a6;font-weight:600;">Where</p>
                                    <p style="margin:4px 0 0;font-size:15px;color:#202124;font-weight:500;">Las Vegas Convention Center, Las Vegas NV</p>
                                </td></tr>
                                <tr><td style="padding:8px 20px;">
                                    <p style="margin:0;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#9aa0a6;font-weight:600;">Experience</p>
                                    <p style="margin:4px 0 0;font-size:15px;color:#202124;font-weight:500;">700+ sessions &middot; 231 announcements &middot; AI Agent Revolution</p>
                                </td></tr>
                            </table>
                            <p style="margin:0 0 24px;font-size:14px;color:#5f6368;line-height:1.7;">
                                Your AI travel concierge <strong>Maya</strong> is ready to help you book flights and hotels. Then join <strong>Alex</strong> for a live AI-powered keynote.
                            </p>
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr><td align="center">
                                    <a href="https://next-live-agent-338756532561.us-central1.run.app"
                                       style="display:inline-block;padding:14px 40px;background:#4285F4;color:#ffffff;text-decoration:none;border-radius:28px;font-size:16px;font-weight:600;box-shadow:0 2px 8px rgba(66,133,244,0.3);">
                                        Start Your Journey
                                    </a>
                                </td></tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:20px 32px;border-top:1px solid #e8eaed;text-align:center;">
                            <p style="margin:0;font-size:11px;color:#9aa0a6;">
                                Built with Google ADK &middot; Gemini Live API &middot; Firestore &middot; Imagen &middot; Cloud Run
                            </p>
                            <p style="margin:6px 0 0;font-size:11px;color:#9aa0a6;">
                                This invitation was generated by an AI agent using Imagen 4.0
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    image_bytes = base64.b64decode(image_b64)
    return _send_email_smtp(
        to_email=email,
        subject="You're Invited to Google Cloud Next 2026!",
        html=html,
        image_bytes=image_bytes,
    )


def generate_invitation(email: str) -> dict:
    """Generate a premium invitation card and send it via email.

    Args:
        email: The attendee's email address.

    Returns:
        Dictionary with status, base64 image string, email, and email_sent flag.
    """
    try:
        prompt = (
            "A beautiful premium invitation card for Google Cloud Next 2026, "
            "April 22-24, Las Vegas Convention Center. "
            "Google Cloud branding colors (#4285F4 blue, #34A853 green, #FBBC04 yellow, #EA4335 red), "
            "modern geometric design with abstract AI and cloud shapes, "
            "conference badge style, elegant gold accents, "
            "text reads 'You are Invited' and 'Google Cloud Next 2026'. "
            "16:9 aspect ratio. No photographs of people."
        )

        logger.info("[INVITATION] Generating card for: %s", email)

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

        logger.info("[INVITATION] Image generated: %d bytes", len(image_bytes))

        email_sent = _send_invitation_email(email, image_b64)

        return {
            "status": "success",
            "image": image_b64,
            "email": email,
            "email_sent": email_sent,
        }

    except Exception as e:
        logger.error("[INVITATION] Generation failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "image": "",
            "email": email,
            "email_sent": False,
            "message": f"Failed to generate invitation: {str(e)}",
        }
