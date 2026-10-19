"""Intégration SolisArt : lecture et réglage d'une carte de régulation de chauffage solaire."""
from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolisartClient
from .coordinator import SolisartConfigEntry, SolisartCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SELECT, Platform.SENSOR]


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


async def _options_modifiees(hass: HomeAssistant, entry: SolisartConfigEntry) -> None:
    """Recharge l'entrée pour appliquer un nouveau rythme de lecture."""
    await hass.config_entries.async_reload(entry.entry_id)
