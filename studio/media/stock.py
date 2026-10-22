"""Vraies images et vidéos via l'API officielle Pexels (licence Pexels : usage commercial gratuit, sans attribution
obligatoire ; interdit de revendre le média tel quel ou de présenter une personne identifiable de façon trompeuse).
Clé gratuite : https://www.pexels.com/api/ -> secret PEXELS_API_KEY. Sans clé : visuels procéduraux."""
from __future__ import annotations

import os
from pathlib import Path

import requests

from ..config import data_dir, settings

API = "https://api.pexels.com"
LICENSE = "Licence Pexels (usage commercial autorisé, attribution facultative)"


def available() -> bool:
    return bool(os.environ.get("PEXELS_API_KEY")) and settings()["visuals"]["provider"] in ("auto", "pexels")


def _get(path, params, session):
    r = session.get(f"{API}{path}", params=params, headers={"Authorization": os.environ["PEXELS_API_KEY"]}, timeout=30)
    r.raise_for_status()
    return r.json()


def _download(url, dest: Path, session):
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        tmp.replace(dest)
    return dest


def _pick_video_file(files):
    """Fichier vertical le plus proche de 1080x1920, sans dépasser 1440 px de large."""
    vertical = [f for f in files if f.get("height", 0) > f.get("width", 0) and f.get("file_type") == "video/mp4"]
    vertical = [f for f in vertical if f["width"] <= 1440] or vertical
    return max(vertical, key=lambda f: f["width"]) if vertical else None


def find(query: str, min_duration: float, used: set, prefer_video=True, session=requests) -> dict | None:
    """Renvoie un média réel téléchargé : {kind, path, id, url, author, license} ou None."""
    cache = data_dir() / "media" / "_stock"
    order = ("video", "photo") if prefer_video else ("photo", "video")
    for kind in order:
        if kind == "video":
            res = _get("/videos/search", {"query": query, "orientation": "portrait", "size": "medium", "per_page": 15}, session)
            for v in res.get("videos", []):
                if f"v{v['id']}" in used or v.get("duration", 0) < min(min_duration, 4):
                    continue
                f = _pick_video_file(v.get("video_files", []))
                if not f:
                    continue
                path = _download(f["link"], cache / f"v{v['id']}.mp4", session)
                return {"kind": "video", "path": str(path), "id": f"v{v['id']}", "url": v.get("url"),
                        "author": (v.get("user") or {}).get("name"), "license": LICENSE, "query": query}
        else:
            res = _get("/v1/search", {"query": query, "orientation": "portrait", "size": "large", "per_page": 15}, session)
            for p in res.get("photos", []):
                if f"p{p['id']}" in used:
                    continue
                path = _download(p["src"].get("large2x") or p["src"]["original"], cache / f"p{p['id']}.jpg", session)
                return {"kind": "photo", "path": str(path), "id": f"p{p['id']}", "url": p.get("url"),
                        "author": p.get("photographer"), "license": LICENSE, "query": query}
    return None
