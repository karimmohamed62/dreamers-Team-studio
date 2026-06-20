"""
Pipeline service - يجمع كل الخطوات في pipeline واحد متكامل.
كل خطوة في try/except منفصلة - فشل خطوة ما يوقفش الباقي.
الملفات بترجع كـ base64 مباشرة (بدون Drive).
"""
import base64
import io

from .gemini_service import generate_script
from .elevenlabs_service import generate_voiceover
from .resize_service import resize_image, PLATFORM_SIZES


def _small_preview(image_bytes, max_size=400):
    """يرجع base64 صغير للعرض السريع."""
    try:
        from PIL import Image as PILImage, ImageOps
        img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        img = ImageOps.contain(img, (max_size, max_size))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return None


def create_full_content(
    image_bytes,
    topic,
    platform,
    language,
    tone,
    duration,
    voice_id=None,
    ai_image_instruction=None,
    generate_video=False,
    platforms_resize=None,
):
    """
    Pipeline كامل:
    1. تعديل الصورة بـ Nano Banana (اختياري)
    2. توليد السكريبت بـ Gemini
    3. توليد الصوت بـ ElevenLabs (اختياري)
    4. توليد الفيديو بـ Veo (اختياري)
    5. Resize الصورة لكل المنصات
    يرجع كل الملفات كـ base64 - بدون Drive.
    """
    steps_log = []
    result = {
        "ok": True,
        "steps_log": steps_log,
        "script": None,
        "edited_image_preview": None,
        "edited_image_b64": None,
        "audio_b64": None,
        "video_generated": False,
        "files": [],
        "errors": [],
    }

    working_image = image_bytes
    edited_image  = None

    if platforms_resize is None:
        platforms_resize = ["instagram_reel", "instagram_feed", "tiktok"]

    # ── 1. تعديل الصورة بـ Nano Banana ────────────────────────────────────────
    if ai_image_instruction and ai_image_instruction.strip():
        steps_log.append({"status": "running", "msg": "⏳ بيعدّل الصورة بـ AI..."})
        try:
            from .image_service import edit_image
            edited_image = edit_image(image_bytes, ai_image_instruction.strip())
            working_image = edited_image
            result["edited_image_preview"] = _small_preview(edited_image)
            result["edited_image_b64"] = base64.b64encode(edited_image).decode("utf-8")
            steps_log[-1] = {"status": "done", "msg": "✅ تم تعديل الصورة بـ AI"}
        except Exception as e:
            err = f"❌ تعديل الصورة فشل: {e}"
            steps_log[-1] = {"status": "error", "msg": err}
            result["errors"].append(err)

    # ── 2. توليد السكريبت ──────────────────────────────────────────────────────
    steps_log.append({"status": "running", "msg": "⏳ بيولّد السكريبت..."})
    try:
        script = generate_script(
            topic=topic,
            platform=platform,
            language=language,
            tone=tone,
            duration=int(duration),
        )
        result["script"] = script
        steps_log[-1] = {"status": "done", "msg": "✅ تم توليد السكريبت"}
    except Exception as e:
        err = f"❌ توليد السكريبت فشل: {e}"
        steps_log[-1] = {"status": "error", "msg": err}
        result["errors"].append(err)
        result["ok"] = False
        return result

    # ── 3. توليد الصوت ─────────────────────────────────────────────────────────
    if voice_id and voice_id.strip():
        steps_log.append({"status": "running", "msg": "⏳ بيولّد الصوت..."})
        try:
            audio_bytes = generate_voiceover(script["scenes"], voice_id.strip())
            result["audio_b64"] = base64.b64encode(audio_bytes).decode("utf-8")
            steps_log[-1] = {"status": "done", "msg": "✅ تم توليد الصوت"}
        except Exception as e:
            err = f"❌ توليد الصوت فشل: {e}"
            steps_log[-1] = {"status": "error", "msg": err}
            result["errors"].append(err)

    # ── 4. توليد الفيديو بـ Veo ────────────────────────────────────────────────
    if generate_video:
        steps_log.append({"status": "running", "msg": "⏳ بيولّد الفيديو (1-3 دقايق)..."})
        try:
            from .video_service import generate_video as veo_generate
            aspect_map = {
                "instagram_reel": "9:16", "tiktok": "9:16",
                "facebook_reel": "9:16", "youtube_short": "9:16",
                "youtube_long": "16:9", "twitter": "16:9",
            }
            aspect_ratio = aspect_map.get(platform, "9:16")
            visuals = " then ".join(
                s.get("visual", "") for s in script.get("scenes", [])[:3]
            )
            prompt = (
                f"Cinematic travel video for Red Sea Egypt tourism. "
                f"{visuals}. "
                f"High quality, vibrant colors, professional cinematography."
            )
            veo_generate(
                prompt=prompt,
                image_bytes=working_image,
                aspect_ratio=aspect_ratio,
            )
            result["video_generated"] = True
            steps_log[-1] = {"status": "done", "msg": "✅ تم توليد الفيديو"}
        except Exception as e:
            err = f"❌ توليد الفيديو فشل: {e}"
            steps_log[-1] = {"status": "error", "msg": err}
            result["errors"].append(err)

    # ── 5. Resize الصور للمنصات ────────────────────────────────────────────────
    steps_log.append({"status": "running", "msg": "⏳ جاري تحجيم الصور للمنصات..."})
    resized_files = []
    for plt in platforms_resize:
        if plt not in PLATFORM_SIZES:
            continue
        w, h = PLATFORM_SIZES[plt]
        fname = f"{plt}_{w}x{h}.jpg"
        try:
            resized = resize_image(working_image, plt)
            resized_files.append({
                "name": fname,
                "data": base64.b64encode(resized).decode("utf-8"),
                "platform": plt,
            })
        except Exception as e:
            resized_files.append({"name": fname, "error": str(e)})

    result["files"] = resized_files
    steps_log[-1] = {
        "status": "done",
        "msg": f"✅ تم تحجيم الصور ({len(resized_files)} نسخ)",
    }

    return result
