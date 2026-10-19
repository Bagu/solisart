"""Ajout de la carte depuis l'interface de Home Assistant."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .analyse import PageInattendue
from .api import AuthentificationRefusee, CarteInjoignable, SolisartClient, adresse_de_base
from .const import (
    CONF_INTERVALLE_ETAT,
    CONF_INTERVALLE_REGLAGES,
    DOMAIN,
    FABRICANT,
    INTERVALLE_ETAT,
    INTERVALLE_ETAT_MIN,
    INTERVALLE_REGLAGES,
    INTERVALLE_REGLAGES_MIN,
)

SCHEMA_IDENTIFIANT = {
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
}


async def essayer(hass: HomeAssistant, hote: str, utilisateur: str, mot_de_passe: str) -> str | None:
    """Lit les deux pages de la carte. Rend la clé d'erreur à afficher, ou None."""
    client = SolisartClient(async_get_clientsession(hass), hote, utilisateur, mot_de_passe)
    try:
        await client.lire_etat()
        await client.lire_reglages()
    except AuthentificationRefusee:
        return "invalid_auth"
    except CarteInjoignable:
        return "cannot_connect"
    except PageInattendue:
        return "not_solisart"
    return None


class SolisartConfigFlow(ConfigFlow, domain=DOMAIN):
    """Adresse de la carte et identifiant de son interface web."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        erreurs: dict[str, str] = {}
        if user_input is not None:
            base = adresse_de_base(user_input[CONF_HOST]).lower()
            await self.async_set_unique_id(base)
            self._abort_if_unique_id_configured()
            erreur = await essayer(self.hass, user_input[CONF_HOST],
                                   user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            if erreur is None:
                return self.async_create_entry(title=f"{FABRICANT} ({user_input[CONF_HOST]})",
                                               data=user_input)
            erreurs["base"] = erreur
        schema = vol.Schema({vol.Required(CONF_HOST): str, **SCHEMA_IDENTIFIANT})
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=erreurs,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entree = self._get_reauth_entry()
        erreurs: dict[str, str] = {}
        if user_input is not None:
            erreur = await essayer(self.hass, entree.data[CONF_HOST],
                                   user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            if erreur is None:
                return self.async_update_reload_and_abort(entree, data_updates=user_input)
            erreurs["base"] = erreur
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(SCHEMA_IDENTIFIANT),
            description_placeholders={"host": entree.data[CONF_HOST]},
            errors=erreurs,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return SolisartOptionsFlow()


class SolisartOptionsFlow(OptionsFlow):
    """Rythme de lecture des deux pages."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema({
            vol.Required(CONF_INTERVALLE_ETAT,
                         default=options.get(CONF_INTERVALLE_ETAT, INTERVALLE_ETAT)):
                vol.All(vol.Coerce(int), vol.Range(min=INTERVALLE_ETAT_MIN)),
            vol.Required(CONF_INTERVALLE_REGLAGES,
                         default=options.get(CONF_INTERVALLE_REGLAGES, INTERVALLE_REGLAGES)):
                vol.All(vol.Coerce(int), vol.Range(min=INTERVALLE_REGLAGES_MIN)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
