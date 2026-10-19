"""Températures, circulateurs, vannes et débits de status.xml."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .analyse import DEBIT, POURCENTAGE, TEMPERATURE
from .coordinator import SolisartConfigEntry, SolisartCoordinator
from .entity import SolisartMesure


async def async_setup_entry(hass: HomeAssistant, entry: SolisartConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SolisartCapteur(coordinator, balise)
        for balise, mesure in coordinator.data.etat.mesures.items()
        if mesure.nature in (TEMPERATURE, POURCENTAGE, DEBIT)
    )


class SolisartCapteur(SolisartMesure, SensorEntity):
    """Valeur numérique d'une balise."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SolisartCoordinator, balise: str) -> None:
        super().__init__(coordinator, balise)
        nature = self.mesure.nature
        if nature == TEMPERATURE:
            self._attr_translation_key = "temperature"
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif nature == DEBIT:
            self._attr_translation_key = "debit"
            self._attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
            self._attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
        else:
            self._attr_translation_key = "vanne" if balise.startswith("v3v") else "circulateur"
            self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> float | None:
        mesure = self.mesure
        return mesure.valeur if mesure else None
