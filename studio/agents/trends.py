"""Agent B — Chercheur de tendances. Sources légales et officielles uniquement :
- API Wikimedia Pageviews (articles les plus consultés, sans clé) ;
- API YouTube Data v3 `videos.list?chart=mostPopular` (si YOUTUBE_API_KEY) ;
- les performances internes du studio (agent I).
Aucun scraping de TikTok ou d'autres plateformes (interdit par leurs conditions)."""
from __future__ import annotations

import json
import os
from datetime import date, timedelta

import requests

from ..config import data_dir, settings
from ..log import redact

UA = {"User-Agent": "StudioIAShorts/0.1 (https://github.com/camaraibrahima353-art/Etsamcf; recherche de tendances)"}
SKIP = ("Spécial:", "Wikipédia:", "Fichier:", "Accueil", "Main_Page", "Special:", "Portail:", "Aide:")

KEYWORDS = {
    "science": ["biolog", "chimie", "physique", "animal", "corps", "cerveau", "virus", "océan"],
    "histoire": ["guerre", "empire", "roi", "reine", "révolution", "siècle", "bataille", "pharaon"],
    "espace": ["planète", "lune", "mars", "étoile", "nasa", "galaxie", "comète", "fusée", "astéroïde"],
    "finance": ["banque", "euro", "inflation", "bourse", "impôt", "salaire", "bitcoin"],
    "tech_ia": ["intelligence artificielle", "openai", "google", "apple", "iphone", "logiciel", "robot", "claude"],
    "psycho": ["psycholog", "biais", "émotion", "sommeil", "mémoire"],
    "langues": ["anglais", "langue", "mot"],
    "quiz": [],
    "afrique": ["afrique", "guinée", "sénégal", "mali", "côte d'ivoire", "cameroun", "maroc", "congo", "nigeria", "éthiopie"],
    "maths": ["mathémat", "nombre", "théorème", "pi"],
}


def guess_niche(term: str):
    t = term.lower()
    for niche, kws in KEYWORDS.items():
        if any(k in t for k in kws):
            return niche
    return None


def wikipedia_top(lang="fr", day: date | None = None, limit=60):
    day = day or (date.today() - timedelta(days=1))
    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{lang}.wikipedia/all-access/{day:%Y/%m/%d}"
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    items = []
    for a in r.json()["items"][0]["articles"]:
        name = a["article"]
        if name.startswith(SKIP) or name in ("-",):
            continue
        term = name.replace("_", " ")
        items.append({"term": term, "source": f"wikipedia-{lang}", "score": a["views"], "niche_guess": guess_niche(term),
                      "url": f"https://{lang}.wikipedia.org/wiki/{name}"})
        if len(items) >= limit:
            break
    return items


def youtube_popular(region="FR", limit=30):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return []
    r = requests.get("https://www.googleapis.com/youtube/v3/videos",
                     params={"part": "snippet,statistics", "chart": "mostPopular", "regionCode": region, "maxResults": limit, "key": key},
                     timeout=20)
    r.raise_for_status()
    return [{"term": v["snippet"]["title"], "source": f"youtube-mostPopular-{region}",
             "score": int(v["statistics"].get("viewCount", 0)), "niche_guess": guess_niche(v["snippet"]["title"]),
             "tags": v["snippet"].get("tags", [])[:8]} for v in r.json().get("items", [])]


def run(db, force=False) -> dict:
    today = date.today().isoformat()
    out = data_dir() / "research" / f"trends-{today}.json"
    if out.exists() and not force:
        return json.loads(out.read_text())
    report = {"date": today, "sources": [], "errors": [], "items": []}
    for name, fn in (("wikipedia-fr", lambda: wikipedia_top("fr")), ("wikipedia-en", lambda: wikipedia_top("en", limit=30)),
                     ("youtube-FR", youtube_popular)):
        try:
            items = fn()
            report["items"] += items
            report["sources"].append({"name": name, "count": len(items)})
        except Exception as e:  # source indisponible : on continue avec les autres
            report["errors"].append({"source": name, "error": redact(str(e))[:300]})
    by_niche = {}
    for it in report["items"]:
        if it["niche_guess"]:
            by_niche.setdefault(it["niche_guess"], []).append(it["term"])
    report["by_niche"] = {k: v[:10] for k, v in by_niche.items()}
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    db.event("B_tendances", f"{len(report['items'])} signaux collectés, {len(report['errors'])} source(s) en erreur",
             sources=report["sources"], errors=report["errors"])
    if not report["items"]:
        db.alert("B_tendances", "aucune source de tendances joignable (réseau ?)", "warning")
    return report
