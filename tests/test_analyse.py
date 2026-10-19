"""Lecture de status.xml et de param.htm sur des pages réelles anonymisées.

    python -m unittest discover tests
"""
import importlib.util
import math
import os
import sys
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(RACINE, "tests", "fixtures")


def _charger(nom, chemin):
    """Charge un module par son chemin, sans importer le paquet Home Assistant."""
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


analyse = _charger("solisart_analyse", os.path.join(RACINE, "custom_components", "solisart", "analyse.py"))
anonymiser = _charger("solisart_anonymiser", os.path.join(RACINE, "outils", "anonymiser.py"))


def _fixture(nom):
    with open(os.path.join(FIXTURES, nom), "rb") as f:
        return f.read()


def _page():
    return _fixture("param_reel.htm").decode("ISO-8859-1")


def _remplacer(texte, avant, apres):
    assert texte.count(avant) == 1, avant
    return texte.replace(avant, apres)


class EtatReel(unittest.TestCase):
    """status.xml relevé sur une vraie carte."""

    @classmethod
    def setUpClass(cls):
        cls.etat = analyse.lire_etat(_fixture("status_reel.xml"))

    def nature(self, nature):
        return {k for k, m in self.etat.mesures.items() if m.nature == nature}

    def test_toutes_les_balises_sont_comptees(self):
        self.assertEqual(len(self.etat.mesures) + len(self.etat.inconnues), 47)

    def test_seules_les_balises_sans_format_sont_inconnues(self):
        self.assertEqual(self.etat.inconnues, {"flpws": "1", "getSave": "142"})

    def test_temperatures(self):
        self.assertEqual(self.nature(analyse.TEMPERATURE), {f"t{i}" for i in range(1, 17)})
        self.assertEqual(self.etat.mesures["t1"].valeur, 53.4)
        self.assertEqual(self.etat.mesures["t9"].valeur, 13.7)

    def test_sonde_deconnectee_sans_valeur(self):
        absentes = {k for k in self.nature(analyse.TEMPERATURE) if self.etat.mesures[k].valeur is None}
        self.assertEqual(absentes, {"t5", "t6", "t10", "t13", "t14", "t15", "t16"})

    def test_pourcentages(self):
        attendus = {f"triac{i}" for i in range(1, 14)} | {"v3vsol", "v3vapp"}
        self.assertEqual(self.nature(analyse.POURCENTAGE), attendus)
        self.assertEqual(self.etat.mesures["triac6"].valeur, 100)

    def test_debits_sans_zero_negatif(self):
        self.assertEqual(self.nature(analyse.DEBIT), {f"fl{i}" for i in range(1, 6)})
        fl5 = self.etat.mesures["fl5"].valeur
        self.assertEqual(fl5, 0.0)
        self.assertEqual(math.copysign(1, fl5), 1.0)

    def test_relais(self):
        attendus = {"fl6"} | {f"{p}rel{n}" for p in ("m", "s", "fp", "sp") for n in (1, 2)}
        self.assertEqual(self.nature(analyse.RELAIS), attendus)
        self.assertIs(self.etat.mesures["mrel1"].valeur, False)


class EtatAnormal(unittest.TestCase):

    def test_xml_casse(self):
        with self.assertRaises(analyse.PageInattendue):
            analyse.lire_etat(b"<response><t1>12 dC</response>")

    def test_page_sans_mesure(self):
        with self.assertRaises(analyse.PageInattendue):
            analyse.lire_etat(b"<html><body>Erreur</body></html>")

    def test_format_inconnu_compte_et_non_devine(self):
        etat = analyse.lire_etat(b"<r><t1>abc</t1><t2>20.5 dC</t2><x>On</x><y>7 kW</y></r>")
        self.assertEqual(etat.inconnues, {"t1": "abc", "y": "7 kW"})
        self.assertEqual(etat.mesures["t2"].valeur, 20.5)
        self.assertIs(etat.mesures["x"].valeur, True)

    def test_sonde_non_initialisee(self):
        etat = analyse.lire_etat(b"<r><t3>...</t3></r>")
        self.assertIsNone(etat.mesures["t3"].valeur)


