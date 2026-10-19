"""Constantes de l'intégration SolisArt."""
from datetime import timedelta

DOMAIN = "solisart"

CONF_INTERVALLE_ETAT = "intervalle_etat"
CONF_INTERVALLE_REGLAGES = "intervalle_reglages"
CONF_ECRITURE_VERSION_NON_TESTEE = "ecriture_version_non_testee"

INTERVALLE_ETAT = 30
INTERVALLE_REGLAGES = 300
INTERVALLE_ETAT_MIN = 10
INTERVALLE_REGLAGES_MIN = 60

DELAI_REQUETE = 15
DELAI_REGROUPEMENT = 1.5

FABRICANT = "SolisArt"
URL_TICKETS = "https://github.com/Bagu/solisart/issues"

# Couples (logiciel de la carte, interface web) sur lesquels l'écriture a été éprouvée.
# Sur tout autre couple, l'écriture est refusée sauf option contraire de l'utilisateur.
VERSIONS_TESTEES = (
    ("SRB_32MX_vD.50-5", "WEB_vA.98"),
)


def cle_sonde(index: int) -> str:
    """Option qui désigne la sonde de température de la zone `index` (6 : eau chaude)."""
    return f"sonde_zone_{index}"


def intervalle(secondes: int) -> timedelta:
    """Durée en secondes vers timedelta."""
    return timedelta(seconds=secondes)
