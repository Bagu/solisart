"""Plannings confort/réduit du formulaire frm_prog : lecture, conversions, corps du
POST. Sans réseau ni dépendance."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paquet import module  # noqa: E402
from variantes import lire_page  # noqa: E402

analyse = module("analyse")


def octets_page(page, zone, jour):
    """Les 6 octets de la journée, lus directement dans le texte de la page."""
    lecteur = analyse._analyser(page)
    valeurs = {e.nom: e.attributs.get("value") for e in lecteur.formulaires["frm_prog"]}
    return [int(valeurs[f"P{zone}{jour}{o}"]) for o in range(6)]


class Lecture(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.page = lire_page()
        cls.reglages = analyse.lire_reglages(cls.page)

    def test_plannings_de_la_page(self):
        plannings = self.reglages.plannings
        self.assertEqual(sorted(plannings), list(range(7)))
        self.assertEqual(analyse.texte_planning(plannings[1][0]), "00:00-01:00, 21:00-24:00")
        self.assertEqual(analyse.texte_planning(plannings[0][6]),
                         "00:00-00:30, 06:00-06:30, 12:30-15:00, 18:00-24:00")
        self.assertEqual(analyse.texte_planning(plannings[6][0]),
                         "00:00-00:30, 01:30-02:00, 03:00-03:30, 06:00-06:30, 13:30-16:30, 22:30-24:00")

    def test_ordre_des_bits(self):
        creneaux = analyse.creneaux_depuis_octets([1, 0, 0, 0, 0, 128])
        self.assertEqual(analyse.texte_planning(creneaux), "00:00-00:30, 23:30-24:00")
        creneaux = analyse.creneaux_depuis_octets([0, 2, 0, 0, 0, 0])
        self.assertEqual(analyse.texte_planning(creneaux), "04:30-05:00")

    def test_aller_retour_des_octets(self):
        for zone in range(7):
            for jour in range(7):
                octets = octets_page(self.page, zone, jour)
                creneaux = analyse.creneaux_depuis_octets(octets)
                self.assertEqual(analyse.octets_depuis_creneaux(creneaux), octets)

    def test_planning_illisible_ecarte(self):
        page = self.page.replace('name="P123" value="0"', 'name="P123" value="300"', 1)
        self.assertNotEqual(page, self.page)
        self.assertNotIn(1, analyse.lire_reglages(page).plannings)
        self.assertIn(0, analyse.lire_reglages(page).plannings)


class Saisie(unittest.TestCase):

    def test_saisies_acceptees(self):
        lire, texte = analyse.lire_texte_planning, analyse.texte_planning
        self.assertEqual(texte(lire("6:00-8:30; 18h00-24h00")), "06:00-08:30, 18:00-24:00")
        self.assertEqual(texte(lire("06:00-08:00, 07:30-09:00")), "06:00-09:00")
        self.assertEqual(lire("  "), (False,) * 48)
        self.assertEqual(lire("00:00-24:00"), (True,) * 48)
        self.assertEqual(texte(lire("6-8:30, 18h-24h")), "06:00-08:30, 18:00-24:00")

    def test_saisies_refusees(self):
        for saisie in ("6:15-7:00", "8:00-6:00", "8:00-8:00", "23:00-24:30", "25:00-26:00", "matin",
                       "6:00-8:00 18:00-20:00"):
            with self.subTest(saisie=saisie), self.assertRaises(analyse.ReglageRefuse):
                analyse.lire_texte_planning(saisie)

    def test_texte_compact(self):
        creneaux = tuple(i % 2 == 0 for i in range(48))
        self.assertGreater(len(analyse.texte_planning(creneaux)), 255)
        compact = analyse.texte_planning(creneaux, compact=True)
        self.assertLessEqual(len(compact), 255)
        self.assertEqual(analyse.lire_texte_planning(compact), creneaux)


class Corps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.page = lire_page()

    def test_seule_la_journee_demandee_change(self):
        voulu = analyse.lire_texte_planning("06:00-08:30, 21:00-24:00")
        corps = analyse.corps_planning(self.page, {(1, 2): voulu})
        avant = analyse.corps_planning(self.page, {})
        differences = {nom for nom in corps if corps[nom] != avant[nom]}
        self.assertEqual(differences - {"U19_0", "U20_0"}, {"P120", "P121", "P122"})
        self.assertEqual([int(corps[f"P12{o}"]) for o in range(6)], analyse.octets_depuis_creneaux(voulu))
        self.assertEqual((corps["U19_0"], corps["U20_0"]), ("1", "2"))
        self.assertEqual((corps["Prog_SHour"], corps["Prog_EHour"], corps["Prog_Temp"]), ("0", "0", "0"))
        self.assertEqual(len(corps), 6 * 7 * 7 + 5)
        self.assertFalse(set(corps) & set(analyse.corps_formulaire(self.page)))

    def test_option_choisie_envoyee(self):
        page = self.page.replace("<option  value='3'>Jeudi</option>", "<option selected value='3'>Jeudi</option>", 1)
        self.assertNotEqual(page, self.page)
        page = page.replace("<option selected value='0'>Lundi</option>", "<option value='0'>Lundi</option>", 1)
        self.assertEqual(analyse.corps_planning(page, {})["U20_0"], "3")

    def test_zone_sans_planning_refusee(self):
        with self.assertRaises(analyse.ReglageRefuse):
            analyse.corps_planning(self.page, {(8, 0): (False,) * 48})

    def test_formulaire_absent(self):
        debut = self.page.index("<form action='param.htm' method='post' name='frm_prog'>")
        fin = self.page.index("</form>", debut) + len("</form>")
        with self.assertRaises(analyse.PageInattendue):
            analyse.corps_planning(self.page[:debut] + self.page[fin:], {})

    def test_ecarts(self):
        reglages = analyse.lire_reglages(self.page)
        voulu = analyse.lire_texte_planning("00:00-01:00, 21:00-24:00")
        self.assertEqual(analyse.ecarts_planning(reglages, {(1, 0): voulu}), {})
        autre = analyse.lire_texte_planning("07:00-08:00")
        self.assertEqual(analyse.ecarts_planning(reglages, {(1, 0): autre}),
                         {"planning 1/0": ("07:00-08:00", "00:00-01:00, 21:00-24:00")})


if __name__ == "__main__":
    unittest.main()


def _horloge(date, heure):
    return f"<response>\t\r\n<date>{date}</date>\r\n<time>{heure}</time>\r\n</response>".encode("latin-1")


class HorlogeDeLaCarte(unittest.TestCase):

    def test_page_reelle(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "dtstat_reel.xml"), "rb") as f:
            horloge = analyse.lire_horloge(f.read())
        self.assertEqual((horloge.jour, horloge.creneau), (0, 47))
        self.assertEqual((horloge.date, horloge.heure), ("lun. 19 oct. 26", "23:33:22"))

    def test_jours_et_demi_heures(self):
        for date, heure, attendu in (("mar. 20 oct. 26", "00:00:00", (1, 0)), ("dim. 25 oct. 26", "12:29:59", (6, 24)),
                                     ("sam. 24 oct. 26", "12:30:00", (5, 25)), ("jeu. 22 oct. 26", "7:05", (3, 14))):
            with self.subTest(date=date, heure=heure):
                horloge = analyse.lire_horloge(_horloge(date, heure))
                self.assertEqual((horloge.jour, horloge.creneau), attendu)

    def test_formats_refuses(self):
        for date, heure in (("Mon 19 Oct 26", "10:00:00"), ("lun. 19 oct. 26", "24:00:00"),
                            ("lun. 19 oct. 26", "10:75:00"), ("", "10:00:00"), ("lun. 19 oct. 26", "...")):
            with self.subTest(date=date, heure=heure), self.assertRaises(analyse.PageInattendue):
                analyse.lire_horloge(_horloge(date, heure))
        with self.assertRaises(analyse.PageInattendue):
            analyse.lire_horloge(b"<response><date>lun.")

    def test_periode_selon_le_planning(self):
        page = lire_page()
        plannings = analyse.lire_reglages(page).plannings
        octets = octets_page(page, 0, 0)
        for creneau in (0, 1, 8, 47):
            with self.subTest(creneau=creneau):
                attendu = bool(octets[creneau // 8] >> (creneau % 8) & 1)
                horloge = analyse.Horloge(0, creneau, "", "")
                self.assertIs(analyse.periode_en_cours(plannings, 0, horloge), attendu)
        self.assertIsNone(analyse.periode_en_cours(plannings, 0, None))
        self.assertIsNone(analyse.periode_en_cours(plannings, 9, analyse.Horloge(0, 0, "", "")))
