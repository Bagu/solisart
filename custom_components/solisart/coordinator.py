"""Relève périodique de la carte."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .analyse import Etat, PageInattendue, ReglageRefuse, Reglages
from .api import AuthentificationRefusee, CarteInjoignable, EcritureNonConfirmee, SolisartClient
from .const import (
    CONF_ECRITURE_VERSION_NON_TESTEE,
    CONF_INTERVALLE_ETAT,
    CONF_INTERVALLE_REGLAGES,
    DELAI_REGROUPEMENT,
    DOMAIN,
    INTERVALLE_ETAT,
    INTERVALLE_REGLAGES,
    URL_TICKETS,
    VERSIONS_TESTEES,
    intervalle,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class Donnees:
    """Dernière lecture : mesures de status.xml et réglages de param.htm (None tant que
    param.htm n'a pas pu être lue)."""

    etat: Etat
    reglages: Reglages | None


type SolisartConfigEntry = ConfigEntry[SolisartCoordinator]


def version_testee(reglages: Reglages | None) -> bool:
    """Vrai si param.htm a été lue et que son couple de versions figure dans VERSIONS_TESTEES."""
    return reglages is not None and (reglages.version_carte, reglages.version_web) in VERSIONS_TESTEES


def versions_lues(reglages: Reglages | None) -> dict[str, str]:
    """Versions lues et versions testées, prêtes pour les messages traduits."""
    return {
        "version_carte": (reglages.version_carte if reglages else None) or "?",
        "version_web": (reglages.version_web if reglages else None) or "?",
        "versions_testees": ", ".join(f"{carte} / {web}" for carte, web in VERSIONS_TESTEES),
    }


def identifiant_probleme(entry_id: str) -> str:
    """Identifiant du problème « version non testée » d'une entrée dans Réparations."""
    return f"version_non_testee_{entry_id}"


class SolisartCoordinator(DataUpdateCoordinator[Donnees]):
    """Lit status.xml à chaque relève, et param.htm à un rythme plus lent : cette page
    coûte près d'une seconde à la carte."""

    config_entry: SolisartConfigEntry

    def __init__(self, hass: HomeAssistant, entree: SolisartConfigEntry,
                 client: SolisartClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entree,
            name=DOMAIN,
            update_interval=intervalle(entree.options.get(CONF_INTERVALLE_ETAT, INTERVALLE_ETAT)),
        )
        self.client = client
        self._rythme_reglages = entree.options.get(CONF_INTERVALLE_REGLAGES, INTERVALLE_REGLAGES)
        self._ecriture_forcee = entree.options.get(CONF_ECRITURE_VERSION_NON_TESTEE, False)
        self._reglages: Reglages | None = None
        self._reglages_lus_a: float | None = None
        self.delai_regroupement = DELAI_REGROUPEMENT
        self._en_attente: dict[str, str | float] = {}
        self._lot: asyncio.Future | None = None
        self._minuteur: asyncio.TimerHandle | None = None

    def _controler_version(self, reglages: Reglages | None) -> None:
        """Refuse l'écriture sur une version non testée, ou dont la version n'a pas pu
        être lue, sauf si l'utilisateur l'a autorisée dans les options."""
        if self._ecriture_forcee or version_testee(reglages):
            return
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="version_non_testee",
                                 translation_placeholders=versions_lues(reglages))

    @callback
    def _signaler_version(self, reglages: Reglages) -> None:
        """Ouvre dans Réparations le problème « version non testée », ou le retire quand
        la version est connue ou l'écriture autorisée."""
        ident = identifiant_probleme(self.config_entry.entry_id)
        if self._ecriture_forcee or version_testee(reglages):
            ir.async_delete_issue(self.hass, DOMAIN, ident)
            return
        ir.async_create_issue(
            self.hass, DOMAIN, ident,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="version_non_testee",
            translation_placeholders={**versions_lues(reglages), "carte": self.config_entry.title},
            learn_more_url=URL_TICKETS,
        )

    def relire_reglages(self) -> None:
        """Force la lecture de param.htm à la prochaine relève."""
        self._reglages_lus_a = None

    async def ecrire_reglages(self, demandes: dict[str, str | float]) -> None:
        """Écrit des réglages sur la carte, regroupés avec ceux qui arrivent dans les
        `delai_regroupement` secondes suivantes : un seul envoi part, la dernière valeur
        demandée pour un champ l'emporte, et chaque appelant attend le résultat de cet
        envoi. Lève HomeAssistantError avec la raison de l'échec, aussitôt si la version
        de la carte n'a pas été testée."""
        self._controler_version(self._reglages)
        self._en_attente.update(demandes)
        if self._lot is None:
            self._lot = self.hass.loop.create_future()
        lot = self._lot
        if self._minuteur is not None:
            self._minuteur.cancel()
        self._minuteur = self.hass.loop.call_later(self.delai_regroupement, self._lancer_lot)
        await asyncio.shield(lot)

    async def async_shutdown(self) -> None:
        """Annule le lot qui n'est pas encore parti : ses appelants reçoivent une erreur."""
        if self._minuteur is not None:
            self._minuteur.cancel()
        if self._lot is not None:
            self._lot.set_exception(HomeAssistantError("écriture SolisArt annulée : intégration arrêtée"))
        self._en_attente, self._lot, self._minuteur = {}, None, None
        await super().async_shutdown()

    @callback
    def _lancer_lot(self) -> None:
        """Envoie les demandes accumulées et libère la place pour le lot suivant."""
        demandes, lot = self._en_attente, self._lot
        self._en_attente, self._lot, self._minuteur = {}, None, None
        self.config_entry.async_create_background_task(
            self.hass, self._ecrire_lot(demandes, lot), "solisart_ecriture")

    async def _ecrire_lot(self, demandes: dict[str, str | float], lot: asyncio.Future) -> None:
        """Écrit un lot et publie aussitôt la page relue. Après un échec, param.htm est
        relue à la relève demandée, car une partie a pu passer."""
        try:
            await self._ecrire(demandes)
        except HomeAssistantError as err:
            lot.set_exception(err)
        else:
            lot.set_result(None)

    async def ecrire_plannings(self, demandes: dict[tuple[int, int], str]) -> None:
        """Écrit des plannings ((zone, jour) vers plages de confort en texte), en un
        seul envoi. Lève HomeAssistantError avec la raison de l'échec, aussitôt si la
        version de la carte n'a pas été testée."""
        self._controler_version(self._reglages)
        await self._ecrire(self.client.ecrire_plannings(demandes, self._controler_version))

    async def _ecrire(self, ecriture: dict[str, str | float] | Coroutine[Any, Any, Reglages]) -> None:
        """Mène une écriture (demandes de champs, ou appel du client déjà préparé) et
        publie la page relue. La version est contrôlée de nouveau sur la page lue juste
        avant l'envoi."""
        if isinstance(ecriture, dict):
            ecriture = self.client.ecrire_reglages(ecriture, self._controler_version)
        try:
            reglages = await ecriture
        except (AuthentificationRefusee, CarteInjoignable, PageInattendue, ReglageRefuse,
                EcritureNonConfirmee) as err:
            self.relire_reglages()
            await self.async_request_refresh()
            if isinstance(err, AuthentificationRefusee):
                raise HomeAssistantError("écriture SolisArt : identifiant refusé par la carte") from err
            raise HomeAssistantError(f"écriture SolisArt : {err}") from err
        self._reglages = reglages
        self._reglages_lus_a = time.monotonic()
        self._signaler_version(reglages)
        if self.data is not None:
            self.async_set_updated_data(Donnees(etat=self.data.etat, reglages=reglages))

    async def _async_update_data(self) -> Donnees:
        try:
            etat = await self.client.lire_etat()
        except (CarteInjoignable, PageInattendue) as err:
            raise UpdateFailed(f"lecture de status.xml impossible : {err}") from err

        maintenant = time.monotonic()
        if self._reglages_lus_a is None or maintenant - self._reglages_lus_a >= self._rythme_reglages:
            try:
                self._reglages = await self.client.lire_reglages()
            except AuthentificationRefusee as err:
                raise ConfigEntryAuthFailed("identifiant refusé par la carte") from err
            except (CarteInjoignable, PageInattendue) as err:
                _LOGGER.warning("Lecture de param.htm impossible, réglages précédents gardés : %s", err)
            else:
                self._signaler_version(self._reglages)
            self._reglages_lus_a = maintenant

        return Donnees(etat=etat, reglages=self._reglages)
