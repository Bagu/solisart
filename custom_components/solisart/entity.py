"""Base commune des entités : un appareil par carte, une entité par balise de status.xml."""
from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .analyse import Mesure
from .api import adresse_de_base
from .const import DOMAIN, FABRICANT
from .coordinator import SolisartCoordinator


class SolisartMesure(CoordinatorEntity[SolisartCoordinator]):
    """Entité liée à une balise de status.xml. Indisponible quand la balise manque ou
    que la sonde est absente (« Dsc »)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolisartCoordinator, balise: str) -> None:
        super().__init__(coordinator)
        entree = coordinator.config_entry
        self.balise = balise
        self._attr_unique_id = f"{entree.entry_id}_{balise}"
        self._attr_translation_placeholders = {"balise": balise.upper()}
        reglages = coordinator.data.reglages
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entree.entry_id)},
            manufacturer=FABRICANT,
            name=FABRICANT,
            sw_version=" / ".join(v for v in (reglages.version_carte, reglages.version_web) if v)
            if reglages else None,
            configuration_url=adresse_de_base(entree.data[CONF_HOST]),
        )
        if self.mesure is None or self.mesure.valeur is None:
            self._attr_entity_registry_enabled_default = False

    @property
    def mesure(self) -> Mesure | None:
        return self.coordinator.data.etat.mesures.get(self.balise)

    @property
    def available(self) -> bool:
        return super().available and self.mesure is not None and self.mesure.valeur is not None
