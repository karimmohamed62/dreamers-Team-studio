"""
Export service — resize + upload all platforms to Drive in one shot.
"""
from .resize_service import resize_image, PLATFORM_SIZES
from .drive_service  import upload_file, _service


def _get_or_create_folder(svc, folder_name):
    """Find or create a Drive folder by name, return folder_id."""
    q = (
        f"name='{folder_name}' "
        "and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    res = svc.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]

    meta = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    f = svc.files().create(body=meta, fields="id").execute()
    return f["id"]


def _build_caption_txt(script):
    """Build a plain-text caption file from script dict."""
    lines = []
    lines.append("=" * 50)
    lines.append("DREAMERS TEAM — CAPTION & HASHTAGS")
    lines.append("=" * 50)
    lines.append("")
    lines.append("📌 HOOK:")
    lines.append(script.get("hook", ""))
    lines.append("")
    lines.append("📝 CAPTION:")
    lines.append(script.get("caption", ""))
    lines.append("")
    lines.append("📣 CTA:")
    lines.append(script.get("cta", ""))
    lines.append("")
    lines.append("🏷️ HASHTAGS:")
    tags = script.get("hashtags", [])
    lines.append(" ".join(f"#{t}" for t in tags))
    lines.append("")
    lines.append("=" * 50)
    lines.append("SCENES:")
    lines.append("=" * 50)
    for i, sc in enumerate(script.get("scenes", []), 1):
        lines.append(f"\n[{i}] {sc.get('time','')}")
        lines.append(f"  🎬 Visual:    {sc.get('visual','')}")
        lines.append(f"  🎙️ Voiceover: {sc.get('voiceover','')}")
        if sc.get("text_overlay"):
            lines.append(f"  📝 Overlay:   {sc.get('text_overlay','')}")
    return "\n".join(lines).encode("utf-8")


def create_export_package(
    image_bytes,
    script,
    audio_bytes,
    platforms,
    access_token,
    folder_name,
):
    """
    Resize image for every platform, upload everything to a Drive folder.
    Returns {folder_id, folder_link, files: [{name, link, platform}]}
    """
    svc = _service(access_token)

    # 1. Create Drive folder
    folder_id = _get_or_create_folder(svc, folder_name)
    folder_link = f"https://drive.google.com/drive/folders/{folder_id}"

    uploaded = []

    # 2. Resize + upload per platform
    for platform in platforms:
        if platform not in PLATFORM_SIZES:
            continue
        w, h = PLATFORM_SIZES[platform]
        try:
            resized = resize_image(image_bytes, platform)
            filename = f"{platform}_{w}x{h}.jpg"
            result = upload_file(
                access_token=access_token,
                file_bytes=resized,
                filename=filename,
                mime_type="image/jpeg",
                folder_id=folder_id,
            )
            uploaded.append({
                "name":     result["name"],
                "link":     result["link"],
                "platform": platform,
                "size":     f"{w}x{h}",
            })
        except Exception as e:
            uploaded.append({
                "name":     f"{platform}_{w}x{h}.jpg",
                "link":     "",
                "platform": platform,
                "error":    str(e),
            })

    # 3. Caption text file
    try:
        caption_bytes = _build_caption_txt(script)
        result = upload_file(
            access_token=access_token,
            file_bytes=caption_bytes,
            filename="caption.txt",
            mime_type="text/plain",
            folder_id=folder_id,
        )
        uploaded.append({"name": "caption.txt", "link": result["link"], "platform": "all"})
    except Exception as e:
        uploaded.append({"name": "caption.txt", "link": "", "error": str(e), "platform": "all"})

    # 4. Audio (optional)
    if audio_bytes:
        try:
            result = upload_file(
                access_token=access_token,
                file_bytes=audio_bytes,
                filename="voiceover.mp3",
                mime_type="audio/mpeg",
                folder_id=folder_id,
            )
            uploaded.append({"name": "voiceover.mp3", "link": result["link"], "platform": "all"})
        except Exception as e:
            uploaded.append({"name": "voiceover.mp3", "link": "", "error": str(e), "platform": "all"})

    return {
        "folder_id":   folder_id,
        "folder_link": folder_link,
        "files":       uploaded,
    }
