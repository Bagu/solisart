"""Intégration SolisArt : lecture et réglage d'une carte de régulation de chauffage solaire."""
from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .analyse import texte_planning
from .api import SolisartClient
from .const import DOMAIN
from .coordinator import SolisartConfigEntry, SolisartCoordinator, identifiant_probleme

PLATFORMS = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.TEXT]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_COPIER_PLANNING = "copier_planning"
SCHEMA_COPIER_PLANNING = vol.Schema({
    vol.Required("source"): cv.entity_id,
    vol.Required("cibles"): cv.entity_ids,
})
MOTIF_PLANNING = re.compile(r"(.+)_planning_(\d)_(\d)")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Enregistre le service de copie de planning."""

    async def copier_planning(appel: ServiceCall) -> None:
        source = _planning(hass, appel.data["source"])
        entree, zone, jour = source
        texte = texte_planning(entree.runtime_data.data.reglages.plannings[zone][jour])
        par_entree: dict[str, dict[tuple[int, int], str]] = {}
        entrees = {}
        for cible in appel.data["cibles"]:
            entree_cible, zone_cible, jour_cible = _planning(hass, cible)
            entrees[entree_cible.entry_id] = entree_cible
            par_entree.setdefault(entree_cible.entry_id, {})[(zone_cible, jour_cible)] = texte
        for entry_id, demandes in par_entree.items():
            await entrees[entry_id].runtime_data.ecrire_plannings(demandes)

    hass.services.async_register(DOMAIN, SERVICE_COPIER_PLANNING, copier_planning,
                                 schema=SCHEMA_COPIER_PLANNING)
    return True


def _planning(hass: HomeAssistant, entity_id: str) -> tuple[SolisartConfigEntry, int, int]:
    """Entrée, zone et jour d'une entité planning SolisArt chargée. Lève
    ServiceValidationError pour toute autre entité."""
    refus = ServiceValidationError(f"{entity_id} n'est pas un planning SolisArt disponible")
    inscrite = er.async_get(hass).async_get(entity_id)
    if inscrite is None or inscrite.platform != DOMAIN or inscrite.config_entry_id is None:
        raise refus
    trouve = MOTIF_PLANNING.fullmatch(inscrite.unique_id)
    entree = hass.config_entries.async_get_entry(inscrite.config_entry_id)
    if trouve is None or entree is None or entree.state is not ConfigEntryState.LOADED:
        raise refus
    zone, jour = int(trouve.group(2)), int(trouve.group(3))
    reglages = entree.runtime_data.data.reglages
    if reglages is None or zone not in reglages.plannings:
        raise refus
    return entree, zone, jour


async def async_setup_entry(hass: HomeAssistant, entry: SolisartConfigEntry) -> bool:
    """Crée le client et la première relève, puis les entités."""
    client = SolisartClient(async_get_clientsession(hass), entry.data[CONF_HOST],
                            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = SolisartCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_options_modifiees))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolisartConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: SolisartConfigEntry) -> None:
    """Retire de Réparations le problème de version laissé par l'entrée supprimée."""
    ir.async_delete_issue(hass, DOMAIN, identifiant_probleme(entry.entry_id))


async def _options_modifiees(hass: HomeAssistant, entry: SolisartConfigEntry) -> None:
    """Recharge l'entrée pour appliquer un nouveau rythme de lecture."""
    await hass.config_entries.async_reload(entry.entry_id)
