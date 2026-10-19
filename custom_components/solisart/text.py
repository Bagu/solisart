"""Planning confort/réduit de chaque zone présente, une entité par jour."""
from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .analyse import JOURS, Zone, texte_planning
from .coordinator import SolisartConfigEntry, SolisartCoordinator
from .entity import SolisartReglage

LONGUEUR_MAX = 255
HEURE = r"\d{1,2}(?:[:hH](?:\d{2})?)?"
PLAGE = rf"{HEURE}\s*-\s*{HEURE}"
MOTIF = rf"^\s*({PLAGE}\s*([,;]\s*{PLAGE}\s*)*)?$"


def identifiant_planning(entry_id: str, zone: int, jour: int) -> str:
    """Identifiant unique de l'entité planning d'une zone et d'un jour."""
    return f"{entry_id}_planning_{zone}_{jour}"


async def async_setup_entry(hass: HomeAssistant, entry: SolisartConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    reglages = coordinator.data.reglages
    if reglages is None:
        return
    async_add_entities(
        SolisartPlanning(coordinator, zone, jour)
        for zone in reglages.zones if zone.index in reglages.plannings
        for jour in range(JOURS)
    )


class SolisartPlanning(SolisartReglage, TextEntity):
    """Plages de confort d'un jour, par exemple « 06:00-08:00, 18:00-22:30 » ; le
    reste de la journée est en réduit. Chaîne vide : réduit toute la journée."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.TEXT
    _attr_native_max = LONGUEUR_MAX
    _attr_pattern = MOTIF

    def __init__(self, coordinator: SolisartCoordinator, zone: Zone, jour: int) -> None:
        super().__init__(coordinator, zone, "planning", f"planning_{jour}")
        self.jour = jour
        self._attr_unique_id = identifiant_planning(coordinator.config_entry.entry_id, zone.index, jour)

    @property
    def available(self) -> bool:
        reglages = self.coordinator.data.reglages
        return super().available and reglages is not None and self.index in reglages.plannings

    @property
    def native_value(self) -> str | None:
        reglages = self.coordinator.data.reglages
        if reglages is None or self.index not in reglages.plannings:
            return None
        creneaux = reglages.plannings[self.index][self.jour]
        texte = texte_planning(creneaux)
        return texte if len(texte) <= LONGUEUR_MAX else texte_planning(creneaux, compact=True)

    async def async_set_value(self, value: str) -> None:
        await self.coordinator.ecrire_plannings({(self.index, self.jour): value})
