"""
الـ Views - Dreamers Studio
"""
import json
import base64
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from .gemini_service import generate_script, PLATFORM_SPECS
from .elevenlabs_service import (
    list_voices, generate_voiceover, text_to_speech,
    save_voice_settings, DEFAULT_SETTINGS
)


# ─── Script ───────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def api_generate_script(request):
    """POST /api/generate-script/"""
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON غير صالح"}, status=400)
    topic = (body.get("topic") or "").strip()
    if not topic:
        return JsonResponse({"ok": False, "error": "الموضوع مطلوب"}, status=400)
    try:
        script = generate_script(
            topic=topic,
            platform=body.get("platform", "instagram"),
            language=body.get("language", "ألمانية"),
            tone=body.get("tone", "حماسي ومغامر"),
            duration=int(body.get("duration", 30)),
        )
        return JsonResponse({"ok": True, "script": script})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ─── Voices ───────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def api_list_voices(request):
    """GET /api/voices/"""
    try:
        return JsonResponse({"ok": True, "voices": list_voices()})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_voice(request):
    """
    POST /api/generate-voice/
    {scenes, voice_id, settings: {stability, similarity_boost, style, speed}}
    """
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON غير صالح"}, status=400)

    scenes   = body.get("scenes", [])
    voice_id = (body.get("voice_id") or "").strip()
    vsettings = body.get("settings", {})

    if not scenes:
        return JsonResponse({"ok": False, "error": "المشاهد مطلوبة"}, status=400)
    if not voice_id:
        return JsonResponse({"ok": False, "error": "voice_id مطلوب"}, status=400)

    try:
        audio_bytes = generate_voiceover(scenes, voice_id, voice_settings=vsettings)
        return HttpResponse(
            audio_bytes,
            content_type="audio/mpeg",
            headers={"Content-Disposition": 'attachment; filename="voiceover.mp3"'},
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_full(request):
    """
    POST /api/generate-full/
    {topic, platform, language, tone, duration, voice_id, settings?}
    يرجّع السكريبت + الصوت كـ base64 في خطوة واحدة
    """
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON غير صالح"}, status=400)

    topic    = (body.get("topic") or "").strip()
    voice_id = (body.get("voice_id") or "").strip()

    if not topic:
        return JsonResponse({"ok": False, "error": "الموضوع مطلوب"}, status=400)
    if not voice_id:
        return JsonResponse({"ok": False, "error": "voice_id مطلوب"}, status=400)

    try:
        script = generate_script(
            topic=topic,
            platform=body.get("platform", "instagram"),
            language=body.get("language", "ألمانية"),
            tone=body.get("tone", "حماسي ومغامر"),
            duration=int(body.get("duration", 30)),
        )
        audio_bytes = generate_voiceover(
            script["scenes"],
            voice_id,
            voice_settings=body.get("settings", {}),
        )
        return JsonResponse({
            "ok": True,
            "script": script,
            "audio_b64": base64.b64encode(audio_bytes).decode("utf-8"),
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_save_voice_settings(request):
    """
    POST /api/voice-settings/
    {voice_id, stability, similarity_boost, style, speed}
    يحفظ الإعدادات على ElevenLabs
    """
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON غير صالح"}, status=400)

    voice_id = (body.get("voice_id") or "").strip()
    if not voice_id:
        return JsonResponse({"ok": False, "error": "voice_id مطلوب"}, status=400)

    try:
        save_voice_settings(
            voice_id=voice_id,
            stability=body.get("stability", DEFAULT_SETTINGS["stability"]),
            similarity_boost=body.get("similarity_boost", DEFAULT_SETTINGS["similarity_boost"]),
            style=body.get("style", DEFAULT_SETTINGS["style"]),
            speed=body.get("speed", DEFAULT_SETTINGS["speed"]),
        )
        return JsonResponse({"ok": True, "message": "تم حفظ الإعدادات"})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ─── Pages ────────────────────────────────────────────────────────────────────

def home(request):
    return render(request, "studio/home.html", {"platforms": PLATFORM_SPECS})


# ─── Google Drive OAuth ───────────────────────────────────────────────────────

def drive_login(request):
    """Redirect user to Google OAuth consent screen."""
    from .drive_service import get_auth_url
    from django.shortcuts import redirect
    source     = request.GET.get("source", "web")
    session_id = request.GET.get("session_id", "")
    # Encode both source and session_id in state: "mobile:SESSION_ID"
    state = f"{source}:{session_id}" if session_id else source
    auth_url = get_auth_url(source=state)
    return redirect(auth_url)


def drive_callback(request):
    """Receive OAuth code, exchange for tokens."""
    from django.shortcuts import redirect
    from django.core.cache import cache
    from django.http import HttpResponse
    from .drive_service import exchange_code
    code  = request.GET.get("code")
    error = request.GET.get("error")
    state = request.GET.get("state", "web")
    # Parse state: "mobile:SESSION_ID" or just "mobile" or "web"
    if ":" in state:
        source, session_id = state.split(":", 1)
    else:
        source, session_id = state, ""
    if error or not code:
        print(f"[Drive OAuth] error={error}")
        if source == "mobile":
            if session_id:
                cache.set(f"oauth_{session_id}", {"error": error or "no_code"}, 300)
            return HttpResponse("فشل تسجيل الدخول، ارجع للتطبيق وحاول مرة أخرى")
        return redirect("/drive/?error=" + (error or "no_code"))
    try:
        tokens = exchange_code(code)
        access_token  = tokens.get("token", "")
        refresh_token = tokens.get("refresh_token", "")
        request.session["drive_tokens"] = tokens
        request.session.modified = True
        print(f"[Drive OAuth] tokens received, access={access_token[:20]}...")
    except Exception as e:
        print(f"[Drive OAuth] exchange failed: {e}")
        if source == "mobile":
            if session_id:
                cache.set(f"oauth_{session_id}", {"error": str(e)[:80]}, 300)
            return HttpResponse(f"فشل تسجيل الدخول: {e}")
        return redirect(f"/drive/?error={e}")
    if source == "mobile":
        if session_id:
            # Store tokens in cache — Flutter app polls for them
            cache.set(f"oauth_{session_id}", {
                "access_token":  access_token,
                "refresh_token": refresh_token,
            }, 300)  # 5-minute TTL
        return HttpResponse(
            "<html><body style='font-family:sans-serif;text-align:center;margin-top:60px;direction:rtl'>"
            "<h2>✅ تم تسجيل الدخول بنجاح!</h2>"
            "<p>يمكنك العودة للتطبيق الآن</p>"
            "</body></html>"
        )
    return redirect("/drive/")


def api_auth_poll(request):
    """GET /api/auth/poll/?session_id=XXX — Flutter polls for OAuth tokens."""
    from django.core.cache import cache
    session_id = request.GET.get("session_id", "")
    if not session_id:
        return JsonResponse({"ready": False})
    data = cache.get(f"oauth_{session_id}")
    if data and "access_token" in data:
        cache.delete(f"oauth_{session_id}")
        return JsonResponse({"ready": True, **data})
    if data and "error" in data:
        cache.delete(f"oauth_{session_id}")
        return JsonResponse({"ready": False, "error": data["error"]})
    return JsonResponse({"ready": False})


def drive_page(request):
    """Main Drive browser page."""
    tokens = request.session.get("drive_tokens")
    error  = request.GET.get("error")
    return render(request, "studio/drive.html", {
        "authenticated": bool(tokens),
        "error": error,
    })


# ─── Drive API endpoints ──────────────────────────────────────────────────────

def _get_drive_token(request):
    """Helper: get access token from X-Google-Token header or session."""
    return (
        request.headers.get("X-Google-Token") or
        request.POST.get("access_token") or
        request.GET.get("access_token") or
        (request.session.get("drive_tokens") or {}).get("token")
    )


@csrf_exempt
@require_http_methods(["POST"])
def api_drive_upload(request):
    """POST /api/drive/upload/ — multipart file upload to Google Drive."""
    access_token = _get_drive_token(request)
    if not access_token:
        return JsonResponse({"ok": False, "error": "غير مسجّل الدخول"}, status=401)
    from .drive_service import upload_file as drive_upload
    f         = request.FILES.get("file")
    folder_id = request.POST.get("folder_id") or None
    if not f:
        return JsonResponse({"ok": False, "error": "لم يتم إرسال ملف"}, status=400)
    try:
        result = drive_upload(
            access_token=access_token,
            file_bytes=f.read(),
            filename=f.name,
            mime_type=f.content_type,
            folder_id=folder_id,
        )
        return JsonResponse({"ok": True, "file": result})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def api_drive_files(request):
    """GET /api/drive/files/ — list media files."""
    access_token = _get_drive_token(request)
    if not access_token:
        return JsonResponse({"ok": False, "error": "غير مسجّل الدخول"}, status=401)
    from .drive_service import list_media_files
    folder_id = request.GET.get("folder_id") or None
    try:
        files = list_media_files(access_token, folder_id=folder_id)
        return JsonResponse({"ok": True, "files": files})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def api_drive_folders(request):
    """GET /api/drive/folders/ — list Drive folders."""
    access_token = _get_drive_token(request)
    if not access_token:
        return JsonResponse({"ok": False, "error": "غير مسجّل الدخول"}, status=401)
    from .drive_service import list_folders
    try:
        folders = list_folders(access_token)
        return JsonResponse({"ok": True, "folders": folders})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_drive_logout(request):
    """POST /api/drive/logout/ — clear Drive session."""
    request.session.pop("drive_tokens", None)
    return JsonResponse({"ok": True})


def api_drive_status(request):
    """GET /api/drive/status/ — check if Drive is connected."""
    access_token = _get_drive_token(request)
    return JsonResponse({"logged_in": bool(access_token)})


@csrf_exempt
@require_http_methods(["POST"])
def api_edit_image(request):
    """
    POST /api/edit-image/
    - multipart: file (image) + instruction
    - JSON:      drive_file_id + instruction
    Returns edited JPEG image.
    """
    tokens = request.session.get("drive_tokens")

    if request.FILES.get("file"):
        instruction  = request.POST.get("instruction", "").strip()
        image_bytes  = request.FILES["file"].read()
    else:
        try:
            body = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON غير صالح"}, status=400)
        instruction   = (body.get("instruction") or "").strip()
        drive_file_id = (body.get("drive_file_id") or "").strip()
        if not drive_file_id:
            return JsonResponse({"ok": False, "error": "file أو drive_file_id مطلوب"}, status=400)
        if not tokens:
            return JsonResponse({"ok": False, "error": "غير مسجّل الدخول على Drive"}, status=401)
        from .drive_service import download_file as drive_dl
        try:
            image_bytes = drive_dl(tokens["token"], drive_file_id)
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"Drive download: {e}"}, status=500)

    if not instruction:
        return JsonResponse({"ok": False, "error": "التعليمات مطلوبة"}, status=400)

    from .image_service import edit_image
    try:
        result_bytes = edit_image(image_bytes, instruction)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    return HttpResponse(
        result_bytes,
        content_type="image/jpeg",
        headers={"Content-Disposition": 'attachment; filename="edited.jpg"'},
    )


@csrf_exempt
@require_http_methods(["POST"])
def api_resize_image(request):
    """
    POST /api/resize-image/
    - multipart: file (image) + platform
    - JSON:      drive_file_id + platform
    Returns JPEG image.
    """
    tokens = request.session.get("drive_tokens")

    # multipart upload
    if request.FILES.get("file"):
        platform = request.POST.get("platform", "instagram_feed")
        image_bytes = request.FILES["file"].read()
        source = "upload"
    else:
        try:
            body = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON غير صالح"}, status=400)
        platform      = body.get("platform", "instagram_feed")
        drive_file_id = (body.get("drive_file_id") or "").strip()
        if not drive_file_id:
            return JsonResponse({"ok": False, "error": "file أو drive_file_id مطلوب"}, status=400)
        if not tokens:
            return JsonResponse({"ok": False, "error": "غير مسجّل الدخول على Drive"}, status=401)
        from .drive_service import download_file as drive_dl
        try:
            image_bytes = drive_dl(tokens["token"], drive_file_id)
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"Drive download: {e}"}, status=500)
        source = "drive"

    from .resize_service import resize_image, get_platform_info
    try:
        result_bytes = resize_image(image_bytes, platform)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    info = get_platform_info(platform)
    return HttpResponse(
        result_bytes,
        content_type="image/jpeg",
        headers={
            "Content-Disposition": f'attachment; filename="resized_{platform}.jpg"',
            "X-Platform":  platform,
            "X-Width":     str(info["width"]),
            "X-Height":    str(info["height"]),
        },
    )


