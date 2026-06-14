"""
AI Image Editing — Gemini image generation API.
"""
import io
from google import genai
from google.genai import types
from django.conf import settings

MODEL = "gemini-2.5-flash-image"

_client = None


def get_client():
    global _client
    if _client is None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY مش موجود في ملف .env")
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def edit_image(image_bytes, instruction, output_format="JPEG"):
    """
    Edit an image using Gemini image generation.
    Returns edited image bytes (JPEG by default).
    Raises RuntimeError with Arabic message on failure.
    """
    client = get_client()

    # Detect mime type from bytes magic header
    mime_type = "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        mime_type = "image/png"
    elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        mime_type = "image/webp"

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            types.Part.from_text(text=instruction),
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    for part in response.parts:
        if part.inline_data and part.inline_data.data:
            raw = part.inline_data.data
            # Convert to requested format if needed
            if output_format.upper() == "JPEG" and part.inline_data.mime_type != "image/jpeg":
                from PIL import Image
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=95)
                return buf.getvalue()
            return raw

    raise RuntimeError("الموديل لم يرجع صورة — تأكد من الـ API key والكوتا")


def edit_image_from_drive(access_token, file_id, instruction):
    """Download image from Drive, edit it, return JPEG bytes."""
    from .drive_service import download_file
    raw = download_file(access_token, file_id)
    return edit_image(raw, instruction)
