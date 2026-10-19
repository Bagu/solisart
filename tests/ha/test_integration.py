"""Intégration dans un Home Assistant de test, carte simulée par aioclient_mock.

    .venv/Scripts/python -m pytest
"""
from pathlib import Path

import aiohttp
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.solisart.const import CONF_INTERVALLE_ETAT, CONF_INTERVALLE_REGLAGES, DOMAIN

FIXTURES = Path(__file__).parents[1] / "fixtures"
HOTE = "192.0.2.10"
STATUS = f"http://{HOTE}/XML/status.xml"
PARAM = f"http://{HOTE}/param.htm"
DONNEES = {CONF_HOST: HOTE, CONF_USERNAME: "essai", CONF_PASSWORD: "mot-de-passe-essai"}


def carte(aioclient_mock, status=200, param=200, param_corps=None, exc=None):
    """Simule la carte : pages réelles anonymisées, ou erreurs demandées."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATUS, status=status, content=(FIXTURES / "status_reel.xml").read_bytes(), exc=exc)
    aioclient_mock.get(PARAM, status=param, content=param_corps or (FIXTURES / "param_reel.htm").read_bytes())


async def installer(hass, aioclient_mock, **carte_kw):
    """Ajoute une entrée déjà configurée et la démarre."""
    carte(aioclient_mock, **carte_kw)
    entree = MockConfigEntry(domain=DOMAIN, data=DONNEES, unique_id=f"http://{HOTE}")
    entree.add_to_hass(hass)
    await hass.config_entries.async_setup(entree.entry_id)
    await hass.async_block_till_done()
    return entree


def entite(hass, entree, balise):
    """entity_id de la balise, retrouvé par son identifiant unique."""
    registre = er.async_get(hass)
    for domaine in ("sensor", "binary_sensor"):
        trouve = registre.async_get_entity_id(domaine, DOMAIN, f"{entree.entry_id}_{balise}")
        if trouve:
            return trouve
    return None


async def test_ajout_reussi(hass: HomeAssistant, aioclient_mock):
    carte(aioclient_mock)
    resultat = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert resultat["type"] is FlowResultType.FORM
    resultat = await hass.config_entries.flow.async_configure(resultat["flow_id"], DONNEES)
    assert resultat["type"] is FlowResultType.CREATE_ENTRY
    assert resultat["data"] == DONNEES
    assert resultat["result"].unique_id == f"http://{HOTE}"


async def _erreur_du_formulaire(hass, aioclient_mock, **carte_kw):
    carte(aioclient_mock, **carte_kw)
    resultat = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    resultat = await hass.config_entries.flow.async_configure(resultat["flow_id"], DONNEES)
    assert resultat["type"] is FlowResultType.FORM
    return resultat["errors"]["base"]


async def test_ajout_carte_injoignable(hass, aioclient_mock):
    assert await _erreur_du_formulaire(hass, aioclient_mock, exc=aiohttp.ClientError()) == "cannot_connect"


async def test_ajout_identifiant_refuse(hass, aioclient_mock):
    assert await _erreur_du_formulaire(hass, aioclient_mock, param=401) == "invalid_auth"


async def test_ajout_autre_appareil(hass, aioclient_mock):
    corps = b"<html><body>Autre appareil</body></html>"
    assert await _erreur_du_formulaire(hass, aioclient_mock, param_corps=corps) == "not_solisart"


async def test_ajout_en_double(hass, aioclient_mock):
    await installer(hass, aioclient_mock)
    resultat = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    resultat = await hass.config_entries.flow.async_configure(
        resultat["flow_id"], {**DONNEES, CONF_HOST: f"http://{HOTE}/"})
    assert resultat["type"] is FlowResultType.ABORT
    assert resultat["reason"] == "already_configured"


async def test_entites(hass, aioclient_mock):
    entree = await installer(hass, aioclient_mock)
    assert entree.state is ConfigEntryState.LOADED
    etat = lambda balise: hass.states.get(entite(hass, entree, balise))  # noqa: E731
    assert etat("t1").state == "53.4"
    assert etat("t1").attributes["unit_of_measurement"] == "°C"
    assert etat("triac6").state == "100.0"
    assert etat("v3vsol").state == "0.0"
    assert etat("fl5").state == "0.0"
    assert etat("mrel1").state == STATE_OFF
    nombre = len(er.async_entries_for_config_entry(er.async_get(hass), entree.entry_id))
    assert nombre == 45, nombre


async def test_sonde_absente_desactivee(hass, aioclient_mock):
    entree = await installer(hass, aioclient_mock)
    registre = er.async_get(hass)
    assert registre.async_get(entite(hass, entree, "t5")).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registre.async_get(entite(hass, entree, "t1")).disabled_by is None


async def test_noms_traduits(hass, aioclient_mock):
    entree = await installer(hass, aioclient_mock)
    nom = lambda balise: hass.states.get(entite(hass, entree, balise)).name  # noqa: E731
    assert nom("t1") == "SolisArt Probe T1"
    assert nom("triac2") == "SolisArt Circulator TRIAC2"
    assert nom("v3vapp") == "SolisArt Valve V3VAPP"
    assert nom("fl1") == "SolisArt Flow FL1"
    assert nom("mrel1") == "SolisArt Relay MREL1"


async def test_carte_perdue_puis_retrouvee(hass, aioclient_mock):
    entree = await installer(hass, aioclient_mock)
    coordinateur = entree.runtime_data
    carte(aioclient_mock, exc=aiohttp.ClientError())
    await coordinateur.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entite(hass, entree, "t1")).state == STATE_UNAVAILABLE
    carte(aioclient_mock)
    await coordinateur.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entite(hass, entree, "t1")).state == "53.4"


async def test_param_lu_au_rythme_lent(hass, aioclient_mock):
    entree = await installer(hass, aioclient_mock)
    await entree.runtime_data.async_refresh()
    appels = [str(appel[1]) for appel in aioclient_mock.mock_calls]
    assert appels.count(STATUS) == 2 and appels.count(PARAM) == 1, appels


async def test_identifiant_refuse_demande_reauthentification(hass, aioclient_mock):
    entree = await installer(hass, aioclient_mock, param=401)
    assert entree.state is ConfigEntryState.SETUP_ERROR
    flux = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flux] == ["reauth"]
    carte(aioclient_mock)
    resultat = await hass.config_entries.flow.async_configure(
        flux[0]["flow_id"], {CONF_USERNAME: "essai", CONF_PASSWORD: "nouveau"})
    assert resultat["type"] is FlowResultType.ABORT
    assert resultat["reason"] == "reauth_successful"
    assert entree.data[CONF_PASSWORD] == "nouveau"


async def test_options(hass, aioclient_mock):
    entree = await installer(hass, aioclient_mock)
    resultat = await hass.config_entries.options.async_init(entree.entry_id)
    resultat = await hass.config_entries.options.async_configure(
        resultat["flow_id"], {CONF_INTERVALLE_ETAT: 60, CONF_INTERVALLE_REGLAGES: 600})
    assert resultat["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entree.runtime_data.update_interval.total_seconds() == 60


async def test_diagnostic_sans_identifiant(hass, aioclient_mock, hass_client):
    entree = await installer(hass, aioclient_mock)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entree)
    texte = str(diag)
    assert DONNEES[CONF_PASSWORD] not in texte and HOTE not in texte
    assert diag["balises_inconnues"] == {"flpws": "1", "getSave": "142"}
    assert [z["index"] for z in diag["reglages"]["zones"]] == [0, 1, 6]
