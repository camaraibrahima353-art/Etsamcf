"""Base SQLite : registre des vidéos, file de tâches, coûts, statistiques, alertes, journal d'événements."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import data_dir, settings
from .log import get_logger, redact

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY,
  topic_key TEXT UNIQUE NOT NULL,          -- empêche de produire deux fois le même sujet
  niche TEXT NOT NULL,
  topic TEXT NOT NULL,
  format TEXT,
  hook TEXT,
  hook_variant TEXT,
  origin TEXT,                              -- backlog | trends | llm
  script_json TEXT,
  sources_json TEXT,
  assets_json TEXT,                         -- ressources utilisées + licences
  final_path TEXT,
  duration_s REAL,
  title TEXT,
  description TEXT,
  hashtags TEXT,
  qc_json TEXT,
  status TEXT NOT NULL DEFAULT 'planned',
  cost_usd REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',   -- pending | running | done | failed | dead | blocked
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL,
  next_run_at REAL NOT NULL,
  locked_at REAL,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(video_id, stage)
);
CREATE TABLE IF NOT EXISTS publications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  status TEXT NOT NULL,                     -- dry_run | scheduled | uploaded_private | published | blocked_credentials | error
  remote_id TEXT,
  scheduled_at TEXT,
  published_at TEXT,
  response_json TEXT,
  UNIQUE(video_id, platform)
);
CREATE TABLE IF NOT EXISTS stats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, video_id TEXT NOT NULL, platform TEXT NOT NULL, source TEXT,
  views INTEGER, likes INTEGER, comments INTEGER, shares INTEGER, saves INTEGER,
  avg_watch_s REAL, completion_rate REAL, followers_gained INTEGER
);
CREATE TABLE IF NOT EXISTS costs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, video_id TEXT, platform TEXT, category TEXT NOT NULL, usd REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, agent TEXT NOT NULL, level TEXT NOT NULL, video_id TEXT, message TEXT NOT NULL, data_json TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, level TEXT NOT NULL, source TEXT NOT NULL, message TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS agents (
  name TEXT PRIMARY KEY, role TEXT, status TEXT, last_run TEXT, last_result TEXT
);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_video_id(niche: str) -> str:
    return f"{datetime.now(timezone.utc):%Y%m%d}-{niche}-{uuid.uuid4().hex[:6]}"


class DB:
    def __init__(self, path=None):
        self.path = path or (data_dir() / "studio.db")
        self.conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.log = get_logger("db")

    @contextmanager
    def tx(self):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def q(self, sql, *args):
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql, *args):
        r = self.conn.execute(sql, args).fetchone()
        return dict(r) if r else None

    # ---------- journal ----------
    def event(self, agent, message, level="INFO", video_id=None, **data):
        message = redact(message)
        self.conn.execute(
            "INSERT INTO events(ts,agent,level,video_id,message,data_json) VALUES(?,?,?,?,?,?)",
            (now_iso(), agent, level, video_id, message, redact(json.dumps(data, ensure_ascii=False)) if data else None),
        )
        self.log.log(getattr(__import__("logging"), level, 20), message, extra={"agent": agent, "video_id": video_id})

    def alert(self, source, message, level="warning"):
        exists = self.one("SELECT id FROM alerts WHERE resolved=0 AND source=? AND message=?", source, message)
        if not exists:
            self.conn.execute("INSERT INTO alerts(ts,level,source,message) VALUES(?,?,?,?)", (now_iso(), level, source, redact(message)))
            self.event(source, f"ALERTE {level}: {message}", level="WARNING")
        return not exists

    def agent_status(self, name, role, status, result=""):
        self.conn.execute(
            "INSERT INTO agents(name,role,status,last_run,last_result) VALUES(?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET role=excluded.role,status=excluded.status,last_run=excluded.last_run,last_result=excluded.last_result",
            (name, role, status, now_iso(), redact(result)[:500]),
        )

    def kv_get(self, key, default=None):
        r = self.one("SELECT value FROM kv WHERE key=?", key)
        return json.loads(r["value"]) if r else default

    def kv_set(self, key, value):
        self.conn.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    # ---------- vidéos ----------
    def create_video(self, niche, topic, topic_key, origin, **fields) -> str | None:
        """Crée la vidéo si le sujet n'a jamais été produit. Renvoie None en cas de doublon."""
        vid = fields.pop("id", None) or new_video_id(niche)
        try:
            cols = {"id": vid, "topic_key": topic_key, "niche": niche, "topic": topic, "origin": origin,
                    "created_at": now_iso(), "updated_at": now_iso(), **fields}
            self.conn.execute(
                f"INSERT INTO videos({','.join(cols)}) VALUES({','.join('?' * len(cols))})", tuple(cols.values())
            )
            return vid
        except sqlite3.IntegrityError:
            return None

    def update_video(self, vid, **fields):
        fields["updated_at"] = now_iso()
        sets = ",".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE videos SET {sets} WHERE id=?", (*fields.values(), vid))

    def video(self, vid):
        return self.one("SELECT * FROM videos WHERE id=?", vid)

    # ---------- coûts ----------
    def add_cost(self, category, usd, video_id=None, platform=None):
        if usd <= 0:
            return
        self.conn.execute("INSERT INTO costs(ts,video_id,platform,category,usd) VALUES(?,?,?,?,?)", (now_iso(), video_id, platform, category, usd))
        if video_id:
            self.conn.execute("UPDATE videos SET cost_usd=cost_usd+? WHERE id=?", (usd, video_id))

    def spend_since(self, iso_prefix: str) -> float:
        r = self.one("SELECT COALESCE(SUM(usd),0) s FROM costs WHERE ts>=?", iso_prefix)
        return float(r["s"])

    # ---------- file de tâches ----------
    def enqueue(self, video_id, stage, delay_s=0, reset=False):
        """Ajoute une tâche (idempotent). reset=True relance une étape déjà terminée (après une reprise en amont)."""
        mx = settings()["retry"]["max_attempts"]
        if reset:
            self.conn.execute("UPDATE jobs SET status='pending', attempts=0, last_error=NULL, next_run_at=?, updated_at=? "
                              "WHERE video_id=? AND stage=? AND status IN ('done','dead','blocked')", (time.time() + delay_s, now_iso(), video_id, stage))
        self.conn.execute(
            "INSERT OR IGNORE INTO jobs(video_id,stage,status,attempts,max_attempts,next_run_at,created_at,updated_at) "
            "VALUES(?,?, 'pending', 0, ?, ?, ?, ?)",
            (video_id, stage, mx, time.time() + delay_s, now_iso(), now_iso()),
        )

    def claim_next(self):
        """Verrouille atomiquement la prochaine tâche exécutable (pas de double exécution)."""
        with self.tx() as c:
            r = c.execute(
                "SELECT * FROM jobs WHERE status='pending' AND next_run_at<=? ORDER BY next_run_at, id LIMIT 1", (time.time(),)
            ).fetchone()
            if not r:
                return None
            c.execute("UPDATE jobs SET status='running', locked_at=?, attempts=attempts+1, updated_at=? WHERE id=?", (time.time(), now_iso(), r["id"]))
            job = dict(r)
            job["attempts"] += 1
            return job

    def finish(self, job_id):
        self.conn.execute("UPDATE jobs SET status='done', locked_at=NULL, last_error=NULL, updated_at=? WHERE id=?", (now_iso(), job_id))

    def fail(self, job, error: str, retryable=True):
        """Échec : nouvelle tentative avec attente exponentielle, ou abandon (dead) après max_attempts."""
        error = redact(error)[:2000]
        base = settings()["retry"]["backoff_base_s"]
        if retryable and job["attempts"] < job["max_attempts"]:
            delay = base * (2 ** (job["attempts"] - 1))
            self.conn.execute(
                "UPDATE jobs SET status='pending', locked_at=NULL, last_error=?, next_run_at=?, updated_at=? WHERE id=?",
                (error, time.time() + delay, now_iso(), job["id"]),
            )
            return "retry", delay
        status = "dead" if retryable else "blocked"
        self.conn.execute("UPDATE jobs SET status=?, locked_at=NULL, last_error=?, updated_at=? WHERE id=?", (status, error, now_iso(), job["id"]))
        return status, 0

    def recover_stale(self, minutes: int) -> int:
        """Remet en file les tâches restées 'running' (processus tué, panne machine)."""
        cutoff = time.time() - minutes * 60
        cur = self.conn.execute(
            "UPDATE jobs SET status='pending', locked_at=NULL, last_error='reprise après verrou expiré', next_run_at=?, updated_at=? "
            "WHERE status='running' AND locked_at<?",
            (time.time(), now_iso(), cutoff),
        )
        return cur.rowcount

    def job_counts(self):
        return {r["status"]: r["n"] for r in self.q("SELECT status, COUNT(*) n FROM jobs GROUP BY status")}
