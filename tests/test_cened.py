import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cened.bilancio import apporti_interni, calcola
from cened.esporta_xml import D, genera_xml
from cened.involucro import Serramento, Strato, StrutturaOpaca
from cened.materiali import LIBRERIA, r_intercapedine
from cened.modello import Clima
from cened.progetto import carica
from cened.scheda import genera_scheda

QUI = os.path.dirname(__file__)
ESEMPIO = os.path.join(QUI, "..", "progetti", "esempio_appartamento.toml")
MODELLO = os.path.join(QUI, "modello_sintetico.xml")


class TestInvolucro(unittest.TestCase):
    def test_u_parete_iso6946(self):
        s = StrutturaOpaca("P", "p", "parete", "esterno",
                           [Strato(LIBRERIA["mattone_pieno"], 0.30), Strato(LIBRERIA["eps"], 0.10)])
        r = 0.13 + 0.30 / 0.72 + 0.10 / 0.035 + 0.04
        self.assertAlmostEqual(s.u, 1 / r, places=6)

    def test_resistenze_superficiali(self):
        sof = StrutturaOpaca("S", "s", "soffitto", "znc", u_imposta=1.0)
        self.assertEqual((sof.rsi, sof.rse), (0.10, 0.10))
        pav = StrutturaOpaca("F", "f", "pavimento", "terreno", u_imposta=1.0)
        self.assertEqual((pav.rsi, pav.rse), (0.17, 0.0))

    def test_intercapedine(self):
        self.assertAlmostEqual(r_intercapedine(0.025, "orizzontale"), 0.18)
        self.assertAlmostEqual(r_intercapedine(0.0125, "orizzontale"), 0.16)
        self.assertAlmostEqual(r_intercapedine(0.5, "discendente"), 0.23)

    def test_k_i_si_ferma_all_isolante(self):
        s = StrutturaOpaca("P", "p", "parete", "esterno",
                           [Strato(LIBRERIA["cartongesso"], 0.0125), Strato(LIBRERIA["lana_roccia"], 0.05),
                            Strato(LIBRERIA["mattone_pieno"], 0.25)])
        self.assertAlmostEqual(s.k_i, 900 * 1000 * 0.0125 / 1000)

    def test_serramento_uw(self):
        s = Serramento("F", "f", 1.2, 1.5, u_g=1.1, u_f=1.3, g_n=0.6, psi_g=0.06, frazione_telaio=0.25)
        self.assertAlmostEqual(s.a_g, 1.35)
        b = s._larghezza_telaio()
        self.assertAlmostEqual((1.2 - 2 * b) * (1.5 - 2 * b), s.a_g, places=9)
        atteso = (1.35 * 1.1 + 0.45 * 1.3 + s.l_g * 0.06) / 1.8
        self.assertAlmostEqual(s.u_w, atteso)
        self.assertTrue(1.1 < s.u_w < 1.6)


class TestClima(unittest.TestCase):
    def test_stagione_zona_e_183_giorni(self):
        c = Clima("X", "E", [0] * 12, {})
        g = c.giorni_riscaldamento()
        self.assertEqual(sum(g), 183)
        self.assertEqual((g[9], g[3], g[5]), (17, 15, 0))

    def test_stagione_zona_d(self):
        self.assertEqual(sum(Clima("X", "D", [0] * 12, {}).giorni_riscaldamento()), 166)


