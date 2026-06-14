"""
محرك توليد السكريبت باستخدام Gemini API.
"""
import json
from google import genai
from django.conf import settings

PLATFORM_SPECS = {
    "instagram": {"label": "Instagram Reel", "ratio": "9:16", "size": "1080x1920", "max_sec": 90},
    "tiktok":    {"label": "TikTok",         "ratio": "9:16", "size": "1080x1920", "max_sec": 60},
    "facebook":  {"label": "Facebook Reel",  "ratio": "9:16", "size": "1080x1920", "max_sec": 90},
    "youtube_short": {"label": "YouTube Short", "ratio": "9:16", "size": "1080x1920", "max_sec": 60},
    "youtube_long":  {"label": "YouTube",       "ratio": "16:9", "size": "1920x1080", "max_sec": 600},
}

WHATSAPP = "+201149538054"
_client = None

def get_client():
    global _client
    if _client is None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY مش موجود في ملف .env")
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client

def build_prompt(topic, platform, language, tone, duration):
    spec = PLATFORM_SPECS.get(platform, PLATFORM_SPECS["instagram"])
    return f"""أنت كاتب محتوى محترف لشركة سياحة مصرية اسمها "Dreamers Team".
اكتب سكريبت فيديو لـ {spec['label']} باللغة ال{language}.
الموضوع: {topic}
الأسلوب: {tone}
المدة: {duration} ثانية
المقاس: {spec['ratio']} ({spec['size']})

اكتب JSON فقط بدون أي نص إضافي:
{{"hook":"...","scenes":[{{"time":"0-5s","visual":"...","voiceover":"...","text_overlay":"..."}}],"cta":"...","caption":"...","hashtags":["..."]}}"""

def clean_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())

def generate_script(topic, platform="instagram", language="ألمانية",
                    tone="حماسي ومغامر", duration=30):
    client = get_client()
    prompt = build_prompt(topic, platform, language, tone, duration)
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
    )
    data = clean_json(response.text)
    spec = PLATFORM_SPECS.get(platform, PLATFORM_SPECS["instagram"])
    data["meta"] = {
        "platform": spec["label"],
        "ratio": spec["ratio"],
        "size": spec["size"],
        "language": language,
        "duration": duration,
    }
    return data