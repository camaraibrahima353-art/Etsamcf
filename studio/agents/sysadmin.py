"""Agent J — Administrateur technique : santé, verrous, stockage, coûts, taux d'erreur, kill switch automatique."""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timezone

from ..config import data_dir, read_control, settings, write_control


def dir_size_mb(p):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6


def cleanup(days=7):
    """Supprime les fichiers intermédiaires de montage anciens (jamais les vidéos finales ni la base)."""
    cutoff = time.time() - days * 86400
    freed = 0
    for sub in ("projects", "media"):
        for f in (data_dir() / sub).rglob("*"):
            if f.is_file() and f.suffix in (".wav", ".mp4", ".png") and f.stat().st_mtime < cutoff:
                freed += f.stat().st_size
                f.unlink()
    return freed / 1e6


def run(db) -> dict:
    cfg = settings()
    report = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    report["stale_recovered"] = db.recover_stale(cfg["retry"]["stale_lock_minutes"])
    if report["stale_recovered"]:
        db.event("J_admin", f"{report['stale_recovered']} tâche(s) bloquée(s) remise(s) en file")

    du = shutil.disk_usage(data_dir())
    report["disk_free_gb"] = round(du.free / 1e9, 1)
    report["data_mb"] = round(dir_size_mb(data_dir()), 1)
    if du.free < 2e9:
        report["cleanup_mb"] = round(cleanup(days=1), 1)
        db.alert("J_admin", f"espace disque faible ({report['disk_free_gb']} Go libres)", "critical")

    today = datetime.now(timezone.utc).date().isoformat()
    month = today[:7]
    report["spend_today_usd"] = round(db.spend_since(today), 4)
    report["spend_month_usd"] = round(db.spend_since(month), 4)
    b = cfg["budget"]
    reason = None
    if report["spend_today_usd"] >= b["daily_usd"]:
        reason = f"plafond quotidien atteint ({report['spend_today_usd']} $ / {b['daily_usd']} $)"
    elif report["spend_month_usd"] >= b["monthly_usd"]:
        reason = f"plafond mensuel atteint ({report['spend_month_usd']} $ / {b['monthly_usd']} $)"

    recent = db.q("SELECT status, COUNT(*) n FROM jobs WHERE updated_at>=? GROUP BY status", today)
    counts = {r["status"]: r["n"] for r in recent}
    failed = counts.get("dead", 0) + counts.get("failed", 0)
    total = sum(counts.values())
    report["jobs_today"] = counts
    if total >= 6 and failed / total > 0.5:
        reason = reason or f"taux d'échec anormal ({failed}/{total} tâches aujourd'hui)"

    if os.environ.get("STUDIO_SECURITY_HALT"):
        reason = "arrêt de sécurité demandé (STUDIO_SECURITY_HALT)"

    if reason and read_control().get("state") == "running":
        write_control("paused", f"pause automatique : {reason}")
        db.kv_set("auto_paused", {"ts": report["ts"], "reason": reason})
        db.alert("J_admin", f"PRODUCTION SUSPENDUE : {reason}", "critical")
    report["paused_reason"] = reason
    db.kv_set("last_health", report)
    return report
