"""manifest.json selon les règles de hassfest et de la validation HACS.

    python -m unittest tests.test_manifeste
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paquet import DOSSIER  # noqa: E402

# Sous-catégories « climate » de homeassistant/components/homeassistant/strings.json
# (branche dev de Home Assistant, relevées le 23/10/2026), seules candidates pour une
# carte de régulation de chauffage et d'eau chaude.
CATEGORIES_CONNUES = {
    "climate", "climate.air_purifiers_humidifiers", "climate.fans_ventilation",
    "climate.heat_pumps_air_conditioning", "climate.thermostats_heating", "climate.water_heaters",
}


def _manifeste():
    with open(os.path.join(DOSSIER, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


class Manifeste(unittest.TestCase):

    def test_categories(self):
        categories = _manifeste().get("categories")
        self.assertIsInstance(categories, list)
        self.assertTrue(1 <= len(categories) <= 3)
        self.assertEqual(len(categories), len(set(categories)))
        for categorie in categories:
            with self.subTest(categorie=categorie):
                self.assertRegex(categorie, r"^[a-z0-9_]+(\.[a-z0-9_]+)?$")
                self.assertIn(categorie, CATEGORIES_CONNUES)
                parent, _, sous = categorie.partition(".")
                self.assertFalse(sous and parent in categories, "catégorie et sa sous-catégorie ensemble")
        self.assertEqual(categories, ["climate.thermostats_heating", "climate.water_heaters"])

    def test_ordre_des_cles(self):
        cles = list(_manifeste())
        self.assertEqual(cles[:2], ["domain", "name"])
        self.assertEqual(cles[2:], sorted(cles[2:]))


if __name__ == "__main__":
    unittest.main()
