"""
Pipeline service — script + voice + resize.
Video generation is a separate step via /api/generate-video/.
"""
import base64
import io

from .gemini_service import generate_script
from .elevenlabs_service import generate_voiceover
from .resize_service import resize_image, PLATFORM_SIZES


def _small_preview(image_bytes, max_size=400):
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
    platforms_resize=None,
):
    """
    Pipeline: AI image edit (optional) → script → voice → resize.
    Returns JSON-serializable dict with base64 files.
    Video generation is done separately via /api/generate-video/.
    """
    steps_log = []
    result = {
        "ok": True,
        "steps_log": steps_log,
        "script": None,
        "edited_image_preview": None,
        "edited_image_b64": None,
        "audio_b64": None,
        "files": [],
        "errors": [],
    }

    working_image = image_bytes

    if platforms_resize is None:
        platforms_resize = ["instagram_reel", "instagram_feed", "tiktok"]

    # ── 1. AI image edit ──────────────────────────────────────────────────────
    if ai_image_instruction and ai_image_instruction.strip():
        steps_log.append({"status": "running", "msg": "⏳ بيعدّل الصورة بـ AI..."})
        try:
            from .image_service import edit_image
            edited = edit_image(image_bytes, ai_image_instruction.strip())
            working_image = edited
            result["edited_image_preview"] = _small_preview(edited)
            result["edited_image_b64"] = base64.b64encode(edited).decode("utf-8")
            steps_log[-1] = {"status": "done", "msg": "✅ تم تعديل الصورة بـ AI"}
        except Exception as e:
            err = f"❌ تعديل الصورة فشل: {e}"
            steps_log[-1] = {"status": "error", "msg": err}
            result["errors"].append(err)

    # ── 2. Generate script ────────────────────────────────────────────────────
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

    # ── 3. Generate voice ─────────────────────────────────────────────────────
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

    # ── 4. Resize images ──────────────────────────────────────────────────────
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
