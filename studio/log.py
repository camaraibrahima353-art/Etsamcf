"""Journalisation JSON avec masquage systématique des secrets."""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

_SECRET_ENV_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD")
_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{12,}"),
    re.compile(r"(?i)(access_token=)[^&\s\"]+"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"EAA[A-Za-z0-9]{20,}"),  # jetons Meta
    re.compile(r"ya29\.[A-Za-z0-9_\-]{20,}"),  # jetons Google OAuth
]


def redact(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    for name, value in os.environ.items():
        if value and len(value) >= 8 and any(h in name.upper() for h in _SECRET_ENV_HINTS):
            text = text.replace(value, "***")
    for p in _PATTERNS:
        text = p.sub(lambda m: (m.group(1) if m.groups() else "") + "***", text)
    return text


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "agent": getattr(record, "agent", record.name),
            "msg": redact(record.getMessage()),
        }
        if getattr(record, "video_id", None):
            payload["video_id"] = record.video_id
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "studio") -> logging.Logger:
    logger = logging.getLogger("studio")
    if not logger.handlers:
        from .config import data_dir

        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(data_dir() / "logs" / "studio.jsonl", encoding="utf-8")
        fh.setFormatter(_JsonFormatter())
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(_JsonFormatter())
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger.getChild(name) if name != "studio" else logger
