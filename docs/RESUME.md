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
- Pilote de 10 vidéos produites ; **30 scripts sourcés** (10 du pilote + 20 en file), soit ≈ 3 jours à 10 vidéos/jour.
  Les vidéos fabriquées en mode essai (`dry_run`, voix et fonds de secours) ne « consomment » pas ces sujets : au
  premier passage en `private` ou `public`, le studio les remet en production avec les vraies images.
- Tests : 14 réussis (+ 1 qui exige espeak-ng, exécuté sur GitHub) ; reprise testée (panne simulée, processus tué,
  double lancement, budget dépassé, arrêt).
- Ordonnanceur vérifié : passages planifiés réussis sur GitHub toutes les 6 h depuis le 22/10, état restauré, pas de doublon.
- Garde-fou : si la publication est activée sans clé Pexels, aucun sujet n'est gâché (alerte critique à la place).
- Tableau de bord HTML + rapport quotidien + alertes critiques en « issues » GitHub.

## Pour commencer maintenant (propriétaire)
Tout se fait dans **GitHub → Settings → Secrets and variables → Actions**.

| # | Action | Obligatoire ? | Coût |
|---|--------|---------------|------|
| 1 | Secret `PEXELS_API_KEY` (pexels.com/api) | **Oui** : sans vraie image, rien n'est publiable | 0 $ |
| 2 | Secret `ANTHROPIC_API_KEY` (console.anthropic.com) | **Oui** pour tourner plus de 3 jours : écrit les nouveaux scripts | ≈ 0,05 $/vidéo |
| 3 | Secret `ELEVENLABS_API_KEY` | Non : sans elle, voix Piper gratuite (correcte) | ≈ 0,05 $/vidéo |
| 4 | Au moins une plateforme (`docs/PLATFORMS.md`) | **Oui** | 0 $ |
| 5 | Actions → studio → Run workflow → action `check` | Vérifie tout et affiche `pret_a_publier` + la liste `a_faire` | — |
| 6 | Onglet *Variables* : `STUDIO_PUBLISH_MODE` = `private`, puis `public` | **Oui** (décision du propriétaire) | — |

Ce que chaque plateforme permet **dès aujourd'hui, sans audit** :
- **TikTok (mode `inbox`)** : la vidéo arrive dans vos brouillons TikTok ; vous la publiez d'un geste (étiquette IA à cocher).
  C'est la voie la plus rapide vers de vraies vues.
- **Facebook Reels** : publication programmée sur votre Page en mode `public` (application Meta passée en mode « Live »,
  accès standard suffisant pour votre propre Page).
- **YouTube Shorts** : envois en privé tant que le projet Google n'a pas passé l'audit ; à demander dès le début (plusieurs semaines).

Ordre conseillé : clés 1-2 → Facebook + TikTok → `check` → `private` pendant 1 passage (vérifier un brouillon sur
chaque compte) → `public`.

## Coûts
Hébergement 0 $ ; images 0 $ ; scripts par IA ≈ 0,05 $/vidéo ; voix ElevenLabs ≈ 0,05 $/vidéo (facultative).
À 10 vidéos/jour : ≈ 0,50 à 1 $/jour, sous le plafond automatique de 2 $/jour et 30 $/mois.

## Limites
Aucune statistique réelle tant que rien n'est publié : le classement des vidéos les plus prometteuses
(énigmes, paradoxe des anniversaires, pyramides du Soudan, lac Rose…) reste une estimation à vérifier.
