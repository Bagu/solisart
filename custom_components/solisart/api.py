"""Accès HTTP à la carte SolisArt."""
from __future__ import annotations

import asyncio
import base64

import aiohttp

from .const import DELAI_REQUETE
from .analyse import Etat, PageInattendue, Reglages, lire_etat, lire_reglages

ENCODAGE = "ISO-8859-1"


class CarteInjoignable(Exception):
    """La carte ne répond pas ou répond par une erreur HTTP."""


class AuthentificationRefusee(Exception):
    """La carte refuse l'identifiant ou le mot de passe."""


def adresse_de_base(hote: str) -> str:
    """Adresse saisie (« 192.168.1.20 », « http://carte:8080/ ») vers l'URL de base."""
    hote = hote.strip().rstrip("/")
    if "://" not in hote:
        hote = f"http://{hote}"
    return hote


def entete_basic(utilisateur: str, mot_de_passe: str) -> str:
    """En-tête d'authentification HTTP Basic, encodé comme les pages de la carte
    (ISO-8859-1), ou en UTF-8 pour un caractère hors de cet alphabet."""
    paire = f"{utilisateur}:{mot_de_passe}"
    try:
        octets = paire.encode(ENCODAGE)
    except UnicodeEncodeError:
        octets = paire.encode("utf-8")
    return "Basic " + base64.b64encode(octets).decode("ascii")


class SolisartClient:
    """Lit la carte : status.xml sans identifiant, param.htm avec identifiant."""

    def __init__(self, session: aiohttp.ClientSession, hote: str,
                 utilisateur: str, mot_de_passe: str, delai: float = DELAI_REQUETE) -> None:
        self._session = session
        self._base = adresse_de_base(hote)
        self._entetes = {"Authorization": entete_basic(utilisateur, mot_de_passe)}
        self._delai = aiohttp.ClientTimeout(total=delai)

    async def _lire(self, chemin: str, entetes: dict[str, str] | None) -> bytes:
        """GET d'une page, corps brut. Lève CarteInjoignable ou AuthentificationRefusee."""
        try:
            async with self._session.get(f"{self._base}{chemin}", headers=entetes,
                                         timeout=self._delai) as reponse:
                if reponse.status == 401:
                    raise AuthentificationRefusee
                if reponse.status != 200:
                    raise CarteInjoignable(f"{chemin} : HTTP {reponse.status}")
                return await reponse.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CarteInjoignable(f"{chemin} : {err!r}") from err

    async def lire_etat(self) -> Etat:
        """Mesures de /XML/status.xml."""
        return lire_etat(await self._lire("/XML/status.xml", None))

    async def lire_reglages(self) -> Reglages:
        """Zones, modes et consignes de /param.htm."""
        page = (await self._lire("/param.htm", self._entetes)).decode(ENCODAGE)
        return lire_reglages(page)


__all__ = [
    "AuthentificationRefusee",
    "CarteInjoignable",
    "PageInattendue",
    "SolisartClient",
    "adresse_de_base",
]
