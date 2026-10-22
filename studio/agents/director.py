"""Agent E — Réalisateur IA : transforme le script en plan de tournage (voix off + visuel par scène)."""
from __future__ import annotations

import json

from ..config import data_dir, niche, settings
from ..media import tts, visuals
from ..media.render import SCENE_PAD_S


def run(db, video_id: str):
    v = db.video(video_id)
    script = json.loads(v["script_json"])
    n = niche(v["niche"])
    mdir = data_dir() / "media" / video_id
    shots, assets = [], []
    total = len(script["scenes"])
    for i, sc in enumerate(script["scenes"]):
        wav = mdir / f"voice_{i:02d}.wav"
        speech = tts.synth(sc["voice"], wav)
        db.add_cost("tts", tts.cost_usd(sc["voice"]), video_id)
        img = visuals.render_scene(mdir / f"scene_{i:02d}.png", sc["onscreen"], sc["visual"], n["palette"], n.get("label", n["name"]), i, total, video_id)
        pad = 0.6 if i == 0 else SCENE_PAD_S  # l'accroche reste un peu plus longtemps à l'écran
        shots.append({"index": i, "voice": sc["voice"], "onscreen": sc["onscreen"], "visual": sc["visual"],
                      "wav": str(wav), "image": str(img), "speech_s": round(speech, 3), "duration_s": round(speech + pad, 3)})
    assets.append({"type": "voix", "engine": tts.engine(), "license": tts.license_note()})
    assets.append({"type": "visuels", "license": visuals.LICENSE})
    assets.append({"type": "musique", "license": "Nappe synthétisée par FFmpeg (aevalsrc), propriété du studio"})
    shotlist = {"video_id": video_id, "niche": v["niche"], "palette": n["palette"], "scenes": shots}
    (mdir / "shotlist.json").write_text(json.dumps(shotlist, ensure_ascii=False, indent=2))
    db.update_video(video_id, assets_json=json.dumps(assets, ensure_ascii=False), status="media_ready")
    return {"scenes": len(shots), "voice": tts.engine(), "duration_s": round(sum(s["duration_s"] for s in shots), 1)}
