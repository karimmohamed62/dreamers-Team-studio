"""
Google Drive API service — OAuth 2.0 + Drive operations
"""
import io
import os
import requests as _requests
from urllib.parse import urlencode
from django.conf import settings
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://127.0.0.1:8000/auth/google/callback/"
)
SCOPES = "https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/drive.readonly"
AUTH_URI  = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"

MEDIA_MIME_PREFIXES = ("image/", "video/", "audio/")


def get_auth_url(source="web"):
    """Build OAuth URL — passes source (web/mobile) via state param."""
    params = {
        "client_id":     settings.GOOGLE_CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         source,
    }
    print(f"DEBUG REDIRECT_URI: {REDIRECT_URI}", flush=True)
    return AUTH_URI + "?" + urlencode(params)


def exchange_code(code):
    """Exchange authorization code for tokens — no code_verifier."""
    data = {
        "code":          code,
        "client_id":     settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri":  REDIRECT_URI,
        "grant_type":    "authorization_code",
    }
    print(f"DEBUG exchange redirect_uri: {REDIRECT_URI}", flush=True)
    resp = _requests.post(TOKEN_URI, data=data, timeout=15)
    print(f"[Drive OAuth] token response {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()
    j = resp.json()
    if "error" in j:
        raise RuntimeError(f"OAuth error: {j['error']} — {j.get('error_description','')}")
    return {
        "token":         j["access_token"],
        "refresh_token": j.get("refresh_token", ""),
        "token_uri":     TOKEN_URI,
        "client_id":     settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "scopes":        SCOPES.split(),
    }


def _service(access_token):
    creds = Credentials(token=access_token)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_folders(access_token):
    """Returns list of {id, name} for all Drive folders."""
    svc = _service(access_token)
    results = svc.files().list(
        q="mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)",
        pageSize=100,
    ).execute()
    return results.get("files", [])


def list_media_files(access_token, folder_id=None):
    """Returns list of {id, name, mimeType, thumbnailLink, webViewLink, size}."""
    svc = _service(access_token)
    mime_conditions = " or ".join(
        f"mimeType contains '{p}'" for p in MEDIA_MIME_PREFIXES
    )
    q = f"({mime_conditions}) and trashed=false"
    if folder_id:
        q += f" and '{folder_id}' in parents"
    results = svc.files().list(
        q=q,
        fields="files(id,name,mimeType,thumbnailLink,webViewLink,size)",
        pageSize=100,
        orderBy="modifiedTime desc",
    ).execute()
    return results.get("files", [])


def download_file(access_token, file_id):
    """Returns raw bytes of the file."""
    svc = _service(access_token)
    request = svc.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def upload_file(access_token, file_bytes, filename, mime_type, folder_id=None):
    """
    Uploads file_bytes to Drive.
    Returns {id, name, link}
    """
    svc = _service(access_token)
    metadata = {"name": filename}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type)
    result = svc.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,webViewLink",
    ).execute()
    return {
        "id":   result["id"],
        "name": result["name"],
        "link": result.get("webViewLink", ""),
    }
