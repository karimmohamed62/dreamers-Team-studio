"""
محرك تحويل النص لصوت باستخدام ElevenLabs API.
بيدعم التحكم الكامل في إعدادات الصوت.
"""
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from django.conf import settings

DEFAULT_MODEL = "eleven_multilingual_v2"

# إعدادات افتراضية متوازنة لمحتوى السوشيال ميديا
DEFAULT_SETTINGS = {
    "stability":        0.50,   # 0-1: ثبات الصوت (أعلى = أكثر ثبات وأقل عشوائية)
    "similarity_boost": 0.75,   # 0-1: تشابه مع الصوت الأصلي
    "style":            0.30,   # 0-1: قوة الأسلوب والتعبير
    "speed":            1.00,   # 0.7-1.2: سرعة الكلام
    "use_speaker_boost": True,  # تحسين جودة الصوت
}

_client = None


def get_client():
    global _client
    if _client is None:
        if not settings.ELEVENLABS_API_KEY:
            raise RuntimeError("ELEVENLABS_API_KEY مش موجود في ملف .env")
        _client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    return _client


def list_voices():
    """يرجّع قائمة الأصوات مع إعداداتها الحالية"""
    client = get_client()
    response = client.voices.search(page_size=50)
    voices = []
    for v in response.voices:
        # نجيب الإعدادات الحالية لكل صوت
        s = v.settings
        voices.append({
            "id":           v.voice_id,
            "name":         v.name,
            "category":     getattr(v, "category", ""),
            "preview_url":  getattr(v, "preview_url", ""),
            "settings": {
                "stability":        s.stability        if s else DEFAULT_SETTINGS["stability"],
                "similarity_boost": s.similarity_boost if s else DEFAULT_SETTINGS["similarity_boost"],
                "style":            s.style            if s else DEFAULT_SETTINGS["style"],
                "speed":            s.speed            if s else DEFAULT_SETTINGS["speed"],
            }
        })
    return voices


def text_to_speech(text, voice_id, model_id=DEFAULT_MODEL, voice_settings=None):
    """
    يحوّل النص لصوت ويرجّع bytes MP3.
    voice_settings: dict بإعدادات الصوت (اختياري، بيستخدم الافتراضي لو مش موجود)
    """
    client = get_client()
    cfg = {**DEFAULT_SETTINGS, **(voice_settings or {})}

    vs = VoiceSettings(
        stability=float(cfg["stability"]),
        similarity_boost=float(cfg["similarity_boost"]),
        style=float(cfg["style"]),
        speed=float(cfg["speed"]),
        use_speaker_boost=bool(cfg.get("use_speaker_boost", True)),
    )

    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        voice_settings=vs,
        output_format="mp3_44100_128",
    )
    return b"".join(audio_generator)


def generate_voiceover(scenes, voice_id, model_id=DEFAULT_MODEL, voice_settings=None):
    """
    يولّد ملف صوتي كامل من مشاهد السكريبت.
    """
    full_text = "\n\n".join(
        scene.get("voiceover", "")
        for scene in scenes
        if scene.get("voiceover")
    )
    if not full_text.strip():
        raise ValueError("مفيش voiceover في السكريبت")
    return text_to_speech(full_text, voice_id, model_id, voice_settings)


def save_voice_settings(voice_id, stability, similarity_boost, style, speed):
    """
    يحفظ إعدادات الصوت على ElevenLabs (تأثير دائم على الحساب).
    """
    client = get_client()
    client.voices.settings.update(
        voice_id=voice_id,
        request=VoiceSettings(
            stability=float(stability),
            similarity_boost=float(similarity_boost),
            style=float(style),
            speed=float(speed),
            use_speaker_boost=True,
        )
    )
