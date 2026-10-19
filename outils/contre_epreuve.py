"""
Prouve que les tests attrapent les défauts : chaque sabotage d'analyse.py doit faire
échouer au moins un test, et la version saine doit tous les passer.

    python outils/contre_epreuve.py
"""
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(RACINE, "custom_components", "solisart", "analyse.py")

SABOTAGES = {
    "sonde déconnectée lue comme 0": ("return Mesure(TEMPERATURE, None, texte)", "return Mesure(TEMPERATURE, 0.0, texte)"),
    "drapeau de zone ignoré": ('if drapeau == "1"}', "}"),
    "zéro négatif gardé": ("_nombre(texte) + 0.0", "_nombre(texte)"),
    "zone à l'arrêt modifiable": ("if mode == MODE_ARRET else set()", "if False else set()"),
    "mode inconnu gardé": ("(v if v in MODES else MODE_ARRET)", "v"),
    "balise inconnue devinée": ("            etat.inconnues[element.tag] = texte\n", "            pass\n"),
}


def tests_passent() -> bool:
    """Lance la suite de tests et rend vrai si elle passe."""
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"],
                       cwd=RACINE, capture_output=True)
    return r.returncode == 0


def main() -> int:
    with open(SOURCE, encoding="utf-8") as f:
        origine = f.read()
    rates = []
    try:
        for nom, (avant, apres) in SABOTAGES.items():
            if origine.count(avant) != 1:
                rates.append(f"{nom} : motif introuvable")
                continue
            with open(SOURCE, "w", encoding="utf-8") as f:
                f.write(origine.replace(avant, apres))
            if tests_passent():
                rates.append(f"{nom} : non détecté")
    finally:
        with open(SOURCE, "w", encoding="utf-8") as f:
            f.write(origine)
    sain = tests_passent()
    for r in rates:
        print(r)
    bon = not rates and sain
    print(f"contre-épreuve {'OK' if bon else 'ÉCHEC'} : {len(SABOTAGES) - len(rates)}/{len(SABOTAGES)} sabotages détectés, témoin sain {'OK' if sain else 'en échec'}")
    return 0 if bon else 1


if __name__ == "__main__":
    sys.exit(main())
