"""Base commune des entités : un appareil par carte, une entité par balise de status.xml
ou par réglage d'une zone de param.htm."""
from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .analyse import MODE_SOLEIL, MODE_SOLEIL_APPOINT, Consigne, Mesure, Zone
from .api import adresse_de_base
from .const import DOMAIN, FABRICANT, cle_sonde

MODES_ACTIFS = (MODE_SOLEIL, MODE_SOLEIL_APPOINT)
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


class SolisartThermostatBase(SolisartReglage):
    """Base des entités climate et water_heater d'une zone : mode de la carte, consigne
    confort, consigne réduit en attribut, et température de la sonde choisie dans les
    options (aucune par défaut). Retient le dernier mode actif (soleil seul ou soleil
    et appoint) pour le rallumage."""

    def __init__(self, coordinator: SolisartCoordinator, zone: Zone, cle: str) -> None:
        super().__init__(coordinator, zone, cle, cle)
        self._sonde: str | None = coordinator.config_entry.options.get(cle_sonde(zone.index))
        self._dernier_mode_actif = zone.mode if zone.mode in MODES_ACTIFS else MODE_SOLEIL_APPOINT

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._sonde:
            self.async_on_remove(async_track_state_change_event(
                self.hass, [self._sonde], self._sonde_changee))

    @callback
    def _sonde_changee(self, _event: Event[EventStateChangedData]) -> None:
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        zone = self.zone
        if zone is not None and zone.mode in MODES_ACTIFS:
            self._dernier_mode_actif = zone.mode
        super()._handle_coordinator_update()

    @property
    def mode_carte(self) -> str | None:
        zone = self.zone
        return zone.mode if zone else None

    @property
    def confort(self) -> Consigne | None:
        zone = self.zone
        return zone.confort if zone else None

    @property
    def current_temperature(self) -> float | None:
        etat = self.hass.states.get(self._sonde) if self._sonde else None
        try:
            return float(etat.state) if etat else None
        except ValueError:
            return None

    @property
    def target_temperature(self) -> float | None:
        confort = self.confort
        return confort.valeur if confort else None

    @property
    def min_temp(self) -> float:
        confort = self.confort
        return confort.minimum if confort and confort.minimum is not None else super().min_temp

    @property
    def max_temp(self) -> float:
        confort = self.confort
        return confort.maximum if confort and confort.maximum is not None else super().max_temp

    @property
    def extra_state_attributes(self) -> dict[str, float | None]:
        zone = self.zone
        return {"consigne_reduit": zone.reduit.valeur if zone else None}

    async def ecrire(self, mode: str | None = None, confort: float | None = None) -> None:
        """Écrit un mode (U06_x) et une consigne confort (U09_x) en un seul envoi. Le
        client refuse avant tout envoi une consigne d'une zone qui reste à l'arrêt."""
        demandes: dict[str, str | float] = {}
        if mode is not None:
            demandes[f"U06_{self.index}"] = mode
        if confort is not None:
            demandes[f"U09_{self.index}"] = confort
        if demandes:
            await self.coordinator.ecrire_reglages(demandes)
