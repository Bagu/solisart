"""Intégration dans un Home Assistant de test, carte simulée par aioclient_mock.

    .venv/Scripts/python -m pytest
"""
import asyncio
from pathlib import Path

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_custom_components
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

from custom_components.solisart.const import CONF_INTERVALLE_ETAT, CONF_INTERVALLE_REGLAGES, DOMAIN
from tests.carte_simulee import appliquer

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


def carte_reglable(aioclient_mock, sourde=False):
    """Simule une carte qui enregistre les POST de param.htm (sauf si `sourde`) et
    répond 302. Rend la liste des corps reçus."""
    page = [(FIXTURES / "param_reel.htm").read_bytes()]
    recus = []

    async def lire(method, url, data):
        return AiohttpClientMockResponse(method, url, response=page[0])

    async def enregistrer(method, url, data):
        recus.append(data)
        if not sourde:
            page[0] = appliquer(page[0], data)
        return AiohttpClientMockResponse(method, url, status=302)

    aioclient_mock.clear_requests()
    aioclient_mock.get(STATUS, content=(FIXTURES / "status_reel.xml").read_bytes())
    aioclient_mock.get(PARAM, side_effect=lire)
    aioclient_mock.post(PARAM, side_effect=enregistrer)
    return recus


async def installer(hass, aioclient_mock, reglable=False, **carte_kw):
    """Ajoute une entrée déjà configurée et la démarre."""
    if not reglable:
        carte(aioclient_mock, **carte_kw)
    entree = MockConfigEntry(domain=DOMAIN, data=DONNEES, unique_id=f"http://{HOTE}")
    entree.add_to_hass(hass)
    await hass.config_entries.async_setup(entree.entry_id)
    await hass.async_block_till_done()
    if entree.state is ConfigEntryState.LOADED:
        entree.runtime_data.delai_regroupement = 0.01
    return entree


def entite(hass, entree, balise):
    """entity_id de la balise ou du champ, retrouvé par son identifiant unique."""
    registre = er.async_get(hass)
    for domaine in ("sensor", "binary_sensor", "select", "number"):
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
    assert nombre == 45 + 3 + 6, nombre


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


async def test_entites_de_reglage(hass, aioclient_mock):
    entree = await installer(hass, aioclient_mock)
    etat = lambda champ: hass.states.get(entite(hass, entree, champ))  # noqa: E731
    assert etat("U06_0").state == "soleil_appoint"
    assert etat("U06_0").name == "SolisArt Mode RDC"
    assert etat("U06_6").name == "SolisArt Hot water mode"
    assert etat("U06_0").attributes["options"] == ["arret", "soleil", "soleil_appoint"]
    assert etat("U09_1").name == "SolisArt Comfort setpoint Etage"
    assert etat("U09_1").state == "18.5"
    assert etat("U10_1").state == "18.0"
    assert (etat("U09_0").attributes["min"], etat("U09_0").attributes["max"]) == (10, 40)
    assert (etat("U10_6").attributes["min"], etat("U10_6").attributes["max"]) == (20, 80)
    assert etat("U09_6").attributes["step"] == 0.1
    assert entite(hass, entree, "U06_2") is None


def _postes(aioclient_mock):
    return [appel for appel in aioclient_mock.mock_calls if appel[0].lower() == "post"]


async def test_mode_ecrit_puis_confirme(hass, aioclient_mock):
    recus = carte_reglable(aioclient_mock)
    entree = await installer(hass, aioclient_mock, reglable=True)
    await hass.services.async_call("select", "select_option",
                                   {"entity_id": entite(hass, entree, "U06_0"), "option": "soleil"},
                                   blocking=True)
    assert len(recus) == 1 and b"U06_0=1&" in recus[0] and b"U06_1=2&" in recus[0]
    entetes = _postes(aioclient_mock)[0][3]
    assert entetes["Referer"] == PARAM
    assert entetes["Content-Type"] == "application/x-www-form-urlencoded"
    assert hass.states.get(entite(hass, entree, "U06_0")).state == "soleil"


async def test_consigne_ecrite(hass, aioclient_mock):
    recus = carte_reglable(aioclient_mock)
    entree = await installer(hass, aioclient_mock, reglable=True)
    await hass.services.async_call("number", "set_value",
                                   {"entity_id": entite(hass, entree, "U09_6"), "value": 55},
                                   blocking=True)
    assert b"U09_6=55.0&" in recus[0]
    assert hass.states.get(entite(hass, entree, "U09_6")).state == "55.0"


async def test_zone_arretee_consignes_indisponibles(hass, aioclient_mock):
    carte_reglable(aioclient_mock)
    entree = await installer(hass, aioclient_mock, reglable=True)
    await hass.services.async_call("select", "select_option",
                                   {"entity_id": entite(hass, entree, "U06_1"), "option": "arret"},
                                   blocking=True)
    assert hass.states.get(entite(hass, entree, "U09_1")).state == STATE_UNAVAILABLE
    assert hass.states.get(entite(hass, entree, "U10_1")).state == STATE_UNAVAILABLE
    assert hass.states.get(entite(hass, entree, "U09_0")).state == "18.5"


async def test_carte_qui_n_applique_rien(hass, aioclient_mock):
    recus = carte_reglable(aioclient_mock, sourde=True)
    entree = await installer(hass, aioclient_mock, reglable=True)
    with pytest.raises(HomeAssistantError, match="U06_6"):
        await hass.services.async_call("select", "select_option",
                                       {"entity_id": entite(hass, entree, "U06_6"), "option": "arret"},
                                       blocking=True)
    await hass.async_block_till_done()
    assert len(recus) == 1
    assert hass.states.get(entite(hass, entree, "U06_6")).state == "soleil_appoint"


async def test_demandes_rapprochees_regroupees(hass, aioclient_mock):
    recus = carte_reglable(aioclient_mock)
    entree = await installer(hass, aioclient_mock, reglable=True)
    entree.runtime_data.delai_regroupement = 0.2
    regler = lambda champ, valeur: hass.services.async_call(  # noqa: E731
        "number", "set_value", {"entity_id": entite(hass, entree, champ), "value": valeur}, blocking=True)
    await asyncio.gather(regler("U09_6", 52), regler("U09_6", 53), regler("U10_6", 40))
    assert len(recus) == 1
    assert b"U09_6=53.0&" in recus[0] and b"U10_6=40.0&" in recus[0]
    assert hass.states.get(entite(hass, entree, "U09_6")).state == "53.0"


async def test_lot_annule_au_dechargement(hass, aioclient_mock):
    recus = carte_reglable(aioclient_mock)
    entree = await installer(hass, aioclient_mock, reglable=True)
    entree.runtime_data.delai_regroupement = 30
    appel = hass.async_create_task(hass.services.async_call(
        "number", "set_value", {"entity_id": entite(hass, entree, "U09_6"), "value": 52}, blocking=True))
    await asyncio.sleep(0)
    await hass.config_entries.async_unload(entree.entry_id)
    with pytest.raises(HomeAssistantError, match="annulée"):
        await asyncio.wait_for(appel, 5)
    assert recus == []


async def test_logo_fourni(hass):
    integration = (await async_get_custom_components(hass))[DOMAIN]
    assert integration.has_branding
    dossier = Path(integration.file_path) / "brand"
    for nom in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png", "dark_logo.png", "dark_logo@2x.png"):
        assert (dossier / nom).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", nom
