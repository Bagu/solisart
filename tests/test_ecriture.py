"""Corps du POST de param.htm : parité avec le corps de référence et contrôle des
changements demandés. Sans réseau ni dépendance."""
import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paquet import module  # noqa: E402
from variantes import MODES, PAGE, REFERENCE, lire_page, variantes  # noqa: E402

analyse = module("analyse")


class Parite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(REFERENCE, encoding="utf-8") as f:
            cls.reference = json.load(f)
        cls.pages = dict(variantes(lire_page()))

    def test_reference_a_jour(self):
        with open(PAGE, "rb") as f:
            empreinte = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(self.reference["page_sha256"], empreinte,
                         "page réelle modifiée : relancer outils/parite_reference.py")
        self.assertEqual(len(self.reference["cas"]), len(self.pages) * len(MODES))

    def test_meme_corps_que_la_reference(self):
        for cas in self.reference["cas"]:
            with self.subTest(variante=cas["variante"], modes=cas["modes"]):
                corps = analyse.corps_formulaire(self.pages[cas["variante"]], cas["modes"])
                self.assertEqual(analyse.encoder_corps(corps).decode("ascii"), cas["corps"])


class Corps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.page = lire_page()
        cls.reglages = analyse.lire_reglages(cls.page)

    def test_formulaire_absent(self):
        with self.assertRaises(analyse.PageInattendue):
            analyse.corps_formulaire("<html><body></body></html>")

    def test_consigne_changee(self):
        corps = analyse.corps_formulaire(self.page, {"U09_0": "20.0"})
        self.assertEqual(corps["U09_0"], "20.0")
        self.assertEqual(corps["U09_1"], "18.5")

    def test_consigne_d_une_zone_arretee_refusee(self):
        changements = {"U06_1": "0", "U09_1": "20.0"}
        corps = analyse.corps_formulaire(self.page, changements)
        self.assertEqual(analyse.champs_refuses(corps, changements), ["U09_1"])

    def test_zone_absente_refusee(self):
        changements = {"U06_3": "1"}
        corps = analyse.corps_formulaire(self.page, changements)
        self.assertEqual(analyse.champs_refuses(corps, changements), ["U06_3"])

    def test_preparer_formate_et_controle(self):
        preparer = analyse.preparer_changements
        self.assertEqual(preparer(self.reglages, {"U09_0": 21, "U06_6": 1, "U10_6": "44.5"}),
                         {"U09_0": "21.0", "U06_6": "1", "U10_6": "44.5"})
        refus = [
            {"U09_0": 40.5},
            {"U10_0": 4.9},
            {"U06_0": "3"},
            {"U06_3": "1"},
            {"Mdp0": "x"},
            {"U09_0": "chaud"},
        ]
        for demande in refus:
            with self.subTest(demande=demande), self.assertRaises(analyse.ReglageRefuse):
                preparer(self.reglages, demande)
        self.assertEqual(preparer(self.reglages, {"U09_6": 80, "U10_6": 20}), {"U09_6": "80.0", "U10_6": "20.0"})

    def test_ecarts(self):
        self.assertEqual(analyse.ecarts(self.page, {"U06_0": "2", "U09_0": "18.50"}), {})
        self.assertEqual(analyse.ecarts(self.page, {"U06_0": "1", "U09_1": "19.0", "Inconnu": "1"}),
                         {"U06_0": ("1", "2"), "U09_1": ("19.0", "18.5"), "Inconnu": ("1", None)})

    def test_decimales_lues(self):
        zone = self.reglages.zones[0]
        self.assertEqual((zone.confort.decimales, zone.reduit.decimales), (1, 1))


if __name__ == "__main__":
    unittest.main()
