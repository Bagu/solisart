"""Relève périodique de la carte."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .analyse import Etat, PageInattendue, Reglages
from .api import AuthentificationRefusee, CarteInjoignable, SolisartClient
from .const import (
    CONF_INTERVALLE_ETAT,
    CONF_INTERVALLE_REGLAGES,
    DOMAIN,
    INTERVALLE_ETAT,
    INTERVALLE_REGLAGES,
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
        self._reglages: Reglages | None = None
        self._reglages_lus_a: float | None = None

    def relire_reglages(self) -> None:
        """Force la lecture de param.htm à la prochaine relève."""
        self._reglages_lus_a = None

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
            self._reglages_lus_a = maintenant

        return Donnees(etat=etat, reglages=self._reglages)
