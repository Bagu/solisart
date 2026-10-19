"""Accès HTTP à la carte SolisArt."""
from __future__ import annotations

import asyncio
import base64

import aiohttp

from .const import DELAI_REQUETE
from .analyse import (
    ENCODAGE,
    Etat,
    PageInattendue,
    ReglageRefuse,
    Reglages,
    champs_refuses,
    corps_formulaire,
    ecarts,
    encoder_corps,
    lire_etat,
    lire_reglages,
    preparer_changements,
)

PAGE_REGLAGES = "/param.htm"


class CarteInjoignable(Exception):
    """La carte ne répond pas ou répond par une erreur HTTP."""


class AuthentificationRefusee(Exception):
    """La carte refuse l'identifiant ou le mot de passe."""


class EcritureNonConfirmee(Exception):
    """La carte a reçu le formulaire mais la page relue ne montre pas les valeurs
    demandées. `ecarts` donne, par champ, (valeur voulue, valeur lue)."""

    def __init__(self, ecarts: dict[str, tuple[str, str | None]]) -> None:
        self.ecarts = ecarts
        detail = ", ".join(f"{nom} voulu {voulu!r}, lu {lu!r}" for nom, (voulu, lu) in ecarts.items())
        super().__init__(f"valeurs non appliquées par la carte : {detail}")


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


def _controler(reponse: aiohttp.ClientResponse, chemin: str, acceptes: tuple[int, ...]) -> None:
    """Lève AuthentificationRefusee sur un 401, CarteInjoignable sur tout code non accepté."""
    if reponse.status == 401:
        raise AuthentificationRefusee
    if reponse.status not in acceptes:
        raise CarteInjoignable(f"{chemin} : HTTP {reponse.status}")


class SolisartClient:
    """Lit la carte (status.xml sans identifiant, param.htm avec identifiant) et écrit
    ses réglages par le formulaire de param.htm, une écriture à la fois."""

    def __init__(self, session: aiohttp.ClientSession, hote: str,
                 utilisateur: str, mot_de_passe: str, delai: float = DELAI_REQUETE) -> None:
        self._session = session
        self._base = adresse_de_base(hote)
        self._entetes = {"Authorization": entete_basic(utilisateur, mot_de_passe)}
        self._delai = aiohttp.ClientTimeout(total=delai)
        self._verrou = asyncio.Lock()

    async def _lire(self, chemin: str, entetes: dict[str, str] | None) -> bytes:
        """GET d'une page, corps brut. Lève CarteInjoignable ou AuthentificationRefusee."""
        try:
            async with self._session.get(f"{self._base}{chemin}", headers=entetes,
                                         timeout=self._delai) as reponse:
                _controler(reponse, chemin, (200,))
                return await reponse.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CarteInjoignable(f"{chemin} : {err!r}") from err

    async def _lire_page_reglages(self) -> str:
        return (await self._lire(PAGE_REGLAGES, self._entetes)).decode(ENCODAGE)

    async def _envoyer(self, corps: bytes) -> None:
        """POST du formulaire comme le navigateur. La carte répond par une redirection
        (302), qui n'est pas suivie : la relecture se fait à part."""
        adresse = f"{self._base}{PAGE_REGLAGES}"
        entetes = {
            **self._entetes,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": adresse,
        }
        try:
            async with self._session.post(adresse, data=corps, headers=entetes,
                                          allow_redirects=False, timeout=self._delai) as reponse:
                _controler(reponse, PAGE_REGLAGES, (200, 302, 303))
                await reponse.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CarteInjoignable(f"POST {PAGE_REGLAGES} : {err!r}") from err

    async def lire_etat(self) -> Etat:
        """Mesures de /XML/status.xml."""
        return lire_etat(await self._lire("/XML/status.xml", None))

    async def lire_reglages(self) -> Reglages:
        """Zones, modes et consignes de /param.htm."""
        return lire_reglages(await self._lire_page_reglages())

    async def ecrire_reglages(self, demandes: dict[str, str | float]) -> Reglages:
        """Écrit des modes (U06_x) et des consignes (U09_x, U10_x) et rend les réglages
        relus après l'écriture.

        Lit param.htm, contrôle les demandes, renvoie le formulaire complet avec les
        valeurs changées, puis relit la page pour confirmer chaque valeur. Lève
        ReglageRefuse avant tout envoi si une demande est invalide ou vise un champ
        désactivé, EcritureNonConfirmee si la page relue ne montre pas les valeurs.
        """
        async with self._verrou:
            page = await self._lire_page_reglages()
            changements = preparer_changements(lire_reglages(page), demandes)
            corps = corps_formulaire(page, changements)
            refuses = champs_refuses(corps, changements)
            if refuses:
                raise ReglageRefuse(f"champs désactivés ou absents : {', '.join(refuses)}")
            await self._envoyer(encoder_corps(corps))
            relue = await self._lire_page_reglages()
            restants = ecarts(relue, changements)
            if restants:
                raise EcritureNonConfirmee(restants)
            return lire_reglages(relue)


__all__ = [
    "AuthentificationRefusee",
    "CarteInjoignable",
    "EcritureNonConfirmee",
    "PageInattendue",
    "ReglageRefuse",
    "SolisartClient",
    "adresse_de_base",
]
