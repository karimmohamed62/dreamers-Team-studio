from google import genai
from google.genai import types
from django.conf import settings
import time

_client = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def generate_video(prompt, image_bytes=None, aspect_ratio="9:16", duration_seconds=8):
    """
    يولّد فيديو من نص (وصورة اختياري) باستخدام Veo.
    يرجع: video bytes (MP4)
    """
    client = get_client()

    config = types.GenerateVideosConfig(
        aspect_ratio=aspect_ratio,
    )

    kwargs = {
        "model": "veo-3.0-generate-preview",
        "prompt": prompt,
        "config": config,
    }

    if image_bytes:
        kwargs["image"] = types.Image(
            image_bytes=image_bytes,
            mime_type="image/jpeg",
        )

    operation = client.models.generate_videos(**kwargs)

    max_wait = 300
    waited = 0
    while not operation.done and waited < max_wait:
        time.sleep(10)
        waited += 10
        operation = client.operations.get(operation)

    if not operation.done:
        raise TimeoutError("الفيديو لسه بيتولد - جرب تاني بعد شوية")

    video = operation.response.generated_videos[0].video
    video_bytes = client.files.download(file=video)

    if isinstance(video_bytes, (bytes, bytearray)):
        return bytes(video_bytes)

    # بعض إصدارات SDK بترجع iterator
    chunks = []
    for chunk in video_bytes:
        chunks.append(chunk if isinstance(chunk, (bytes, bytearray)) else chunk.data)
    return b"".join(chunks)


def generate_video_from_script(script_scenes, platform="instagram_reel"):
    """
    يولّد فيديو من مشاهد السكريبت.
    """
    aspect_map = {
        "instagram_reel": "9:16",
        "tiktok":         "9:16",
        "facebook_reel":  "9:16",
        "youtube_short":  "9:16",
        "youtube_long":   "16:9",
    }
    aspect_ratio = aspect_map.get(platform, "9:16")

    visuals = " then ".join(
        s.get("visual", "") for s in script_scenes[:3]
    )
    prompt = (
        f"Cinematic travel video for Red Sea Egypt tourism. "
        f"{visuals}. "
        f"High quality, vibrant colors, professional cinematography."
    )

    return generate_video(prompt, aspect_ratio=aspect_ratio)
