# Résumé du projet — Studio IA Shorts

**Dépôt :** https://github.com/camaraibrahima353-art/Etsamcf (public, branche par défaut `claude/determined-galileo-938hma`)

## But
Un studio automatisé qui fabrique des vidéos verticales courtes en français (TikTok, YouTube Shorts, Facebook Reels),
24 h/24 sans ordinateur allumé : tendances → choix du sujet → script sourcé → voix + images → montage → contrôle
qualité → publication via les API officielles → statistiques → amélioration.

## Comment ça marche
- **Hébergement :** GitHub Actions (gratuit, dépôt public). Un passage toutes les 6 h, 2 vidéos par passage,
  10 vidéos/jour max. L'état (base SQLite) est conservé d'un passage à l'autre.
- **10 agents** (code Python + sous-agents Claude Code) : A directeur, B tendances, C stratégie, D scénariste,
  E réalisateur, F monteur, G contrôle qualité, H publication, I analyste, J administrateur.
- **Vidéos :** 1080x1920, 20-35 s, accroche en moins de 2 s, sous-titres mot à mot, barre de progression,
  musique synthétisée libre de droits, volume normalisé.
- **10 niches :** science, histoire, espace, finance personnelle, tech & IA, psychologie, anglais, quiz/énigmes,
  Afrique méconnue, maths.
- **Voix :** ElevenLabs (payant, naturelle) si la clé existe, sinon Piper (gratuite). La voix robotique de secours
  ne peut jamais être publiée.
- **Images :** vraies vidéos/photos Pexels (gratuit, usage commercial autorisé) derrière chaque scène ; l'accroche
  doit obligatoirement avoir une vraie image pour être publiée.
- **Sécurité :** plafonds de dépenses (2 $/jour, 30 $/mois) avec pause automatique, arrêt d'urgence, reprise après
  panne, aucun doublon, secrets jamais écrits dans le code, mention « contenu IA » sur chaque plateforme,
  aucune ruse contre les plateformes (pas de faux comptes ni de fausses vues).

## Ce qui est fait et vérifié
- Recherche documentée (tendances, outils, coûts, top 10 des niches) : `docs/RESEARCH.md`.
- Pilote de 10 vidéos produites et validées ; 30 scripts sourcés en réserve (≈ 3 jours d'autonomie).
- Tests : 13/13 ; reprise testée (panne simulée, processus tué, double lancement, budget dépassé, arrêt).
- Ordonnanceur vérifié : passages manuels et planifiés réussis sur GitHub, état restauré, pas de doublon.
- Tableau de bord HTML + rapport quotidien + alertes critiques en « issues » GitHub.

## Ce qui reste à faire (par le propriétaire)
1. **ElevenLabs :** payer l'abonnement, créer une clé API → secret GitHub `ELEVENLABS_API_KEY`.
2. **Pexels :** compte gratuit, clé sur pexels.com/api → secret GitHub `PEXELS_API_KEY`.
   (GitHub → Settings → Secrets and variables → Actions → New repository secret.)
3. Lancer le workflow « studio » avec l'action `check` pour vérifier les clés.
4. **Publication :** créer les accès API TikTok / YouTube / Facebook (`docs/PLATFORMS.md`), puis variable
   `STUDIO_PUBLISH_MODE=private`. TikTok et YouTube imposent un audit avant la publication publique.
5. Facultatif : `ANTHROPIC_API_KEY` pour que le studio écrive lui-même de nouveaux scripts quand la réserve est vide.

## Coûts
Hébergement 0 $ ; images 0 $ ; voix ElevenLabs ≈ 0,05 $/vidéo ; scripts par IA ≈ 0,05 $/vidéo (facultatif).

## Limites
Aucune statistique réelle tant que rien n'est publié : le classement des vidéos les plus prometteuses
(énigmes, paradoxe des anniversaires, pyramides du Soudan, lac Rose…) reste une estimation à vérifier.
