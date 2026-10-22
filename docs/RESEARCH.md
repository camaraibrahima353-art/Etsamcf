# Rapport de recherche — vidéos courtes virales (octobre 2026)

> Méthode : recherches web (sources officielles en priorité : TikTok for Developers, Google Developers,
> Meta for Developers, rapports TikTok Next 2026), recoupées avec des sources secondaires signalées comme telles.
> Les chiffres non officiels sont marqués **[non vérifié]**. Les pages développeurs n'ont pas pu être téléchargées
> directement depuis l'environnement (proxy) : leurs contenus proviennent des extraits indexés.

## 1. Ce qui est confirmé, ce qui est une hypothèse

| Constat | Statut | Source |
|---|---|---|
| Les 2-3 premières secondes conditionnent la distribution ; la rétention initiale est le premier signal | **Confirmé** (consensus + donnée historique Facebook : 65 % de ceux qui regardent 3 s regardent ≥ 10 s) | Synthèses Kapwing / OpusClip 2026 ; donnée Facebook citée |
| Taux de rétention à 3 s « moyens » (32 % TikTok, 28 % Reels, 35 % Shorts) | **Non vérifié** (blog éditeur, aucune étude citée) | blogs 2026 |
| TikTok Next 2026 : « Reali-TEA » (authenticité), « Curiosity Detours » (niches de curiosité), « Emotional ROI » | **Confirmé** (rapport officiel TikTok, résumé par Social Media Today / Gigazine) | ads.tiktok.com/business/en/next |
| Contenu natif vertical > recyclage de pubs longues | Tendance forte, chiffres vendeurs | OpusClip, Klap |
| YouTube démonétise le contenu « produit en masse / répétitif » (YPP, 15/07/2025) | **Confirmé** (multiples médias ; texte officiel à relire) | Gulf News, CineD, Daily Star |
| Le RPM des Shorts est faible (≈ 0,03-0,25 $ / 1000 vues ; finance/éducation en haut) | **Non vérifié** (fourchettes déclaratives) | ClipSpeed, Vozo, ShortsFast |
| Les formats « sans visage » fonctionnent quand ils apportent une vraie valeur (récit, pédagogie, curiosité) | Hypothèse raisonnable, aucune donnée sérieuse publiée | — |

**Conséquence pour le studio :** l'avantage ne viendra pas du volume brut (risque « AI slop » et démonétisation)
mais de scripts originaux, sourcés, avec une accroche forte et une signature visuelle reconnaissable par série.

## 2. Formats et techniques de rétention retenus

- **Accroche < 2 s** dite ET écrite à l'écran (double canal) ; 6 types testés : question, affirmation choc, chiffre,
  défi, mythe, promesse.
