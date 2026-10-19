"""Base commune des entités : un appareil par carte, une entité par balise de status.xml
ou par réglage d'une zone de param.htm."""
from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .analyse import Mesure, Zone
from .api import adresse_de_base
from .const import DOMAIN, FABRICANT
from .coordinator import SolisartCoordinator


def _appareil(coordinator: SolisartCoordinator) -> DeviceInfo:
    """Fiche de la carte, versions lues sur param.htm quand elle a pu être lue."""
    entree = coordinator.config_entry
    reglages = coordinator.data.reglages
    return DeviceInfo(
        identifiers={(DOMAIN, entree.entry_id)},
        manufacturer=FABRICANT,
        name=FABRICANT,
        sw_version=" / ".join(v for v in (reglages.version_carte, reglages.version_web) if v)
        if reglages else None,
        configuration_url=adresse_de_base(entree.data[CONF_HOST]),
    )


class SolisartMesure(CoordinatorEntity[SolisartCoordinator]):
    """Entité liée à une balise de status.xml. Indisponible quand la balise manque ou
    que la sonde est absente (« Dsc »)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolisartCoordinator, balise: str) -> None:
        super().__init__(coordinator)
        self.balise = balise
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{balise}"
        self._attr_translation_placeholders = {"balise": balise.upper()}
        self._attr_device_info = _appareil(coordinator)
        if self.mesure is None or self.mesure.valeur is None:
            self._attr_entity_registry_enabled_default = False

    @property
    def mesure(self) -> Mesure | None:
        return self.coordinator.data.etat.mesures.get(self.balise)

    @property
    def available(self) -> bool:
        return super().available and self.mesure is not None and self.mesure.valeur is not None


class SolisartReglage(CoordinatorEntity[SolisartCoordinator]):
    """Entité liée à un champ d'une zone de param.htm (U06_x, U09_x...). Nommée
    d'après le libellé de la zone lu sur la carte, ou son numéro à défaut ; l'eau
    chaude a ses propres noms (clé de traduction suivie de « _ecs »)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolisartCoordinator, zone: Zone, champ: str, cle: str) -> None:
        super().__init__(coordinator)
        self.index = zone.index
        self.champ = f"{champ}_{zone.index}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.champ}"
        self._attr_device_info = _appareil(coordinator)
        if zone.eau_chaude:
            self._attr_translation_key = f"{cle}_ecs"
        else:
            self._attr_translation_key = cle
            self._attr_translation_placeholders = {"zone": zone.libelle or str(zone.index + 1)}

    @property
    def zone(self) -> Zone | None:
        reglages = self.coordinator.data.reglages
        if reglages is None:
            return None
        return next((z for z in reglages.zones if z.index == self.index), None)

    @property
    def available(self) -> bool:
        return super().available and self.zone is not None
