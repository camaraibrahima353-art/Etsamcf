"""Tests : file de tâches, reprise après panne, idempotence, kill switch, budget, clients de publication (simulés)."""
import json
import os
import shutil
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def studio(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DATA_DIR", str(tmp_path / "data"))
    ctl = ROOT / "config" / "control.yaml"
    saved = ctl.read_text()
    from studio import config
    config.settings.cache_clear()
    import logging
    logging.getLogger("studio").handlers.clear()
    from studio.db import DB
    db = DB()
    yield db
    ctl.write_text(saved)
    logging.getLogger("studio").handlers.clear()


def test_topic_key_dedup(studio):
    from studio.schema import topic_key
    k1 = topic_key("science", "La pieuvre a trois cœurs !")
    k2 = topic_key("science", "la PIEUVRE a trois coeurs")
    assert k1 == k2
    assert studio.create_video("science", "x", k1, "test") is not None
    assert studio.create_video("science", "x", k1, "test") is None  # doublon refusé


def test_queue_retry_backoff_and_dead(studio):
    from studio.config import settings
    vid = studio.create_video("science", "t", "k", "test")
    studio.enqueue(vid, "write")
    studio.enqueue(vid, "write")  # idempotent
    assert studio.q("SELECT COUNT(*) n FROM jobs")[0]["n"] == 1
    for attempt in range(1, settings()["retry"]["max_attempts"] + 1):
        studio.conn.execute("UPDATE jobs SET next_run_at=0")
        job = studio.claim_next()
        assert job and job["attempts"] == attempt
        assert studio.claim_next() is None  # verrou : pas de double exécution
        outcome, delay = studio.fail(job, "boom")
    assert outcome == "dead"
    assert studio.one("SELECT status FROM jobs")["status"] == "dead"


def test_stale_lock_recovery(studio):
    vid = studio.create_video("science", "t", "k2", "test")
    studio.enqueue(vid, "write")
    job = studio.claim_next()
    studio.conn.execute("UPDATE jobs SET locked_at=? WHERE id=?", (time.time() - 3600, job["id"]))
    assert studio.recover_stale(30) == 1
    assert studio.claim_next()["id"] == job["id"]


def test_budget_auto_pause(studio):
    from studio.agents import sysadmin
    from studio.agents.orchestrator import effective_state
    studio.add_cost("llm_script", 999.0)
    rep = sysadmin.run(studio)
    assert "plafond" in rep["paused_reason"]
    assert effective_state(studio)[0] == "paused"


def test_secret_redaction(monkeypatch):
    from studio.log import redact
    monkeypatch.setenv("FB_PAGE_TOKEN", "EAAsupersecretvalue123456789")
    s = redact("token=EAAsupersecretvalue123456789 key sk-ant-api03-abcdefghijkl Bearer abcdefghijklmnop1234")
    assert "supersecret" not in s and "abcdefghijkl" not in s


class FakeResp:
    def __init__(self, data=None, headers=None, ok=True):
        self._d, self.headers, self.ok = data or {}, headers or {}, ok

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def _do(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for frag, resp in self.routes:
            if frag in url:
                return resp
        raise AssertionError(f"URL inattendue {url}")

    def post(self, url, **kw):
        return self._do("POST", url, **kw)

    def put(self, url, **kw):
        return self._do("PUT", url, **kw)

    def get(self, url, **kw):
        return self._do("GET", url, **kw)


META = {"title": "Titre", "description": "Desc", "hashtags": ["#a", "#shorts"]}


def test_youtube_upload_payload(tmp_path, monkeypatch):
    from studio.platforms import youtube
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        monkeypatch.setenv(k, "x" * 12)
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 100)
    s = FakeSession([("oauth2", FakeResp({"access_token": "tok"})),
                     ("upload/youtube", FakeResp(headers={"Location": "https://upload.example/session"})),
                     ("upload.example", FakeResp({"id": "abc", "status": {"privacyStatus": "private"}}))])
    r = youtube.upload(f, META, privacy="private", publish_at="2026-10-23T17:00+00:00", session=s)
    body = json.loads(s.calls[1][2]["data"])
    assert body["status"]["containsSyntheticMedia"] is True
    assert body["status"]["publishAt"] == "2026-10-23T17:00+00:00"
    assert r["remote_id"] == "abc"


def test_tiktok_direct_forces_private_when_unaudited(tmp_path, monkeypatch):
    from studio.platforms import tiktok
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "tok" * 5)
    monkeypatch.delenv("TIKTOK_REFRESH_TOKEN", raising=False)
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 100)
    s = FakeSession([("creator_info", FakeResp({"data": {"privacy_level_options": ["SELF_ONLY"]}, "error": {"code": "ok"}})),
                     ("video/init", FakeResp({"data": {"publish_id": "p1", "upload_url": "https://up.tiktok/x"}, "error": {"code": "ok"}})),
                     ("up.tiktok", FakeResp())])
    r = tiktok.upload(f, META, mode="direct", want_public=True, session=s)
    body = s.calls[1][2]["json"]
    assert body["post_info"]["privacy_level"] == "SELF_ONLY"
    assert body["post_info"]["is_aigc"] is True
    assert s.calls[2][2]["headers"]["Content-Range"] == "bytes 0-99/100"
    assert r["remote_id"] == "p1"


