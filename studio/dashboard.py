"""Tableau de bord (HTML autonome) et rapport quotidien (Markdown)."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from .agents import AGENTS
from .agents.orchestrator import effective_state
from .config import data_dir, settings


def snapshot(db) -> dict:
    state, reason = effective_state(db)
    videos = db.q("""SELECT v.id, v.niche, v.topic, v.format, v.hook_variant, v.status, v.duration_s, v.cost_usd, v.title, v.created_at,
                     v.final_path, (SELECT MAX(views) FROM stats s WHERE s.video_id=v.id) views,
                     (SELECT SUM(likes) FROM stats s WHERE s.video_id=v.id) likes
                     FROM videos v ORDER BY v.created_at DESC""")
    agents = {r["name"]: r for r in db.q("SELECT * FROM agents")}
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "state": state, "reason": reason,
        "agents": [{"name": k, "role": v, **{x: agents.get(k, {}).get(x) for x in ("status", "last_run", "last_result")}} for k, v in AGENTS.items()],
        "jobs": db.job_counts(),
        "jobs_detail": db.q("SELECT video_id, stage, status, attempts, last_error, updated_at FROM jobs WHERE status!='done' ORDER BY updated_at DESC LIMIT 30"),
        "videos": videos,
        "publications": db.q("SELECT video_id, platform, status, scheduled_at, published_at, remote_id FROM publications ORDER BY scheduled_at"),
        "costs_by_category": db.q("SELECT category, ROUND(SUM(usd),4) usd FROM costs GROUP BY category"),
        "costs_by_platform": db.q("SELECT COALESCE(platform,'production') platform, ROUND(SUM(usd),4) usd FROM costs GROUP BY 1"),
        "niches": db.q("""SELECT v.niche, COUNT(DISTINCT v.id) videos, ROUND(AVG(v.duration_s),1) avg_duration,
                          ROUND(SUM(v.cost_usd),4) cost, MAX(s.views) best_views, SUM(s.views) total_views
                          FROM videos v LEFT JOIN stats s ON s.video_id=v.id GROUP BY v.niche ORDER BY total_views DESC, videos DESC"""),
        "alerts": db.q("SELECT ts, level, source, message FROM alerts WHERE resolved=0 ORDER BY id DESC LIMIT 20"),
        "errors": db.q("SELECT ts, agent, level, video_id, message FROM events WHERE level IN ('WARNING','ERROR') ORDER BY id DESC LIMIT 20"),
        "health": db.kv_get("last_health", {}),
        "settings": {"budget": settings()["budget"], "production": settings()["production"], "publishing_mode": settings()["publishing"]["mode"]},
    }


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Studio IA Shorts</title><style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#14171c;--muted:#5d6673;--line:#e3e6eb;--accent:#1f6feb;--ok:#1e8449;--warn:#b9770e;--bad:#c0392b}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0e1116;--card:#161b22;--fg:#e6edf3;--muted:#8b949e;--line:#30363d;--accent:#58a6ff;--ok:#3fb950;--warn:#d29922;--bad:#f85149}}
:root[data-theme=dark]{--bg:#0e1116;--card:#161b22;--fg:#e6edf3;--muted:#8b949e;--line:#30363d;--accent:#58a6ff;--ok:#3fb950;--warn:#d29922;--bad:#f85149}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1200px;margin:0 auto;padding:20px 16px}h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:0 0 10px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin:14px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:12px 0;overflow-x:auto}
.kpi b{display:block;font-size:26px;font-variant-numeric:tabular-nums}.kpi span{color:var(--muted);font-size:12px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums}.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;border:1px solid var(--line)}
.running{color:var(--ok)}.paused,.warning{color:var(--warn)}.stopped,.critical,.ERROR{color:var(--bad)}
button{font:inherit;padding:7px 14px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer;margin-right:6px}
button.stop{border-color:var(--bad);color:var(--bad)}.muted{color:var(--muted)}.bar{height:8px;background:var(--accent);border-radius:4px}
</style></head><body><main>
<h1>Studio IA Shorts</h1><div class="muted" id="gen"></div>
<div class="card"><h2>Contrôle</h2><p>État : <b id="state"></b> <span class="muted" id="reason"></span></p>
<button onclick="ctl('resume')">▶ Reprendre</button><button onclick="ctl('pause')">⏸ Suspendre</button><button class="stop" onclick="ctl('stop')">■ Arrêt général</button>
<p class="muted" id="ctlhelp"></p></div>
<div class="grid" id="kpis"></div>
<div class="card"><h2>Agents</h2><table id="agents"></table></div>
<div class="card"><h2>Tâches</h2><div id="jobs"></div><table id="jobsd"></table></div>
<div class="card"><h2>Vidéos</h2><table id="videos"></table></div>
<div class="card"><h2>Calendrier de publication</h2><table id="pubs"></table></div>
<div class="card"><h2>Niches</h2><table id="niches"></table></div>
<div class="card"><h2>Coûts</h2><table id="costs"></table></div>
<div class="card"><h2>Alertes et erreurs</h2><table id="alerts"></table><table id="errors"></table></div>
<div class="card"><h2>Paramètres et limites</h2><pre id="settings" style="white-space:pre-wrap"></pre></div>
</main><script>
const D = __DATA__;
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const tbl = (id, cols, rows, num=[]) => { document.getElementById(id).innerHTML = "<tr>" + cols.map(c=>`<th>${c[1]}</th>`).join("") + "</tr>" +
  (rows.length ? rows.map(r => "<tr>" + cols.map(c => `<td class="${num.includes(c[0])?'n':''} ${esc(r[c[0]])}">${esc(r[c[0]])}</td>`).join("") + "</tr>").join("")
  : `<tr><td colspan="${cols.length}" class="muted">aucune donnée</td></tr>`); };
document.getElementById("gen").textContent = "Instantané du " + D.generated + " (UTC)";
const st = document.getElementById("state"); st.textContent = D.state; st.className = D.state;
document.getElementById("reason").textContent = D.reason || "";
const live = location.protocol.startsWith("http") && !location.hostname.endsWith("claude.ai") && !location.hostname.endsWith("github.io");
document.getElementById("ctlhelp").textContent = live ? "Commandes actives (serveur local)." :
  "Page statique : utiliser `python -m studio pause|resume|stop`, ou l'action GitHub « studio » (entrée action), ou éditer config/control.yaml.";
async function ctl(a){ if(!live){alert(document.getElementById("ctlhelp").textContent);return;}
  const r = await fetch("/api/control", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({action:a})}); location.reload(); }
const v = D.videos, pub = D.publications;
const cost = v.reduce((a,x)=>a+(x.cost_usd||0),0);
const kp = [["Vidéos créées", v.filter(x=>x.final_path).length], ["Prêtes / publiées", v.filter(x=>["ready","published"].includes(x.status)).length],
  ["Publications réelles", pub.filter(p=>!["dry_run","blocked_credentials","error"].includes(p.status)).length],
  ["Bloquées / échouées", v.filter(x=>/blocked|failed/.test(x.status)).length], ["Coût total ($)", cost.toFixed(3)],
  ["Coût / vidéo ($)", v.length ? (cost/v.length).toFixed(3) : "0"], ["Vues cumulées", v.reduce((a,x)=>a+(x.views||0),0)],
  ["Disque libre (Go)", D.health.disk_free_gb ?? "?"]];
document.getElementById("kpis").innerHTML = kp.map(k=>`<div class="card kpi"><b>${esc(k[1])}</b><span>${esc(k[0])}</span></div>`).join("");
tbl("agents", [["name","Agent"],["role","Rôle"],["status","État"],["last_run","Dernière activité"],["last_result","Dernier résultat"]], D.agents);
const jt = Object.values(D.jobs).reduce((a,b)=>a+b,0)||1;
document.getElementById("jobs").innerHTML = ["pending","running","done","failed","dead","blocked"].map(s =>
  `<div style="display:flex;gap:8px;align-items:center;margin:4px 0"><span style="width:90px">${s}</span><div class="bar" style="width:${(D.jobs[s]||0)/jt*60}%"></div><span class="n">${D.jobs[s]||0}</span></div>`).join("");
tbl("jobsd", [["video_id","Vidéo"],["stage","Étape"],["status","État"],["attempts","Essais"],["last_error","Dernière erreur"]], D.jobs_detail);
tbl("videos", [["id","ID"],["niche","Niche"],["title","Titre"],["format","Format"],["hook_variant","Accroche"],["duration_s","Durée (s)"],["status","Statut"],["cost_usd","Coût ($)"],["views","Vues"]], v, ["duration_s","cost_usd","views"]);
tbl("pubs", [["scheduled_at","Créneau (UTC)"],["platform","Plateforme"],["video_id","Vidéo"],["status","Statut"],["remote_id","ID distant"]], pub);
tbl("niches", [["niche","Niche"],["videos","Vidéos"],["avg_duration","Durée moy."],["cost","Coût ($)"],["total_views","Vues"],["best_views","Meilleure"]], D.niches, ["videos","avg_duration","cost","total_views","best_views"]);
tbl("costs", [["category","Catégorie / plateforme"],["usd","USD"]], D.costs_by_category.concat(D.costs_by_platform.map(p=>({category:"plateforme : "+p.platform, usd:p.usd}))), ["usd"]);
tbl("alerts", [["ts","Date"],["level","Niveau"],["source","Agent"],["message","Alerte"]], D.alerts);
tbl("errors", [["ts","Date"],["level","Niveau"],["agent","Agent"],["video_id","Vidéo"],["message","Événement"]], D.errors);
document.getElementById("settings").textContent = JSON.stringify(D.settings, null, 2);
</script></body></html>"""


