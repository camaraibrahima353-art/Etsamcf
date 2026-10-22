"""Synthèse vocale locale et gratuite : Piper (voix neuronale) ou espeak-ng (secours)."""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

from ..config import ROOT, settings

PIPER_LICENSES = {
    # Licence de la voix à vérifier dans MODEL_CARD du dépôt rhasspy/piper-voices avant usage commercial.
    "fr_FR-siwis-medium": "Piper (MIT) + voix SIWIS (CC BY 4.0, attribution requise)",
}


def _piper_model() -> Path | None:
    p = ROOT / settings()["voice"]["piper_model"]
    return p if p.exists() and p.with_suffix(".onnx.json").exists() else None


def engine() -> str:
    eng = settings()["voice"]["engine"]
    if eng == "auto":
        return "piper" if _piper_model() else "espeak-ng"
    return eng


def license_note() -> str:
    if engine() == "piper":
        return PIPER_LICENSES.get(_piper_model().stem, "Piper (MIT) + licence de la voix : voir MODEL_CARD")
    return "espeak-ng (GPL-3.0 pour le logiciel ; l'audio produit n'est pas soumis à la GPL)"


_voice_cache = {}


def synth(text: str, out_wav: Path) -> float:
    """Génère `out_wav` (mono 44,1 kHz) et renvoie sa durée en secondes."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    raw = out_wav.with_suffix(".raw.wav")
    if engine() == "piper":
        from piper import PiperVoice

        model = _piper_model()
        voice = _voice_cache.get(model) or PiperVoice.load(str(model))
        _voice_cache[model] = voice
        with wave.open(str(raw), "wb") as wf:
            voice.synthesize_wav(text, wf)
    else:
        if not shutil.which("espeak-ng"):
            raise RuntimeError("aucun moteur TTS disponible (installer espeak-ng ou un modèle Piper)")
        v = settings()["voice"]
        subprocess.run(["espeak-ng", "-v", v["espeak_voice"], "-s", str(v["espeak_speed"]), "-w", str(raw), text],
                       check=True, capture_output=True)
    # rééchantillonnage + léger traitement voix (passe-haut, compression douce)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
                    "-af", "highpass=f=80,acompressor=threshold=-18dB:ratio=3:attack=5:release=80",
                    "-ar", "44100", "-ac", "1", str(out_wav)], check=True)
    raw.unlink(missing_ok=True)
    with wave.open(str(out_wav)) as wf:
        return wf.getnframes() / wf.getframerate()
