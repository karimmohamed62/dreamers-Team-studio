from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("voices/", views.voice_settings_page, name="voices"),
    path("drive/", views.drive_page, name="drive"),
    path("export/", views.export_page, name="export"),
    path("api/export/", views.api_export, name="api_export"),
    # OAuth
    path("auth/google/", views.drive_login, name="drive_login"),
    path("auth/google/callback/", views.drive_callback, name="drive_callback"),
    # Script API
    path("api/generate-script/",   views.api_generate_script,    name="api_generate_script"),
    path("api/generate-full/",     views.api_generate_full,       name="api_generate_full"),
    # Voice API
    path("api/voices/",            views.api_list_voices,         name="api_list_voices"),
    path("api/generate-voice/",    views.api_generate_voice,      name="api_generate_voice"),
    path("api/voice-settings/",    views.api_save_voice_settings, name="api_save_voice_settings"),
    # Image AI API
    path("api/edit-image/",                views.api_edit_image,      name="api_edit_image"),
    # Resize API
    path("api/resize-image/",              views.api_resize_image,    name="api_resize_image"),
    # Drive API
    path("api/drive/upload/",                  views.api_drive_upload,    name="api_drive_upload"),
    path("api/drive/download/<str:file_id>/",  views.api_drive_download,  name="api_drive_download"),
    path("api/drive/files/",                   views.api_drive_files,     name="api_drive_files"),
    path("api/drive/folders/",                 views.api_drive_folders,   name="api_drive_folders"),
    path("api/drive/logout/",                  views.api_drive_logout,    name="api_drive_logout"),
]
