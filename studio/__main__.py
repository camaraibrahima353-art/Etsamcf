"""Interface en ligne de commande : python -m studio <commande>."""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import write_control
from .db import DB


def cmd_run(a):
    import fcntl

    from .agents.orchestrator import run_cycle
    from .config import data_dir
    from .dashboard import daily_report, render_dashboard

    # verrou global : un seul orchestrateur à la fois sur cette machine (libéré automatiquement si le processus meurt)
    lock = open(data_dir() / "studio.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("un autre passage est déjà en cours : abandon", file=sys.stderr)
        return 3
    db = DB()
    summary = run_cycle(db, n_videos=a.videos, time_budget_s=a.time_budget, skip_trends=a.no_trends)
    render_dashboard(db)
    daily_report(db, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_control(a):
    db = DB()
    if a.cmd == "resume":
        db.kv_set("auto_paused", None)
        db.kv_set("manual_control", None)
        db.conn.execute("UPDATE alerts SET resolved=1 WHERE source='J_admin' AND message LIKE 'PRODUCTION SUSPENDUE%'")
        ctl = write_control("running", a.reason or "reprise manuelle")
    else:
        ctl = write_control("paused" if a.cmd == "pause" else "stopped", a.reason or f"{a.cmd} manuel")
        db.kv_set("manual_control", ctl)  # persiste dans la base (utile sur GitHub Actions où le fichier n'est pas conservé)
    db.event("A_directeur", f"commande {a.cmd} : {ctl['reason']}")
    print(json.dumps(ctl, ensure_ascii=False))
    return 0


def cmd_status(a):
    from .dashboard import snapshot

    s = snapshot(DB())
    print(json.dumps({k: s[k] for k in ("state", "reason", "jobs", "health")} | {"videos": len(s["videos"]), "alerts": s["alerts"][:5]},
                     ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_dashboard(a):
    from .dashboard import daily_report, render_dashboard

    db = DB()
    print(render_dashboard(db))
    print(daily_report(db))
    return 0


def cmd_alerts(a):
    """Ouvre une issue GitHub par alerte critique non encore signalée (API REST officielle, GITHUB_TOKEN)."""
    import os

    import requests

    db = DB()
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    sent = set(db.kv_get("alerts_notified", []))
    todo = [x for x in db.q("SELECT * FROM alerts WHERE resolved=0 AND level='critical'") if x["id"] not in sent]
    for al in todo:
        if repo and token:
            r = requests.post(f"https://api.github.com/repos/{repo}/issues", timeout=30,
                              headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                              json={"title": f"[studio] {al['message'][:90]}", "labels": ["studio-alerte"],
                                    "body": f"Alerte critique levée par **{al['source']}** le {al['ts']}.\n\n{al['message']}\n\n"
                                            "Voir docs/OPERATIONS.md (section Incidents)."})
            if r.status_code >= 300:
                print(f"issue non créée ({r.status_code})", file=sys.stderr)
                continue
        print(f"ALERTE CRITIQUE : {al['message']}")
        sent.add(al["id"])
    db.kv_set("alerts_notified", sorted(sent))
    return 0


def cmd_check(a):
    """Vérifie les clés configurées par un appel léger à chaque service, sans jamais afficher leur valeur."""
    import os

    import requests

    out = {}
    if os.environ.get("ELEVENLABS_API_KEY"):
        try:
            r = requests.get("https://api.elevenlabs.io/v1/user/subscription", timeout=30,
                             headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]})
            j = r.json() if r.ok else {}
            out["elevenlabs"] = (f"OK — forfait {j.get('tier')}, {j.get('character_count')}/{j.get('character_limit')} caractères utilisés"
                                 if r.ok else f"ÉCHEC HTTP {r.status_code} (clé invalide ?)")
        except Exception as e:
            out["elevenlabs"] = f"ÉCHEC : {type(e).__name__}"
    else:
        out["elevenlabs"] = "absente (secret ELEVENLABS_API_KEY non défini)"
    if os.environ.get("PEXELS_API_KEY"):
        try:
            r = requests.get("https://api.pexels.com/v1/search", params={"query": "ocean", "per_page": 1}, timeout=30,
                             headers={"Authorization": os.environ["PEXELS_API_KEY"]})
            out["pexels"] = f"OK — {r.json().get('total_results')} photos pour « ocean »" if r.ok else f"ÉCHEC HTTP {r.status_code} (clé invalide ?)"
        except Exception as e:
            out["pexels"] = f"ÉCHEC : {type(e).__name__}"
    else:
        out["pexels"] = "absente (secret PEXELS_API_KEY non défini)"
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            r = requests.get("https://api.anthropic.com/v1/models", params={"limit": 1}, timeout=30,
                             headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
            out["anthropic"] = "OK — le studio peut écrire de nouveaux scripts" if r.ok else f"ÉCHEC HTTP {r.status_code} (clé invalide ?)"
        except Exception as e:
            out["anthropic"] = f"ÉCHEC : {type(e).__name__}"
    else:
        out["anthropic"] = "absente (secret ANTHROPIC_API_KEY) : production arrêtée quand la réserve sera vide"
    for k in ("YT_REFRESH_TOKEN", "TIKTOK_REFRESH_TOKEN", "FB_PAGE_TOKEN"):
        out[k] = "présent" if os.environ.get(k) else "absent"

    from .agents import publisher, strategist
    from .agents.strategist import topic_key

    db = DB()
    left = sum(1 for s in strategist.backlog_scripts()
               if not db.one("SELECT 1 FROM videos WHERE topic_key=?", topic_key(s["niche"], s["topic"])))
    mode = publisher.effective_mode()
    out["mode_publication"] = mode
    out["reserve_scripts"] = f"{left} script(s) non produits" 
    todo = []
    if not out["pexels"].startswith("OK"):
        todo.append("enregistrer PEXELS_API_KEY (sans elle, aucune vidéo ne peut être publiée)")
    if not out["anthropic"].startswith("OK"):
        todo.append("enregistrer ANTHROPIC_API_KEY (sinon arrêt quand la réserve est vide)")
    if not out["elevenlabs"].startswith("OK"):
        todo.append("facultatif : ELEVENLABS_API_KEY (voix plus naturelle que Piper)")
    if not any(out[k] == "présent" for k in ("YT_REFRESH_TOKEN", "TIKTOK_REFRESH_TOKEN", "FB_PAGE_TOKEN")):
        todo.append("brancher au moins une plateforme (docs/PLATFORMS.md)")
    if mode == "dry_run":
        todo.append("variable de dépôt STUDIO_PUBLISH_MODE = private (essai réel) ou public")
    out["pret_a_publier"] = "OUI" if not [t for t in todo if not t.startswith("facultatif")] else "NON"
    out["a_faire"] = todo
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if all(not str(v).startswith("ÉCHEC") for v in out.values()) else 1


def cmd_requeue(a):
    db = DB()
    db.conn.execute("UPDATE jobs SET status='pending', attempts=0, next_run_at=0, last_error=NULL WHERE video_id=? AND stage=?", (a.video_id, a.stage))
    db.event("A_directeur", f"relance manuelle {a.video_id}/{a.stage}")
    return 0


def cmd_serve(a):
    """Tableau de bord local avec boutons Reprendre / Suspendre / Arrêt (écoute sur 127.0.0.1 uniquement)."""
    from .dashboard import render_dashboard

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            db = DB()
            body = render_dashboard(db).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/api/control":
                self.send_error(404)
                return
            n = int(self.headers.get("Content-Length", 0))
            action = json.loads(self.rfile.read(n) or b"{}").get("action")
            if action not in ("pause", "resume", "stop"):
                self.send_error(400)
                return
            cmd_control(argparse.Namespace(cmd=action, reason="tableau de bord"))
            self.send_response(204)
            self.end_headers()

    print(f"Tableau de bord : http://127.0.0.1:{a.port}")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


def main(argv=None):
    p = argparse.ArgumentParser(prog="studio")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="un passage complet de l'orchestrateur")
    r.add_argument("--videos", type=int, default=None)
    r.add_argument("--time-budget", type=int, default=1500)
    r.add_argument("--no-trends", action="store_true")
    r.set_defaults(fn=cmd_run)
    for c in ("pause", "resume", "stop"):
        s = sub.add_parser(c)
        s.add_argument("--reason", default="")
        s.set_defaults(fn=cmd_control)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("dashboard").set_defaults(fn=cmd_dashboard)
    sub.add_parser("check", help="vérifie les clés API configurées (sans les afficher)").set_defaults(fn=cmd_check)
    sub.add_parser("alerts", help="signale les alertes critiques (issues GitHub)").set_defaults(fn=cmd_alerts)
    q = sub.add_parser("requeue")
    q.add_argument("video_id")
    q.add_argument("stage")
    q.set_defaults(fn=cmd_requeue)
    sv = sub.add_parser("serve")
    sv.add_argument("--port", type=int, default=8765)
    sv.set_defaults(fn=cmd_serve)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
