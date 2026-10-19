"""Consignes de confort (U09_x) et de réduit (U10_x) de chaque zone présente."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .analyse import Consigne, Zone
from .coordinator import SolisartConfigEntry, SolisartCoordinator
from .entity import SolisartReglage

CONSIGNES = (("U09", "confort"), ("U10", "reduit"))


async def async_setup_entry(hass: HomeAssistant, entry: SolisartConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    reglages = coordinator.data.reglages
    if reglages is None:
        return
    async_add_entities(
        SolisartConsigne(coordinator, zone, champ, cle)
        for zone in reglages.zones
        for champ, cle in CONSIGNES
    )


class SolisartConsigne(SolisartReglage, NumberEntity):
    """Température de consigne, bornes et pas lus sur la page. Indisponible quand la
    carte désactive le champ (zone à l'arrêt) ou n'en donne pas les bornes."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: SolisartCoordinator, zone: Zone, champ: str, cle: str) -> None:
        super().__init__(coordinator, zone, champ, cle)
        self._cle = cle

    @property
    def consigne(self) -> Consigne | None:
        zone = self.zone
        if zone is None:
            return None
        return zone.confort if self._cle == "confort" else zone.reduit

    @property
    def available(self) -> bool:
        consigne = self.consigne
        return (super().available and consigne is not None and consigne.actif
                and consigne.minimum is not None and consigne.maximum is not None)

    @property
    def native_value(self) -> float | None:
        consigne = self.consigne
        return consigne.valeur if consigne else None

    @property
    def native_min_value(self) -> float:
        consigne = self.consigne
        return consigne.minimum if consigne and consigne.minimum is not None else super().native_min_value

    @property
    def native_max_value(self) -> float:
        consigne = self.consigne
        return consigne.maximum if consigne and consigne.maximum is not None else super().native_max_value

    @property
    def native_step(self) -> float:
        consigne = self.consigne
        return 10 ** -(consigne.decimales if consigne else 1)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.ecrire_reglages({self.champ: value})
