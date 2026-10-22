"""Agent I — Analyste de performance.

Sources : API officielles (si identifiants) + import manuel `data/stats/manual.csv` (export ou relevé depuis
TikTok Studio / YouTube Studio / Meta Business Suite), colonnes :
video_id,platform,views,likes,comments,shares,saves,avg_watch_s,completion_rate,followers_gained
Sortie : `niche_scores` (utilisé par le stratège) et recommandations dans data/stats/insights-*.json."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from ..config import data_dir
from ..db import now_iso
from ..platforms import MissingCredentials, facebook, tiktok, youtube

FIELDS = ["views", "likes", "comments", "shares", "saves", "avg_watch_s", "completion_rate", "followers_gained"]


def _num(x):
    try:
        return float(x) if x not in (None, "") else None
    except ValueError:
        return None


def import_manual(db):
    f = data_dir() / "stats" / "manual.csv"
    if not f.exists():
        return 0
    seen = db.kv_get("manual_csv_rows", 0)
    rows = list(csv.DictReader(f.open(encoding="utf-8")))
    for r in rows[seen:]:
        db.conn.execute(f"INSERT INTO stats(ts,video_id,platform,source,{','.join(FIELDS)}) VALUES(?,?,?,?,{','.join('?' * len(FIELDS))})",
                        (now_iso(), r["video_id"], r["platform"], "manual", *[_num(r.get(k)) for k in FIELDS]))
    db.kv_set("manual_csv_rows", len(rows))
    return len(rows) - seen


def collect_api(db):
    n = 0
    for platform, mod in (("youtube", youtube), ("tiktok", tiktok), ("facebook", facebook)):
        pubs = db.q("SELECT video_id, remote_id FROM publications WHERE platform=? AND remote_id IS NOT NULL AND status!='dry_run'", platform)
        if not pubs:
            continue
        try:
            got = mod.stats([p["remote_id"] for p in pubs])
        except MissingCredentials:
            continue
        except Exception as e:
            db.event("I_analyste", f"{platform} : statistiques indisponibles ({str(e)[:150]})", level="WARNING")
            continue
        for p in pubs:
            s = got.get(p["remote_id"])
            if s:
                db.conn.execute(f"INSERT INTO stats(ts,video_id,platform,source,{','.join(FIELDS)}) VALUES(?,?,?,?,{','.join('?' * len(FIELDS))})",
                                (now_iso(), p["video_id"], platform, "api", *[s.get(k) for k in FIELDS]))
                n += 1
    return n


def latest_stats(db):
    return db.q("""SELECT s.* , v.niche, v.hook_variant, v.format, v.duration_s FROM stats s JOIN videos v ON v.id=s.video_id
                   WHERE s.id IN (SELECT MAX(id) FROM stats GROUP BY video_id, platform)""")


def score(row):
    """Score d'engagement : privilégie complétion, partages et sauvegardes (signaux de rétention)."""
    views = row["views"] or 0
    if views <= 0:
        return None
    inter = (row["likes"] or 0) + 2 * (row["comments"] or 0) + 3 * (row["shares"] or 0) + 3 * (row["saves"] or 0)
    comp = row["completion_rate"] if row["completion_rate"] is not None else 0.3
    return (inter / views) * 10 + comp


def run(db):
    added = import_manual(db) + collect_api(db)
    rows = latest_stats(db)
    by = {}
    for r in rows:
        s = score(r)
        if s is not None:
            for dim in ("niche", "hook_variant", "format"):
                by.setdefault(dim, {}).setdefault(r[dim], []).append(s)
    avg = {d: {k: sum(v) / len(v) for k, v in m.items()} for d, m in by.items()}
    if avg.get("niche"):
        mean = sum(avg["niche"].values()) / len(avg["niche"])
        # facteur multiplicatif borné [0.5 ; 2] pour éviter qu'une seule vidéo fasse basculer la stratégie
        db.kv_set("niche_scores", {k: max(0.5, min(2.0, v / mean)) for k, v in avg["niche"].items()} if mean else {})
    recos = []
    for dim, label in (("hook_variant", "accroche"), ("format", "format"), ("niche", "niche")):
        if len(avg.get(dim, {})) >= 2:
            best = max(avg[dim], key=avg[dim].get)
            worst = min(avg[dim], key=avg[dim].get)
            recos.append(f"{label} la plus performante : {best} ; la moins performante : {worst}")
    if not rows:
        recos.append("aucune statistique disponible : publier puis importer les chiffres (API ou data/stats/manual.csv)")
    insights = {"ts": now_iso(), "new_rows": added, "videos_with_stats": len({r['video_id'] for r in rows}), "averages": avg,
                "recommendations": recos}
    (data_dir() / "stats" / f"insights-{datetime.now(timezone.utc):%Y%m%d}.json").write_text(json.dumps(insights, ensure_ascii=False, indent=2))
    db.event("I_analyste", f"{added} nouvelle(s) mesure(s) ; {len(recos)} recommandation(s)")
    return insights
