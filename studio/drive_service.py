"""
Google Drive API service — OAuth 2.0 + Drive operations
"""
import io
from django.conf import settings
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

REDIRECT_URI = "http://127.0.0.1:8000/auth/google/callback/"
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
]

MEDIA_MIME_PREFIXES = ("image/", "video/", "audio/")


def _flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id":     settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


def get_auth_url():
    """Returns (auth_url, state)"""
    flow = _flow()
    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url, state


def exchange_code(code):
    """Exchange authorization code for tokens dict."""
    flow = _flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes or []),
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
