"""Chauffe-eau de l'eau chaude sanitaire : modes arrêt, soleil seul (eco) et soleil et
appoint (performance), consigne confort, et température de la sonde choisie dans les
options."""
from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    STATE_ECO,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .analyse import MODE_ARRET, MODE_SOLEIL, MODE_SOLEIL_APPOINT, Zone
from .coordinator import SolisartConfigEntry, SolisartCoordinator
from .entity import SolisartThermostatBase

OPERATIONS = {STATE_OFF: MODE_ARRET, STATE_ECO: MODE_SOLEIL, STATE_PERFORMANCE: MODE_SOLEIL_APPOINT}
OPERATION_DU_MODE = {mode: operation for operation, mode in OPERATIONS.items()}


async def async_setup_entry(hass: HomeAssistant, entry: SolisartConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    reglages = coordinator.data.reglages
    if reglages is None:
        return
    async_add_entities(SolisartChauffeEau(coordinator, zone)
                       for zone in reglages.zones if zone.eau_chaude)


class SolisartChauffeEau(SolisartThermostatBase, WaterHeaterEntity):
    """Eau chaude : le rallumage remet le dernier mode actif connu."""

    _attr_operation_list = list(OPERATIONS)
    _attr_supported_features = (WaterHeaterEntityFeature.TARGET_TEMPERATURE
                                | WaterHeaterEntityFeature.OPERATION_MODE
                                | WaterHeaterEntityFeature.ON_OFF)
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: SolisartCoordinator, zone: Zone) -> None:
        super().__init__(coordinator, zone, "chauffe_eau")

    @property
    def current_operation(self) -> str | None:
        return OPERATION_DU_MODE.get(self.mode_carte)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        await self.ecrire(mode=OPERATIONS[operation_mode])

    async def async_set_temperature(self, **kwargs: Any) -> None:
        operation = kwargs.get(ATTR_OPERATION_MODE)
        await self.ecrire(mode=OPERATIONS[operation] if operation else None,
                          confort=kwargs.get(ATTR_TEMPERATURE))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.ecrire(mode=self._dernier_mode_actif)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.ecrire(mode=MODE_ARRET)