@require_http_methods(["GET"])
def api_drive_download(request, file_id):
    """GET /api/drive/download/<file_id>/ — stream file from Drive."""
    tokens = request.session.get("drive_tokens")
    if not tokens:
        return JsonResponse({"ok": False, "error": "غير مسجّل الدخول"}, status=401)
    from .drive_service import download_file as drive_download
    try:
        data = drive_download(tokens["token"], file_id)
        return HttpResponse(data, content_type="application/octet-stream",
                            headers={"Content-Disposition": f'attachment; filename="{file_id}"'})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ─── Export ───────────────────────────────────────────────────────────────────

def export_page(request):
    """صفحة Export المتكاملة."""
    return render(request, "studio/export.html", {"platforms": PLATFORM_SPECS})


@csrf_exempt
@require_http_methods(["POST"])
def api_export(request):
    """
    POST /api/export/
    multipart/form-data:
      image (file, optional)  |  drive_file_id (optional)
      topic, platform, language, tone, duration
      voice_id (optional)
      platforms[] — list of target platforms
      ai_instruction (optional)
    Returns JSON with folder_link, files, script, caption.
    """
    tokens = request.session.get("drive_tokens")

    # ── 0. Early Drive check ──────────────────────────────────────────────────
    if not tokens:
        return JsonResponse({"ok": False, "error": "سجّل دخولك على Drive أولاً من صفحة /drive/"}, status=401)

    # ── 1. Get image ──────────────────────────────────────────────────────────
    image_bytes = None
    if request.FILES.get("image"):
        image_bytes = request.FILES["image"].read()
    elif request.POST.get("drive_file_id") and tokens:
        from .drive_service import download_file as drive_dl
        try:
            image_bytes = drive_dl(tokens["token"], request.POST["drive_file_id"])
        except Exception as e:
            return JsonResponse({"ok": False, "step": "image", "error": str(e)}, status=500)

    if not image_bytes:
        return JsonResponse({"ok": False, "error": "صورة مطلوبة (upload أو drive_file_id)"}, status=400)

    # ── 2. AI edit (optional) ─────────────────────────────────────────────────
    ai_instruction = (request.POST.get("ai_instruction") or "").strip()
    ai_warning     = None
    if ai_instruction:
        from .image_service import edit_image
        try:
            image_bytes = edit_image(image_bytes, ai_instruction)
        except Exception as e:
            ai_warning = f"Nano Banana فشل ({e}) — متابع بالصورة الأصلية"

    # ── 3. Generate script ────────────────────────────────────────────────────
    topic    = (request.POST.get("topic") or "").strip()
    if not topic:
        return JsonResponse({"ok": False, "error": "الموضوع مطلوب"}, status=400)
    try:
        script = generate_script(
            topic=topic,
            platform=request.POST.get("platform", "instagram"),
            language=request.POST.get("language", "ألمانية"),
            tone=request.POST.get("tone", "حماسي ومغامر"),
            duration=int(request.POST.get("duration", 30)),
        )
    except Exception as e:
        return JsonResponse({"ok": False, "step": "script", "error": str(e)}, status=500)

    # ── 4. Generate voice (optional) ──────────────────────────────────────────
    audio_bytes   = None
    voice_warning = None
    voice_id      = (request.POST.get("voice_id") or "").strip()
    if voice_id:
        try:
            audio_bytes = generate_voiceover(script["scenes"], voice_id)
        except Exception as e:
            voice_warning = f"ElevenLabs فشل ({e}) — بدون صوت"

    # ── 5. Export to Drive ────────────────────────────────────────────────────
    import datetime
    slug = topic[:20].replace(" ", "_")
    folder_name = f"Dreamers_{datetime.date.today().strftime('%Y%m%d')}_{slug}"

    raw_platforms = request.POST.getlist("platforms[]") or request.POST.getlist("platforms")
    if not raw_platforms:
        raw_platforms = ["instagram_reel", "instagram_feed", "tiktok"]

    from .export_service import create_export_package
    try:
        export = create_export_package(
            image_bytes=image_bytes,
            script=script,
            audio_bytes=audio_bytes,
            platforms=raw_platforms,
            access_token=tokens["token"],
            folder_name=folder_name,
        )
    except Exception as e:
        return JsonResponse({"ok": False, "step": "drive", "error": str(e)}, status=500)

    warnings = [w for w in [ai_warning, voice_warning] if w]
    return JsonResponse({
        "ok":          True,
        "folder_link": export["folder_link"],
        "folder_name": folder_name,
        "files":       export["files"],
        "script":      script,
        "caption":     script.get("caption", ""),
        "hashtags":    script.get("hashtags", []),
        "warnings":    warnings,
    })


