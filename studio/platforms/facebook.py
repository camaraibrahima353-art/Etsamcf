"""Facebook Reels Publishing API (Graph API, Page).

Flux officiel en 3 temps : POST /{page-id}/video_reels upload_phase=start -> envoi binaire sur
rupload.facebook.com -> POST upload_phase=finish avec video_state (DRAFT | SCHEDULED | PUBLISHED).
Prérequis : application Meta, Page Facebook, jeton de Page longue durée avec pages_show_list,
pages_read_engagement, pages_manage_posts (App Review requise pour d'autres comptes que les vôtres).
Pas de champ API documenté pour l'étiquette IA : la mention figure dans la description."""
from __future__ import annotations

import os
from datetime import datetime

import requests

from . import need

GRAPH = "https://graph.facebook.com"
RUPLOAD = "https://rupload.facebook.com/video-upload"


def _ver():
    return os.environ.get("FB_GRAPH_VERSION", "v23.0")


def upload(path, meta: dict, state="DRAFT", scheduled_at: str | None = None, session=requests) -> dict:
    page_id, token = need("FB_PAGE_ID", "FB_PAGE_TOKEN")
    v = _ver()
    r = session.post(f"{GRAPH}/{v}/{page_id}/video_reels", data={"upload_phase": "start", "access_token": token}, timeout=30)
    r.raise_for_status()
    video_id = r.json()["video_id"]
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        up = session.post(f"{RUPLOAD}/{v}/{video_id}", headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)},
                          data=f, timeout=600)
    up.raise_for_status()
    fin = {"upload_phase": "finish", "video_id": video_id, "video_state": state, "access_token": token,
           "description": f"{meta['description']}\n\n{' '.join(meta['hashtags'])}", "title": meta["title"]}
    if state == "SCHEDULED" and scheduled_at:
        fin["scheduled_publish_time"] = str(int(datetime.fromisoformat(scheduled_at).timestamp()))
    r = session.post(f"{GRAPH}/{v}/{page_id}/video_reels", data=fin, timeout=60)
    r.raise_for_status()
    if not r.json().get("success"):
        raise RuntimeError(f"Facebook : finish sans succès {r.json()}")
    return {"remote_id": video_id, "state": state}


def stats(video_ids: list[str], session=requests) -> dict:
    _, token = need("FB_PAGE_ID", "FB_PAGE_TOKEN")
    out = {}
    for vid in video_ids:
        r = session.get(f"{GRAPH}/{_ver()}/{vid}/video_insights", params={"access_token": token}, timeout=30)
        if not r.ok:
            continue
        vals = {m["name"]: (m.get("values") or [{}])[0].get("value") for m in r.json().get("data", [])}
        out[vid] = {"views": vals.get("blue_reels_play_count") or vals.get("fb_reels_total_plays") or 0,
                    "avg_watch_s": (vals.get("post_video_avg_time_watched") or 0) / 1000}
    return out
