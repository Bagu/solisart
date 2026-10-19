"""Constantes de l'intégration SolisArt."""
from datetime import timedelta

DOMAIN = "solisart"

CONF_INTERVALLE_ETAT = "intervalle_etat"
CONF_INTERVALLE_REGLAGES = "intervalle_reglages"

INTERVALLE_ETAT = 30
INTERVALLE_REGLAGES = 300
INTERVALLE_ETAT_MIN = 10
INTERVALLE_REGLAGES_MIN = 60

DELAI_REQUETE = 15
DELAI_REGROUPEMENT = 1.5

FABRICANT = "SolisArt"


def intervalle(secondes: int) -> timedelta:
    """Durée en secondes vers timedelta."""
    return timedelta(seconds=secondes)
