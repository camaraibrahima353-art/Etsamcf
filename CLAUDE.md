# Studio IA Shorts — consignes pour Claude Code

- Code Python dans `studio/`, commentaires et messages en français, style existant (fonctions courtes, docstrings brèves).
- Tests : `python -m pytest -q tests` (FFmpeg et espeak-ng requis). Les lancer avant tout commit.
- Rôles : utiliser les sous-agents `.claude/agents/studio-*.md` (A à J) selon la tâche.
- Nouveaux scripts vidéo : `backlog/queue/*.json`, schéma `studio/schema.py`, faits vérifiés sur les sources citées.
- Ne jamais : commiter `data/`, `models/` ou `.env` ; relever les plafonds de `config/studio.yaml` (budget) sans accord ;
  passer `publishing.mode` à `public` ; écrire un secret dans un fichier ou un journal.
