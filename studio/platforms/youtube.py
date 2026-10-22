"""YouTube Data API v3 — envoi d'un Short (vidéo verticale <= 3 min) par upload résumable.

Prérequis : projet Google Cloud, API « YouTube Data API v3 » activée, client OAuth (scope
https://www.googleapis.com/auth/youtube.upload), jeton d'actualisation (refresh token) du compte de la chaîne.
Limites : quota par défaut 10 000 unités/jour ; un `videos.insert` est facturé 100 unités selon la doc
officielle actuelle (1 600 historiquement : le studio retient 1 600 par prudence). Les projets non audités
créés après le 28/07/2020 ne peuvent publier qu'en privé jusqu'à l'audit de conformité.
Divulgation IA : `status.containsSyntheticMedia` (ajouté le 30/10/2024)."""
from __future__ import annotations

import json
import os

import requests

from . import need

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"


def access_token(session=requests):
    cid, secret, refresh = need("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")
    r = session.post(TOKEN_URL, data={"client_id": cid, "client_secret": secret, "refresh_token": refresh, "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def build_metadata(meta: dict, privacy: str, publish_at: str | None, ai: bool) -> dict:
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": ai}
    if publish_at and privacy == "private":
        status["publishAt"] = publish_at  # programmation native : la vidéo devient publique à cette date
    return {
        "snippet": {"title": meta["title"][:100], "description": meta["description"][:5000],
                    "tags": [h.lstrip("#") for h in meta["hashtags"]][:15], "categoryId": "27", "defaultLanguage": "fr",
                    "defaultAudioLanguage": "fr"},
        "status": status,
    }


def upload(path, meta: dict, privacy="private", publish_at=None, ai=True, session=requests) -> dict:
    token = access_token(session)
    body = build_metadata(meta, privacy, publish_at, ai)
    size = os.path.getsize(path)
    init = session.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                        data=json.dumps(body), timeout=60)
    init.raise_for_status()
    with open(path, "rb") as f:
        r = session.put(init.headers["Location"], headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"},
                        data=f, timeout=600)
    r.raise_for_status()
    data = r.json()
    return {"remote_id": data["id"], "url": f"https://youtube.com/shorts/{data['id']}", "privacy": data["status"]["privacyStatus"]}


def stats(video_ids: list[str], session=requests) -> dict:
    token = access_token(session)
    r = session.get(f"{API}/videos", params={"part": "statistics", "id": ",".join(video_ids)},
                    headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    out = {}
    for it in r.json().get("items", []):
        s = it["statistics"]
        out[it["id"]] = {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0))}
    return out
