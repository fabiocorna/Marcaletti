import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from fastapi.testclient import TestClient
except ImportError:  # dipendenze web non installate
    TestClient = None

MODELLO = os.path.join(os.path.dirname(__file__), "modello_sintetico.xml")
TE = "1,7 4,2 9,2 14,0 17,9 22,5 25,1 24,1 20,4 14,0 7,9 3,1"
IRR = "5 6 8 10 12 13 14 12 10 7 5 4"


@unittest.skipIf(TestClient is None, "fastapi non installato")
class TestWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        from web import db
        db.DB_PATH = os.path.join(cls.tmp.name, "t.db")
        db.inizializza()
        db.crea_utente("fabio", "password-lunga")
        from web.app import app
        cls.c = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _login(self):
        r = self.c.post("/login", data={"username": "fabio", "password": "password-lunga"},
                        follow_redirects=False)
        self.assertEqual(r.status_code, 303)

    def test_senza_login_redirect(self):
        c = TestClient(self.c.app)
        r = c.get("/", follow_redirects=False)
        self.assertEqual(r.headers["location"], "/login")
        r = c.post("/login", data={"username": "fabio", "password": "sbagliata!!"})
        self.assertIn("Credenziali non valide", r.text)

    def test_flusso_completo(self):
        self._login()
        dati = {"comune": "Bergamo", "provincia": "bg", "zona_climatica": "E", "gg": "2533", "te": TE}
        dati.update({f"irr_{e}": IRR for e in ("S", "N", "E", "O", "ORIZ")})
        r = self.c.post("/climi", data=dati)
        self.assertIn("Bergamo", r.text)
        r = self.c.post("/progetti/nuovo", data={
            "nome": "Prova <b>", "comune": "Bergamo", "intervento": "riqualificazione",
            "anno_costruzione": "1975", "tipologia": "appartamento", "piano": "ultimo",
            "superficie_utile": "82,5", "altezza_netta": "2,70",
            "lato_S": "esterno", "lato_N": "esterno", "lato_E": "adiacente", "lato_O": "scala",
            "generatore": "caldaia", "combustibile": "metano"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text[:500])
        url = r.headers["location"]
        pag = self.c.get(url).text
        self.assertIn("Prova &lt;b&gt;", pag)  # escape HTML
        self.assertIn("Verifiche di legge", pag)
        self.assertIn("NON VERIFICATA", pag)
        self.assertIn("Copertura", pag)
        self.assertTrue(re.search(r"EP<sub>H,nd</sub></span><b>[\d.,]+</b>", pag))
        self.assertIn("# Scheda di compilazione", self.c.get(url + "/scheda.md").text)
        self.assertIn("[zona]", self.c.get(url + "/progetto.toml").text)
        with open(MODELLO, "rb") as f:
            self.c.post(url + "/modello", files={"file": ("calcolo.xml", f, "application/xml")})
        xml = self.c.get(url + "/import.xml")
        self.assertEqual(xml.status_code, 200)
        self.assertIn("<c:calcolo", xml.text)

    def test_modello_predefinito(self):
        self._login()
        r = self.c.post("/impostazioni/modello", files={"file": ("x.xml", b"<a/>", "application/xml")})
        self.assertIn("non è un calcolo.xml", r.text)
        with open(MODELLO, "rb") as f:
            self.c.post("/impostazioni/modello", files={"file": ("mio.xml", f, "application/xml")})
        self.assertIn("mio.xml", self.c.get("/impostazioni").text)
        from web import db
        uid = db.utente_da_token(self.c.cookies.get("sessione"))["id"]
        with open(os.path.join(os.path.dirname(__file__), "..", "progetti", "esempio_appartamento.toml")) as f:
            pid = db.crea_progetto(uid, "con predefinito", f.read(), None)
        self.assertEqual(self.c.get(f"/progetti/{pid}/import.xml").status_code, 200)

    def test_toml_errato_mostra_errore(self):
        self._login()
        from web import db
        uid = db.utente_da_token(self.c.cookies.get("sessione"))["id"]
        pid = db.crea_progetto(uid, "rotto", "[zona\n", None)
        self.assertIn("Il progetto contiene un errore", self.c.get(f"/progetti/{pid}").text)

    def test_progetto_altrui_non_visibile(self):
        from web import db
        db.crea_utente("altro", "altra-password")
        altro = db.utente_da_token(db.autentica("altro", "altra-password"))
        pid = db.crea_progetto(altro["id"], "segreto", "", None)
        self._login()
        r = self.c.get(f"/progetti/{pid}", follow_redirects=False)
        self.assertEqual(r.status_code, 303)


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(TestClient is None, "fastapi non installato")
class TestComuni(unittest.TestCase):
    def test_comune_ufficiale_riempie_zona_e_gg(self):
        from cened import comuni
        if not comuni.tutti():
            self.skipTest("risorse/comuni_istat.json assente")
        c = comuni.cerca("bergamo")
        self.assertEqual(c["zc"], "E")
        self.assertTrue(c["istat"].startswith("016"))