class TestBilancio(unittest.TestCase):
    def setUp(self):
        self.prog = carica(ESEMPIO)
        self.ris = calcola(self.prog)

    def test_apporti_interni(self):
        self.assertAlmostEqual(apporti_interni(80), 7.987 * 80 - 0.0353 * 6400)
        self.assertEqual(apporti_interni(200), 450)

    def test_h_tr_somma_componenti(self):
        tot = sum(d["H_elemento"] + d["H_ponti"] for d in self.ris.dettaglio_h)
        self.assertAlmostEqual(tot, self.ris.h_tr, delta=0.1)

    def test_solaio_adiacente_non_disperde(self):
        sol = [d for d in self.ris.dettaglio_h if d["verso"] == "adiacente"][0]
        self.assertEqual(sol["H_elemento"], 0)

    def test_fabbisogno_plausibile(self):
        ep = self.ris.ep_h_nd(self.prog.zona.superficie_utile)
        self.assertTrue(50 < ep < 150, ep)
        self.assertEqual(sum(m.q_h_nd for m in self.ris.mesi if m.giorni == 0), 0)

    def test_isolamento_riduce_fabbisogno(self):
        p = carica(ESEMPIO)
        p.strutture["PAR_EST"].strati.append(Strato(LIBRERIA["eps_grafite"], 0.12))
        self.assertLess(calcola(p).q_h_nd, self.ris.q_h_nd * 0.85)

    def test_scheda(self):
        testo = genera_scheda(self.prog, self.ris)
        self.assertIn("EP_H,nd", testo)
        self.assertIn("Registro ipotesi", testo)


class TestEsportaXml(unittest.TestCase):
    def setUp(self):
        self.prog = carica(ESEMPIO)
        self.xml, self.avvisi = genera_xml(self.prog, MODELLO)
        self.root = ET.fromstring(self.xml.encode())

    def test_blocchi_calcolati_e_firma_rimossi(self):
        locali = [e.tag.split("}")[-1] for e in self.root]
        self.assertEqual(locali, ["datiInput"])
        self.assertNotIn("QUM|", self.xml)

    def test_namespace_prefissi_conservati(self):
        self.assertIn("<c:calcolo", self.xml)
        self.assertIn("<d:dizionario", self.xml)

    def test_libreria_strutture(self):
        op = self.root.findall(f".//{D}servizioOpache/{D}opache")
        self.assertEqual(len(op), len(self.prog.strutture))
        par = next(e for e in op if e.find(f"{D}input").get("nome").startswith("Muratura mattone"))
        self.assertIsNone(par.find(f"{D}output"))  # lo ricalcola il motore
        inp = par.find(f"{D}input")
        self.assertEqual(inp.get("versoDispersione"), "1")
        self.assertEqual(inp.get("tipoStrutturaOpache"), "1")
        strati = inp.findall(f"{D}datiStrato")
        self.assertEqual(len(strati), 3 + 2)  # 3 strati + resistenze superficiali
        self.assertEqual(strati[0].get("categoriaStrato"), "16")
        self.assertEqual(strati[2].get("d_i"), "300")  # mm
        # la somma delle resistenze degli strati ridà la U calcolata
        r = sum(float(x.get("r_i")) if x.get("r_i") else float(x.get("d_i")) / 1000 / float(x.get("lambda_i"))
                for x in strati)
        self.assertAlmostEqual(1 / r, self.prog.strutture["PAR_EST"].u, places=4)
        mats = {m.get("id") for m in self.root.iter(f"{D}materiale")}
        self.assertTrue(all(x.get("rifMateriali") in mats for x in strati))
        sol = next(e for e in op if e.find(f"{D}input").get("nome").startswith("Solaio"))
        self.assertEqual(sol.find(f"{D}input").get("versoDispersione"), "5")  # verso altra unità

    def test_dispersioni_e_riferimenti(self):
        disp = self.root.findall(f".//{D}zona/{D}dispersioni/{D}dispersione")
        attese = sum(d.quantita if d.is_serramento else 1 for d in self.prog.zona.dispersioni)
        self.assertEqual(len(disp), attese)  # una dispersione per ogni serramento, come in CENED
        ids = [e.get("id") for e in self.root.iter() if e.get("id")]
        self.assertTrue(all(i.isdigit() and int(i) > 0 for i in ids), ids)  # sd:positiveInt
        self.assertEqual(len(ids), len(set(ids)))
        znc = self.root.find(f".//{D}zonaNonClimatizzata")
        scala = next(e for e in disp if e.get("nome") == "Parete vano scala")
        self.assertEqual(scala.get("rifAmbienteConfinante"), znc.get("id"))
        self.assertIsNone(scala.get("verso"))  # le opache non hanno verso negli export CENED
        self.assertNotIn("rifIrraggiamento", scala.attrib)
        fin = [e for e in disp if e.get("nome").startswith("Finestre Sud")]
        self.assertEqual(len(fin), 2)
        fin = fin[0]
        self.assertIsNone(fin.get("area"))  # l'area la dà il servizio serramenti
        self.assertEqual(fin.get("verso"), "esterno")
        self.assertAlmostEqual(float(fin.find(f"{D}ponteTermico").get("lunghezza")), 10.8 / 2)
        ser = self.root.find(f".//{D}servizioSerramenti/{D}serramenti/{D}input")
        self.assertEqual(ser.get("doppio"), "false")
        self.assertAlmostEqual(float(ser.get("a_g_2")) + float(ser.get("a_t_2")), 1.8)
        self.assertEqual(fin.get("rifIrraggiamento"), "14")  # S già nel modello
        nord = next(e for e in disp if e.get("nome") == "Parete Nord")
        irr_n = nord.get("rifIrraggiamento")
        self.assertNotEqual(irr_n, "14")
        nuovo = [e for e in self.root.iter(f"{D}irraggiamento") if e.get("id") == irr_n][0]
        self.assertEqual(nuovo.find(f"{D}input").get("gamma"), "180")
        self.assertFalse([a for a in self.avvisi if a.startswith("riferimento")], self.avvisi)

    def test_geometria(self):
        geo = self.root.find(f".//{D}zona/{D}geometria")
        self.assertEqual(geo.get("superficieUtile"), "80")
        self.assertEqual(geo.get("volumeLordo"), "290")