def render_dashboard(db, out=None):
    out = out or (data_dir() / "reports" / "dashboard.html")
    data = json.dumps(snapshot(db), ensure_ascii=False, default=str).replace("</", "<\\/")
    out.write_text(PAGE.replace("__DATA__", data), encoding="utf-8")
    return out


def daily_report(db, summary: dict | None = None):
    s = snapshot(db)
    day = datetime.now(timezone.utc).date().isoformat()
    today_v = [v for v in s["videos"] if (v["created_at"] or "").startswith(day)]
    lines = [f"# Rapport quotidien — {day}", "", f"- État de la production : **{s['state']}** {s['reason']}",
             f"- Vidéos créées aujourd'hui : {len(today_v)} ; total : {len(s['videos'])}",
             f"- Tâches : {s['jobs']}",
             f"- Dépense du jour : {s['health'].get('spend_today_usd', 0)} $ / plafond {s['settings']['budget']['daily_usd']} $ ; "
             f"mois : {s['health'].get('spend_month_usd', 0)} $ / {s['settings']['budget']['monthly_usd']} $",
             f"- Disque libre : {s['health'].get('disk_free_gb')} Go ; données : {s['health'].get('data_mb')} Mo", "",
             "## Vidéos du jour", ""]
    lines += [f"- `{v['id']}` [{v['niche']}] {html.unescape(v['title'] or v['topic'])} — {v['status']} — {v['duration_s']} s" for v in today_v] or ["- aucune"]
    lines += ["", "## Alertes ouvertes", ""] + ([f"- {a['level']} — {a['source']} : {a['message']}" for a in s["alerts"]] or ["- aucune"])
    if summary:
        lines += ["", "## Dernier passage", "", "```json", json.dumps(summary, ensure_ascii=False, indent=2, default=str), "```"]
    out = data_dir() / "reports" / f"daily-{day}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
