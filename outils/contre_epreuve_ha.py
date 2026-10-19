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
    ("options ignorées", "coordinator.py", "entree.options.get(CONF_INTERVALLE_ETAT, INTERVALLE_ETAT)", "INTERVALLE_ETAT"),
]


def tests_passent() -> bool:
    env = dict(os.environ, PYTHONPATH=os.path.join(RACINE, "tests", "ha", "windows"))
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"],
                       cwd=RACINE, capture_output=True, env=env)
    return r.returncode == 0


def main() -> int:
    rates = []
    for nom, fichier, avant, apres in SABOTAGES:
        chemin = os.path.join(CC, fichier)
        with open(chemin, encoding="utf-8") as f:
            origine = f.read()
        if origine.count(avant) != 1:
            rates.append(f"{nom} : motif introuvable")
            continue
        try:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(origine.replace(avant, apres))
            if tests_passent():
                rates.append(f"{nom} : non détecté")
        finally:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(origine)
    sain = tests_passent()
    for r in rates:
        print(r)
    bon = not rates and sain
    print(f"contre-épreuve HA {'OK' if bon else 'ÉCHEC'} : {len(SABOTAGES) - len(rates)}/{len(SABOTAGES)} sabotages détectés, témoin sain {'OK' if sain else 'en échec'}")
    return 0 if bon else 1


if __name__ == "__main__":
    sys.exit(main())
