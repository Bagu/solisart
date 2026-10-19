"""
Prouve que les tests Home Assistant attrapent les défauts : chaque sabotage doit faire
échouer au moins un test, et la version saine doit tous les passer.

    .venv/Scripts/python outils/contre_epreuve_ha.py
"""
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CC = os.path.join(RACINE, "custom_components", "solisart")

SABOTAGES = [
    ("relais inversé", "binary_sensor.py", "return mesure.valeur if mesure else None", "return (not mesure.valeur) if mesure else None"),
    ("sonde absente activée", "entity.py", "self._attr_entity_registry_enabled_default = False", "pass"),
    ("mot de passe dans le diagnostic", "diagnostics.py", "A_MASQUER = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME}", "A_MASQUER = {CONF_USERNAME}"),
    ("param.htm lu à chaque relève", "coordinator.py", "maintenant - self._reglages_lus_a >= self._rythme_reglages", "True"),
    ("401 pris pour une panne", "api.py", "raise AuthentificationRefusee\n", "raise CarteInjoignable('401')\n"),
    ("doublon accepté", "config_flow.py", "self._abort_if_unique_id_configured()", "pass"),
    ("identifiant unique gardé à la reconfiguration", "config_flow.py", "entree, unique_id=base, title=", "entree, title="),
    ("mot de passe vide écrasé", "config_flow.py", "user_input.get(CONF_PASSWORD) or entree.data[CONF_PASSWORD]", 'user_input.get(CONF_PASSWORD, "")'),
    ("doublon accepté à la reconfiguration", "config_flow.py", '                return self.async_abort(reason="already_configured")\n', "                pass\n"),
    ("reconfiguration sans essai de la carte", "config_flow.py", "            erreur = await essayer(self.hass, donnees[CONF_HOST],", "            erreur = None if True else await essayer(self.hass, donnees[CONF_HOST],"),
    ("options ignorées", "coordinator.py", "entree.options.get(CONF_INTERVALLE_ETAT, INTERVALLE_ETAT)", "INTERVALLE_ETAT"),
    ("écriture non confirmée acceptée", "api.py", "            restants = ecarts(relue, changements)\n", "            restants = {}\n"),
    ("copie vers la dernière cible seulement", "__init__.py", "par_entree.setdefault(entree_cible.entry_id, {})[(zone_cible, jour_cible)] = texte", "par_entree[entree_cible.entry_id] = {(zone_cible, jour_cible): texte}"),
    ("planning écrit dans le mauvais jour", "text.py", "{(self.index, self.jour): value}", "{(self.index, 0): value}"),
    ("page relue non publiée", "coordinator.py", "            self.async_set_updated_data(Donnees(etat=self.data.etat, reglages=reglages,\n                                                horloge=self.data.horloge))\n", "            pass\n"),
    ("échec d'écriture passé sous silence", "coordinator.py", "            raise erreur_ecriture(err) from err\n", "            return\n"),
    ("refus pris pour une panne", "coordinator.py", "    if isinstance(err, ReglageRefuse):\n", "    if False:\n"),
    ("écarts relus non transmis", "coordinator.py", 'translation_placeholders={"detail": detail})', 'translation_placeholders={"detail": ""})'),
    ("lecture en échec sans sa clé", "coordinator.py", 'translation_key="lecture_etat_impossible"', 'translation_key="carte_injoignable"'),
    ("option liée au mauvais mode", "select.py", '"soleil": MODE_SOLEIL,', '"soleil": MODE_SOLEIL_APPOINT,'),
    ("consigne d'une zone arrêtée disponible", "number.py", "consigne is not None and consigne.actif", "consigne is not None"),
    ("bornes de la page ignorées", "number.py", "return consigne.maximum if consigne and consigne.maximum is not None else super().native_max_value", "return super().native_max_value"),
    ("demandes d'un lot perdues", "coordinator.py", "self._en_attente.update(demandes)", "self._en_attente = dict(demandes)"),
    ("valeur la plus ancienne gardée", "coordinator.py", "self._en_attente.update(demandes)", "self._en_attente = {**demandes, **self._en_attente}"),
    ("lot laissé en suspens au déchargement", "coordinator.py", '            self._lot.set_exception(HomeAssistantError(translation_domain=DOMAIN,\n                                                       translation_key="ecriture_annulee"))\n', "            pass\n"),
    ("confort et réduit confondus", "number.py", 'return zone.confort if self._cle == "confort" else zone.reduit', "return zone.confort"),
    ("horloge jamais relue", "coordinator.py", "horloge=await self._lire_horloge())", "horloge=None)"),
    ("horloge illisible fatale à la relève", "coordinator.py", "        except (CarteInjoignable, PageInattendue) as err:\n            if self._horloge_lue:", "        except ZeroDivisionError as err:\n            if self._horloge_lue:"),
    ("horloge perdue après une écriture", "coordinator.py", "horloge=self.data.horloge))", "horloge=None))"),
    ("confort et réduit inversés dans la période", "sensor.py", '"confort" if confort else "reduit"', '"reduit" if confort else "confort"'),
    ("préréglages inversés", "climate.py", '{"soleil": MODE_SOLEIL, "soleil_appoint": MODE_SOLEIL_APPOINT}', '{"soleil": MODE_SOLEIL_APPOINT, "soleil_appoint": MODE_SOLEIL}'),
    ("rallumage sans le dernier préréglage", "climate.py", "else self._dernier_mode_actif", "else MODE_SOLEIL_APPOINT"),
    ("thermostat créé pour l'eau chaude", "climate.py", "for zone in reglages.zones if not zone.eau_chaude)", "for zone in reglages.zones)"),
    ("dernier mode actif jamais retenu", "entity.py", "            self._dernier_mode_actif = zone.mode\n", "            pass\n"),
    ("sonde non suivie", "entity.py", "        if self._sonde:\n            self.async_on_remove(", "        if False:\n            self.async_on_remove("),
    ("sonde de la mauvaise zone", "entity.py", "options.get(cle_sonde(zone.index))", "options.get(cle_sonde(0))"),
    ("consigne réduit prise pour la cible", "entity.py", "        return confort.valeur if confort else None\n", "        return self.zone.reduit.valeur if confort else None\n"),
    ("consigne et mode en deux envois", "entity.py", "            demandes[f\"U09_{self.index}\"] = confort\n        if demandes:\n            await self.coordinator.ecrire_reglages(demandes)", "            await self.coordinator.ecrire_reglages({f\"U09_{self.index}\": confort})\n        if demandes:\n            await self.coordinator.ecrire_reglages(demandes)"),
    ("eco et performance inversés", "water_heater.py", "STATE_ECO: MODE_SOLEIL, STATE_PERFORMANCE: MODE_SOLEIL_APPOINT", "STATE_ECO: MODE_SOLEIL_APPOINT, STATE_PERFORMANCE: MODE_SOLEIL"),
    ("chauffe-eau rallumé sans son dernier mode", "water_heater.py", "await self.ecrire(mode=self._dernier_mode_actif)", "await self.ecrire(mode=MODE_SOLEIL_APPOINT)"),
    ("sondes absentes des options", "config_flow.py", "            for zone in zones\n        })", "            for zone in []\n        })"),
    ("version jamais contrôlée", "coordinator.py", "        if self._ecriture_forcee or version_testee(reglages):\n            return\n", "        return\n"),
    ("version contrôlée seulement avant le regroupement", "coordinator.py", "self.client.ecrire_reglages(ecriture, self._controler_version)", "self.client.ecrire_reglages(ecriture)"),
    ("planning non contrôlé sur la page fraîche", "coordinator.py", "self.client.ecrire_plannings(demandes, self._controler_version)", "self.client.ecrire_plannings(demandes)"),
    ("problème jamais ouvert", "coordinator.py", "        ir.async_create_issue(\n", "        (lambda *a, **k: None)(\n"),
    ("problème jamais retiré", "coordinator.py", "            ir.async_delete_issue(self.hass, DOMAIN, ident)\n", "            pass\n"),
    ("option d'écriture ignorée", "coordinator.py", "entree.options.get(CONF_ECRITURE_VERSION_NON_TESTEE, False)", "False"),
    ("problème laissé après suppression", "__init__.py", "    ir.async_delete_issue(hass, DOMAIN, identifiant_probleme(entry.entry_id))\n", "    pass\n"),
    ("option activée par défaut", "config_flow.py", "default=options.get(CONF_ECRITURE_VERSION_NON_TESTEE, False)", "default=options.get(CONF_ECRITURE_VERSION_NON_TESTEE, True)"),
    ("version éprouvée oubliée", "const.py", '    ("SRB_32MX_vD.50-5", "WEB_vA.98"),\n', '    ("SRB_32MX_vD.50-5", "WEB_vA.97"),\n'),
]