class ReglagesReels(unittest.TestCase):
    """param.htm relevé sur une vraie carte : deux zones et l'eau chaude."""

    @classmethod
    def setUpClass(cls):
        cls.reglages = analyse.lire_reglages(_page())
        cls.zones = {z.index: z for z in cls.reglages.zones}

    def test_zones_presentes(self):
        self.assertEqual(sorted(self.zones), [0, 1, 6])
        self.assertTrue(self.zones[6].eau_chaude)

    def test_libelles_lus_sur_la_page(self):
        self.assertEqual(self.zones[0].libelle, "RDC")
        self.assertEqual(self.zones[1].libelle, "Etage")
        self.assertEqual(self.zones[6].libelle, "")

    def test_modes(self):
        self.assertEqual({i: z.mode for i, z in self.zones.items()}, {0: "2", 1: "2", 6: "2"})

    def test_consignes_et_bornes(self):
        lu = {i: (z.confort.valeur, z.confort.minimum, z.confort.maximum,
                  z.reduit.valeur, z.reduit.minimum, z.reduit.maximum) for i, z in self.zones.items()}
        self.assertEqual(lu, {
            0: (18.5, 10, 40, 18.0, 5, 35),
            1: (18.5, 10, 40, 18.0, 5, 35),
            6: (50.0, 30, 80, 45.0, 20, 80),
        })
        self.assertTrue(all(z.confort.actif and z.reduit.actif for z in self.zones.values()))

    def test_version(self):
        self.assertEqual(self.reglages.version_carte, "SRB_32MX_vD.50-5")
        self.assertEqual(self.reglages.version_web, "WEB_vA.98")


class ReglagesVariantes(unittest.TestCase):
    """Variantes de la vraie page, une règle chacune."""

    def lire(self, avant, apres):
        return {z.index: z for z in analyse.lire_reglages(_remplacer(_page(), avant, apres)).zones}

    def test_zone_a_l_arret_consignes_inactives(self):
        zones = self.lire("FillUtilModeChauff('U06_1','2')", "FillUtilModeChauff('U06_1','0')")
        self.assertEqual(zones[1].mode, "0")
        self.assertFalse(zones[1].confort.actif or zones[1].reduit.actif)
        self.assertTrue(zones[0].confort.actif)

    def test_mode_inconnu_lu_comme_arret(self):
        zones = self.lire("FillUtilModeChauff('U06_0','2')", "FillUtilModeChauff('U06_0','7')")
        self.assertEqual(zones[0].mode, "0")

    def test_zone_supplementaire_activee(self):
        zones = self.lire("elements['U06_2'].value,'0')", "elements['U06_2'].value,'1')")
        self.assertEqual(sorted(zones), [0, 1, 2, 6])
        self.assertIsNone(zones[2].confort.valeur)

    def test_champ_desactive(self):
        zones = self.lire("name='U10_1' value=", "name='U10_1' disabled value=")
        self.assertFalse(zones[1].reduit.actif)
        self.assertTrue(zones[1].confort.actif)

    def test_libelle_avec_accents_et_entite(self):
        zones = self.lire("RDC\r\n</td>", "S&eacute;jour &amp; cuisine\r\n</td>")
        self.assertEqual(zones[0].libelle, "Séjour & cuisine")

    def test_page_sans_formulaire(self):
        with self.assertRaises(analyse.PageInattendue):
            analyse.lire_reglages("<html><body>401 Unauthorized</body></html>")


class FixturesAnonymes(unittest.TestCase):

    def test_aucune_donnee_personnelle(self):
        for nom in os.listdir(FIXTURES):
            with self.subTest(fixture=nom):
                texte = _fixture(nom).decode("latin-1")
                self.assertEqual(anonymiser.restes(texte), [])
                self.assertNotIn("bottom_frame", texte)

    def test_nom_d_installation_masque(self):
        self.assertIn("XXXX - SRB_", _page())

    def test_controle_des_restes_se_declenche(self):
        piege = _page().replace("XXXX - SRB_", "192.168.1.20 maison@exemple.fr - SRB_", 1)
        self.assertEqual(len(anonymiser.restes(piege)), 2)


if __name__ == "__main__":
    unittest.main()