def test_facebook_reels_three_phases(tmp_path, monkeypatch):
    from studio.platforms import facebook
    monkeypatch.setenv("FB_PAGE_ID", "123")
    monkeypatch.setenv("FB_PAGE_TOKEN", "EAA" + "x" * 30)
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 100)

    class S(FakeSession):
        n = 0

        def post(self, url, **kw):
            if "video_reels" in url:
                S.n += 1
                self.calls.append(("POST", url, kw))
                return FakeResp({"video_id": "v9"} if S.n == 1 else {"success": True})
            return super().post(url, **kw)

    s = S([("rupload", FakeResp())])
    r = facebook.upload(f, META, state="DRAFT", session=s)
    phases = [c[2].get("data", {}).get("upload_phase") for c in s.calls if "video_reels" in c[1]]
    assert phases == ["start", "finish"] and r["remote_id"] == "v9"


def test_missing_credentials_is_explicit(monkeypatch):
    from studio.platforms import MissingCredentials, youtube
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(MissingCredentials):
        youtube.access_token()


def test_llm_structured_call_with_fake_client():
    from studio import llm
    from studio.schema import SCRIPT_SCHEMA

    class Usage:
        input_tokens, output_tokens = 1000, 1000

    class Block:
        type, text = "text", json.dumps({"ok": True})

    class Resp:
        stop_reason, usage, content = "end_turn", Usage(), [Block()]

    class Msgs:
        def create(self, **kw):
            assert kw["output_config"]["format"]["schema"] is SCRIPT_SCHEMA
            return Resp()

    class C:
        class beta:
            messages = Msgs()

    data, cost = llm.generate_json("sys", "p", SCRIPT_SCHEMA, client=C())
    assert data == {"ok": True} and abs(cost - 0.024) < 1e-9


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg requis")
def test_full_pipeline_with_injected_failure(studio, monkeypatch):
    """Pipeline complet sur 1 vidéo, avec panne simulée au montage puis reprise automatique."""
    from studio.agents.orchestrator import process_queue, run_cycle
    from studio.config import settings
    settings()["retry"]["backoff_base_s"] = 0
    monkeypatch.setenv("STUDIO_INJECT_FAILURE", "edit:1")
    monkeypatch.delenv("_injected_edit", raising=False)
    s = run_cycle(studio, n_videos=1, skip_trends=True)
    assert s["queue"]["failed"] == 1  # la panne simulée a bien eu lieu
    process_queue(studio, time.time() + 600)  # passage suivant : reprise
    v = studio.q("SELECT * FROM videos")[0]
    assert v["status"] == "ready", v["status"]
    assert studio.one("SELECT attempts FROM jobs WHERE stage='edit'")["attempts"] == 2
    from studio.config import data_dir
    assert (data_dir() / v["final_path"]).exists()
    pubs = studio.q("SELECT status FROM publications")
    assert pubs and all(p["status"] == "dry_run" for p in pubs)
