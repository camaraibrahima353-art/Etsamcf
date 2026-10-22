"""Contrats de données échangés entre agents (JSON)."""
from __future__ import annotations

import hashlib
import re
import unicodedata

VISUAL_TYPES = ["title", "text", "bignumber", "question", "list", "reveal"]
FORMATS = ["fait_surprenant", "liste", "quiz", "histoire", "mini_tuto", "mythe_realite"]
HOOKS = ["question", "affirmation_choc", "chiffre", "defi", "mythe", "promesse"]

SCRIPT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["niche", "topic", "format", "hook_variant", "hook", "scenes", "title", "description", "hashtags", "sources"],
    "properties": {
        "niche": {"type": "string"},
        "topic": {"type": "string"},
        "format": {"type": "string", "enum": FORMATS},
        "hook_variant": {"type": "string", "enum": HOOKS},
        "hook": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["voice", "onscreen", "visual"],
                "properties": {
                    "voice": {"type": "string"},
                    "onscreen": {"type": "string"},
                    "visual": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["type", "accent", "query"],
                        "properties": {"type": {"type": "string", "enum": VISUAL_TYPES}, "accent": {"type": "string"},
                                       "query": {"type": "string", "description": "2 à 4 mots-clés EN ANGLAIS décrivant une vraie image/vidéo de la scène"}},
                    },
                },
            },
        },
        "title": {"type": "string"},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "url"],
                "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
            },
        },
    },
}


def validate_script(s: dict) -> list[str]:
    """Validation légère sans dépendance : renvoie la liste des problèmes."""
    errs = [f"champ manquant : {k}" for k in SCRIPT_SCHEMA["required"] if k not in s]
    if errs:
        return errs
    if not (3 <= len(s["scenes"]) <= 10):
        errs.append("3 à 10 scènes attendues")
    for i, sc in enumerate(s["scenes"]):
        if not sc.get("voice", "").strip():
            errs.append(f"scène {i} : voix vide")
        if sc.get("visual", {}).get("type") not in VISUAL_TYPES:
            errs.append(f"scène {i} : type visuel invalide")
        if len(sc.get("onscreen", "")) > 70:
            errs.append(f"scène {i} : texte à l'écran trop long (>70 caractères)")
    if s["format"] not in FORMATS:
        errs.append("format invalide")
    if s["hook_variant"] not in HOOKS:
        errs.append("type d'accroche invalide")
    if len(s["title"]) > 100:
        errs.append("titre > 100 caractères (limite YouTube)")
    return errs


def topic_key(niche: str, topic: str) -> str:
    """Clé d'unicité : même sujet normalisé => même clé => jamais produit deux fois."""
    t = unicodedata.normalize("NFKD", topic.lower().replace("œ", "oe").replace("æ", "ae")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    words = sorted(w for w in t.split() if len(w) > 3)
    return f"{niche}:" + hashlib.sha1(" ".join(words).encode()).hexdigest()[:16]
