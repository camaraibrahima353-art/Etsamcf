"""Chargement de la configuration et de l'interrupteur général."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv():
    """Charge .env (local ou VPS) sans écraser les variables déjà définies. Jamais commité (.gitignore)."""
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def settings() -> dict:
    cfg = _load(ROOT / os.environ.get("STUDIO_CONFIG", "config/studio.yaml"))
    cfg["niches"] = _load(ROOT / cfg["niches_file"])["niches"]
    return cfg


def data_dir() -> Path:
    d = ROOT / os.environ.get("STUDIO_DATA_DIR", settings()["studio"]["data_dir"])
    for sub in ("research", "scripts", "media", "projects", "final", "publications", "stats", "logs", "reports"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def niche(niche_id: str) -> dict:
    for n in settings()["niches"]:
        if n["id"] == niche_id:
            return n
    raise KeyError(f"niche inconnue : {niche_id}")


CONTROL_FILE = ROOT / "config" / "control.yaml"


def read_control() -> dict:
    """État de l'interrupteur. La variable STUDIO_STATE (ex. variable de dépôt GitHub) a priorité."""
    ctl = _load(CONTROL_FILE) if CONTROL_FILE.exists() else {"state": "running"}
    env_state = os.environ.get("STUDIO_STATE")
    if env_state:
        ctl["state"] = env_state
        ctl["reason"] = "variable STUDIO_STATE"
    return ctl


def write_control(state: str, reason: str = "", publishing_enabled: bool | None = None) -> dict:
    ctl = read_control() if CONTROL_FILE.exists() else {}
    ctl["state"] = state
    ctl["reason"] = reason
    if publishing_enabled is not None:
        ctl["publishing_enabled"] = publishing_enabled
    ctl.setdefault("publishing_enabled", True)
    with open(CONTROL_FILE, "w", encoding="utf-8") as f:
        f.write("# Interrupteur général (voir docs/OPERATIONS.md). running | paused | stopped\n")
        yaml.safe_dump(ctl, f, allow_unicode=True, sort_keys=False)
    return ctl
