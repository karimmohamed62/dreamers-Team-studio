"""
Pipeline service — script + voice + resize (multi-image support).
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
    images_bytes_list,
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
    images_bytes_list: list of image bytes (one or more images).
    Returns JSON-serializable dict with base64 files.
    Video generation is done separately via /api/generate-video/.
    """
    # Normalize to list for backward compatibility
    if isinstance(images_bytes_list, (bytes, bytearray)):
        images_bytes_list = [bytes(images_bytes_list)]

    steps_log = []
    result = {
        "ok": True,
        "steps_log": steps_log,
        "script": None,
        "edited_images": [],      # list of {preview, b64} — one per input image
        "edited_image_preview": None,  # backward compat (first image)
        "edited_image_b64": None,      # backward compat (first image)
        "audio_b64": None,
        "files": [],
        "errors": [],
    }

    working_images = list(images_bytes_list)

    if platforms_resize is None:
        platforms_resize = ["instagram_reel", "instagram_feed", "tiktok"]

    # ── 1. AI image edit (applied to each image) ──────────────────────────────
    if ai_image_instruction and ai_image_instruction.strip():
        n = len(images_bytes_list)
        steps_log.append({"status": "running", "msg": f"⏳ بيعدّل {n} صورة بـ AI..."})
        edited_images_out = []
        any_error = False
        for i, img_bytes in enumerate(images_bytes_list):
            try:
                from .image_service import edit_image
                edited = edit_image(img_bytes, ai_image_instruction.strip())
                working_images[i] = edited
                edited_images_out.append({
                    "preview": _small_preview(edited),
                    "b64": base64.b64encode(edited).decode("utf-8"),
                })
            except Exception as e:
                err = f"❌ تعديل الصورة {i + 1} فشل: {e}"
                edited_images_out.append({"error": err})
                result["errors"].append(err)
                any_error = True

        result["edited_images"] = edited_images_out
        # backward compat: expose first successful edit at top level
        for ei in edited_images_out:
            if "b64" in ei:
                result["edited_image_preview"] = ei.get("preview")
                result["edited_image_b64"] = ei.get("b64")
                break

        msg = f"✅ تم تعديل الصور ({n} صورة)"
        if any_error:
            msg = "⚠️ اكتمل التعديل مع بعض الأخطاء"
        steps_log[-1] = {"status": "done" if not any_error else "error", "msg": msg}

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

    # ── 4. Resize images (each image × each platform) ─────────────────────────
    n = len(working_images)
    steps_log.append({"status": "running", "msg": f"⏳ جاري تحجيم {n} صورة للمنصات..."})
    resized_files = []
    for i, img_bytes in enumerate(working_images):
        for plt in platforms_resize:
            if plt not in PLATFORM_SIZES:
                continue
            w, h = PLATFORM_SIZES[plt]
            fname = f"img{i + 1}_{plt}_{w}x{h}.jpg"
            try:
                resized = resize_image(img_bytes, plt)
                resized_files.append({
                    "name": fname,
                    "data": base64.b64encode(resized).decode("utf-8"),
                    "platform": plt,
                    "img_index": i,
                })
            except Exception as e:
                resized_files.append({"name": fname, "error": str(e), "img_index": i})

    result["files"] = resized_files
    total = len(resized_files)
    steps_log[-1] = {
        "status": "done",
        "msg": f"✅ تم تحجيم الصور ({total} نسخ من {n} صورة)",
    }

    return result
