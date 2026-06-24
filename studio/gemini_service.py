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
    return f"""أنت كاتب محتوى إبداعي محترف متخصص في صناعة المحتوى لوسائل التواصل الاجتماعي.

مهمتك الوحيدة: اكتب سكريبت فيديو احترافي ومقنع حصريًا عن الموضوع التالي:
«{topic}»

تفاصيل السكريبت:
- المنصة: {spec['label']}
- اللغة: {language}
- الأسلوب: {tone}
- المدة الإجمالية: {duration} ثانية تقريبًا
- النسبة: {spec['ratio']}

تعليمات صارمة:
- السكريبت يجب أن يكون عن «{topic}» تحديدًا وليس أي موضوع آخر
- ابدأ بـ hook يخطف الانتباه في أول 3 ثواني
- الـ voiceover يكون طبيعي ومناسب للمدة المحددة
- اكتب فقط JSON بدون أي نص أو شرح إضافي

الصيغة المطلوبة:
{{"hook":"نص الـ hook","scenes":[{{"time":"0-5s","visual":"وصف المشهد البصري","voiceover":"نص الكلام المنطوق","text_overlay":"نص يظهر على الشاشة"}}],"cta":"نص الـ call to action","caption":"كابشن السوشيال ميديا","hashtags":["هاشتاق1","هاشتاق2"]}}"""

def clean_json(text):
    text = text.strip()
    # Strip markdown code fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                return json.loads(part)
    # Try direct parse
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start != -1 and end > start:
        return json.loads(text[start:end])
    return json.loads(text)

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