if __name__ == "__main__":
    unittest.main()


class TestRapido(unittest.TestCase):
    BASE = {
        "anno_costruzione": 1972, "superficie_utile": 75.0, "tipologia": "appartamento",
        "piano": "intermedio", "lati": {"S": "esterno", "N": "esterno", "E": "adiacente", "O": "scala"},
        "clima": {"comune": "X", "zona_climatica": "E", "te": [2, 4, 9, 14, 18, 22, 25, 24, 20, 14, 8, 3],
                  "irradianza": {e: [5.0] * 12 for e in ("S", "N", "E", "O", "ORIZ")}},
    }

    def _prog(self, **kw):
        from cened.progetto import da_dizionario
        from cened.rapido import genera_progetto
        dati = {**self.BASE, **kw}
        return genera_progetto(dati), da_dizionario(genera_progetto(dati))

    def test_toml_riletto_uguale(self):
        import tomllib
        from cened.progetto import da_dizionario
        from cened.rapido import a_toml
        d, p = self._prog()
        p2 = da_dizionario(tomllib.loads(a_toml(d)))
        self.assertAlmostEqual(calcola(p).q_h_nd, calcola(p2).q_h_nd, places=3)
        self.assertEqual(set(p.ipotesi), set(p2.ipotesi))

    def test_superficie_finestrata(self):
        _, p = self._prog()
        a_fin = sum(d.area for d in p.zona.dispersioni if d.is_serramento)
        self.assertAlmostEqual(a_fin, 75 * 0.125, delta=1.8)

    def test_epoca_recente_migliore(self):
        _, vecchio = self._prog(anno_costruzione=1960)
        _, nuovo = self._prog(anno_costruzione=2020)
        self.assertLess(calcola(nuovo).q_h_nd, calcola(vecchio).q_h_nd / 2)
        self.assertLess(nuovo.strutture["PAR_EST"].u, 0.30)

    def test_villetta_su_cantina(self):
        d, p = self._prog(tipologia="villetta", numero_piani=2, sotto="cantina", superficie_utile=140,
                          lati={"S": "esterno", "N": "esterno", "E": "esterno", "O": "esterno"})
        nomi = {x.nome for x in p.zona.dispersioni}
        self.assertIn("Copertura", nomi)
        self.assertIn("Pavimento verso cantina", nomi)
        self.assertIn("CANTINA", p.znc)
        ep = calcola(p).ep_h_nd(140)
        self.assertTrue(80 < ep < 300, ep)

    def test_lato_non_valido(self):
        with self.assertRaises(ValueError):
            self._prog(lati={"X": "esterno"})


