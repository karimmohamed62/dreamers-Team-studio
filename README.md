# 🐬 Dreamers Studio — محطة توليد محتوى السوشيال ميديا

باك-إند Django لتوليد سكريبتات فيديو احترافية لـ Dreamers Team
على Instagram, TikTok, Facebook, YouTube — باستخدام Gemini API (مجاني).

دي **المرحلة الأولى** من المشروع: توليد السكريبت.
المراحل الجاية: ElevenLabs (صوت) → Nano Banana (صور) → Google Drive → النشر.

---

## خطوات التشغيل

### ١. احصل على مفتاح Gemini المجاني
ادخل على: https://aistudio.google.com/apikey
اعمل "Create API Key" وانسخ المفتاح.

### ٢. ظبّط ملف البيئة
انسخ `.env.example` لـ `.env`:
```bash
cp .env.example .env
```
افتح `.env` وحط مفتاحك الحقيقي مكان `ضع_مفتاحك_هنا`.

### ٣. ثبّت المكتبات
```bash
pip install -r requirements.txt
```

### ٤. جهّز قاعدة البيانات
```bash
python manage.py migrate
```

### ٥. شغّل السيرفر
```bash
python manage.py runserver
```
افتح المتصفح على: http://127.0.0.1:8000

اكتب موضوع، اختار المنصة واللغة، ودوس "توليد السكريبت".

---

## الـ API (لتطبيق Flutter لاحقاً)

```
POST /api/generate-script/
Content-Type: application/json

{
  "topic": "رحلة دولفين VIP في الغردقة",
  "platform": "instagram",   // instagram | tiktok | facebook | youtube_short | youtube_long
  "language": "ألمانية",
  "tone": "حماسي ومغامر",
  "duration": 30
}
```

الرد:
```json
{
  "ok": true,
  "script": {
    "hook": "...",
    "scenes": [{"time":"0-5s","visual":"...","voiceover":"...","text_overlay":"..."}],
    "cta": "...",
    "caption": "...",
    "hashtags": ["..."],
    "_meta": {"platform":"...","ratio":"9:16","size":"1080x1920","language":"...","duration":30}
  }
}
```

---

## ملاحظات مهمة

- **الـ free tier:** 100-1000 طلب/يوم حسب الموديل. كفاية جداً للبداية.
- **الاستخدام التجاري في أوروبا:** الـ free tier مسموح تجارياً ما عدا في EU/UK/سويسرا.
  للاستخدام التجاري من ألمانيا فعّل الـ paid tier (رخيص جداً).
- نفس مفتاح Gemini ده هيشتغل لتعديل الصور (Nano Banana) في المرحلة الجاية.

## هيكل المشروع
```
dreamers_studio/
├── config/          إعدادات Django
├── studio/
│   ├── gemini_service.py   ← محرك التوليد (القلب)
│   ├── views.py            ← الـ endpoint + صفحة التجربة
│   └── urls.py
├── templates/studio/home.html
├── requirements.txt
└── .env             ← مفتاحك (لا ترفعه على git أبداً)
```
