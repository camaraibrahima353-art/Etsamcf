"""Agent F — Monteur : assemble le master vertical 1080x1920 (H.264/AAC) valable pour TikTok, Shorts et Reels."""
from __future__ import annotations

import json

from ..config import data_dir, niche, settings
from ..media import render, visuals


def run(db, video_id: str):
    v = db.video(video_id)
    shotlist = json.loads((data_dir() / "media" / video_id / "shotlist.json").read_text())
    cfg = settings()
    n = niche(v["niche"])
    out = data_dir() / "final" / f"{video_id}.mp4"
    total = render.render_video(shotlist, data_dir() / "projects" / video_id, out, fps=cfg["production"]["fps"],
                                max_caption_chars=cfg["quality"]["max_caption_chars_per_line"], accent=n["palette"][2],
                                target_lufs=cfg["quality"]["target_lufs"])
    script = json.loads(v["script_json"])
    visuals.render_thumbnail(data_dir() / "final" / f"{video_id}.jpg", script["title"], n["palette"], n.get("label", n["name"]), video_id)
    db.update_video(video_id, final_path=str(out.relative_to(data_dir())), duration_s=round(total, 2), status="edited")
    return {"file": out.name, "duration_s": round(total, 2), "size_mb": round(out.stat().st_size / 1e6, 2)}