class TestDinamicaGlaser(unittest.TestCase):
    TE = [1.7, 4.2, 9.2, 14.0, 17.9, 22.5, 25.1, 24.1, 20.4, 14.0, 7.9, 3.1]
    UR = [0.85, 0.8, 0.75, 0.75, 0.75, 0.7, 0.7, 0.7, 0.75, 0.8, 0.85, 0.87]

    def _s(self, *strati):
        return StrutturaOpaca("X", "x", "parete", "esterno", [Strato(LIBRERIA[m], d) for m, d in strati])

    def test_yie_strato_sottile_tende_a_u(self):
        from cened.dinamica import dinamica
        s = self._s(("lana_vetro", 0.03))
        d = dinamica(s)
        self.assertAlmostEqual(d.y_ie, s.u, delta=0.01 * s.u)
        self.assertLess(d.sfasamento_h, 1.0)

    def test_sfasamento_cresce_con_spessore(self):
        from cened.dinamica import dinamica
        sf = [dinamica(self._s(("mattone_pieno", d))).sfasamento_h for d in (0.1, 0.2, 0.3)]
        self.assertTrue(sf[0] < sf[1] < sf[2], sf)
        self.assertTrue(8.5 < sf[2] < 10.5, sf)  # ~9-10 h per 30 cm di mattone pieno

    def test_p_sat(self):
        from cened.igrotermia import p_sat, theta_da_p_sat
        self.assertAlmostEqual(p_sat(20), 2337, delta=3)
        self.assertAlmostEqual(p_sat(0), 610.5, delta=0.1)
        for t in (-10, 0.5, 18):
            self.assertAlmostEqual(theta_da_p_sat(p_sat(t)), t, places=6)

    def test_cappotto_senza_condensa(self):
        from cened.igrotermia import glaser
        g = glaser(self._s(("intonaco_calce_cemento", 0.015), ("blocco_alveolato", 0.25), ("eps", 0.10),
                           ("intonaco_calce_cemento", 0.01)), self.TE, self.UR)
        self.assertTrue(g.muffa_ok)
        self.assertEqual(g.accumulo_max, 0)

    def test_isolamento_interno_senza_barriera_condensa(self):
        from cened.igrotermia import glaser
        g = glaser(self._s(("cartongesso", 0.0125), ("lana_roccia", 0.08), ("calcestruzzo_armato", 0.20)),
                   self.TE, self.UR)
        self.assertGreater(g.accumulo_max, 0.01)

    def test_muro_non_isolato_rischio_muffa(self):
        from cened.igrotermia import glaser
        g = glaser(self._s(("mattone_pieno", 0.25)), self.TE, self.UR)
        self.assertFalse(g.muffa_ok)


class TestSchema(unittest.TestCase):
    def test_validazione_xsd(self):
        from cened import schema
        if not schema.disponibile():
            self.skipTest("lxml o risorse/SCHEMA_XSD assenti")
        with open(MODELLO, encoding="utf-8") as f:
            errori = schema.valida(f.read())
        self.assertTrue(errori)  # il modello sintetico è volutamente incompleto
        self.assertIn("configurazioneCalcolo", errori[0])


