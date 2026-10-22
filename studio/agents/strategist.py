"""Agent C — Stratège éditorial : choisit les niches et les sujets, construit le calendrier.

Politique de sélection (bandit simple, sans boucle infinie) :
  poids(niche) = priorité × score de performance (agent I, 1.0 par défaut) × bonus d'exploration
  le bonus favorise les niches encore peu produites, ce qui garantit la diversité du pilote.
Ordre des sources de sujets : 1) réserve de scripts validés (backlog/)  2) tendances + LLM (si clé API).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import ROOT, data_dir, settings
from ..schema import topic_key, validate_script
from .. import llm


def backlog_scripts():
    files = sorted((ROOT / "backlog").glob("**/*.json"))
    out = []
    for f in files:
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        s["_file"] = str(f.relative_to(ROOT))
        out.append(s)
    return out


def niche_weights(db):
    scores = db.kv_get("niche_scores", {})
    counts = {r["niche"]: r["n"] for r in db.q("SELECT niche, COUNT(*) n FROM videos GROUP BY niche")}
    w = {}
    for n in settings()["niches"]:
        explore = 1.0 / (1 + counts.get(n["id"], 0))
        w[n["id"]] = n.get("priority", 1.0) * scores.get(n["id"], 1.0) * (0.5 + explore)
    return w


def next_slots(n, db):
    """Créneaux de publication (UTC) libres à partir de maintenant."""
    slots = settings()["publishing"]["schedule_slots_utc"]
    taken = {r["scheduled_at"] for r in db.q("SELECT DISTINCT scheduled_at FROM publications WHERE scheduled_at IS NOT NULL")}
    taken |= set(db.kv_get("reserved_slots", []))
    out, day = [], datetime.now(timezone.utc).date()
    while len(out) < n:
        for s in slots:
            hh, mm = map(int, s.split(":"))
            dt = datetime(day.year, day.month, day.day, hh, mm, tzinfo=timezone.utc)
            iso = dt.isoformat(timespec="minutes")
            if dt > datetime.now(timezone.utc) + timedelta(minutes=30) and iso not in taken:
                out.append(iso)
                if len(out) == n:
                    break
        day += timedelta(days=1)
    return out


def run(db, trends: dict | None, n_wanted: int) -> list[str]:
    cfg = settings()["production"]
    today = datetime.now(timezone.utc).date().isoformat()
    made_today = db.one("SELECT COUNT(*) n FROM videos WHERE created_at>=?", today)["n"]
    n = max(0, min(n_wanted, cfg["max_videos_per_day"] - made_today))
    if n == 0:
        db.event("C_strategie", "plafond quotidien atteint : aucune nouvelle vidéo planifiée")
        return []

    weights = niche_weights(db)
    candidates = []
    for s in backlog_scripts():
        if validate_script(s):
            db.alert("C_strategie", f"script invalide ignoré : {s.get('_file')} -> {validate_script(s)[:2]}")
            continue
        key = topic_key(s["niche"], s["topic"])
        if db.one("SELECT 1 FROM videos WHERE topic_key=?", key):
            continue
        candidates.append((weights.get(s["niche"], 0.5), s, key))

    planned, used_niches = [], set()
    candidates.sort(key=lambda c: -c[0])
    # une niche différente par vidéo tant que possible (diversité du pilote)
    for pass_ in (0, 1):
        for w, s, key in candidates:
            if len(planned) >= n:
                break
            if pass_ == 0 and s["niche"] in used_niches:
                continue
            if any(p[2] == key for p in planned):
                continue
            planned.append((w, s, key))
            used_niches.add(s["niche"])

    ids = []
    for _, s, key in planned:
        script = {k: v for k, v in s.items() if not k.startswith("_")}
        vid = db.create_video(s["niche"], s["topic"], key, "backlog", format=s["format"], hook=s["hook"],
                              hook_variant=s["hook_variant"], script_json=json.dumps(script, ensure_ascii=False),
                              sources_json=json.dumps(s["sources"], ensure_ascii=False))
        if vid:
            db.enqueue(vid, "write")
            ids.append(vid)

    # sujets issus des tendances, rédigés par le LLM, si la réserve ne suffit pas
    remaining = n - len(ids)
    if remaining > 0 and trends and llm.available():
        ranked = sorted(weights, key=lambda k: -weights[k])
        for niche_id in ranked:
            if remaining == 0:
                break
            for term in (trends.get("by_niche", {}).get(niche_id) or [])[:3]:
                key = topic_key(niche_id, term)
                vid = db.create_video(niche_id, term, key, "trends")
                if vid:
                    db.enqueue(vid, "write")
                    ids.append(vid)
                    remaining -= 1
                    break
    backlog_left = len(candidates) - len(planned)
    if backlog_left < cfg["min_backlog_alert"] and not llm.available():
        db.alert("C_strategie", f"réserve de scripts presque vide ({backlog_left} restant(s)) et pas de clé ANTHROPIC_API_KEY : "
                 "ajouter des scripts dans backlog/ ou configurer la clé", "warning")

    plan = {"date": today, "weights": weights, "planned": ids, "backlog_left": backlog_left}
    (data_dir() / "research" / f"plan-{datetime.now(timezone.utc):%Y%m%dT%H%M}.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    db.event("C_strategie", f"{len(ids)} vidéo(s) planifiée(s), réserve restante : {backlog_left}", planned=ids)
    return ids
