"""Agent E — Réalisateur IA : transforme le script en plan de tournage (voix off + visuel par scène).

Visuels : vraie vidéo ou vraie photo Pexels derrière le texte quand PEXELS_API_KEY existe (requête `visual.query`
du script, sinon le sujet) ; à défaut, fond procédural. Chaque média réel est consigné avec sa licence et son auteur."""
from __future__ import annotations

import json
import subprocess

from ..config import data_dir, niche, settings
from ..media import stock, tts, visuals
from ..media.render import SCENE_PAD_S


def _real_media(db, query, min_duration, used, video_id, index):
    """Cherche un média réel ; renvoie None (fond procédural) si indisponible."""
    if not stock.available():
        return None
    try:
        return stock.find(query, min_duration, used, prefer_video=settings()["visuals"]["prefer_video"])
    except Exception as e:
        db.event("E_realisateur", f"scène {index} : média réel indisponible pour « {query} » ({str(e)[:150]})",
                 level="WARNING", video_id=video_id)
        return None


def _poster(video_path, out):
    """Image fixe extraite de la vidéo de l'accroche (pour la miniature)."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", video_path, "-frames:v", "1", str(out)], check=True)
    return str(out)


def run(db, video_id: str):
    v = db.video(video_id)
    script = json.loads(v["script_json"])
    n = niche(v["niche"])
    label = n.get("label", n["name"])
    mdir = data_dir() / "media" / video_id
    shots, assets = [], []
    used = set(db.kv_get("stock_used", []))
    total = len(script["scenes"])
    for i, sc in enumerate(script["scenes"]):
        wav = mdir / f"voice_{i:02d}.wav"
        speech = tts.synth(sc["voice"], wav)
        db.add_cost("tts", tts.cost_usd(sc["voice"]), video_id)
        pad = 0.6 if i == 0 else SCENE_PAD_S  # l'accroche reste un peu plus longtemps à l'écran
        query = sc["visual"].get("query") or script.get("visual_query") or v["topic"]
        media = _real_media(db, query, speech + pad, used, video_id, i)
        shot = {"index": i, "voice": sc["voice"], "onscreen": sc["onscreen"], "visual": sc["visual"],
                "wav": str(wav), "speech_s": round(speech, 3), "duration_s": round(speech + pad, 3)}
        out_png = mdir / f"scene_{i:02d}.png"
        if media and media["kind"] == "video":
            shot["bg_video"] = media["path"]
            img = visuals.render_scene(out_png, sc["onscreen"], sc["visual"], n["palette"], label, i, total, video_id, overlay_only=True)
            if i == 0:
                shot["poster"] = _poster(media["path"], mdir / "poster.jpg")
        elif media:
            shot["bg_photo"] = media["path"]
            img = visuals.render_scene(out_png, sc["onscreen"], sc["visual"], n["palette"], label, i, total, video_id, background=media["path"])
            if i == 0:
                shot["poster"] = media["path"]
        else:
            img = visuals.render_scene(out_png, sc["onscreen"], sc["visual"], n["palette"], label, i, total, video_id)
        if media:
            used.add(media["id"])
            assets.append({"type": f"{media['kind']} réelle", "scene": i, "id": media["id"], "source": media["url"],
                           "author": media["author"], "query": query, "license": media["license"]})
        shot["image"] = str(img)
        shots.append(shot)
    db.kv_set("stock_used", sorted(used)[-5000:])
    assets.append({"type": "voix", "engine": tts.engine(), "license": tts.license_note()})
    assets.append({"type": "visuels", "license": visuals.LICENSE})
    assets.append({"type": "musique", "license": "Nappe synthétisée par FFmpeg (aevalsrc), propriété du studio"})
    shotlist = {"video_id": video_id, "niche": v["niche"], "palette": n["palette"], "scenes": shots}
    (mdir / "shotlist.json").write_text(json.dumps(shotlist, ensure_ascii=False, indent=2))
    db.update_video(video_id, assets_json=json.dumps(assets, ensure_ascii=False), status="media_ready")
    real = sum(1 for s in shots if s.get("bg_video") or s.get("bg_photo"))
    return {"scenes": len(shots), "real_media": real, "voice": tts.engine(), "duration_s": round(sum(s["duration_s"] for s in shots), 1)}
