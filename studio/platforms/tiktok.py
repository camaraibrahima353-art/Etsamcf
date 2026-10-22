"""TikTok Content Posting API (v2).

Deux modes officiels :
- `inbox` (par défaut, scope video.upload) : la vidéo arrive en BROUILLON dans l'application TikTok ; le créateur
  la finalise et l'étiquette « contenu généré par IA » lui-même. Compatible avec un client non audité.
- `direct` (scope video.publish) : publication directe avec `is_aigc`. Tant que le client n'est pas audité par
  TikTok, les publications sont forcées en SELF_ONLY (privé), 5 utilisateurs max / 24 h, et le compte doit être privé.
Le niveau de confidentialité doit appartenir à `privacy_level_options` renvoyé par creator_info/query."""
from __future__ import annotations

import os

import requests

from . import need

API = "https://open.tiktokapis.com/v2"


def access_token(session=requests):
    if os.environ.get("TIKTOK_ACCESS_TOKEN") and not os.environ.get("TIKTOK_REFRESH_TOKEN"):
        return os.environ["TIKTOK_ACCESS_TOKEN"]
    key, secret, refresh = need("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN")
    r = session.post(f"{API}/oauth/token/", data={"client_key": key, "client_secret": secret, "grant_type": "refresh_token",
                                                  "refresh_token": refresh},
                     headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def _check(r):
    r.raise_for_status()
    j = r.json()
    if j.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok : {j['error'].get('code')} — {j['error'].get('message')}")
    return j["data"]


def upload(path, meta: dict, mode="inbox", want_public=False, ai=True, session=requests) -> dict:
    token = access_token(session)
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    size = os.path.getsize(path)
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}  # < 64 Mo : un seul segment
    if mode == "direct":
        info = _check(session.post(f"{API}/post/publish/creator_info/query/", headers=h, timeout=30))
        options = info.get("privacy_level_options", [])
        privacy = "PUBLIC_TO_EVERYONE" if want_public and "PUBLIC_TO_EVERYONE" in options else "SELF_ONLY"
        caption = f"{meta['title']} {' '.join(meta['hashtags'])}"[:2200]
        body = {"post_info": {"title": caption, "privacy_level": privacy, "disable_comment": False, "disable_duet": False,
                              "disable_stitch": False, "video_cover_timestamp_ms": 1000, "is_aigc": ai},
                "source_info": source}
        data = _check(session.post(f"{API}/post/publish/video/init/", headers=h, json=body, timeout=30))
    else:
        privacy = "DRAFT"
        data = _check(session.post(f"{API}/post/publish/inbox/video/init/", headers=h, json={"source_info": source}, timeout=30))
    with open(path, "rb") as f:
        r = session.put(data["upload_url"], headers={"Content-Type": "video/mp4", "Content-Length": str(size),
                                                     "Content-Range": f"bytes 0-{size - 1}/{size}"}, data=f, timeout=600)
    r.raise_for_status()
    return {"remote_id": data["publish_id"], "privacy": privacy, "mode": mode}


def publish_status(publish_id: str, session=requests) -> dict:
    token = access_token(session)
    return _check(session.post(f"{API}/post/publish/status/fetch/", headers={"Authorization": f"Bearer {token}",
                               "Content-Type": "application/json; charset=UTF-8"}, json={"publish_id": publish_id}, timeout=30))


def stats(video_ids: list[str], session=requests) -> dict:
    """Nécessite le scope video.list et l'identifiant public de la vidéo (publicaly_available_post_id)."""
    token = access_token(session)
    r = session.post(f"{API}/video/query/", params={"fields": "id,view_count,like_count,comment_count,share_count"},
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                     json={"filters": {"video_ids": video_ids[:20]}}, timeout=30)
    data = _check(r)
    return {v["id"]: {"views": v.get("view_count", 0), "likes": v.get("like_count", 0), "comments": v.get("comment_count", 0),
                      "shares": v.get("share_count", 0)} for v in data.get("videos", [])}
