from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("pipeline/", views.pipeline_page, name="pipeline"),
    path("voices/", views.voice_settings_page, name="voices"),
    path("export/", views.export_page, name="export"),
    path("_check/", views.deploy_check, name="deploy_check"),
    # Script API
    path("api/generate-script/",   views.api_generate_script,    name="api_generate_script"),
    path("api/generate-full/",     views.api_generate_full,       name="api_generate_full"),
    # Voice API
    path("api/voices/",            views.api_list_voices,         name="api_list_voices"),
    path("api/generate-voice/",    views.api_generate_voice,      name="api_generate_voice"),
    path("api/voice-settings/",    views.api_save_voice_settings, name="api_save_voice_settings"),
    # Image API
    path("api/edit-image/",        views.api_edit_image,          name="api_edit_image"),
    path("api/resize-image/",      views.api_resize_image,        name="api_resize_image"),
    # Pipeline API
    path("api/create-full-content/", views.api_create_full_content, name="api_create_full_content"),
    # Video API (Veo) — async job pattern
    path("api/generate-video/",             views.api_generate_video,             name="api_generate_video"),
    path("api/video-status/<str:job_id>/",  views.api_video_status,               name="api_video_status"),
    path("api/generate-video-from-script/", views.api_generate_video_from_script, name="api_generate_video_from_script"),
    # Export
    path("api/export/", views.api_export, name="api_export"),
]
