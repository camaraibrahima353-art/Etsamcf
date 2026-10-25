# Activer la publication (actions de votre part)

Par défaut le studio est en **`dry_run`** : il prépare la charge utile exacte (`data/publications/*.json`) sans rien
envoyer. Les identifiants se placent dans **GitHub → Settings → Secrets and variables → Actions** (jamais dans le code).

## Voix premium (recommandé avant toute publication)
La voix espeak-ng (pilote local) est robotique : le contrôle qualité **refuse sa publication** hors `dry_run`.
Sur GitHub Actions, la voix neuronale Piper (gratuite) est utilisée automatiquement. Pour une voix vraiment naturelle :
1. Créer un compte sur elevenlabs.io (abonnement payant requis pour l'usage commercial, à partir d'environ 5-6 $/mois).
2. Profile → API Keys → créer une clé ; l'ajouter en secret GitHub `ELEVENLABS_API_KEY` (ne jamais la coller dans un fichier).
3. Facultatif : choisir une voix française dans la Voice Library et mettre son identifiant dans
   `config/studio.yaml` → `voice.elevenlabs_voice_id`.
Coût ≈ 0,05 $ par vidéo de 30 s, compté dans le budget et le tableau de bord.

## Vraies images et vidéos (Pexels, gratuit)
Chaque scène reçoit une vraie vidéo verticale (ou, à défaut, une vraie photo) cherchée avec les mots-clés `visual.query`
du script ; l'accroche utilise toujours un média réel, sinon le QC bloque la publication (`require_real_hook_image`).
1. Créer un compte gratuit sur pexels.com, puis https://www.pexels.com/api/ → « Your API Key ».
2. L'ajouter en secret GitHub `PEXELS_API_KEY`.
Licence Pexels : usage commercial gratuit, attribution facultative (le studio enregistre auteur et lien de chaque média).

## YouTube Shorts
1. Google Cloud Console → nouveau projet → activer **YouTube Data API v3**.
2. Écran de consentement OAuth (type Externe, vous comme utilisateur test) ; identifiants « Application de bureau ».
3. Obtenir un *refresh token* avec le scope `https://www.googleapis.com/auth/youtube.upload` (et `youtube.readonly`
   pour les statistiques) — par exemple via l'OAuth Playground de Google avec vos propres identifiants.
4. Secrets : `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` ; facultatif `YOUTUBE_API_KEY` (tendances).
5. Les envois restent **privés** tant que le projet n'a pas passé l'**audit de conformité** YouTube API Services.
   En mode `public`, le studio programme la sortie avec `publishAt` (la vidéo devient publique au créneau).

## TikTok
1. developers.tiktok.com → créer une application → produit **Content Posting API** (+ Login Kit).
2. Scopes : `video.upload` (brouillons, recommandé), `video.publish` (publication directe), `video.list` (stats).
3. Autoriser votre compte, récupérer `refresh_token` ; secrets `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`,
   `TIKTOK_REFRESH_TOKEN` ; variable `TIKTOK_MODE` = `inbox` (défaut) ou `direct`.
4. Avant audit : publications directes forcées en **privé**, compte privé requis, 5 comptes/24 h. Mode `inbox` :
   la vidéo arrive dans vos brouillons TikTok ; activez l'étiquette « contenu généré par IA » au moment de publier.
5. Pour le public : demander l'audit (respect des Content Sharing Guidelines).

## Facebook Reels
1. developers.facebook.com → application de type Business ; une **Page** Facebook dont vous êtes administrateur.
2. Permissions : `pages_show_list`, `pages_read_engagement`, `pages_manage_posts` (App Review si autres comptes).
3. Jeton de Page longue durée → secrets `FB_PAGE_ID`, `FB_PAGE_TOKEN` ; facultatif variable `FB_GRAPH_VERSION`.
4. Mode `private` = brouillon (`DRAFT`), `public` = programmé (`SCHEDULED`) au créneau choisi.

## Instagram Reels (non activé)
Même master vidéo ; publication via Instagram Graph API (compte professionnel lié à la Page, `instagram_content_publish`).
À ajouter quand Facebook fonctionne.

## Passer d'un mode à l'autre
Variable de dépôt `STUDIO_PUBLISH_MODE` : `dry_run` → `private` (tester les intégrations sur vos comptes) → `public`.

| Plateforme | `private` | `public` avant audit | `public` après audit |
|---|---|---|---|
| TikTok `inbox` | brouillon | brouillon (vous publiez d'un geste) | brouillon |
| TikTok `direct` | privé | privé (forcé par TikTok) | public |
| Facebook Reels | brouillon | programmé, public | programmé, public |
| YouTube Shorts | privé | privé (verrouillé par YouTube) | programmé, public |

Passer en `public` avant les audits est donc sans risque : TikTok et YouTube gardent eux-mêmes les vidéos privées.
Au premier passage hors `dry_run`, les sujets fabriqués en essai sont remis en production avec les vraies images. Une plateforme sans identifiants passe en `blocked_credentials` sans bloquer les autres.