class TestEsportaSuExportReali(unittest.TestCase):
    """Usa come modello i calcolo.xml reali in esempi/ (non versionati): saltato se assenti."""

    def test_xsd_valido_su_tutti_i_modelli(self):
        import glob
        from cened import schema
        modelli = sorted(glob.glob(os.path.join(QUI, "..", "esempi", "*.xml")))
        if not modelli or not schema.disponibile():
            self.skipTest("nessun export reale o XSD assenti")
        import tomllib
        from cened.progetto import da_dizionario
        from cened.rapido import genera_progetto
        with open(os.path.join(QUI, "..", "progetti", "rapido_esempio.toml"), "rb") as f:
            rapido = tomllib.load(f)
        progetti = {
            "appartamento": carica(ESEMPIO),
            "piano terra su terreno": da_dizionario(genera_progetto({**rapido, "piano": "terra"})),
            "villetta su cantina": da_dizionario(genera_progetto(
                {**rapido, "tipologia": "villetta", "numero_piani": 2, "sotto": "cantina",
                 "lati": {"S": "esterno", "N": "esterno", "E": "esterno", "O": "esterno"}})),
        }
        for m in modelli:
            for nome, prog in progetti.items():
                with self.subTest(modello=os.path.basename(m), progetto=nome):
                    xml, avvisi = genera_xml(prog, m)
                    self.assertEqual(schema.valida(xml), [])
                    self.assertFalse([a for a in avvisi if a.startswith("riferimento")], avvisi)


class TestTerreno(unittest.TestCase):
    def test_come_cened(self):
        from cened.terreno import u_pavimento_terreno
        # caso reale: CENED u_b = 0,18149 con d_t = 8,720
        self.assertAlmostEqual(u_pavimento_terreno(164.66, 65.451, 4.150228054429912, 0.42), 0.18149, places=4)

    def test_pavimento_piccolo_disperde_di_piu(self):
        from cened.terreno import u_pavimento_terreno
        self.assertGreater(u_pavimento_terreno(50, 30, 0.5), u_pavimento_terreno(500, 90, 0.5))

    def test_rapido_piano_terra_usa_13370(self):
        from cened.progetto import da_dizionario
        from cened.rapido import genera_progetto
        dati = {**TestRapido.BASE, "piano": "terra", "sotto": "terreno"}
        p = da_dizionario(genera_progetto(dati))
        pav = next(d for d in p.zona.dispersioni if d.nome.startswith("Pavimento"))
        self.assertIsNotNone(pav.u_terreno)
        self.assertLess(pav.u_terreno, pav.elemento.u)


class TestVerifiche2026(unittest.TestCase):
    def setUp(self):
        self.prog = carica(ESEMPIO)
        self.ris = calcola(self.prog)

    def test_tabelle_allegato_b(self):
        from cened import verifiche as v
        self.assertEqual(v.h_t_limite_nuova(0.8, "E"), 0.50)
        self.assertEqual(v.h_t_limite_nuova(0.5, "F"), 0.53)
        self.assertEqual(v.h_t_limite_nuova(0.3, "E"), 0.75)
        self.assertEqual(v.h_t_limite_ristr1(9, "E"), 0.55)
        self.assertEqual(v.h_t_limite_ristr1(30, "E"), 0.62)
        self.assertEqual(v.h_t_limite_ristr1(100, "F"), 0.96)
        self.assertEqual(v.zona_normativa("F1"), "F")

    def test_riqualificazione_limiti_e_znc(self):
        from cened.verifiche import verifica
        ver = {x.oggetto: x for x in verifica(self.prog, self.ris, "riqualificazione")}
        self.assertEqual(ver["Muratura mattone pieno 30 cm intonacata"].limite, 0.28)
        self.assertAlmostEqual(ver["Parete verso vano scala 25 cm"].limite, 0.28 / 0.6)
        self.assertEqual(ver["Solaio interpiano laterocemento"].limite, 0.8)

    def test_isolamento_interno_maggiorazione(self):
        from cened.verifiche import posizione_isolante
        s = StrutturaOpaca("X", "x", "parete", "esterno",
                           [Strato(LIBRERIA["cartongesso"], 0.0125), Strato(LIBRERIA["eps"], 0.06),
                            Strato(LIBRERIA["mattone_pieno"], 0.25)])
        self.assertEqual(posizione_isolante(s), "interno")
        s2 = StrutturaOpaca("Y", "y", "parete", "esterno",
                            [Strato(LIBRERIA["mattone_pieno"], 0.25), Strato(LIBRERIA["eps"], 0.10),
                             Strato(LIBRERIA["intonaco_calce_cemento"], 0.01)])
        self.assertEqual(posizione_isolante(s2), "esterno")

    def test_nuova_costruzione_h_t(self):
        from cened.verifiche import verifica
        h = [x for x in verifica(self.prog, self.ris, "nuova") if x.grandezza == "H'_T"][0]
        self.assertEqual(h.limite, 0.75)  # S/V 0,27 < 0,4, zona E
        self.assertEqual(h.esito, "NON VERIFICATA")