# ─── Full Pipeline ────────────────────────────────────────────────────────────

def pipeline_page(request):
    """صفحة الـ Pipeline المتكاملة."""
    from .elevenlabs_service import list_voices
    voices = []
    try:
        voices = list_voices()
    except Exception:
        pass
    return render(request, "studio/pipeline.html", {"voices": voices})


@csrf_exempt
@require_http_methods(["POST"])
def api_create_full_content(request):
    """
    POST /api/create-full-content/
    multipart/form-data:
      image (file) | drive_file_id
      topic, platform, language, tone, duration
      voice_id (optional)
      ai_image_instruction (optional)
      generate_video (true/false)
      platforms[] (list for resize)
    """
    tokens = request.session.get("drive_tokens")

    # ── صورة ─────────────────────────────────────────────────────────────────
    image_bytes = None
    if request.FILES.get("image"):
        image_bytes = request.FILES["image"].read()
    elif request.POST.get("drive_file_id") and tokens:
        from .drive_service import download_file as drive_dl
        try:
            image_bytes = drive_dl(tokens["token"], request.POST["drive_file_id"])
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"Drive download فشل: {e}"}, status=500)

    if not image_bytes:
        return JsonResponse({"ok": False, "error": "صورة مطلوبة"}, status=400)

    topic = (request.POST.get("topic") or "").strip()
    if not topic:
        return JsonResponse({"ok": False, "error": "الموضوع مطلوب"}, status=400)

    # Flutter sends comma-separated, web sends platforms[] array
    _plat_raw = request.POST.get("platforms", "")
    if _plat_raw:
        platforms_resize = [p.strip() for p in _plat_raw.split(",") if p.strip()]
    else:
        platforms_resize = (
            request.POST.getlist("platforms[]") or
            ["instagram_reel", "instagram_feed", "tiktok"]
        )

    gen_video_raw = (request.POST.get("generate_video") or "").lower()
    gen_video = gen_video_raw in ("true", "1", "yes")

    from .pipeline_service import create_full_content
    try:
        result = create_full_content(
            image_bytes=image_bytes,
            topic=topic,
            platform=request.POST.get("platform", "instagram_reel"),
            language=request.POST.get("language", "العربية"),
            tone=request.POST.get("tone", "حماسي ومغامر"),
            duration=int(request.POST.get("duration", 30)),
            voice_id=request.POST.get("voice_id") or None,
            ai_image_instruction=request.POST.get("ai_image_instruction") or None,
            generate_video=gen_video,
            access_token=tokens["token"] if tokens else None,
            folder_name=request.POST.get("folder_name") or None,
            platforms_resize=platforms_resize,
        )
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ─── Video (Veo) ──────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def api_generate_video(request):
    """
    POST /api/generate-video/
    JSON: {prompt, aspect_ratio, drive_file_id (اختياري)}
    Returns: MP4 video bytes
    """
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON غير صالح"}, status=400)

    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return JsonResponse({"ok": False, "error": "البرومت مطلوب"}, status=400)

    aspect_ratio  = body.get("aspect_ratio", "9:16")
    drive_file_id = (body.get("drive_file_id") or "").strip()

    image_bytes = None
    if drive_file_id:
        tokens = request.session.get("drive_tokens")
        if tokens:
            from .drive_service import download_file as drive_dl
            try:
                image_bytes = drive_dl(tokens["token"], drive_file_id)
            except Exception:
                pass

    from .video_service import generate_video
    try:
        video_bytes = generate_video(
            prompt=prompt,
            image_bytes=image_bytes,
            aspect_ratio=aspect_ratio,
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    return HttpResponse(
        video_bytes,
        content_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="generated_video.mp4"'},
    )


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_video_from_script(request):
    """
    POST /api/generate-video-from-script/
    JSON: {scenes: [...], platform: "instagram_reel"}
    Returns: MP4 video bytes
    """
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON غير صالح"}, status=400)

    scenes   = body.get("scenes", [])
    platform = body.get("platform", "instagram_reel")

    if not scenes:
        return JsonResponse({"ok": False, "error": "المشاهد مطلوبة"}, status=400)

    from .video_service import generate_video_from_script
    try:
        video_bytes = generate_video_from_script(scenes, platform)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    return HttpResponse(
        video_bytes,
        content_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="script_video.mp4"'},
    )


def voice_settings_page(request):
    """صفحة التحكم في إعدادات الأصوات"""
    voices = []
    error  = None
    try:
        voices = list_voices()
    except Exception as e:
        error = str(e)

    return render(request, "studio/voice_settings.html", {
        "voices": voices,
        "error":  error,
        "default_settings": DEFAULT_SETTINGS,
    })
