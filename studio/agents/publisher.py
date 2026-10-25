"""Agent H — Gestionnaire de publication : métadonnées, créneau, envoi via les API officielles.

Modes (config publishing.mode) :
  dry_run : rien n'est envoyé ; la charge utile exacte est écrite dans data/publications/ (par défaut).
  private : envoi en privé / brouillon (YouTube private, TikTok brouillon ou SELF_ONLY, Facebook DRAFT).
  public  : publication programmée (YouTube publishAt, Facebook SCHEDULED, TikTok direct public si client audité).
Une plateforme sans identifiants passe en `blocked_credentials` sans bloquer les autres."""
from __future__ import annotations

import json
import os

from ..config import ROOT, data_dir, niche, read_control, settings
from ..db import now_iso
from ..platforms import MissingCredentials, facebook, tiktok, youtube
from .strategist import next_slots

AI_NOTE = "Contenu créé avec l'aide de l'IA (voix et visuels générés)."


def package(db, video_id):
    v = db.video(video_id)
    s = json.loads(v["script_json"])
    n = niche(v["niche"])
    tags = list(dict.fromkeys([*(h if h.startswith("#") else f"#{h}" for h in s["hashtags"]), *n["hashtags"]]))[:6]
    tags = [t for t in tags if t.lower() != "#shorts"] + ["#shorts"]
    src = " | ".join(f"{x['title']} : {x['url']}" for x in s["sources"])
    desc = f"{s['description']}\n\nSources : {src}\n{AI_NOTE}"
    meta = {"title": s["title"], "description": desc, "hashtags": tags}
    db.update_video(video_id, title=s["title"], description=desc, hashtags=" ".join(tags))
    return meta


def _record(db, video_id, platform, status, scheduled_at=None, remote_id=None, response=None):
    db.conn.execute(
        "INSERT INTO publications(video_id,platform,status,remote_id,scheduled_at,published_at,response_json) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(video_id,platform) DO UPDATE SET status=excluded.status, remote_id=COALESCE(excluded.remote_id, publications.remote_id), "
        "scheduled_at=excluded.scheduled_at, published_at=excluded.published_at, response_json=excluded.response_json",
        (video_id, platform, status, remote_id, scheduled_at, now_iso() if status in ("published", "uploaded_private", "draft") else None,
         json.dumps(response, ensure_ascii=False) if response else None))


def _published_today(db, platform):
    return db.one("SELECT COUNT(*) n FROM publications WHERE platform=? AND published_at>=? AND status!='dry_run'",
                  platform, now_iso()[:10])["n"]


def effective_mode() -> str:
    """Mode de publication réel : variable STUDIO_PUBLISH_MODE, sinon config ; dry_run si la publication est coupée."""
    mode = os.environ.get("STUDIO_PUBLISH_MODE") or settings()["publishing"]["mode"]
    if not read_control().get("publishing_enabled", True):
        return "dry_run"
    return mode if mode in ("dry_run", "private", "public") else "dry_run"


def release_rehearsals(db) -> int:
    """Libère les sujets consommés en répétition (dry_run) pour qu'ils soient refaits avec la vraie voix et les
    vraies images. Ne touche ni aux vidéos en cours de fabrication ni à celles réellement envoyées."""
    rows = db.conn.execute(
        "SELECT id FROM videos v WHERE (status IN ('ready','qc_failed','publish_failed') OR status LIKE 'failed_%' "
        "OR status LIKE 'blocked_%') "
        "AND NOT EXISTS (SELECT 1 FROM publications p WHERE p.video_id=v.id AND p.status!='dry_run') "
        "AND NOT EXISTS (SELECT 1 FROM jobs j WHERE j.video_id=v.id AND j.status IN ('pending','running'))").fetchall()
    ids = [r[0] for r in rows]
    for vid in ids:
        for table in ("jobs", "publications", "videos"):
            db.conn.execute(f"DELETE FROM {table} WHERE {'id' if table == 'videos' else 'video_id'}=?", (vid,))
    db.conn.commit()
    return len(ids)


def run(db, video_id: str):
    cfg = settings()["publishing"]
    mode = effective_mode()
    v = db.video(video_id)
    meta = package(db, video_id)
    path = data_dir() / v["final_path"]
    slot = next_slots(1, db)[0]
    db.kv_set("reserved_slots", (db.kv_get("reserved_slots", []) + [slot])[-200:])
    results = {}
    for platform, pcfg in cfg["platforms"].items():
        if not pcfg.get("enabled"):
            continue
        if db.one("SELECT 1 FROM publications WHERE video_id=? AND platform=? AND status IN ('published','uploaded_private','draft','scheduled')",
                  video_id, platform):
            results[platform] = "déjà publiée"  # idempotence : jamais deux envois
            continue
        payload = {"platform": platform, "file": str(path), "scheduled_at": slot, "ai_disclosure": cfg["ai_disclosure"], **meta}
        if mode == "dry_run":
            (data_dir() / "publications" / f"{video_id}-{platform}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            _record(db, video_id, platform, "dry_run", slot, response=payload)
            results[platform] = "dry_run"
            continue
        limit = pcfg.get("max_posts_per_day") or (pcfg.get("daily_quota_units", 10000) // pcfg.get("upload_cost_units", 1600))
        if _published_today(db, platform) >= limit:
            results[platform] = "quota du jour atteint (reporté)"
            continue
        try:
            if platform == "youtube":
                r = youtube.upload(path, meta, privacy="private", publish_at=slot if mode == "public" else None, ai=cfg["ai_disclosure"])
                status = "scheduled" if mode == "public" else "uploaded_private"
            elif platform == "tiktok":
                tmode = os.environ.get("TIKTOK_MODE", "inbox")
                r = tiktok.upload(path, meta, mode=tmode, want_public=(mode == "public"), ai=cfg["ai_disclosure"])
                status = "draft" if tmode == "inbox" else ("published" if r["privacy"] != "SELF_ONLY" else "uploaded_private")
            elif platform == "facebook":
                state = "SCHEDULED" if mode == "public" else "DRAFT"
                r = facebook.upload(path, meta, state=state, scheduled_at=slot)
                status = "scheduled" if mode == "public" else "draft"
            else:
                continue
            _record(db, video_id, platform, status, slot, r.get("remote_id"), r)
            results[platform] = status
        except MissingCredentials as e:
            _record(db, video_id, platform, "blocked_credentials", slot, response={"error": str(e)})
            db.alert("H_publication", f"{platform} : {e}", "info")
            results[platform] = "blocked_credentials"
        except Exception as e:
            _record(db, video_id, platform, "error", slot, response={"error": str(e)[:500]})
            db.alert("H_publication", f"{platform} : échec d'envoi ({str(e)[:200]})", "warning")
            results[platform] = "error"
    ok = any(r in ("published", "scheduled", "uploaded_private", "draft", "dry_run", "déjà publiée") for r in results.values())
    db.update_video(video_id, status="published" if mode != "dry_run" and ok else ("ready" if ok else "publish_failed"))
    if not ok and any(r == "error" for r in results.values()):
        raise RuntimeError(f"aucune plateforme n'a accepté la vidéo : {results}")
    return {"mode": mode, "slot": slot, **results}
