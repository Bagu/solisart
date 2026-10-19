"""Thermostat de chaque zone de chauffage : arrêt ou chauffage, préréglage soleil seul ou
soleil et appoint, consigne confort, et température de la sonde choisie dans les options."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .analyse import MODE_ARRET, MODE_SOLEIL, MODE_SOLEIL_APPOINT, Zone
from .coordinator import SolisartConfigEntry, SolisartCoordinator
from .entity import SolisartThermostatBase

PRESETS = {"soleil": MODE_SOLEIL, "soleil_appoint": MODE_SOLEIL_APPOINT}
PRESET_DU_MODE = {mode: preset for preset, mode in PRESETS.items()}


async def async_setup_entry(hass: HomeAssistant, entry: SolisartConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    reglages = coordinator.data.reglages
    if reglages is None:
        return
    async_add_entities(SolisartThermostat(coordinator, zone)
                       for zone in reglages.zones if not zone.eau_chaude)


class SolisartThermostat(SolisartThermostatBase, ClimateEntity):
    """Mode Arrêt pour le mode 0 de la carte, Chauffage pour les modes 1 et 2, que le
    préréglage distingue. Rallumer remet le dernier préréglage connu."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = list(PRESETS)
    _attr_supported_features = (ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
                                | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF)
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: SolisartCoordinator, zone: Zone) -> None:
        super().__init__(coordinator, zone, "thermostat")

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = self.mode_carte
        if mode is None:
            return None
        return HVACMode.OFF if mode == MODE_ARRET else HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        return PRESET_DU_MODE.get(self.mode_carte)

    @property
    def target_temperature_step(self) -> float:
        confort = self.confort
        return 10 ** -(confort.decimales if confort else 1)

    def _mode_hvac(self, hvac_mode: HVACMode) -> str:
        return MODE_ARRET if hvac_mode == HVACMode.OFF else self._dernier_mode_actif

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.ecrire(mode=self._mode_hvac(hvac_mode))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.ecrire(mode=PRESETS[preset_mode])

    async def async_set_temperature(self, **kwargs: Any) -> None:
        mode = self._mode_hvac(kwargs[ATTR_HVAC_MODE]) if ATTR_HVAC_MODE in kwargs else None
        await self.ecrire(mode=mode, confort=kwargs.get(ATTR_TEMPERATURE))
