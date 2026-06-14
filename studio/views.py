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
    auth_url, state = get_auth_url()
    request.session["oauth_state"] = state
    from django.shortcuts import redirect
    return redirect(auth_url)


def drive_callback(request):
    """Receive OAuth code, exchange for tokens, save in session."""
    from django.shortcuts import redirect
    from .drive_service import exchange_code
    code  = request.GET.get("code")
    error = request.GET.get("error")
    if error or not code:
        print(f"[Drive OAuth] error={error} params={dict(request.GET)}")
        return redirect("/drive/?error=" + (error or "no_code"))
    try:
        tokens = exchange_code(code)
        request.session["drive_tokens"] = tokens
        print(f"[Drive OAuth] tokens received, token={tokens['token'][:20]}...")
    except Exception as e:
        print(f"[Drive OAuth] exchange failed: {e}")
        return redirect(f"/drive/?error={e}")
    return redirect("/drive/")


def drive_page(request):
    """Main Drive browser page."""
    tokens = request.session.get("drive_tokens")
    error  = request.GET.get("error")
    return render(request, "studio/drive.html", {
        "authenticated": bool(tokens),
        "error": error,
    })


# ─── Drive API endpoints ──────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def api_drive_upload(request):
    """POST /api/drive/upload/ — multipart file upload to Google Drive."""
    tokens = request.session.get("drive_tokens")
    if not tokens:
        return JsonResponse({"ok": False, "error": "غير مسجّل الدخول"}, status=401)
    from .drive_service import upload_file as drive_upload
    f         = request.FILES.get("file")
    folder_id = request.POST.get("folder_id") or None
    if not f:
        return JsonResponse({"ok": False, "error": "لم يتم إرسال ملف"}, status=400)
    try:
        result = drive_upload(
            access_token=tokens["token"],
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
    """GET /api/drive/files/?folder_id=<id> — list media files."""
    tokens = request.session.get("drive_tokens")
    if not tokens:
        return JsonResponse({"ok": False, "error": "غير مسجّل الدخول"}, status=401)
    from .drive_service import list_media_files
    folder_id = request.GET.get("folder_id") or None
    try:
        files = list_media_files(tokens["token"], folder_id=folder_id)
        return JsonResponse({"ok": True, "files": files})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def api_drive_folders(request):
    """GET /api/drive/folders/ — list Drive folders."""
    tokens = request.session.get("drive_tokens")
    if not tokens:
        return JsonResponse({"ok": False, "error": "غير مسجّل الدخول"}, status=401)
    from .drive_service import list_folders
    try:
        folders = list_folders(tokens["token"])
        return JsonResponse({"ok": True, "folders": folders})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_drive_logout(request):
    """POST /api/drive/logout/ — clear Drive session."""
    request.session.pop("drive_tokens", None)
    return JsonResponse({"ok": True})


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
