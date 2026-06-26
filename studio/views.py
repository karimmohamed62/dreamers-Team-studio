"""
الـ Views - Dreamers Studio (Drive removed)
"""
import json
import base64
import datetime
import os
import threading
import uuid as _uuid_mod
from pathlib import Path
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.conf import settings
from .gemini_service import generate_script, PLATFORM_SPECS
from .elevenlabs_service import (
    list_voices, generate_voiceover, text_to_speech,
    save_voice_settings, DEFAULT_SETTINGS
)

# ── Video rate limiting + async jobs ──────────────────────────────────────────

_COUNTER_FILE = Path("/tmp/veo_daily_counter.json")
_JOBS_DIR     = Path("/tmp/veo_jobs")


def _get_today_video_count():
    today = str(datetime.date.today())
    try:
        data = json.loads(_COUNTER_FILE.read_text())
        if data.get("date") == today:
            return int(data.get("count", 0))
    except Exception:
        pass
    return 0


def _increment_video_count():
    today = str(datetime.date.today())
    count = _get_today_video_count() + 1
    try:
        _COUNTER_FILE.write_text(json.dumps({"date": today, "count": count}))
    except Exception:
        pass
    return count


def _check_video_allowed():
    """Returns (allowed: bool, error_msg: str | None)"""
    if not settings.ENABLE_VIDEO_GENERATION:
        return False, "توليد الفيديو معطّل مؤقتاً. تواصل مع المطور."
    count = _get_today_video_count()
    limit = settings.MAX_VIDEO_GENERATIONS_PER_DAY
    if count >= limit:
        return False, (
            f"تم الوصول للحد اليومي المسموح من توليد الفيديو ({limit}). "
            "جرّب بكرة أو زوّد الحد من الكود."
        )
    return True, None


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
    if not scenes:
        return JsonResponse({"ok": False, "error": "المشاهد مطلوبة"}, status=400)
    if not voice_id:
        return JsonResponse({"ok": False, "error": "voice_id مطلوب"}, status=400)

    try:
        audio_bytes = generate_voiceover(
            scenes, voice_id,
            voice_settings=body.get("settings", {}),
        )
        return HttpResponse(audio_bytes, content_type="audio/mpeg",
                            headers={"Content-Disposition": 'attachment; filename="voiceover.mp3"'})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_full(request):
    """POST /api/generate-full/ — script + voice in one call."""
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
    """POST /api/voice-settings/"""
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


def deploy_check(request):
    """Quick check to confirm current deployment version."""
    return HttpResponse("v20260626-hard-block-image-ai-and-video")


