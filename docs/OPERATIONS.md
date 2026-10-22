# Exploitation

## Commandes
```bash
pip install -r requirements.txt            # + apt : ffmpeg espeak-ng fonts-inter
python -m studio run [--videos N]          # un passage complet
python -m studio status                    # état, tâches, santé
python -m studio pause|resume|stop --reason "..."
python -m studio requeue <video_id> <write|direct|edit|qc|publish>
python -m studio dashboard                 # data/reports/dashboard.html + rapport du jour
python -m studio serve --port 8765         # tableau de bord local avec boutons de contrôle
python -m studio alerts                    # issues GitHub pour les alertes critiques
python -m pytest -q tests
```

## Sur GitHub Actions
- Workflow **studio** : toutes les 6 h (00:17, 06:17, 12:17, 18:17 UTC) ; bouton *Run workflow* avec l'entrée
  `action` = run / pause / resume / stop / status.
- **Arrêt d'urgence** : Settings → Variables → `STUDIO_STATE=stopped` (prioritaire sur tout), ou désactiver le workflow.
- Vidéos : artefact `videos-<run_id>` de chaque exécution (30 jours). État : artefact `studio-state` (90 jours).
  Le dépôt étant public, ces artefacts sont visibles par les utilisateurs GitHub connectés (aucun secret dedans).
- Résumé du passage : onglet *Summary* de l'exécution. Alertes critiques : issues étiquetées `studio-alerte`.

## Alimenter la production
- Sans `ANTHROPIC_API_KEY` : le studio consomme la réserve `backlog/` (2 vidéos par passage) et lève une alerte
  quand il reste moins de 3 scripts. Pour la réapprovisionner : dans une session Claude Code, demander au sous-agent
  `studio-scenariste` d'écrire N scripts dans `backlog/queue/`, puis pousser.
- Avec `ANTHROPIC_API_KEY` (secret) : quand la réserve est vide, le stratège choisit des sujets dans les tendances et
  le scénariste les rédige via l'API (≈ 0,05 $ / script, plafonné par le budget).

## Statistiques manuelles (avant d'avoir les API)
Ajouter des lignes à `data/stats/manual.csv` :
`video_id,platform,views,likes,comments,shares,saves,avg_watch_s,completion_rate,followers_gained`.

## Incidents
| Symptôme | Action |
|---|---|
| Alerte « PRODUCTION SUSPENDUE » | Lire la cause (budget, taux d'échec) ; corriger ; `action=resume` |
| Tâche `dead` | `requeue` après correction ; voir `last_error` dans le tableau de bord |
| Vidéo `blocked_qc` | Lire `data/projects/<id>/qc.json`, corriger le script, `requeue <id> write` |
| `blocked_credentials` | Ajouter les secrets de la plateforme (docs/PLATFORMS.md) |
| Réserve vide | Ajouter des scripts ou la clé API |

## Montée en charge
Après le pilote : `videos_per_run` 2 → 3, `max_videos_per_day` 10 → 12, en surveillant la complétion moyenne.
Ne monter que si les vidéos du pilote ont des statistiques mesurées ; ne jamais relever les plafonds de dépenses sans décision humaine.
