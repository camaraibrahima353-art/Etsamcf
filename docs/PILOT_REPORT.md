# Rapport du pilote (10 vidéos) — 22/10/2026

## Ce qui a été produit et vérifié

10 vidéos originales, 10 niches, produites de bout en bout par le pipeline (`python -m studio run --videos 10`)
dans le conteneur de développement : 50 tâches terminées, 0 échec, ~5 min 30 au total (≈ 33 s par vidéo).

| Vidéo | Niche | Format | Accroche | Durée | Volume | Scènes | QC |
|---|---|---|---|---|---|---|---|
| 20261022-science-6196e5 | science | fait surprenant | chiffre | 30,5 s | -15,0 LUFS | 7 | ✅ |
| 20261022-histoire-952759 | histoire | histoire | question | 28,2 s | -15,0 | 6 | ✅ |
| 20261022-espace-530cdb | espace | fait surprenant | affirmation choc | 32,3 s | -15,0 | 6 | ✅ |
| 20261022-finance-1be5fd | finance | mini-tuto | promesse | 30,0 s | -15,0 | 6 | ✅ (avertissement pédagogique présent) |
| 20261022-tech_ia-32d37f | tech & IA | mythe/réalité | mythe | 30,5 s | -15,1 | 6 | ✅ |
| 20261022-psycho-83c068 | psycho | histoire | question | 32,1 s | -15,0 | 6 | ✅ |
| 20261022-langues-1f160c | anglais | liste | défi | 26,9 s | -15,0 | 5 | ✅ (orthographe : mots anglais signalés, non bloquant) |
| 20261022-quiz-ddd3bc | quiz | quiz | défi | 28,6 s | -15,1 | 6 | ✅ |
| 20261022-afrique-eec8a9 | afrique | fait surprenant | question | 31,6 s | -14,9 | 6 | ✅ |
| 20261022-maths-87a561 | maths | mini-tuto | promesse | 30,3 s | -15,1 | 6 | ✅ |

Contrôles appliqués à chaque fichier (ffprobe / ebur128 / blackdetect) : 1080x1920, H.264 yuv420p 30 i/s, AAC,
durée 12-90 s, < 287 Mo, -14 LUFS ±2,5, < 5 % d'écran noir, sources https, aucun terme interdit, licences connues,
mention IA. Taille moyenne ≈ 2,8 Mo. Inspection visuelle de planches-contacts : deux défauts corrigés avant le rendu
final (pastille de niche qui chevauchait le compteur, point d'interrogation décoratif sous le texte).

Vérification éditoriale (par Claude, avant production) : 4 corrections factuelles appliquées — titre « 90 % des
gens » remplacé (non sourcé), « jour sur Vénus » précisé (rotation sidérale 243 j vs jour solaire ≈ 117 j),
statistique « moyenne » remplacée par « autour de » (médianes dans l'étude de 1974), localisation de Zanzibar.

## Tests de robustesse (preuves dans data/logs/studio.jsonl)

| Test | Résultat |
|---|---|
| Panne simulée au montage (`STUDIO_INJECT_FAILURE=edit:1`) | échec → `retry dans 60s` → réussi à la 2e tentative, QC et publication relancés |
| Processus tué (`kill -9`) pendant un montage | tâche restée `running` → remise en file par l'agent J (« 1 tâche bloquée remise en file ») → terminée |
| Deux passages simultanés | le second s'arrête : « un autre passage est déjà en cours » |
| Doublons | 3e passage : 0 vidéo planifiée (sujets déjà produits) |
| Arrêt général (`stop`) | « production stopped — aucun travail lancé » |
| Plafond de dépense (5 $ > 2 $/jour) | pause automatique + alerte critique ; reprise par `resume` |
| Tests automatisés | 11/11 (`pytest`), dont un pipeline complet avec panne et reprise |

## Limites constatées

- **Voix** : jugée « pas du tout bonne » à l'écoute. Le pilote local utilise **espeak-ng** (voix robotique) car Hugging Face est bloqué dans le conteneur ;
  sur GitHub Actions la voix neuronale **Piper fr_FR-siwis-medium** est téléchargée automatiquement. Une voix premium
  (ElevenLabs ≈ 0,02 $/vidéo) améliorerait nettement la rétention. Correctif livré : moteur ElevenLabs intégré (activé dès que le secret
  `ELEVENLABS_API_KEY` existe) et blocage par le QC de toute publication réelle en voix espeak-ng.
- **Visuels** : procéduraux (texte animé sur fonds abstraits). Propres et libres de droits, mais moins captivants que
  des plans illustratifs ; c'est le principal levier d'amélioration (génération d'images/vidéo IA sur les niches gagnantes).
- **Aucune statistique de performance** : rien n'a été publié (mode `dry_run`, pas d'identifiants). Les comparaisons
  accroches/durées/niches sont **prêtes à être mesurées**, pas encore mesurées.
- Volume final à -15 LUFS (limiteur) au lieu de -14 : dans la tolérance, différence imperceptible sur mobile.

## Stratégie après le pilote

1. Publier les 10 vidéos en privé/brouillon pour valider les intégrations, puis en public sur 1 compte par plateforme.
2. Après 7 jours : saisir les statistiques (API ou `data/stats/manual.csv`) ; l'agent I recalcule les poids de niche
   (bornés entre 0,5 et 2).
3. Garder les 4 niches et les 2 types d'accroche les plus performants, en conservant 30 % d'exploration.
4. Ajouter la clé API Claude pour que le scénariste écrive à partir des tendances quand la réserve est vide.

## Vérification sur le serveur (GitHub Actions)

| Exécution | Déclencheur | Résultat |
|---|---|---|
| [39731006867](https://github.com/camaraibrahima353-art/Etsamcf/actions/runs/39731006867) | manuel | ✅ 1 min 40 ; voix Piper téléchargée et mise en cache ; 2 vidéos (histoire, science) |
| [39773054799](https://github.com/camaraibrahima353-art/Etsamcf/actions/runs/39773054799) | **planifié (cron)** | ✅ « état restauré depuis le passage 39731006867 » ; 2 nouvelles vidéos (espace, tech) ; aucun doublon ; 10 tâches, 0 échec |

Remarque : GitHub retarde ou saute parfois des déclenchements planifiés en période de forte charge (le créneau de
06:17 UTC n'a pas été exécuté, celui de 12:17 l'a été à 11:46). Les passages manqués ne font perdre aucune donnée :
le suivant reprend la file là où elle en était.

## Réserve de scripts

20 scripts supplémentaires (2 par niche) ajoutés dans `backlog/queue/`, sources vérifiées par recherche web ; corrections
apportées avant validation : origine de l'effet Zeigarnik (Kurt Lewin, Berlin), datation du « Sahara vert »,
formulation du titre sur la tour Eiffel. Rendu de contrôle des 20 scripts : 18 validés du premier coup, 2 bloqués par le
QC sur le mot « garanti » (employé dans une négation) puis reformulés et validés : 20/20 prêts. Autonomie : ≈ 13 passages, soit 3 jours à 4 passages par jour.
