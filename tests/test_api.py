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


class FausseCarte(BaseHTTPRequestHandler):
    """Sert status.xml sans identifiant et param.htm en HTTP Basic. `reponses` force
    une réponse (code, corps) pour un chemin."""

    reponses = {}
    entetes_status = []

    def do_GET(self):
        chemin = self.path.split("?")[0]
        if chemin in self.reponses:
            code, corps = self.reponses[chemin]
            return self._repondre(code, corps)
        if chemin == "/XML/status.xml":
            FausseCarte.entetes_status.append(self.headers.get("Authorization"))
            return self._repondre(200, _lire("status_reel.xml"), "text/xml")
        if chemin == "/param.htm":
            attendu = "Basic " + base64.b64encode(f"{UTILISATEUR}:{MOT_DE_PASSE}".encode()).decode()
            if self.headers.get("Authorization") != attendu:
                return self._repondre(401, b"Unauthorized")
            return self._repondre(200, _lire("param_reel.htm"))
        self._repondre(404, b"")

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

    def appeler(self, methode, hote=None, mot_de_passe=MOT_DE_PASSE):
        async def corps():
            async with aiohttp.ClientSession() as session:
                client = self.api.SolisartClient(session, hote or self.hote, UTILISATEUR, mot_de_passe, delai=3)
                return await getattr(client, methode)()
        return asyncio.run(corps())

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
