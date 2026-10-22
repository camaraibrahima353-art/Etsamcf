"""Agent G — Contrôle qualité : technique (ffprobe/ebur128/blackdetect), éditorial (orthographe, sources,
termes interdits, lisibilité) et juridique (licences de toutes les ressources, mention IA)."""
from __future__ import annotations

import json
import os
import re
import subprocess

from ..config import ROOT, data_dir, niche, settings
from . import NonRetryable

# Mots valides que le dictionnaire ne connaît pas forcément (noms propres, anglicismes de la niche langues…)
EXTRA_WORDS = {"tiktok", "youtube", "shorts", "reels", "ia", "abonne-toi", "abonnez-vous", "c'est", "qu'il", "d'un", "d'une"}


def probe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate:format=duration,size",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def loudness(path):
    p = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    return float(m[-1]) if m else None


def black_ratio(path, duration):
    p = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-vf", "blackdetect=d=0.3:pix_th=0.08", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    total = sum(float(x) for x in re.findall(r"black_duration:([\d.]+)", p.stderr))
    return total / duration if duration else 1.0


def spelling(texts):
    try:
        from spellchecker import SpellChecker
    except ImportError:
        return {"checked": False, "unknown": []}
    sp = SpellChecker(language="fr")
    words = set()
    for t in texts:
        for i, w in enumerate(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿœŒ']+", t)):
            w = w.strip("'")
            if i > 0 and w[:1].isupper():
                continue  # nom propre probable (hors début de phrase)
            w = w.lower().split("'")[-1]
            if len(w) > 3:
                words.add(w)
    unknown = sorted(w for w in sp.unknown(words) if w not in EXTRA_WORDS)
    return {"checked": True, "unknown": unknown, "ratio": len(unknown) / max(len(words), 1)}


def run(db, video_id: str):
    cfg = settings()
    q = cfg["quality"]
    v = db.video(video_id)
    script = json.loads(v["script_json"])
    path = data_dir() / v["final_path"]
    checks = []

    def check(name, ok, detail="", blocking=True):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "blocking": blocking})

    info = probe(path)
    vs = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if vs is None:
        raise RuntimeError(f"fichier vidéo illisible ou incomplet : {path.name}")
    aus = [s for s in info["streams"] if s["codec_type"] == "audio"]
    dur = float(info["format"]["duration"])
    check("dimensions 1080x1920 (9:16)", (vs["width"], vs["height"]) == (cfg["production"]["width"], cfg["production"]["height"]),
          f"{vs['width']}x{vs['height']}")
    check("codec H.264 yuv420p", vs["codec_name"] == "h264" and vs.get("pix_fmt") == "yuv420p", f"{vs['codec_name']} {vs.get('pix_fmt')}")
    check("cadence 30 i/s", vs["r_frame_rate"] in ("30/1", "30000/1001"), vs["r_frame_rate"])
    check("piste audio AAC", bool(aus) and aus[0]["codec_name"] == "aac", aus[0]["codec_name"] if aus else "absente")
    check(f"durée {q['min_duration_s']}-{q['max_duration_s']} s", q["min_duration_s"] <= dur <= q["max_duration_s"], f"{dur:.1f} s")
    check("taille < 287 Mo (limite la plus basse : TikTok mobile)", int(info["format"]["size"]) < 287e6, f"{int(info['format']['size'])/1e6:.1f} Mo")
    lufs = loudness(path)
    check(f"volume {q['target_lufs']} LUFS ±{q['lufs_tolerance']}", lufs is not None and abs(lufs - q["target_lufs"]) <= q["lufs_tolerance"], f"{lufs} LUFS")
    br = black_ratio(path, dur)
    check("pas d'écran noir", br < 0.05, f"{br:.1%}")

    texts = [script["hook"], script["title"], script["description"]] + [s["voice"] for s in script["scenes"]] + [s["onscreen"] for s in script["scenes"]]
    sp = spelling(texts)
    check("orthographe (mots inconnus du dictionnaire)", not sp["checked"] or sp["ratio"] < 0.08,
          ", ".join(sp["unknown"][:12]) or "aucun", blocking=False)
    max_on = max(len(s["onscreen"]) for s in script["scenes"])
    check("texte à l'écran lisible (<= 70 car.)", max_on <= 70, f"max {max_on}")
    first = script["scenes"][0]["voice"]
    check("accroche courte (<= 18 mots)", len(first.split()) <= 18, f"{len(first.split())} mots", blocking=False)
    check("sources présentes", not q["require_sources"] or len(script.get("sources", [])) >= 1, f"{len(script.get('sources', []))} source(s)")
    check("sources en https", all(s["url"].startswith("https://") for s in script.get("sources", [])))
    low = " ".join(texts).lower()
    hits = [t for t in q["banned_terms"] if t.lower() in low]
    check("aucun terme interdit / promesse trompeuse", not hits, ", ".join(hits))
    if niche(v["niche"])["risk"] == "high":
        check("niche sensible : avertissement pédagogique présent", "conseil" in low or "pédagogique" in low or "informati" in low,
              "doit préciser qu'il ne s'agit pas d'un conseil personnalisé")
    assets = json.loads(v["assets_json"] or "[]")
    check("licence connue pour chaque ressource", assets and all(a.get("license") for a in assets), f"{len(assets)} ressource(s)")
    check("mention IA activée pour la publication", cfg["publishing"]["ai_disclosure"])
    voice = next((a.get("engine") for a in assets if a.get("type") == "voix"), "")
    mode = os.environ.get("STUDIO_PUBLISH_MODE", cfg["publishing"]["mode"])
    check("voix de qualité publiable", voice != "espeak-ng" or mode == "dry_run" or q.get("allow_robotic_voice_publish"),
          f"moteur {voice} (robotique) refusé en mode {mode}")
    hook_real = any(a.get("scene") == 0 and "réelle" in a.get("type", "") for a in assets)
    real_n = sum(1 for a in assets if "réelle" in a.get("type", ""))
    check("accroche sur une vraie image", hook_real or mode == "dry_run" or not q.get("require_real_hook_image"),
          f"{real_n}/{len(script['scenes'])} scène(s) avec média réel")

    blocking_fail = [c for c in checks if c["blocking"] and not c["ok"]]
    report = {"video_id": video_id, "passed": not blocking_fail, "duration_s": dur, "lufs": lufs, "checks": checks}
    (data_dir() / "projects" / video_id / "qc.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    db.update_video(video_id, qc_json=json.dumps(report, ensure_ascii=False), status="qc_passed" if report["passed"] else "qc_failed")
    if blocking_fail:
        raise NonRetryable("QC refusé : " + "; ".join(f"{c['check']} ({c['detail']})" for c in blocking_fail))
    return {"passed": True, "warnings": [c["check"] for c in checks if not c["ok"]]}
