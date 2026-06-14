from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("voices/", views.voice_settings_page, name="voices"),
    path("api/generate-script/",   views.api_generate_script,    name="api_generate_script"),
    path("api/voices/",            views.api_list_voices,         name="api_list_voices"),
    path("api/generate-voice/",    views.api_generate_voice,      name="api_generate_voice"),
    path("api/voice-settings/",    views.api_save_voice_settings, name="api_save_voice_settings"),
]
