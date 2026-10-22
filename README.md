# Studio IA Shorts

Studio automatisé de vidéos verticales courtes (TikTok, YouTube Shorts, Facebook Reels) : recherche de tendances →
sélection des sujets → scripts sourcés → voix et visuels → montage FFmpeg → contrôle qualité → publication via les
API officielles → analyse → amélioration. Fonctionne 24/7 sur GitHub Actions, sans machine allumée.

| Document | Contenu |
|---|---|
| [docs/RESEARCH.md](docs/RESEARCH.md) | Tendances, formats, outils, coûts, **top 10 des niches** |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Choix d'hébergement, pipeline, données, résilience |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Commandes, pause/arrêt, incidents, montée en charge |
| [docs/PLATFORMS.md](docs/PLATFORMS.md) | Activer YouTube, TikTok, Facebook (vos actions) |
| [docs/PILOT_REPORT.md](docs/PILOT_REPORT.md) | Résultats du pilote de 10 vidéos et tests de reprise |

## Démarrage rapide (local)
```bash
sudo apt install ffmpeg espeak-ng fonts-inter
pip install -r requirements.txt
python -m studio run --videos 2      # vidéos dans data/final/
python -m studio serve               # tableau de bord : http://127.0.0.1:8765
```

## Structure
```
studio/agents/   10 agents (A directeur … J admin)       .claude/agents/  sous-agents Claude Code équivalents
studio/media/    voix (Piper/espeak-ng), visuels, rendu   studio/platforms/ YouTube, TikTok, Facebook
config/          studio.yaml (budgets, quotas), niches.yaml, control.yaml (interrupteur)
backlog/         scripts validés en attente (pilot/, queue/)
.github/workflows/studio.yml   ordonnanceur 6 h       deploy/   option VPS (systemd)
```

Contenus créés avec l'aide de l'IA : la mention est appliquée sur chaque plateforme. Aucun contournement des
plateformes, aucune interaction artificielle, aucune ressource tierce sans licence.