# ─── Image Edit & Resize ──────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def api_edit_image(request):
    """
    POST /api/edit-image/
    multipart: image (file) + instruction
    Returns edited JPEG image.
    """
    if not request.FILES.get("file") and not request.FILES.get("image"):
        return JsonResponse({"ok": False, "error": "image file مطلوب"}, status=400)

    f = request.FILES.get("file") or request.FILES.get("image")
    instruction = (request.POST.get("instruction") or "").strip()
    if not instruction:
        return JsonResponse({"ok": False, "error": "التعليمات مطلوبة"}, status=400)

    if not settings.ENABLE_IMAGE_AI_EDIT:
        return JsonResponse({
            "ok": False,
            "error": "تعديل الصور بـ AI معطّل مؤقتاً لحماية رصيد الـ API.",
        }, status=403)

    from .image_service import edit_image
    try:
        result_bytes = edit_image(f.read(), instruction)
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
    multipart: image (file) + platform
    Returns JPEG image.
    """
    if not request.FILES.get("file") and not request.FILES.get("image"):
        return JsonResponse({"ok": False, "error": "image file مطلوب"}, status=400)

    f        = request.FILES.get("file") or request.FILES.get("image")
    platform = request.POST.get("platform", "instagram_feed")

    from .resize_service import resize_image, get_platform_info
    try:
        result_bytes = resize_image(f.read(), platform)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    info = get_platform_info(platform)
    return HttpResponse(
        result_bytes,
        content_type="image/jpeg",
        headers={
            "Content-Disposition": f'attachment; filename="resized_{platform}.jpg"',
            "X-Platform": platform,
            "X-Width":    str(info["width"]),
            "X-Height":   str(info["height"]),
        },
    )


# ─── Export (بدون Drive — يرجع خطأ واضح) ────────────────────────────────────

def export_page(request):
    return render(request, "studio/export.html", {"platforms": PLATFORM_SPECS})


@csrf_exempt
@require_http_methods(["POST"])
def api_export(request):
    """
    Export endpoint — Drive removed.
    TODO: rewrite to save locally when needed.
    """
    return JsonResponse({
        "ok": False,
        "error": "ميزة Export بدون Drive ستُضاف قريباً. استخدم Pipeline + حفظ محلي.",
    }, status=501)


# ─── Pipeline ────────────────────────────────────────────────────────────────

def pipeline_page(request):
    from .elevenlabs_service import list_voices as _lv
    voices = []
    try:
        voices = _lv()
    except Exception:
        pass
    return render(request, "studio/pipeline.html", {"voices": voices})


@csrf_exempt
@require_http_methods(["POST"])
def api_create_full_content(request):
    """
    POST /api/create-full-content/
    multipart/form-data:
      image (file), topic, platform, language, tone, duration,
      voice_id (optional), ai_image_instruction (optional),
      platforms (comma-separated)
    Note: video generation removed from pipeline — use /api/generate-video/ separately.
    """
    # Support multi-image: multiple files sent under same 'image' field name
    image_files = request.FILES.getlist("image")
    if not image_files:
        return JsonResponse({"ok": False, "error": "صورة واحدة على الأقل مطلوبة"}, status=400)
    images_bytes_list = [f.read() for f in image_files]

    topic = (request.POST.get("topic") or "").strip()
    if not topic:
        return JsonResponse({"ok": False, "error": "الموضوع مطلوب"}, status=400)

    _plat_raw = request.POST.get("platforms", "")
    if _plat_raw:
        platforms_resize = [p.strip() for p in _plat_raw.split(",") if p.strip()]
    else:
        platforms_resize = (
            request.POST.getlist("platforms[]") or
            ["instagram_reel", "instagram_feed", "tiktok"]
        )

    from .pipeline_service import create_full_content
    try:
        result = create_full_content(
            images_bytes_list=images_bytes_list,
            topic=topic,
            platform=request.POST.get("platform", "instagram_reel"),
            language=request.POST.get("language", "العربية"),
            tone=request.POST.get("tone", "حماسي ومغامر"),
            duration=int(request.POST.get("duration", 30)),
            voice_id=request.POST.get("voice_id") or None,
            ai_image_instruction=request.POST.get("ai_image_instruction") or None,
            platforms_resize=platforms_resize,
        )
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ─── Video (Veo) — async job pattern (avoids Render 502 timeout) ─────────────

def _video_worker(job_id: str, prompt: str, image_bytes, aspect_ratio: str):
    """Runs in background thread; writes result to /tmp/veo_jobs/<job_id>.json."""
    job_file = _JOBS_DIR / f"{job_id}.json"
    try:
        from .video_service import generate_video
        video_bytes = generate_video(
            prompt=prompt, image_bytes=image_bytes, aspect_ratio=aspect_ratio
        )
        job_file.write_text(json.dumps({
            "status": "done",
            "video_b64": base64.b64encode(video_bytes).decode("utf-8"),
        }))
    except Exception as e:
        job_file.write_text(json.dumps({"status": "error", "error": str(e)}))


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_video(request):
    """
    POST /api/generate-video/
    Returns immediately with {ok, job_id}.
    Flutter polls /api/video-status/<job_id>/ until done.
    """
    if not settings.ENABLE_VIDEO_GENERATION:
        return JsonResponse({
            "ok": False,
            "error": "توليد الفيديو متوقف مؤقتاً لحماية الكريديت. سيتم تفعيله يدوياً.",
        }, status=403)
    allowed, err_msg = _check_video_allowed()
    if not allowed:
        return JsonResponse({"ok": False, "error": err_msg}, status=429)

    if request.FILES.get("image"):
        image_bytes  = request.FILES["image"].read()
        prompt       = (request.POST.get("prompt") or "").strip()
        aspect_ratio = request.POST.get("aspect_ratio", "9:16")
    else:
        try:
            body = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON غير صالح"}, status=400)
        image_bytes  = None
        prompt       = (body.get("prompt") or "").strip()
        aspect_ratio = body.get("aspect_ratio", "9:16")

    if not prompt:
        return JsonResponse({"ok": False, "error": "البرومت مطلوب"}, status=400)

    count = _increment_video_count()
    print(f"[VEO COST WARNING] Video generation #{count} today - estimated cost: $0.25-0.30")

    job_id = str(_uuid_mod.uuid4())
    _JOBS_DIR.mkdir(exist_ok=True)
    (_JOBS_DIR / f"{job_id}.json").write_text(json.dumps({"status": "pending"}))

    threading.Thread(
        target=_video_worker,
        args=(job_id, prompt, image_bytes, aspect_ratio),
        daemon=True,
    ).start()

    return JsonResponse({"ok": True, "job_id": job_id, "count_today": count})


@require_http_methods(["GET"])
def api_video_status(request, job_id):
    """GET /api/video-status/<job_id>/ → {status: pending|done|error, video_b64?, error?}"""
    job_file = _JOBS_DIR / f"{job_id}.json"
    if not job_file.exists():
        return JsonResponse({"status": "not_found"}, status=404)
    try:
        return JsonResponse(json.loads(job_file.read_text()))
    except Exception:
        return JsonResponse({"status": "error", "error": "تعذّر قراءة حالة المهمة"})


@csrf_exempt
@require_http_methods(["POST"])
def api_generate_video_from_script(request):
    """POST /api/generate-video-from-script/ — for web interface."""
    if not settings.ENABLE_VIDEO_GENERATION:
        return JsonResponse({
            "ok": False,
            "error": "توليد الفيديو متوقف مؤقتاً لحماية الكريديت. سيتم تفعيله يدوياً.",
        }, status=403)
    allowed, err_msg = _check_video_allowed()
    if not allowed:
        return JsonResponse({"ok": False, "error": err_msg}, status=429)

    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON غير صالح"}, status=400)

    scenes   = body.get("scenes", [])
    platform = body.get("platform", "instagram_reel")

    if not scenes:
        return JsonResponse({"ok": False, "error": "المشاهد مطلوبة"}, status=400)

    count = _increment_video_count()
    print(f"[VEO COST WARNING] Video generation #{count} today - estimated cost: $0.25-0.30")

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


# ─── Voice Settings page ──────────────────────────────────────────────────────

def voice_settings_page(request):
    voices = []
    error  = None
    try:
        voices = list_voices()
    except Exception as e:
        error = str(e)
    return render(request, "studio/voice_settings.html", {
        "voices": voices,
        "error":  error,
    })