- **Boucle de curiosité** au milieu (« et ce n'est pas tout… », « réfléchis encore trois secondes »).
- **Sous-titres mot à mot** (beaucoup de visionnage sans son) et chiffres colorés.
- **Barre de progression + compteur de scène (2/6)** : l'utilisateur sait que la fin est proche.
- **Conclusion-question** qui provoque les commentaires (signal d'engagement), plutôt qu'un appel générique.
- **Durée 25-35 s** pour le pilote (assez pour un fait complet, assez court pour viser une complétion élevée) ;
  à faire varier ensuite (15-20 s vs 45-60 s) selon les données.
- **Séries** : un nom de niche fixe, une palette et une structure stable par niche = épisodes reconnaissables.
- **Réutilisation légitime multi-plateformes** : un master 1080x1920 unique, publié sous forme native sur chaque
  plateforme via son API (pas de filigrane d'une autre plateforme, métadonnées adaptées).

## 3. Outils évalués

| Besoin | Retenu | Écarté / optionnel | Raison |
|---|---|---|---|
| Orchestration | Python + SQLite + file de tâches maison | Celery/Redis, Airflow | Zéro service à maintenir ; suffisant jusqu'à des centaines de vidéos/jour |
| Ordonnanceur | GitHub Actions (cron, gratuit sur dépôt public) ; systemd timer pour VPS | cron local | Le conteneur Claude est éphémère ; Actions tourne sans machine allumée |
| Scripts | Réserve rédigée par Claude Code + API Claude (`claude-opus-5-5`) si clé | — | Qualité et sourçage |
| Voix | Piper (neuronal, local, MIT) ; repli espeak-ng | ElevenLabs (40-100 $/M car.), OpenAI TTS (15-30 $/M car.) | Coût nul ; montée en gamme possible plus tard |
| Visuels | Procédural (Pillow) : zéro droit tiers | Veo 3.1 (0,05-0,40 $/s), Kling (~0,08-0,11 $/s), Runway Gen-4 (~0,05 $/s) **[tarifs non vérifiés]** | 30 s de vidéo IA = 1,5 à 12 $ : à tester seulement sur les niches gagnantes |
| Montage / export | FFmpeg (libx264, libass, loudnorm) | MoviePy, Remotion | Plus rapide, plus robuste, déjà installé |
| Sous-titres | Générés depuis le script (alignement par phrase) | Whisper | Le texte est connu : pas besoin de transcription |
| QC | ffprobe, ebur128, blackdetect, pyspellchecker, règles éditoriales | LanguageTool (Java) | Léger ; LanguageTool possible plus tard |
| Tendances | Wikimedia Pageviews (sans clé), YouTube Data API `mostPopular` (clé) | pytrends, scraping TikTok | Non officiels / contraires aux CGU |
| Publication | API officielles YouTube, TikTok, Facebook | Outils de « posting » non officiels, automatisation de navigateur | Conformité et pérennité des comptes |

## 4. Contraintes des plateformes (vérifiées sur les docs officielles indexées)

- **TikTok Content Posting API** : client non audité ⇒ toutes les publications en **privé (SELF_ONLY)**, 5 comptes
  max / 24 h, compte en privé obligatoire ; `privacy_level` doit appartenir à `creator_info/query`. L'audit lève la
  restriction. Le mode **brouillon (inbox, scope `video.upload`)** est la voie la plus simple : le créateur valide
  dans l'app. Champ de divulgation IA `is_aigc` documenté par plusieurs intégrateurs (à confirmer sur la doc officielle).
- **YouTube Data API v3** : `videos.insert` = 100 unités (doc officielle actuelle ; 1 600 dans les anciennes docs —
  le studio planifie sur 1 600 par prudence ⇒ 6 envois/jour avec le quota par défaut de 10 000). Projets non audités
  créés après le 28/07/2020 ⇒ vidéos **privées** jusqu'à l'audit. `status.containsSyntheticMedia` (30/10/2024) pour la
  divulgation IA ; `publishAt` pour programmer.
- **Facebook Reels Publishing API** : `/{page-id}/video_reels` en 3 phases (start → rupload.facebook.com → finish,
  `video_state` DRAFT/SCHEDULED/PUBLISHED). Permissions `pages_manage_posts`, `pages_read_engagement`,
  `pages_show_list` (App Review pour des tiers). Pas de champ IA documenté ⇒ mention en description.

## 5. Top 10 des niches à tester

Notation 1 (faible) à 5 (fort). Coût = coût marginal par vidéo avec la pile actuelle (hors temps humain).

| # | Niche | Pourquoi | Public | Difficulté | Coût/vidéo | Fidélisation |
|---|---|---|---|---|---|---|
| 1 | **Quiz & énigmes** | Interaction native (réponses en commentaire), rejouable, aucun risque factuel | 10-35 ans | 1 | ~0 $ (0,05 $ avec LLM) | 4 (séries « défi du jour ») |
| 2 | **Science étonnante** | « Curiosity Detours » (TikTok Next 2026), partageable, intemporel | 15-35 ans | 2 | ~0 $ | 4 |
| 3 | **Afrique méconnue** | Francophonie africaine sous-servie, fierté/partage, diaspora | 15-45 ans, Afrique/diaspora | 3 (sourcing) | ~0 $ | 5 (communauté) |
| 4 | **Anglais en 30 s** | Utilité immédiate, sauvegardes élevées, synergie avec « J'apprends à lire » | 12-40 ans apprenants | 1 | ~0 $ | 5 (apprentissage quotidien) |
| 5 | **Histoire express** | Récit + chiffre choc, fort potentiel de séries | 18-45 ans | 2 | ~0 $ | 4 |
| 6 | **Espace** | Curiosité universelle, visuels abstraits faciles | 13-35 ans | 2 | ~0 $ | 3 |
| 7 | **Tech & IA utiles** | Forte demande, RPM supérieur, astuces sauvegardables | 16-40 ans | 3 (actualité rapide) | ~0 $ | 3 |
| 8 | **Psychologie & biais** | Très partagé, s'applique à la vie quotidienne | 18-40 ans | 3 (rigueur scientifique) | ~0 $ | 4 |
| 9 | **Argent malin** | RPM le plus élevé **[non vérifié]**, besoin réel (budget, épargne) | 18-35 ans | 4 (règles strictes : jamais de conseil personnalisé) | ~0 $ | 4 |
| 10 | **Maths satisfaisantes** | Astuces démontrables visuellement, « satisfying » pédagogique | 13-35 ans | 2 | ~0 $ | 3 |

Écartées pour l'instant : santé/nutrition (risque de désinformation élevé), actualité chaude (vérification
impossible à temps), compilations de clips tiers (droits + politique « contenu réutilisé »), crypto/trading.

## 6. Hypothèses à tester pendant le pilote

1. Accroche « question » vs « chiffre » vs « affirmation choc » : écart de rétention à 3 s.
2. Durée 25-30 s vs 30-35 s sur la complétion.
3. Niches à forte interaction (quiz, anglais) vs niches de curiosité (science, espace) sur l'abonnement.
4. Visuels procéduraux simples vs (plus tard) plans IA sur 2 niches gagnantes : gain réel vs coût.

## 7. Coûts réels estimés

| Poste | Coût | Remarque |
|---|---|---|
| Hébergement / calcul | **0 $** | GitHub Actions illimité sur dépôt public ; ~1,2 min de calcul / vidéo mesuré en local (4 vCPU) |
| Voix (Piper / espeak-ng) | 0 $ | ElevenLabs Flash ≈ 0,02 $ / vidéo de 30 s (500 car.) si besoin |
| Script (API Claude `claude-opus-5-5`, 4 $/20 $ par M tokens) | ≈ 0,03-0,05 $ / script | ~2 500 tokens d'entrée + 1 500 de sortie |
| Visuels IA (option) | 1,5 à 12 $ / vidéo de 30 s | Veo/Kling/Runway, tarifs à confirmer |
| Stockage | 0 $ | artefacts GitHub (30-90 j) ; ~3 Mo / vidéo |
| **Total pile actuelle** | **0 à 0,05 $ / vidéo** | Plafonds configurés : 0,50 $/vidéo, 2 $/jour, 30 $/mois |

## Sources

- [TikTok — Content Posting API, Direct Post](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post)
- [TikTok — Content Posting API, Get started](https://developers.tiktok.com/doc/content-posting-api-get-started)
- [TikTok — Content Sharing Guidelines](https://developers.tiktok.com/docs/en/content-sharing-guidelines)
- [Google — YouTube Data API videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert)
- [Google — YouTube Data API revision history (containsSyntheticMedia)](https://developers.google.com/youtube/v3/revision_history)
- [Meta — Reels Publishing API](https://developers.facebook.com/docs/video-api/guides/reels-publishing)
- [Social Media Today — TikTok 2026 trend predictions](https://www.socialmediatoday.com/news/tiktok-shares-2026-trend-predictions-for-marketers/809651/)
- [Gigazine — TikTok 2026 trend report](https://gigazine.net/gsc_news/en/20260124-tiktok-trend-report)
- [Kapwing — Short-form video statistics 2026](https://www.kapwing.com/resources/short-form-video-statistics-tiktok-reels-and-shorts-by-the-numbers-in-2026/)
- [OpusClip — Short-form video trends 2026](https://www.opus.pro/blog/short-form-video-trends-reshaping-creator-marketing-2026)
- [Gulf News — YouTube inauthentic content rule](https://gulfnews.com/technology/youtube-updates-monetisation-policies-ai-and-repetitive-content-ban-begins-july-15-1.500192660)
- [ClipSpeed — Faceless niches 2026](https://www.clipspeed.ai/blog/faceless-youtube-niches-2026.html)
- [texttolab — TTS pricing 2026](https://texttolab.com/pricing) ; [micdrop — ElevenLabs API pricing](https://micdrop.dev/blog/elevenlabs-api-pricing-voice-agent)
- [invideo — AI video model pricing (Aug 2026)](https://invideo.io/blog/ai-video-model-pricing) ; [benchlm — Veo pricing](https://benchlm.ai/media-pricing/veo)
- [Postiz — TikTok provider notes](https://docs.postiz.com/providers/tiktok.md) ; [adaptlypost — TikTok AI label](https://adaptlypost.com/blog/tiktok-ai-generated-label)
