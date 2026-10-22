"""Agent A — Directeur / orchestrateur. Un « passage » (run) est borné dans le temps et en nombre de tâches :
pas de boucle infinie, pas de duplication d'agents. L'ordonnanceur externe (GitHub Actions, systemd, cron)
déclenche les passages ; les tâches échouées sont reprises au passage suivant selon l'attente exponentielle."""
from __future__ import annotations

import os
import time
import traceback

from ..config import read_control, settings
from . import AGENTS, NonRetryable, analyst, director, editor, publisher, qc, strategist, sysadmin, trends, writer

PIPELINE = ["write", "direct", "edit", "qc", "publish"]
STAGE_AGENT = {"write": ("D_scenariste", writer), "direct": ("E_realisateur", director), "edit": ("F_monteur", editor),
               "qc": ("G_qualite", qc), "publish": ("H_publication", publisher)}


def effective_state(db):
    ctl = read_control()
    auto = db.kv_get("auto_paused")
    manual = db.kv_get("manual_control")
    if ctl.get("state", "running") != "running":
        return ctl["state"], ctl.get("reason", "")
    if manual and manual.get("state") != "running":
        return manual["state"], manual.get("reason", "")
    if auto:
        return "paused", auto["reason"]
    return "running", ""


def _inject_failure(stage):
    """Test de reprise : STUDIO_INJECT_FAILURE=edit:1 fait échouer la 1re exécution de l'étape edit."""
    spec = os.environ.get("STUDIO_INJECT_FAILURE", "")
    if not spec:
        return
    st, n = (spec.split(":") + ["1"])[:2]
    if st == stage:
        key = f"_injected_{stage}"
        done = int(os.environ.get(key, "0"))
        if done < int(n):
            os.environ[key] = str(done + 1)
            raise RuntimeError(f"panne simulée sur l'étape {stage} (test de reprise)")


def process_queue(db, deadline: float, max_jobs: int = 50) -> dict:
    done = failed = 0
    for _ in range(max_jobs):
        if time.time() > deadline:
            db.event("A_directeur", "limite de temps du passage atteinte : reprise au prochain passage")
            break
        state, _ = effective_state(db)
        if state != "running":
            break
        job = db.claim_next()
        if not job:
            break
        name, mod = STAGE_AGENT[job["stage"]]
        db.agent_status(name, AGENTS[name], "en cours", f"{job['stage']} {job['video_id']}")
        t0 = time.time()
        try:
            _inject_failure(job["stage"])
            result = mod.run(db, job["video_id"])
            db.finish(job["id"])
            db.event(name, f"{job['stage']} terminé en {time.time() - t0:.1f}s", video_id=job["video_id"], result=result)
            db.agent_status(name, AGENTS[name], "inactif", f"OK {job['video_id']}")
            i = PIPELINE.index(job["stage"])
            if i + 1 < len(PIPELINE):
                db.enqueue(job["video_id"], PIPELINE[i + 1], reset=True)
            done += 1
        except NonRetryable as e:
            db.fail(job, str(e), retryable=False)
            db.update_video(job["video_id"], status=f"blocked_{job['stage']}")
            db.alert(name, f"{job['video_id']} bloquée à l'étape {job['stage']} : {str(e)[:300]}", "warning")
            db.agent_status(name, AGENTS[name], "inactif", f"BLOQUÉ {job['video_id']}")
            failed += 1
        except Exception as e:
            outcome, delay = db.fail(job, f"{e}\n{traceback.format_exc()[-800:]}")
            lvl = "WARNING" if outcome == "retry" else "ERROR"
            db.event(name, f"échec {job['stage']} (tentative {job['attempts']}) -> {outcome}" + (f" dans {delay}s" if delay else "") + f" : {e}",
                     level=lvl, video_id=job["video_id"])
            if outcome == "dead":
                db.update_video(job["video_id"], status=f"failed_{job['stage']}")
                db.alert(name, f"{job['video_id']} abandonnée après {job['attempts']} tentatives ({job['stage']}) : {str(e)[:200]}", "critical")
            db.agent_status(name, AGENTS[name], "inactif", f"ÉCHEC {job['video_id']}")
            failed += 1
    return {"done": done, "failed": failed}


def run_cycle(db, n_videos: int | None = None, time_budget_s: int = 1500, skip_trends=False) -> dict:
    t_start = time.time()
    deadline = t_start + time_budget_s
    db.agent_status("A_directeur", AGENTS["A_directeur"], "en cours", "passage démarré")
    summary = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    summary["health"] = sysadmin.run(db)
    db.agent_status("J_admin", AGENTS["J_admin"], "inactif", f"disque libre {summary['health']['disk_free_gb']} Go")

    state, reason = effective_state(db)
    summary["state"] = state
    if state != "running":
        db.event("A_directeur", f"production {state} : {reason} — aucun travail lancé")
        db.agent_status("A_directeur", AGENTS["A_directeur"], state, reason)
        return summary

    tr = None
    if not skip_trends:
        try:
            tr = trends.run(db)
            db.agent_status("B_tendances", AGENTS["B_tendances"], "inactif", f"{len(tr['items'])} signaux")
        except Exception as e:
            db.event("B_tendances", f"échec recherche de tendances : {e}", level="WARNING")
            db.agent_status("B_tendances", AGENTS["B_tendances"], "erreur", str(e)[:200])

    n = n_videos if n_videos is not None else settings()["production"]["videos_per_run"]
    summary["planned"] = strategist.run(db, tr, n)
    db.agent_status("C_strategie", AGENTS["C_strategie"], "inactif", f"{len(summary['planned'])} planifiée(s)")

    summary["queue"] = process_queue(db, deadline)

    try:
        ins = analyst.run(db)
        db.agent_status("I_analyste", AGENTS["I_analyste"], "inactif", "; ".join(ins["recommendations"])[:300])
    except Exception as e:
        db.event("I_analyste", f"échec analyse : {e}", level="WARNING")

    summary["duration_s"] = round(time.time() - t_start, 1)
    summary["jobs"] = db.job_counts()
    db.event("A_directeur", f"passage terminé en {summary['duration_s']}s : {summary['queue']}", summary=summary)
    db.agent_status("A_directeur", AGENTS["A_directeur"], "inactif", f"dernier passage : {summary['queue']}")
    return summary
