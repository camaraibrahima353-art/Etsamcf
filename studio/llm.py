"""Accès optionnel à l'API Claude (agents B, D). Sans ANTHROPIC_API_KEY, le studio fonctionne
sur sa réserve de scripts (backlog) et lève une alerte quand elle s'épuise."""
from __future__ import annotations

import json
import os

MODEL = os.environ.get("STUDIO_LLM_MODEL", "claude-opus-5-5")
PRICE_IN, PRICE_OUT = 4.00 / 1e6, 20.00 / 1e6  # USD par token (claude-opus-5-5)


class LLMUnavailable(RuntimeError):
    pass


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def generate_json(system: str, prompt: str, schema: dict, max_tokens: int = 16000, client=None) -> tuple[dict, float]:
    """Appel structuré : renvoie (objet JSON validé par le schéma, coût estimé en USD)."""
    if client is None:
        if not available():
            raise LLMUnavailable("ANTHROPIC_API_KEY absente : génération automatique de scripts désactivée")
        import anthropic

        client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        raise LLMUnavailable("le modèle a refusé la demande (sujet écarté)")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("réponse tronquée (max_tokens)")
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    cost = resp.usage.input_tokens * PRICE_IN + resp.usage.output_tokens * PRICE_OUT
    return json.loads(text), cost
