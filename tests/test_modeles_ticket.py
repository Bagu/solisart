"""Modèles de ticket GitHub : formulaires lisibles, et mêmes consignes que la
documentation et le code (commande d'anonymisation, versions d'exemple).

Demande PyYAML (fourni avec Home Assistant dans .venv) : ignoré sans lui.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paquet import RACINE, module  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None

DOSSIER = os.path.join(RACINE, ".github", "ISSUE_TEMPLATE")
FORMULAIRES = ("bug_report.yml", "version_report.yml")
COMMANDE = "python outils/anonymiser.py param.htm param_anonyme.htm"


def _texte(*chemin):
    with open(os.path.join(RACINE, *chemin), encoding="utf-8") as f:
        return f.read()


@unittest.skipIf(yaml is None, "PyYAML absent : lancer avec .venv")
class ModelesDeTicket(unittest.TestCase):

    def formulaire(self, nom):
        return yaml.safe_load(_texte(".github", "ISSUE_TEMPLATE", nom))

    def test_formulaires_complets(self):
        for nom in FORMULAIRES:
            with self.subTest(nom=nom):
                modele = self.formulaire(nom)
                self.assertTrue(modele["name"] and modele["description"])
                ids = [champ["id"] for champ in modele["body"] if champ["type"] != "markdown"]
                self.assertEqual(len(ids), len(set(ids)))
                for champ in ids:
                    self.assertRegex(champ, r"^[a-z_]+$")

    def test_versions_demandees(self):
        for nom in FORMULAIRES:
            with self.subTest(nom=nom):
                ids = {champ.get("id") for champ in self.formulaire(nom)["body"]}
                self.assertLessEqual({"version_carte", "version_web", "version_integration", "page"}, ids)

    def test_exemples_de_version_testes(self):
        carte, web = module("const").VERSIONS_TESTEES[0]
        for nom in FORMULAIRES:
            with self.subTest(nom=nom):
                exemples = {champ["id"]: champ["attributes"].get("placeholder")
                            for champ in self.formulaire(nom)["body"] if champ.get("id")}
                self.assertEqual((exemples["version_carte"], exemples["version_web"]), (carte, web))

    def test_meme_commande_d_anonymisation_partout(self):
        for chemin in [(".github", "ISSUE_TEMPLATE", nom) for nom in FORMULAIRES] + [
                ("CONTRIBUTING.md",), ("README.md",), ("LISEZMOI.md",)]:
            with self.subTest(fichier="/".join(chemin)):
                self.assertIn(COMMANDE, _texte(*chemin))

    def test_la_commande_existe(self):
        script = re.match(r"python (\S+)", COMMANDE).group(1)
        self.assertTrue(os.path.isfile(os.path.join(RACINE, script)))

    def test_lien_vers_les_tickets(self):
        self.assertIn("blank_issues_enabled", yaml.safe_load(_texte(".github", "ISSUE_TEMPLATE", "config.yml")))


if __name__ == "__main__":
    unittest.main()
