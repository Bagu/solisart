"""Client HTTP face à une fausse carte locale qui sert les pages réelles anonymisées.

Demande aiohttp (environnement .venv du projet) : ignoré sans lui.
"""
import asyncio
import base64
import os
import secrets
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from carte_simulee import appliquer  # noqa: E402
from paquet import RACINE, module  # noqa: E402

try:
    import aiohttp
except ImportError:
    aiohttp = None

FIXTURES = os.path.join(RACINE, "tests", "fixtures")
UTILISATEUR = "essai"
MOT_DE_PASSE = secrets.token_hex(8)


def _lire(nom):
    with open(os.path.join(FIXTURES, nom), "rb") as f:
        return f.read()


ATTENDU = "Basic " + base64.b64encode(f"{UTILISATEUR}:{MOT_DE_PASSE}".encode()).decode()


class FausseCarte(BaseHTTPRequestHandler):
    """Sert status.xml sans identifiant et param.htm en HTTP Basic. `reponses` force
    une réponse (code, corps) pour un chemin. Un POST de param.htm modifie la page
    servie (sauf si `sourde`) et répond 302 ; `journal` garde l'ordre des requêtes."""

    reponses = {}
    entetes_status = []
    page = b""
    sourde = False
    journal = []
    postes = []

    def do_GET(self):
        chemin = self.path.split("?")[0]
        if chemin in self.reponses:
            code, corps = self.reponses[chemin]
            return self._repondre(code, corps)
        if chemin == "/XML/status.xml":
            FausseCarte.entetes_status.append(self.headers.get("Authorization"))
            return self._repondre(200, _lire("status_reel.xml"), "text/xml")
        if chemin == "/param.htm":
            if self.headers.get("Authorization") != ATTENDU:
                return self._repondre(401, b"Unauthorized")
            FausseCarte.journal.append("GET")
            return self._repondre(200, FausseCarte.page)
        self._repondre(404, b"")

    def do_POST(self):
        corps = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path != "/param.htm":
            return self._repondre(404, b"")
        if self.headers.get("Authorization") != ATTENDU:
            return self._repondre(401, b"Unauthorized")
        FausseCarte.journal.append("POST")
        FausseCarte.postes.append((corps, dict(self.headers)))
        if not FausseCarte.sourde:
            FausseCarte.page = appliquer(FausseCarte.page, corps)
        self.send_response(302)
        self.send_header("Location", "/param.htm")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _repondre(self, code, corps, type_="text/html"):
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *_):
        pass


