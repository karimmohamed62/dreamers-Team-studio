"""
Image resize service — smart center-crop to platform dimensions.
"""
import io
from PIL import Image, ImageOps

PLATFORM_SIZES = {
    "instagram_feed":  (1080, 1350),
    "instagram_reel":  (1080, 1920),
    "tiktok":          (1080, 1920),
    "facebook_reel":   (1080, 1920),
    "facebook_feed":   (1080, 1080),
    "youtube_short":   (1080, 1920),
    "youtube_long":    (1920, 1080),
    "twitter":         (1600,  900),
}

PLATFORM_LABELS = {
    "instagram_feed":  "Instagram Feed (4:5)",
    "instagram_reel":  "Instagram Reel (9:16)",
    "tiktok":          "TikTok (9:16)",
    "facebook_reel":   "Facebook Reel (9:16)",
    "facebook_feed":   "Facebook Feed (1:1)",
    "youtube_short":   "YouTube Short (9:16)",
    "youtube_long":    "YouTube (16:9)",
    "twitter":         "Twitter/X (16:9)",
}


def get_platform_info(platform):
    w, h = PLATFORM_SIZES.get(platform, (1080, 1080))
    from math import gcd
    g = gcd(w, h)
    return {
        "width":  w,
        "height": h,
        "ratio":  f"{w//g}:{h//g}",
        "label":  PLATFORM_LABELS.get(platform, platform),
    }


def resize_image(image_bytes, platform):
    """
    Smart center-crop + resize to platform dimensions.
    Returns JPEG bytes at 95% quality.
    Supports JPEG, PNG, WEBP input.
    """
    size = PLATFORM_SIZES.get(platform)
    if not size:
        raise ValueError(f"منصة غير معروفة: {platform}")

    img = Image.open(io.BytesIO(image_bytes))

    # Convert to RGB (handles RGBA/palette PNGs)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # ImageOps.fit = resize + center crop with no distortion
    img = ImageOps.fit(img, size, method=Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=95, optimize=True)
    return out.getvalue()


def resize_from_drive(access_token, file_id, platform):
    """Pull image from Drive, resize, return JPEG bytes."""
    from .drive_service import download_file
    raw = download_file(access_token, file_id)
    return resize_image(raw, platform)
