"""Accords entre le code et les traductions : chaque message d'erreur levé a sa
traduction en français et en anglais, avec les mêmes paramètres, et aucune traduction
n'est orpheline.

    python -m unittest tests.test_traductions
"""
import json
import os
import re
import string
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paquet import DOSSIER, module  # noqa: E402

analyse = module("analyse")


def _json(nom):
    with open(os.path.join(DOSSIER, nom), encoding="utf-8") as f:
        return json.load(f)


def _source():
    textes = []
    for nom in sorted(os.listdir(DOSSIER)):
        if nom.endswith(".py"):
            with open(os.path.join(DOSSIER, nom), encoding="utf-8") as f:
                textes.append(f.read())
    return "\n".join(textes)


def _parametres(message):
    return {champ for _, champ, _, _ in string.Formatter().parse(message) if champ}


FICHIERS = {"en": "translations/en.json", "fr": "translations/fr.json"}


class Exceptions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = _source()
        cls.traductions = {langue: _json(nom)["exceptions"] for langue, nom in FICHIERS.items()}

    def cles_du_code(self):
        cles = set(re.findall(r'translation_key="(\w+)"', self.source))
        if 'translation_key=f"refus_{err.cle}"' in self.source:
            cles |= {f"refus_{cle}" for cle in analyse.MESSAGES_REFUS}
        return cles

    def test_chaque_cle_du_code_est_traduite_et_aucune_n_est_orpheline(self):
        attendues = self.cles_du_code()
        self.assertGreater(len(attendues), 10)
        for langue, exceptions in self.traductions.items():
            with self.subTest(langue=langue):
                self.assertEqual(set(exceptions), attendues)

    def test_memes_parametres_en_francais_et_en_anglais(self):
        for cle, message in self.traductions["en"].items():
            with self.subTest(cle=cle):
                self.assertEqual(_parametres(message["message"]),
                                 _parametres(self.traductions["fr"][cle]["message"]))

    def test_refus_traduits_avec_les_valeurs_du_client(self):
        for cle, gabarit in analyse.MESSAGES_REFUS.items():
            with self.subTest(cle=cle):
                self.assertEqual(_parametres(self.traductions["en"][f"refus_{cle}"]["message"]),
                                 _parametres(gabarit))

    def test_chaque_refus_leve_a_un_gabarit(self):
        levees = set(re.findall(r'ReglageRefuse\("(\w+)"', self.source))
        self.assertTrue(levees)
        self.assertLessEqual(levees, set(analyse.MESSAGES_REFUS))
        self.assertNotIn('ReglageRefuse(f"', self.source)

    def test_aucun_message_d_erreur_ecrit_en_dur(self):
        en_dur = re.findall(r'(?:HomeAssistantError|ServiceValidationError|UpdateFailed|ConfigEntryAuthFailed)\(\s*f?"',
                            self.source)
        self.assertEqual(en_dur, [])

    def test_sans_point_final(self):
        for langue, exceptions in self.traductions.items():
            for cle, message in exceptions.items():
                with self.subTest(langue=langue, cle=cle):
                    self.assertFalse(message["message"].endswith("."))

    def test_tous_les_textes_ont_les_memes_cles_et_parametres(self):
        def plat(x, chemin=""):
            if isinstance(x, dict):
                for cle, valeur in x.items():
                    yield from plat(valeur, f"{chemin}.{cle}" if chemin else cle)
            else:
                yield chemin, x
        textes = {langue: dict(plat(_json(nom))) for langue, nom in FICHIERS.items()}
        self.assertEqual(set(textes["fr"]), set(textes["en"]))
        for chemin, anglais in textes["en"].items():
            with self.subTest(chemin=chemin):
                self.assertEqual(_parametres(textes["fr"][chemin]), _parametres(anglais))

    def test_strings_identique_a_l_anglais(self):
        self.assertEqual(_json("strings.json"), _json(FICHIERS["en"]))

    def test_refus_porte_sa_cle_et_ses_valeurs(self):
        with self.assertRaises(analyse.ReglageRefuse) as err:
            analyse.lire_texte_planning("25:00-26:00")
        self.assertEqual(err.exception.cle, "plage_demi_heure")
        self.assertEqual(err.exception.valeurs, {"plage": "25:00-26:00"})
        self.assertIn("25:00-26:00", str(err.exception))



def _texte_page():
    """Texte visible de la page Utilisateur enregistrée sur la carte (espaces réduits)."""
    import html
    with open(os.path.join(os.path.dirname(DOSSIER), "..", "tests", "fixtures", "param_reel.htm"), "rb") as f:
        page = f.read().decode("ISO-8859-1")
    page = re.sub(r"(?is)<script.*?</script>", " ", page)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


class VocabulaireDeLaCarte(unittest.TestCase):
    """Les libellés français reprennent les mots de la page Utilisateur de la carte."""

    ACCORDS = (
        (("entity", "select", "mode", "name"), "Mode de chauffage"),
        (("entity", "number", "confort", "name"), "Température de confort"),
        (("entity", "number", "reduit", "name"), "Température de réduit"),
        (("entity", "text", "planning_0", "name"), "Programmation"),
        (("entity", "sensor", "periode", "state", "confort"), "Confort"),
        (("entity", "sensor", "periode", "state", "reduit"), "Réduit"),
        (("entity", "climate", "thermostat", "state_attributes", "consigne_reduit", "name"), "Température de réduit"),
        (("config", "step", "user", "description"), "Carte de régulation"),
    )

    def test_libelles_pris_sur_la_page(self):
        page = _texte_page()
        francais = _json(FICHIERS["fr"])
        for chemin, mots in self.ACCORDS:
            with self.subTest(chemin=".".join(chemin)):
                self.assertIn(mots, page)
                texte = francais
                for cle in chemin:
                    texte = texte[cle]
                self.assertIn(mots.lower(), texte.lower())

    def test_carte_de_regulation_partout(self):
        francais = json.dumps(_json(FICHIERS["fr"]), ensure_ascii=False)
        seules = re.findall(r"(?<!\{)\bcartes?\b(?! de régulation)", francais, re.IGNORECASE)
        self.assertEqual(seules, [])
        self.assertNotIn("régulateur", francais)


if __name__ == "__main__":
    unittest.main()