class TestClimaLombardia(unittest.TestCase):
    def test_irradiazione_come_cened(self):
        # valori calcolati da CENED+2.0 per una parete a gamma = 120° (Bergamo, lat 45°43')
        from cened.clima_lombardia import irradiazione
        from cened.dati_allegato1 import CAPOLUOGHI
        b = CAPOLUOGHI["Bergamo"]
        hb = [x / 3.6 for x in b["hb"]]
        hd = [x / 3.6 for x in b["hd"]]
        h = irradiazione(45 + 43 / 60, hb, hd, 90.0, 120.0)
        self.assertAlmostEqual(h[0], 0.6443617691838124, places=4)
        self.assertAlmostEqual(h[6], 3.5819559137433097, places=4)

    def test_temperatura_corretta_per_quota(self):
        # CENED per Brembate (BG, 173 m): gennaio 3,3573 °C
        from cened.clima_lombardia import clima_comune
        c = clima_comune("Brembate", quota=173, provincia_istat="016")
        self.assertAlmostEqual(c.te[0], 3.3573, places=3)
        self.assertEqual(c.provincia, "BG")
        self.assertEqual(len(c.irradianza), 9)

    def test_rapido_senza_clima(self):
        from cened.progetto import da_dizionario
        from cened.rapido import genera_progetto
        from cened import comuni
        if not comuni.tutti():
            self.skipTest("risorse/comuni_istat.json assente")
        dati = {k: v for k, v in TestRapido.BASE.items() if k != "clima"}
        p = da_dizionario(genera_progetto({**dati, "comune": "Dalmine", "quota": 207}))
        self.assertEqual(p.clima.provincia, "BG")
        self.assertGreater(calcola(p).q_h_nd, 0)


class TestCalibrazioneCened(unittest.TestCase):
    """Bilancio Allegato H contro i risultati di CENED+2.0 sugli export reali in esempi/ (se presenti)."""

    def _casi(self):
        import glob
        from cened.importa_cened import leggi_zona
        casi = {os.path.basename(f): leggi_zona(f) for f in glob.glob(os.path.join(QUI, "..", "esempi", "*.xml"))}
        if not casi:
            self.skipTest("nessun export reale in esempi/")
        return casi

    def test_h_t_e_ep_h_nd(self):
        from cened.bilancio_h import calcola_h
        for nome, (z, c, rif) in self._casi().items():
            with self.subTest(caso=nome):
                r = calcola_h(z, c)
                if not rif.get("ep_h_nd"):
                    continue
                self.assertAlmostEqual(r.h_t, rif["h_t"][0], delta=0.05 * rif["h_t"][0])
                ep = r.q_nh / z.superficie_utile
                if rif["ep_h_nd"] > 20:  # sui fabbisogni molto bassi lo scarto relativo non è significativo
                    self.assertAlmostEqual(ep, rif["ep_h_nd"], delta=0.05 * rif["ep_h_nd"])
