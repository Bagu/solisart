"""Relais de status.xml (On / Off)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .analyse import RELAIS
from .coordinator import SolisartConfigEntry
from .entity import SolisartMesure


async def async_setup_entry(hass: HomeAssistant, entry: SolisartConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SolisartRelais(coordinator, balise)
        for balise, mesure in coordinator.data.etat.mesures.items()
        if mesure.nature == RELAIS
    )


class SolisartRelais(SolisartMesure, BinarySensorEntity):
    """Sortie tout ou rien de la carte."""

    _attr_translation_key = "relais"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool | None:
        mesure = self.mesure
        return mesure.valeur if mesure else None
