# Architecture

## Choix : hybride « GitHub Actions + dépôt GitHub », VPS en option

Inspection de l'environnement de développement (22/10/2026) : conteneur cloud Ubuntu 24.04, 4 vCPU, 15 Go RAM,
30 Go libres, **pas de GPU**, FFmpeg 6.1 et Python 3.13 présents, réseau sortant filtré (Wikimedia, Hugging Face,
API TikTok/Meta bloqués), conteneur **éphémère** (détruit après inactivité). Ce n'est donc pas un hôte 24/7.

| Option | Verdict |
|---|---|
| Local (votre ordinateur) | Possible (`python -m studio serve` + cron/systemd), mais dépend d'une machine allumée |
| **GitHub Actions** (retenu) | Gratuit et illimité pour un dépôt public, cron natif, aucune machine à entretenir, réseau ouvert |
| VPS (option) | 4-6 €/mois (2 vCPU / 4 Go suffisent) : `deploy/install_vps.sh` + `systemd` timer, si besoin de plus de 6 h/run ou de données privées |

Aucun GPU n'est nécessaire : rendu ≈ 30 s par vidéo de 30 s sur 4 vCPU.

## Pipeline

```
 ordonnanceur (cron 6 h)                         base SQLite (data/studio.db)
        │                                                    ▲
        ▼                                                    │
 A directeur ─► J admin (verrous, disque, budget, kill switch)
        │
        ├─► B tendances (Wikimedia, YouTube) ─► data/research/trends-*.json
        ├─► C stratégie (poids de niche, dédoublonnage, créneaux) ─► videos + jobs « write »
        │
        └─► file de tâches :  write ─► direct ─► edit ─► qc ─► publish
                              (D)       (E)       (F)     (G)    (H)
        ▼
 I analyste (API + CSV manuel) ─► niche_scores ─► réinjecté dans C au passage suivant
        ▼
 tableau de bord HTML + rapport quotidien + issues GitHub pour les alertes critiques
```

## Données conservées pour chaque vidéo (table `videos` + fichiers)

| Exigence | Emplacement |
|---|---|
| Identifiant unique | `videos.id` (`AAAAMMJJ-niche-xxxxxx`) |
| Niche, sujet, clé anti-doublon | `niche`, `topic`, `topic_key` (UNIQUE) |
| Sources | `sources_json` + description publiée |
| Script et accroche | `script_json`, `hook`, `hook_variant`, `data/scripts/<id>.json` |
| Ressources et licences | `assets_json`, `data/media/<id>/shotlist.json` |
| Fichier final + miniature | `data/final/<id>.mp4`, `.jpg` |
| Titre, description, hashtags | `title`, `description`, `hashtags` |
| Statuts production / publication | `videos.status`, table `publications` |
| Statistiques | table `stats` |
| Coûts | `videos.cost_usd`, table `costs` |
| Contrôle qualité | `qc_json`, `data/projects/<id>/qc.json` |

Dossiers : `data/research`, `scripts`, `media`, `projects` (montage), `final`, `publications`, `stats`, `logs`, `reports`.

## Résilience

- **File de tâches** SQLite avec verrou atomique (`BEGIN IMMEDIATE`), contrainte `UNIQUE(video_id, stage)`.
- **Reprises** : attente exponentielle (60 s, 120 s, 240 s), 3 tentatives, puis `dead` + alerte critique.
  Erreurs non réparables (clé absente, QC refusé) ⇒ `blocked` immédiatement, sans boucle.
- **Verrous expirés** : une tâche `running` depuis plus de 30 min (processus tué, panne) est remise en file.
- **Verrou global** `flock` : un seul orchestrateur à la fois ; `concurrency` côté GitHub Actions.
- **Écriture atomique** des vidéos (rendu dans `projects/`, puis déplacement).
- **Anti-doublon** : `topic_key` (sujet normalisé), publication idempotente par plateforme.
- **Passage borné** (25 min, 50 tâches max) : pas de boucle infinie.
- **Kill switch** : `config/control.yaml`, variable de dépôt `STUDIO_STATE`, commande `pause|resume|stop`,
  pause automatique sur plafond de dépense, taux d'échec > 50 % ou `STUDIO_SECURITY_HALT`.
- **Secrets** : uniquement variables d'environnement / secrets GitHub ; masquage dans tous les journaux (`studio/log.py`).

## Agents

Deux niveaux complémentaires :
1. **Agents d'exécution** (`studio/agents/*.py`) : déterministes, lancés par l'ordonnanceur, sans supervision.
2. **Sous-agents Claude Code** (`.claude/agents/studio-*.md`) : mêmes rôles, pour les tâches qui demandent du
   jugement lors d'une session Claude (écrire de nouveaux scripts, vérifier les faits, diagnostiquer une panne).