def tests_passent() -> bool:
    env = dict(os.environ)
    if sys.platform == "win32":
        env["PYTHONPATH"] = os.path.join(RACINE, "tests", "ha", "windows")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"],
                       cwd=RACINE, capture_output=True, env=env)
    return r.returncode == 0


def main() -> int:
    rates = []
    for nom, fichier, avant, apres in SABOTAGES:
        chemin = os.path.join(CC, fichier)
        with open(chemin, "rb") as f:
            octets = f.read()
        origine = octets.decode("utf-8").replace("\r\n", "\n")
        if origine.count(avant) != 1:
            rates.append(f"{nom} : motif introuvable")
            continue
        try:
            with open(chemin, "w", encoding="utf-8", newline="\n") as f:
                f.write(origine.replace(avant, apres))
            if tests_passent():
                rates.append(f"{nom} : non détecté")
        finally:
            with open(chemin, "wb") as f:
                f.write(octets)
    sain = tests_passent()
    for r in rates:
        print(r)
    bon = not rates and sain
    print(f"contre-épreuve HA {'OK' if bon else 'ÉCHEC'} : {len(SABOTAGES) - len(rates)}/{len(SABOTAGES)} sabotages détectés, témoin sain {'OK' if sain else 'en échec'}")
    return 0 if bon else 1


if __name__ == "__main__":
    sys.exit(main())
