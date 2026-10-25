"""Images de scène générées par IA, avec personnages (FLUX.1 [schnell] via l'API officielle Replicate).

Un présentateur récurrent (config `ai_images.host`) ouvre et ferme chaque vidéo ; les autres scènes mettent en
scène le sujet avec des personnages expressifs. Jamais de personne réelle vivante identifiable.
Clé : https://replicate.com/account/api-tokens -> secret REPLICATE_API_TOKEN. Coût ≈ 0,003 $ par image.
Aperçu sans clé : STUDIO_AI_BACKEND=pollinations (service gratuit, même famille de modèle FLUX, sans garantie de
disponibilité) — réservé à la commande `preview`, jamais à la production."""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from urllib.parse import quote

import requests

from ..config import settings

API = "https://api.replicate.com/v1"
LICENSE = "Image générée par IA (FLUX.1 [schnell], licence Apache 2.0, usage commercial autorisé) via Replicate"


def cfg() -> dict:
    return settings().get("ai_images", {})


def backend() -> str:
    return os.environ.get("STUDIO_AI_BACKEND", "replicate")


def available() -> bool:
    has_key = bool(os.environ.get("REPLICATE_API_TOKEN")) or backend() == "pollinations"
    return has_key and settings()["visuals"]["provider"] in ("auto", "ai")


def _seed(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest()[:8], 16)


def scene_prompt(script: dict, index: int) -> str:
    """Prompt anglais : présentateur pour l'accroche et la conclusion, personnages du sujet entre les deux."""
    c = cfg()
    sc = script["scenes"][index]
    subject = sc["visual"].get("scene") or sc["visual"].get("query") or script["topic"]
    last = index == len(script["scenes"]) - 1
    if index == 0:
        body = f"{c['host']}, looking amazed and pointing at {subject}, close-up, dramatic and curious mood"
    elif last:
        body = f"{c['host']}, smiling and asking the viewer a question, with {subject} in the background"
    else:
        body = f"{subject}, featuring expressive characters reacting, storytelling scene"
    return (f"{c['style']}. {body}. Main characters in the lower two thirds of the frame, calm empty area at the top, "
            "vertical 9:16 composition, no text, no letters, no words, no logo, no watermark")


def _wait(pred: dict, headers: dict, session, timeout_s=120) -> dict:
    end = time.time() + timeout_s
    while pred.get("status") not in ("succeeded", "failed", "canceled"):
        if time.time() > end:
            raise TimeoutError("génération d'image trop longue")
        time.sleep(2)
        r = session.get(pred["urls"]["get"], headers=headers, timeout=30)
        r.raise_for_status()
        pred = r.json()
    if pred["status"] != "succeeded":
        raise RuntimeError(f"génération d'image {pred['status']} : {str(pred.get('error'))[:150]}")
    return pred


def generate(prompt: str, dest: Path, seed_text: str, session=requests) -> dict:
    """Génère une image verticale et la télécharge : {kind, path, id, url, author, license, query}."""
    if dest.exists() and dest.stat().st_size > 0:  # reprise après panne : pas de double facturation
        return _media(dest, prompt)
    if backend() == "pollinations":
        return _pollinations(prompt, dest, seed_text, session)
    headers = {"Authorization": f"Bearer {os.environ['REPLICATE_API_TOKEN']}", "Prefer": "wait=60"}
    body = {"input": {"prompt": prompt, "aspect_ratio": "9:16", "output_format": "jpg", "output_quality": 92,
                      "num_outputs": 1, "seed": _seed(seed_text), "go_fast": True}}
    r = session.post(f"{API}/models/{cfg()['model']}/predictions", headers=headers, json=body, timeout=90)
    r.raise_for_status()
    pred = _wait(r.json(), headers, session)
    out = pred["output"]
    url = out[0] if isinstance(out, list) else out
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = session.get(url, timeout=60)
    img.raise_for_status()
    dest.write_bytes(img.content)
    return _media(dest, prompt)


def _pollinations(prompt: str, dest: Path, seed_text: str, session) -> dict:
    """Aperçu gratuit sans clé (image.pollinations.ai, modèle FLUX), avec quelques nouvelles tentatives."""
    url = (f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=768&height=1344&model=flux"
           f"&seed={_seed(seed_text)}&nologo=true&private=true")
    last = None
    for attempt in range(4):
        try:
            r = session.get(url, timeout=180)
            if r.ok and r.headers.get("content-type", "").startswith("image/"):
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(r.content)
                return _media(dest, prompt)
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = type(e).__name__
        time.sleep(8 * (attempt + 1))
    raise RuntimeError(f"aperçu pollinations indisponible ({last})")


def _media(path: Path, prompt: str) -> dict:
    return {"kind": "photo", "path": str(path), "id": f"ai-{path.stem}", "url": None, "author": "IA (FLUX.1 schnell)",
            "license": LICENSE, "query": prompt[:200], "ai": True}
