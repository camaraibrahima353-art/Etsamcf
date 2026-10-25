"""Agent D — Scénariste. Valide les scripts de la réserve ou en rédige de nouveaux via l'API Claude."""
from __future__ import annotations

import json

from .. import llm
from ..config import data_dir, niche
from ..schema import SCRIPT_SCHEMA, validate_script
from . import NonRetryable

SYSTEM = """Tu es le scénariste d'une chaîne francophone de vidéos verticales courtes (20 à 50 secondes).
Règles impératives :
- Accroche dans la première phrase (moins de 2 secondes à l'oral), sans mensonge ni promesse exagérée.
- 4 à 8 scènes. Chaque scène : une phrase de voix off (8 à 22 mots), un texte à l'écran de 2 à 6 mots, un type visuel.
- Structure : accroche -> contexte -> élément de curiosité (boucle ouverte) -> révélation -> conclusion ou question aux spectateurs.
- Faits uniquement vérifiables, avec 1 à 3 sources réelles et précises (Wikipédia, institutions, publications). Jamais d'URL inventée.
  Si tu n'es pas certain d'un fait, ne l'utilise pas.
- Aucun faux témoignage, aucun faux événement, aucun conseil financier ou médical personnalisé.
- Français correct, phrases courtes, écrites pour être lues par une synthèse vocale (chiffres en toutes lettres si ambigu).
- Pour chaque scène, `visual.query` : 2 à 4 mots-clés EN ANGLAIS pour trouver une vraie vidéo ou photo correspondante
  (ex. « octopus swimming », « pink lake salt workers »). L'accroche doit avoir l'image la plus frappante. Jamais de
  personne identifiable présentée comme liée au sujet si ce n'est pas le cas.
- Pour chaque scène, `visual.scene` : UNE phrase EN ANGLAIS décrivant l'illustration de la scène avec des personnages
  expressifs en action (ex. « a giant octopus with three glowing hearts hugging a surprised diver »). Le présentateur
  récurrent du studio apparaît automatiquement dans l'accroche et la conclusion : ne le décris pas. Jamais de personne réelle vivante ;
  les personnages historiques sont permis, représentés de façon fidèle et respectueuse.
- Titre <= 70 caractères, description de 1 à 2 phrases, 3 à 5 hashtags pertinents."""


def write_with_llm(video: dict, trends_context: str = "") -> tuple[dict, float]:
    n = niche(video["niche"])
    prompt = (f"Niche : {n['name']} (public : {n['audience']}).\nSujet ou tendance de départ : {video['topic']}\n"
              f"{trends_context}\nÉcris un script original. Champ niche = \"{video['niche']}\".")
    return llm.generate_json(SYSTEM, prompt, SCRIPT_SCHEMA)


def run(db, video_id: str):
    v = db.video(video_id)
    if v["script_json"]:
        script = json.loads(v["script_json"])
    else:
        try:
            script, cost = write_with_llm(v)
        except llm.LLMUnavailable as e:
            raise NonRetryable(str(e))
        db.add_cost("llm_script", cost, video_id)
    errs = validate_script(script)
    if errs:
        raise NonRetryable(f"script invalide : {errs}")
    if not script.get("sources"):
        raise NonRetryable("script sans source : refusé")
    (data_dir() / "scripts" / f"{video_id}.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    db.update_video(video_id, script_json=json.dumps(script, ensure_ascii=False), hook=script["hook"], hook_variant=script["hook_variant"],
                    format=script["format"], sources_json=json.dumps(script["sources"], ensure_ascii=False), status="scripted")
    return {"scenes": len(script["scenes"])}
