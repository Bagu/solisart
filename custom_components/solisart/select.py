"""Mode de chauffage de chaque zone présente sur la carte (U06_x de param.htm)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .analyse import MODE_ARRET, MODE_SOLEIL, MODE_SOLEIL_APPOINT
from .coordinator import SolisartConfigEntry
from .entity import SolisartReglage

OPTIONS = {"arret": MODE_ARRET, "soleil": MODE_SOLEIL, "soleil_appoint": MODE_SOLEIL_APPOINT}
OPTION_DU_MODE = {mode: option for option, mode in OPTIONS.items()}


async def async_setup_entry(hass: HomeAssistant, entry: SolisartConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    reglages = coordinator.data.reglages
    if reglages is None:
        return
    async_add_entities(SolisartMode(coordinator, zone, "U06", "mode") for zone in reglages.zones)


class SolisartMode(SolisartReglage, SelectEntity):
    """Arrêt, soleil seul, ou soleil et appoint."""

    _attr_options = list(OPTIONS)

    @property
    def current_option(self) -> str | None:
        zone = self.zone
        return OPTION_DU_MODE.get(zone.mode) if zone else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.ecrire_reglages({self.champ: OPTIONS[option]})
