"""
Prouve que les tests attrapent les défauts : chaque sabotage d'analyse.py ou d'api.py
doit faire échouer au moins un test, et la version saine doit tous les passer.

    python outils/contre_epreuve.py

Les tests tournent avec le Python de .venv s'il existe : les sabotages d'api.py ne
sont vérifiables qu'avec aiohttp, et comptent comme ratés sans lui.
"""
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CC = os.path.join(RACINE, "custom_components", "solisart")
VENV = os.path.join(RACINE, ".venv", "Scripts", "python.exe")
PYTHON = VENV if os.path.exists(VENV) else sys.executable

SABOTAGES = [
    ("sonde déconnectée lue comme 0", "analyse.py", "return Mesure(TEMPERATURE, None, texte)", "return Mesure(TEMPERATURE, 0.0, texte)"),
    ("drapeau de zone ignoré", "analyse.py", 'if drapeau == "1"}', "}"),
    ("zéro négatif gardé", "analyse.py", "_nombre(texte) + 0.0", "_nombre(texte)"),
    ("zone à l'arrêt modifiable", "analyse.py", "if mode == MODE_ARRET else set()", "if False else set()"),
    ("mode inconnu gardé", "analyse.py", "(v if v in MODES else MODE_ARRET)", "v"),
    ("balise inconnue devinée", "analyse.py", "            etat.inconnues[element.tag] = texte\n", "            pass\n"),
    ("hors-gel transmis case décochée", "analyse.py", "        desactives.update(CHAMPS_HORS_GEL)\n", "        pass\n"),
    ("champ désactivé transmis", "analyse.py", 'if not nom or "disabled" in attributs:', "if not nom:"),
    ("case décochée recopiée à 1", "analyse.py", '"1" if cochee else "0"', '"1"'),
    ("mode demandé ignoré", "analyse.py", "listes.update({nom: v for nom, v in changements.items() if nom in listes})", "pass"),
    ("champs d'une zone arrêtée transmis", "analyse.py", 'if listes.get(f"U06_{zone}") == MODE_ARRET:', "if False:"),
    ("consigne hors bornes acceptée", "analyse.py", "if not consigne.minimum <= nombre <= consigne.maximum:", "if False:"),
    ("nombres relus comparés comme textes", "analyse.py", "(lu and _nombre(lu) is not None and _nombre(lu) == _nombre(voulu))", "False"),
    ("corps encodé en UTF-8", "analyse.py", "urlencode(corps, encoding=ENCODAGE)", "urlencode(corps)"),
    ("écritures simultanées", "api.py", "        async with self._verrou:\n", "        if True:\n"),
    ("champ refusé envoyé quand même", "api.py", "            if refuses:\n", "            if False:\n"),
    ("valeurs non relues acceptées", "api.py", "            if restants:\n", "            if False:\n"),
    ("redirection suivie", "api.py", "allow_redirects=False", "allow_redirects=True"),
    ("Referer absent", "api.py", '            "Referer": adresse,\n', ""),
]


def tests_passent() -> bool:
    """Lance la suite de tests et rend vrai si elle passe."""
    r = subprocess.run([PYTHON, "-m", "unittest", "discover", "tests"],
                       cwd=RACINE, capture_output=True)
    return r.returncode == 0


def main() -> int:
    avec_aiohttp = subprocess.run([PYTHON, "-c", "import aiohttp"], capture_output=True).returncode == 0
    rates = []
    for nom, fichier, avant, apres in SABOTAGES:
        if fichier == "api.py" and not avec_aiohttp:
            rates.append(f"{nom} : non vérifiable, aiohttp absent de {PYTHON}")
            continue
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
    print(f"contre-épreuve {'OK' if bon else 'ÉCHEC'} : {len(SABOTAGES) - len(rates)}/{len(SABOTAGES)} sabotages détectés, témoin sain {'OK' if sain else 'en échec'}")
    return 0 if bon else 1


if __name__ == "__main__":
    sys.exit(main())
