"""Températures, circulateurs, vannes et débits de status.xml, et période en cours
(Confort ou Réduit) de chaque zone selon son planning et l'horloge de la carte."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .analyse import DEBIT, POURCENTAGE, TEMPERATURE, Zone, periode_en_cours
from .coordinator import SolisartConfigEntry, SolisartCoordinator
from .entity import SolisartMesure, SolisartReglage


async def async_setup_entry(hass: HomeAssistant, entry: SolisartConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SolisartCapteur(coordinator, balise)
        for balise, mesure in coordinator.data.etat.mesures.items()
        if mesure.nature in (TEMPERATURE, POURCENTAGE, DEBIT)
    )
    reglages = coordinator.data.reglages
    if reglages is not None:
        async_add_entities(SolisartPeriode(coordinator, zone)
                           for zone in reglages.zones if zone.index in reglages.plannings)


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


class SolisartPeriode(SolisartReglage, SensorEntity):
    """Confort ou Réduit : la demi-heure en cours du planning de la zone, à l'heure de la
    carte. Indisponible si l'horloge de la carte ou le planning n'a pas pu être lu."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["confort", "reduit"]

    def __init__(self, coordinator: SolisartCoordinator, zone: Zone) -> None:
        super().__init__(coordinator, zone, "periode", "periode")

    @property
    def _confort(self) -> bool | None:
        reglages = self.coordinator.data.reglages
        if reglages is None:
            return None
        return periode_en_cours(reglages.plannings, self.index, self.coordinator.data.horloge)

    @property
    def available(self) -> bool:
        return super().available and self._confort is not None

    @property
    def native_value(self) -> str | None:
        confort = self._confort
        if confort is None:
            return None
        return "confort" if confort else "reduit"
