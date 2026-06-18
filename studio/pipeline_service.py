"""
Pipeline service - يجمع كل الخطوات في pipeline واحد متكامل.
كل خطوة في try/except منفصلة - فشل خطوة ما يوقفش الباقي.
"""
import base64
import datetime
import io

from .gemini_service import generate_script
from .elevenlabs_service import generate_voiceover
from .resize_service import resize_image, PLATFORM_SIZES
from .drive_service import upload_file, _service


def _get_or_create_folder(svc, folder_name):
    q = (
        f"name='{folder_name}' "
        "and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    res = svc.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    f = svc.files().create(body=meta, fields="id").execute()
    return f["id"]


def _build_caption_txt(script):
    lines = [
        "=" * 50,
        "DREAMERS TEAM — CAPTION & HASHTAGS",
        "=" * 50, "",
        "HOOK:", script.get("hook", ""), "",
        "CAPTION:", script.get("caption", ""), "",
        "CTA:", script.get("cta", ""), "",
        "HASHTAGS:",
        " ".join(f"#{t}" for t in script.get("hashtags", [])), "",
        "=" * 50, "SCENES:", "=" * 50,
    ]
    for i, sc in enumerate(script.get("scenes", []), 1):
        lines.append(f"\n[{i}] {sc.get('time','')}")
        lines.append(f"  Visual:    {sc.get('visual','')}")
        lines.append(f"  Voiceover: {sc.get('voiceover','')}")
        if sc.get("text_overlay"):
            lines.append(f"  Overlay:   {sc.get('text_overlay','')}")
    return "\n".join(lines).encode("utf-8")


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
    access_token=None,
    folder_name=None,
    platforms_resize=None,
):
    """
    Pipeline كامل:
    1. تعديل الصورة بـ Nano Banana (اختياري)
    2. توليد السكريبت بـ Gemini
    3. توليد الصوت بـ ElevenLabs (اختياري)
    4. توليد الفيديو بـ Veo (اختياري)
    5. Resize الصورة لكل المنصات المطلوبة
    6. رفع كل حاجة على Drive

    يرجع dict بالنتائج والـ steps_log.
    """
    steps_log = []
    result = {
        "ok": True,
        "steps_log": steps_log,
        "script": None,
        "folder_link": None,
        "files": [],
        "edited_image_preview": None,
        "video_link": None,
        "errors": [],
    }

    working_image = image_bytes
    edited_image  = None

    if not folder_name:
        slug = topic[:20].replace(" ", "_")
        folder_name = f"Dreamers_{datetime.date.today().strftime('%Y%m%d')}_{slug}"

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
    audio_bytes = None
    if voice_id and voice_id.strip():
        steps_log.append({"status": "running", "msg": "⏳ بيولّد الصوت..."})
        try:
            audio_bytes = generate_voiceover(script["scenes"], voice_id.strip())
            steps_log[-1] = {"status": "done", "msg": "✅ تم توليد الصوت"}
        except Exception as e:
            err = f"❌ توليد الصوت فشل: {e}"
            steps_log[-1] = {"status": "error", "msg": err}
            result["errors"].append(err)

    # ── 4. توليد الفيديو بـ Veo ────────────────────────────────────────────────
    video_bytes = None
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
            video_bytes = veo_generate(
                prompt=prompt,
                image_bytes=working_image,
                aspect_ratio=aspect_ratio,
            )
            steps_log[-1] = {"status": "done", "msg": "✅ تم توليد الفيديو"}
        except Exception as e:
            err = f"❌ توليد الفيديو فشل: {e}"
            steps_log[-1] = {"status": "error", "msg": err}
            result["errors"].append(err)

    # ── 5 + 6. Resize + رفع على Drive ─────────────────────────────────────────
    if not access_token:
        steps_log.append({"status": "error", "msg": "⚠️ مش متصل بـ Drive - تم حفظ الملفات محلياً"})
        return result

    steps_log.append({"status": "running", "msg": "⏳ بيرفع على Drive..."})
    try:
        svc = _service(access_token)
        folder_id = _get_or_create_folder(svc, folder_name)
        folder_link = f"https://drive.google.com/drive/folders/{folder_id}"
        result["folder_link"] = folder_link
        uploaded = []

        # الصورة الأصلية
        try:
            r = upload_file(access_token, image_bytes, "original_image.jpg", "image/jpeg", folder_id)
            uploaded.append({"name": "original_image.jpg", "link": r["link"]})
        except Exception as e:
            uploaded.append({"name": "original_image.jpg", "link": "", "error": str(e)})

        # الصورة المعدّلة
        if edited_image:
            try:
                r = upload_file(access_token, edited_image, "edited_image.jpg", "image/jpeg", folder_id)
                uploaded.append({"name": "edited_image.jpg", "link": r["link"]})
            except Exception as e:
                uploaded.append({"name": "edited_image.jpg", "link": "", "error": str(e)})

        # Resize لكل منصة
        for plt in platforms_resize:
            if plt not in PLATFORM_SIZES:
                continue
            w, h = PLATFORM_SIZES[plt]
            fname = f"{plt}_{w}x{h}.jpg"
            try:
                resized = resize_image(working_image, plt)
                r = upload_file(access_token, resized, fname, "image/jpeg", folder_id)
                uploaded.append({"name": fname, "link": r["link"], "platform": plt})
            except Exception as e:
                uploaded.append({"name": fname, "link": "", "error": str(e)})

        # الفيديو
        if video_bytes:
            try:
                r = upload_file(access_token, video_bytes, "video.mp4", "video/mp4", folder_id)
                uploaded.append({"name": "video.mp4", "link": r["link"]})
                result["video_link"] = r["link"]
            except Exception as e:
                uploaded.append({"name": "video.mp4", "link": "", "error": str(e)})

        # الصوت
        if audio_bytes:
            try:
                r = upload_file(access_token, audio_bytes, "voiceover.mp3", "audio/mpeg", folder_id)
                uploaded.append({"name": "voiceover.mp3", "link": r["link"]})
            except Exception as e:
                uploaded.append({"name": "voiceover.mp3", "link": "", "error": str(e)})

        # الكابشن
        try:
            caption_txt = _build_caption_txt(script)
            r = upload_file(access_token, caption_txt, "caption.txt", "text/plain", folder_id)
            uploaded.append({"name": "caption.txt", "link": r["link"]})
        except Exception as e:
            uploaded.append({"name": "caption.txt", "link": "", "error": str(e)})

        result["files"] = uploaded
        steps_log[-1] = {"status": "done", "msg": f"✅ تم الرفع على Drive ({len(uploaded)} ملفات)"}

    except Exception as e:
        err = f"❌ Drive فشل: {e}"
        steps_log[-1] = {"status": "error", "msg": err}
        result["errors"].append(err)

    return result
