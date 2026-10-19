"""Données de diagnostic, identifiants masqués."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import SolisartConfigEntry

A_MASQUER = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(hass: HomeAssistant,
                                             entry: SolisartConfigEntry) -> dict[str, Any]:
    donnees = entry.runtime_data.data
    return {
        "entree": async_redact_data(dict(entry.data), A_MASQUER),
        "options": dict(entry.options),
        "mesures": {k: m.brut for k, m in donnees.etat.mesures.items()},
        "balises_inconnues": donnees.etat.inconnues,
        "reglages": asdict(donnees.reglages) if donnees.reglages else None,
    }
