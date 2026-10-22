"""Les dix agents du studio. Chaque agent lit et écrit des données structurées (base SQLite + fichiers JSON)."""

AGENTS = {
    "A_directeur": "Orchestrateur : coordonne, priorise, relance les tâches réparables",
    "B_tendances": "Recherche de tendances, mots-clés et opportunités",
    "C_strategie": "Choix des niches, calendrier éditorial, sélection des sujets",
    "D_scenariste": "Écriture des scripts (accroche, développement, curiosité, conclusion)",
    "E_realisateur": "Plan de tournage : voix off et visuels de chaque scène",
    "F_monteur": "Montage, synchronisation, sous-titres, export vertical",
    "G_qualite": "Contrôle qualité technique, éditorial et juridique",
    "H_publication": "Métadonnées, calendrier et publication via API officielles",
    "I_analyste": "Statistiques et recommandations",
    "J_admin": "Santé du système, ressources, coûts, verrous, alertes",
}


class NonRetryable(Exception):
    """Erreur qui ne se résoudra pas par une nouvelle tentative (ex. clé API manquante, QC refusé)."""