@unittest.skipIf(aiohttp is None, "aiohttp absent : lancer avec .venv")
class ClientFaceALaCarte(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.api = module("api")
        cls.analyse = module("analyse")
        cls.serveur = ThreadingHTTPServer(("127.0.0.1", 0), FausseCarte)
        cls.hote = f"127.0.0.1:{cls.serveur.server_port}"
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def setUp(self):
        FausseCarte.reponses = {}
        FausseCarte.entetes_status = []
        FausseCarte.page = _lire("param_reel.htm")
        FausseCarte.sourde = False
        FausseCarte.journal = []
        FausseCarte.postes = []

    def appeler(self, methode, *args, hote=None, mot_de_passe=MOT_DE_PASSE):
        async def corps():
            async with aiohttp.ClientSession() as session:
                client = self.api.SolisartClient(session, hote or self.hote, UTILISATEUR, mot_de_passe, delai=3)
                return await getattr(client, methode)(*args)
        return asyncio.run(corps())

    def test_ecriture_confirmee(self):
        reglages = self.appeler("ecrire_reglages", {"U06_0": "1", "U09_0": 20})
        self.assertEqual(FausseCarte.journal, ["GET", "POST", "GET"])
        zone = reglages.zones[0]
        self.assertEqual((zone.mode, zone.confort.valeur), ("1", 20.0))
        corps, entetes = FausseCarte.postes[0]
        attendu = self.analyse.encoder_corps(self.analyse.corps_formulaire(
            _lire("param_reel.htm").decode("latin-1"), {"U06_0": "1", "U09_0": "20.0"}))
        self.assertEqual(corps, attendu)
        self.assertEqual(entetes["Content-Type"], "application/x-www-form-urlencoded")
        self.assertEqual(entetes["Referer"], f"http://{self.hote}/param.htm")

    def test_carte_qui_n_applique_rien(self):
        FausseCarte.sourde = True
        with self.assertRaises(self.api.EcritureNonConfirmee) as err:
            self.appeler("ecrire_reglages", {"U06_6": "1"})
        self.assertEqual(err.exception.ecarts, {"U06_6": ("1", "2")})
        self.assertEqual(FausseCarte.journal, ["GET", "POST", "GET"])

    def test_demande_invalide_rien_envoye(self):
        for demande in ({"U09_0": 99}, {"U06_1": "0", "U09_1": 20}, {"Mdp0": "x"}):
            with self.subTest(demande=demande), self.assertRaises(self.api.ReglageRefuse):
                self.appeler("ecrire_reglages", demande)
        self.assertNotIn("POST", FausseCarte.journal)

    def test_planning_ecrit_puis_confirme(self):
        reglages = self.appeler("ecrire_plannings", {(1, 2): "6:00-8:30, 21h-24h", (6, 6): ""})
        self.assertEqual(FausseCarte.journal, ["GET", "POST", "GET"])
        texte = self.analyse.texte_planning
        self.assertEqual(texte(reglages.plannings[1][2]), "06:00-08:30, 21:00-24:00")
        self.assertEqual(texte(reglages.plannings[6][6]), "")
        self.assertEqual(texte(reglages.plannings[1][3]), "00:00-01:00, 21:00-24:00")
        corps, entetes = FausseCarte.postes[0]
        self.assertIn(b"P120=0&P121=240&P122=1&", corps)
        self.assertNotIn(b"U06_0", corps)
        self.assertEqual(entetes["Referer"], f"http://{self.hote}/param.htm")

    def test_planning_non_applique(self):
        FausseCarte.sourde = True
        with self.assertRaises(self.api.EcritureNonConfirmee) as err:
            self.appeler("ecrire_plannings", {(0, 0): "07:00-09:00"})
        self.assertIn("planning 0/0", err.exception.ecarts)

    def test_planning_invalide_rien_envoye(self):
        for demande in ({(3, 0): "07:00-09:00"}, {(0, 7): "07:00-09:00"}, {(0, 0): "7h15-9h"}):
            with self.subTest(demande=demande), self.assertRaises(self.api.ReglageRefuse):
                self.appeler("ecrire_plannings", demande)
        self.assertNotIn("POST", FausseCarte.journal)

    def test_ecriture_identifiant_refuse(self):
        with self.assertRaises(self.api.AuthentificationRefusee):
            self.appeler("ecrire_reglages", {"U06_0": "1"}, mot_de_passe="faux")

    def test_ecritures_une_par_une(self):
        async def deux():
            async with aiohttp.ClientSession() as session:
                client = self.api.SolisartClient(session, self.hote, UTILISATEUR, MOT_DE_PASSE, delai=3)
                await asyncio.gather(client.ecrire_reglages({"U06_0": "1"}),
                                     client.ecrire_reglages({"U06_1": "1"}))
        asyncio.run(deux())
        self.assertEqual(FausseCarte.journal, ["GET", "POST", "GET"] * 2)
        reglages = self.analyse.lire_reglages(FausseCarte.page.decode("latin-1"))
        self.assertEqual([z.mode for z in reglages.zones], ["1", "1", "2"])

    def test_etat_lu_sans_identifiant(self):
        etat = self.appeler("lire_etat")
        self.assertEqual(etat.mesures["t1"].valeur, 53.4)
        self.assertEqual(FausseCarte.entetes_status, [None])

    def test_reglages_avec_identifiant(self):
        reglages = self.appeler("lire_reglages")
        self.assertEqual([z.index for z in reglages.zones], [0, 1, 6])

    def test_identifiant_refuse(self):
        with self.assertRaises(self.api.AuthentificationRefusee):
            self.appeler("lire_reglages", mot_de_passe="faux")

    def test_erreur_http(self):
        FausseCarte.reponses = {"/XML/status.xml": (500, b"")}
        with self.assertRaises(self.api.CarteInjoignable):
            self.appeler("lire_etat")

    def test_page_qui_n_est_pas_celle_de_la_carte(self):
        FausseCarte.reponses = {"/param.htm": (200, b"<html><body>Connexion</body></html>")}
        with self.assertRaises(self.api.PageInattendue):
            self.appeler("lire_reglages")

    def test_carte_eteinte(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            libre = s.getsockname()[1]
        with self.assertRaises(self.api.CarteInjoignable):
            self.appeler("lire_etat", hote=f"127.0.0.1:{libre}")

    def test_entete_basic_accentue(self):
        entete = self.api.entete_basic("zone", "été")
        self.assertEqual(base64.b64decode(entete.split()[1]), "zone:été".encode("ISO-8859-1"))
        hors_alphabet = self.api.entete_basic("zone", "€uro")
        self.assertEqual(base64.b64decode(hors_alphabet.split()[1]), "zone:€uro".encode("utf-8"))

    def test_adresse_saisie(self):
        base = self.api.adresse_de_base
        self.assertEqual(base(" 10.0.0.5/ "), "http://10.0.0.5")
        self.assertEqual(base("https://carte:8443/"), "https://carte:8443")


if __name__ == "__main__":
    unittest.main()
