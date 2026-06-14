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
