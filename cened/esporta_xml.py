"""Genera un XML di INPUT per la funzione "File > Importa file XML" di CENED+2.0.

Strategia "a modello": si parte da un calcolo.xml esportato da CENED+2.0 (un lavoro
qualsiasi dello stesso certificatore) e se ne riusano gli elementi come prototipi,
così tutti gli attributi e i codici non gestiti restano quelli validi prodotti da CENED.
Vengono sostituiti:
  - libreria strutture opache, serramenti, ponti termici (dizionario)
  - zone non climatizzate
  - geometria e dispersioni della prima zona del primo subalterno
Vengono rimossi i blocchi calcolati (valoriIntermedi, datiOutput, messaggi, licenza) e
la firma finale: sarà CENED+2.0 a ricalcolare tutto e a produrre il file firmato da
depositare al Catasto Energetico (CEER). Impianti, anagrafica e dati APE restano quelli
del modello e vanno verificati/completati in CENED+2.0.

Codici CENED noti (da export reali, vedi docs/ANALISI_XML_CENED.md). Quando un codice
non è noto va indicato nel progetto con le chiavi "cened_<attributo>".
"""
import copy
import io
import re
import xml.etree.ElementTree as ET

from .modello import AZIMUT, Progetto

NS = {
    "c": "http://www.cened.it/cenedplus2/calcolo",
    "d": "http://www.cened.it/cenedplus2/datiCalcolo",
    "sd": "http://www.cened.it/cenedplus2/struttureDati",
}
D = "{%s}" % NS["d"]
C = "{%s}" % NS["c"]

# Codici da export reali (docs/CODICI_CENED.md)
TIPO_STRUTTURA_OPACHE = {"parete": "1", "pavimento": "2", "soffitto": "3", "copertura": "4", "porta": "5"}
VERSO_DISPERSIONE = {"esterno": "1", "terreno": "2", "znc": "3", "adiacente": "5", "interno": "6"}
PREFISSO_CODICE = {"1": "PAR", "2": "PAV", "3": "SOF", "4": "COP", "5": "POR"}
COLORE_DEFAULT = "2"  # medio
ATTR_PRECALCOLATI_OPACHE = ("rifPrecalcolate", "u", "d", "k_i", "y_ie_precalcolata", "codiceSpessore")
ATTR_OSTRUZIONI = ("a_h", "b_h", "c_h", "alpha_h", "a_o", "b_o", "alpha_o", "c_f_sx", "d_f_sx",
                   "beta_f_sx", "c_f_dx", "d_f_dx", "beta_f_dx", "f_h_d", "f_o_d", "f_f_d", "f_s_d",
                   "rifSerramenti", "g_n", "g_n_sh_b", "g_n_sh_d", "f_sh_tende", "w_h", "w_l", "l",
                   "h_b", "w", "d", "b_s", "b_d", "z_w", "x_w", "a_or", "h_or", "a_v_sx", "a_v_dx")
BLOCCHI_CALCOLATI = ("valoriIntermedi", "datiOutput", "messaggi", "licenza")


class ErroreModello(Exception):
    pass


def _fmt(x: float, dec: int = 4) -> str:
    return f"{round(x, dec):.{dec}f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def _registra_namespace(template_path):
    for _, (prefisso, uri) in ET.iterparse(template_path, events=("start-ns",)):
        if re.fullmatch(r"ns\d+", prefisso):
            continue  # prefissi riservati da ElementTree (es. ns5 della licenza, che viene rimossa)
        ET.register_namespace(prefisso, uri)


VERSO_DISPERSIONE_XSD = {"esterno": "esterno", "znc": "znc", "terreno": "terreno", "adiacente": "interno"}


class _Generatore:
    def __init__(self, prog: Progetto, template_path: str):
        self.prog = prog
        self.avvisi: list[str] = []
        self.ids: dict[tuple[str, str], str] = {}  # (servizio, id progetto) -> id intero XSD
        _registra_namespace(template_path)
        self.tree = ET.parse(template_path)
        self.root = self.tree.getroot()
        self.cert = self._trova(self.root, f"{C}datiInput/{D}certificazione")
        self.diz = self._trova(self.cert, f"{D}dizionario")
        self.edificio = self._trova(self.cert, f"{D}datiEdificio")

    @staticmethod
    def _trova(el, percorso):
        r = el.find(percorso)
        if r is None:
            raise ErroreModello(f"il modello non contiene '{percorso}': non è un calcolo.xml CENED+2.0?")
        return r

    def _nuovo_id(self, tipo: str, chiave: str) -> str:
        """Gli id CENED sono interi positivi (sd:positiveInt): si assegna il primo libero."""
        if (tipo, chiave) not in self.ids:
            usati = {int(e.get("id")) for e in self.root.iter() if (e.get("id") or "").isdigit()}
            usati |= {int(v) for v in self.ids.values()}
            self.ids[(tipo, chiave)] = str(max(usati, default=0) + 1)
        return self.ids[(tipo, chiave)]

    def _set(self, el, attr, valore, contesto):
        """Imposta un attributo solo se il prototipo lo prevede (evita attributi inventati)."""
        if el is None:
            return
        if attr in el.attrib:
            el.set(attr, valore if isinstance(valore, str) else _fmt(valore))
        else:
            self.avvisi.append(f"{contesto}: attributo '{attr}' assente nel modello, non impostato")

    def _set_extra(self, el_input, extra, contesto):
        for k, v in extra.items():
            attr = k.removeprefix("cened_")
            el_input.set(attr, str(v))

    def _servizio(self, nome, elemento):
        serv = self.diz.find(f"{D}{nome}")
        if serv is None:
            raise ErroreModello(f"il modello non contiene il servizio {nome}")
        voci = serv.findall(f"{D}{elemento}")
        if not voci:
            raise ErroreModello(f"il modello non ha nessun elemento {elemento} in {nome}: "
                                "usare come modello un lavoro che ne contenga almeno uno")
        return serv, voci

    @staticmethod
    def _svuota(padre, voci):
        for v in voci:
            padre.remove(v)

    def rimuovi_calcolati(self):
        for figlio in list(self.root):
            locale = figlio.tag.split("}")[-1]
            if locale in BLOCCHI_CALCOLATI:
                self.root.remove(figlio)

    def _materiale(self, chiave, nome, categoria, tipologia, caratt, **valori) -> str:
        """Materiale utente (custom) nel servizioMateriali; restituisce l'id, riusando i duplicati."""
        k = (categoria, tipologia, caratt, tuple(sorted((a, round(v, 6)) for a, v in valori.items())))
        if k in self._materiali_creati:
            return self._materiali_creati[k]
        mid = self._nuovo_id("materiale", f"{chiave}#{len(self._materiali_creati)}")
        pref = {16: "RES SUP", 6: "INTER"}.get(categoria, "MUR")
        e = ET.SubElement(self._serv_materiali, f"{D}materiale", {"id": mid})
        ET.SubElement(e, f"{D}input", {"codiceMateriale": f"{pref}{1000 + len(self._materiali_creati)}",
                                       "custom": "true", "nome": nome[:500]})
        out = {"codiceCategoria": str(categoria), "rifNorma": "Materiali utente",
               "codiceTipologia": str(tipologia), "codiceCarattTermica": str(caratt)}
        out.update({a: _fmt(float(v), 6) for a, v in valori.items()})
        ET.SubElement(e, f"{D}output", out)
        self._materiali_creati[k] = mid
        return mid

    def _servizio_materiali(self):
        serv = self.diz.find(f"{D}servizioMateriali")
        if serv is None:
            serv = ET.Element(f"{D}servizioMateriali")
            # nell'XSD servizioMateriali segue servizioDatiClimatici
            figli = list(self.diz)
            pos = next((i + 1 for i, f in enumerate(figli) if f.tag == f"{D}servizioDatiClimatici"), 0)
            self.diz.insert(pos, serv)
        for m in list(serv):
            serv.remove(m)
        self._serv_materiali = serv
        self._materiali_creati = {}

    def _strati_xml(self, inp, s):
        """datiStrato dall'interno all'esterno, con le resistenze superficiali come strati."""
        flusso = s.flusso
        strati = [("rsi", s.rsi)]
        if s.strati:
            strati += [("strato", st) for st in s.strati]
        else:  # U imposta: un unico strato equivalente a resistenza nota
            strati.append(("r_equiv", max(1 / s.u - s.rsi - s.rse, 0.001)))
        if s.rse > 0:
            strati.append(("rse", s.rse))
        for pos, (tipo, val) in enumerate(strati, 1):
            a = {"posStrato": str(pos)}
            if tipo in ("rsi", "rse"):
                mid = self._materiale("res", "Resistenza", 16, 2, 1, rho=1.2, r=val, mu=1.0, c_p=1.0)
                a.update(rifMateriali=mid, tipoStrato="2", categoriaStrato="16", r_i=_fmt(val, 5), rho_i="1.2")
            elif tipo == "r_equiv":
                mid = self._materiale("req", f"Strato equivalente U={s.u:.3f}", 13, 1, 1,
                                      rho=1000.0, r=val, s=10.0, mu=10.0, c_p=1.0)
                a.update(rifMateriali=mid, tipoStrato="1", categoriaStrato="13", r_i=_fmt(val, 5),
                         rho_i="1000", c_i="1", d_i="10")
                self.avvisi.append(f"struttura {s.id}: U imposta, esportata come strato equivalente")
            else:
                st = val
                m = st.materiale
                d_mm = st.spessore * 1000
                if st.intercapedine:
                    r = st.resistenza(flusso)
                    lam = st.spessore / r
                    mid = self._materiale("aria", f"Intercapedine d'aria {d_mm:g} mm", 6, 3, 2,
                                          rho=1.3, **{"lambda": lam}, mu=1.0, c_p=1.008)
                    a.update(rifMateriali=mid, tipoStrato="3", categoriaStrato="6", lambda_i=_fmt(lam, 5),
                             rho_i="1.3", c_i="1.008", d_i=_fmt(d_mm, 2))
                elif m.r is not None:
                    mid = self._materiale("mat", m.nome, 13, 1, 1, rho=m.rho, r=m.r, s=d_mm, mu=m.mu,
                                          c_p=m.c / 1000)
                    a.update(rifMateriali=mid, tipoStrato="1", categoriaStrato="13", r_i=_fmt(m.r, 5),
                             rho_i=_fmt(m.rho, 3), c_i=_fmt(m.c / 1000, 4), d_i=_fmt(d_mm, 2))
                else:
                    mid = self._materiale("mat", m.nome, 13, 1, 2, rho=m.rho, **{"lambda": m.lambda_},
                                          mu=m.mu, c_p=m.c / 1000)
                    a.update(rifMateriali=mid, tipoStrato="1", categoriaStrato="13",
                             lambda_i=_fmt(m.lambda_, 5), rho_i=_fmt(m.rho, 3), c_i=_fmt(m.c / 1000, 4),
                             d_i=_fmt(d_mm, 2))
            ET.SubElement(inp, f"{D}datiStrato", a)

    def strutture_opache(self):
        serv, voci = self._servizio("servizioOpache", "opache")
        proto = voci[0]
        self._svuota(serv, voci)
        self._servizio_materiali()
        con_ponti = {d.elemento.id for d in self.prog.zona.dispersioni if d.ponti and not d.is_serramento}
        for n, s in enumerate(self.prog.strutture.values(), 1):
            e = copy.deepcopy(proto)
            e.set("id", self._nuovo_id("opache", s.id))
            o = e.find(f"{D}output")
            if o is not None:
                e.remove(o)  # lo ricalcola il motore
            i = e.find(f"{D}input")
            for figlio in list(i):
                i.remove(figlio)
            for attr in ATTR_PRECALCOLATI_OPACHE:
                i.attrib.pop(attr, None)
            tipo = "copertura" if s.tipo == "soffitto" and s.verso == "esterno" else s.tipo
            cod_tipo = TIPO_STRUTTURA_OPACHE[tipo]
            verso = VERSO_DISPERSIONE.get(s.verso)
            if verso is None and "cened_versoDispersione" not in s.extra:
                self.avvisi.append(f"struttura {s.id}: verso '{s.verso}' senza codice CENED "
                                   "(terreno: usare il servizio terreno in CENED)")
                verso = "1"
            i.set("nome", s.nome)
            i.set("codice", f"{PREFISSO_CODICE[cod_tipo]}{1000 + n}")
            i.set("tipoStruttura", cod_tipo)
            i.set("tipoStrutturaOpache", cod_tipo)
            i.set("versoDispersione", verso)
            i.set("versoDispersioneOpache", verso)
            i.set("coloreEsterno", i.get("coloreEsterno") or COLORE_DEFAULT)
            i.set("pontiTermici", "true" if s.id in con_ponti else "false")
            self._strati_xml(i, s)
            self._set_extra(i, s.extra, f"struttura {s.id}")
            serv.append(e)

    def serramenti(self):
        """Serramento singolo (doppio=false, gruppo di attributi "2") descritto per componenti:
        U_g, U_t, A_g, A_t, l_g, ψ_g. Tipo di vetro, gas, chiusure e schermature restano quelli
        del modello (segnalato), salvo override `cened_*` nel progetto."""
        serv, voci = self._servizio("servizioSerramenti", "serramenti")
        proto = voci[0]
        self._svuota(serv, voci)
        for n, s in enumerate(self.prog.serramenti.values(), 1):
            e = copy.deepcopy(proto)
            e.set("id", self._nuovo_id("serramenti", s.id))
            o = e.find(f"{D}output")
            if o is not None:
                e.remove(o)  # lo ricalcola il motore
            i = e.find(f"{D}input")
            for a in list(i.attrib):
                if a.startswith("rifPrecalcolate") or a.endswith("_1") or a in ("tipoVetro1", "tipoGas1",
                                                                                 "tipoTelaio1"):
                    del i.attrib[a]
            i.set("nome", s.nome)
            i.set("codice", f"SER{1000 + n}")
            i.set("doppio", "false")
            i.set("u_g_2", _fmt(s.u_g))
            i.set("a_g_2", _fmt(s.a_g))
            i.set("a_t_2", _fmt(s.a_f))
            i.set("g_n", _fmt(s.g_n))
            if s.u_w_imposta is not None:
                i.set("u_w_2", _fmt(s.u_w_imposta))
                for a in ("u_t_2", "l_g_2", "psi_g_2"):
                    i.attrib.pop(a, None)
            else:
                i.attrib.pop("u_w_2", None)
                i.set("tipoTelaio2", i.get("tipoTelaio2") or "2")
                i.set("u_t_2", _fmt(s.u_f))
                i.set("l_g_2", _fmt(s.l_g))
                i.set("tipoDistanziatore2", i.get("tipoDistanziatore2") or "1")
                i.set("psi_g_2", _fmt(s.psi_g))
                i.set("epsilon_ne_2", i.get("epsilon_ne_2") or "0.837")
            self._set_extra(i, s.extra, f"serramento {s.id}")
            serv.append(e)
        self.avvisi.append("serramenti: tipo vetro/gas, chiusure oscuranti e schermature presi dal "
                           "modello, da verificare in CENED")

    def terreno(self):
        """Servizio terreno (UNI EN ISO 13370) per i pavimenti su terreno con perimetro noto."""
        vecchio = self.diz.find(f"{D}servizioTerreno")
        proto = None
        if vecchio is not None:
            voci = vecchio.findall(f"{D}terreno")
            proto = copy.deepcopy(voci[0]) if voci else None
            self.diz.remove(vecchio)
        pavimenti = [d for d in self.prog.zona.dispersioni if d.u_terreno is not None]
        senza_perimetro = [d for d in self.prog.zona.dispersioni
                           if not d.is_serramento and d.elemento.verso == "terreno" and d.u_terreno is None]
        for d in senza_perimetro:
            self.avvisi.append(f"dispersione {d.id}: pavimento su terreno senza perimetro esposto, "
                               "da completare in CENED")
        if not pavimenti:
            return
        serv = ET.Element(f"{D}servizioTerreno")
        figli = list(self.diz)  # nell'XSD servizioTerreno segue servizioOpache
        pos = next(i + 1 for i, f in enumerate(figli) if f.tag == f"{D}servizioOpache")
        self.diz.insert(pos, serv)
        for d in pavimenti:
            e = ET.SubElement(serv, f"{D}terreno", {"id": self._nuovo_id("terreno", d.id)})
            attr = {"nome": d.nome[:500], "codice": "", "tipoElemento": "1", "p": _fmt(d.perimetro),
                    "a": _fmt(d.area), "lambda_g": "2.0",
                    "rifOpacheGf": self.ids[("opache", d.elemento.id)], "r_gf": _fmt(d.r_tot_terreno, 6),
                    "tipoIsolamento": "1", "flagPerLocale": "false",
                    "w_w": _fmt(d.spessore_muri * 1000), "k_i_pav": _fmt(d.elemento.k_i, 4)}
            if proto is not None:  # eventuali attributi aggiuntivi del modello non gestiti qui
                for k, v in proto.find(f"{D}input").attrib.items():
                    attr.setdefault(k, v)
            ET.SubElement(e, f"{D}input", attr)

    def ponti(self):
        """Ponti termici con ψ inserito dall'utente (custom=true, psi_e_utente/psi_i_utente)."""
        if not self.prog.ponti:
            return
        serv, voci = self._servizio("servizioPonti", "ponti")
        self._svuota(serv, voci)
        for n, p in enumerate(self.prog.ponti.values(), 1):
            e = ET.SubElement(serv, f"{D}ponti", {"id": self._nuovo_id("ponti", p.id)})
            attr = {"nome": p.nome, "codice": f"PON{n}", "custom": "true",
                    "psi_e_utente": _fmt(p.psi, 6), "psi_i_utente": _fmt(p.psi, 6)}
            attr.update({k.removeprefix("cened_"): str(v) for k, v in p.extra.items()})
            ET.SubElement(e, f"{D}input", attr)

    def zone_non_climatizzate(self):
        amb = self.edificio.find(f"{D}ambientiConfinanti")
        if not self.prog.znc:
            return
        if amb is None:
            raise ErroreModello("il modello non ha ambientiConfinanti: usarne uno con un vano scala")
        voci = amb.findall(f"{D}zonaNonClimatizzata")
        if not voci:
            raise ErroreModello("il modello non ha zone non climatizzate da usare come prototipo")
        proto = voci[0]
        self._svuota(amb, voci)
        cfg = self.cert.find(f"{D}configurazioneCalcolo")
        if cfg is not None and cfg.get("metodoAnaliticoZNCTerreno") == "true":
            cfg.set("metodoAnaliticoZNCTerreno", "false")
            self.avvisi.append("ZNC con metodo semplificato (b_tr): disattivato il metodo analitico del modello")
        for z in self.prog.znc.values():
            e = copy.deepcopy(proto)
            for figlio in list(e):  # dispersioni proprie della ZNC (metodo analitico) del modello
                if figlio.tag == f"{D}dispersioni":
                    e.remove(figlio)
            e.set("id", self._nuovo_id("znc", z.id))
            self._set(e, "nome", z.nome, f"ZNC {z.id}")
            self._set_extra(e, z.extra, f"ZNC {z.id}")
            amb.append(e)

    def _irraggiamento(self):
        """Mappa esposizione -> id del servizioIrraggiamento, creando le voci mancanti."""
        serv = self.diz.find(f"{D}servizioIrraggiamento")
        mappa = {}
        if serv is None:
            return mappa
        voci = list(serv)
        for v in voci:
            i = v.find(f"{D}input")
            if i is None:
                continue
            try:
                gamma, beta = float(i.get("gamma", "nan")), float(i.get("beta", "nan"))
            except ValueError:
                continue
            for esp, az in AZIMUT.items():
                if abs(gamma - az) < 0.5 and abs(beta - 90) < 0.5:
                    mappa.setdefault(esp, v.get("id"))
            if abs(beta) < 0.5:
                mappa.setdefault("ORIZ", v.get("id"))
        esposizioni = {d.esposizione for d in self.prog.zona.dispersioni if d.esposizione}
        mancanti = esposizioni - set(mappa)
        if mancanti and voci and voci[0].find(f"{D}input") is not None \
                and "gamma" in voci[0].find(f"{D}input").attrib:
            for esp in sorted(mancanti):
                e = copy.deepcopy(voci[0])
                nuovo_id = self._nuovo_id("irraggiamento", esp)
                e.set("id", nuovo_id)
                i = e.find(f"{D}input")
                i.set("gamma", _fmt(float(AZIMUT.get(esp, 0))))
                i.set("beta", "0.0" if esp == "ORIZ" else "90.0")
                o = e.find(f"{D}output")
                if o is not None:
                    e.remove(o)  # lo ricalcola CENED
                serv.append(e)
                mappa[esp] = nuovo_id
        elif mancanti:
            self.avvisi.append(f"esposizioni {sorted(mancanti)} non presenti nel modello: "
                               "assegnarle in CENED+2.0")
        return mappa

    def _ombre(self, id_irr: str, esp: str, trasparente: bool) -> str | None:
        """Ombre per esposizione e tipo (opaco/trasparente): riusa quelle senza ostruzioni del
        modello con lo stesso irraggiamento, altrimenti le crea dal prototipo senza ostruzioni."""
        chiave = (id_irr, trasparente)
        if chiave in self._ombre_create:
            return self._ombre_create[chiave]
        serv = self.diz.find(f"{D}servizioOmbre")
        if serv is None:
            return None
        flag = "true" if trasparente else "false"
        voci = [v for v in self._proto_ombre if v.find(f"{D}input") is not None]
        simili = [v for v in voci if v.find(f"{D}input").get("trasparente") == flag] or voci
        if not simili:
            return None
        e = copy.deepcopy(simili[0])
        e.set("id", self._nuovo_id("ombre", f"{esp}-{flag}"))
        i = e.find(f"{D}input")
        for a in ATTR_OSTRUZIONI:
            i.attrib.pop(a, None)
        i.set("trasparente", flag)
        i.set("rifIrraggiamento", id_irr)
        i.set("gamma", _fmt(float(AZIMUT.get(esp, 0))))
        i.set("beta", "0.0" if esp == "ORIZ" else "90.0")
        o = e.find(f"{D}output")
        if o is not None:
            e.remove(o)
        # i dati mensili (ore di soleggiamento) dipendono dall'orientamento: si copiano
        # dall'output dell'irraggiamento corrispondente, se il modello lo contiene
        irr = next((v for v in self.diz.iter(f"{D}irraggiamento") if v.get("id") == id_irr), None)
        mesi_irr = irr.findall(f"{D}output/{D}datiMensili") if irr is not None else []
        if mesi_irr:
            for dm, di in zip(i.findall(f"{D}datiMensili"), mesi_irr):
                for a in ("t_a_y", "t_a_y2", "t_t_y", "t_t_y2"):
                    if a in di.attrib:
                        dm.set(a, di.get(a))
        else:
            self.avvisi.append(f"ombre {esp}: dati mensili copiati dal modello, verificarli in CENED")
        serv.append(e)
        self._ombre_create[chiave] = e.get("id")
        return e.get("id")

    def zona(self):
        zona_xml = self.edificio.find(f"{D}subalterni/{D}subalterno/{D}zone/{D}zona")
        if zona_xml is None:
            raise ErroreModello("il modello non contiene subalterni/zone")
        z = self.prog.zona
        geo = zona_xml.find(f"{D}geometria")
        self._set(zona_xml, "nome", z.nome, "zona")
        self._set(geo, "superficieUtile", z.superficie_utile, "geometria")
        self._set(geo, "volumeLordo", z.volume_lordo, "geometria")
        self._set(geo, "altezzaMediaNetta", z.altezza_netta, "geometria")

        cont = zona_xml.find(f"{D}dispersioni")
        voci = cont.findall(f"{D}dispersione") if cont is not None else []
        proto_op = next((v for v in voci if v.get("rifOpache")), None)
        proto_se = next((v for v in voci if v.get("rifSerramenti")), None)
        proto_pt = next((p for v in voci for p in v.findall(f"{D}ponteTermico")), None)
        if proto_op is None or proto_se is None:
            raise ErroreModello("la zona del modello deve contenere almeno una dispersione opaca "
                                "e una con serramento")
        for p in (proto_op, proto_se):
            for pt in p.findall(f"{D}ponteTermico"):
                p.remove(pt)
        self._svuota(cont, voci)
        irr = self._irraggiamento()
        serv_ombre = self.diz.find(f"{D}servizioOmbre")
        self._proto_ombre = []
        if serv_ombre is not None:  # le ombre del modello riferiscono serramenti/ostruzioni sostituiti
            self._proto_ombre = [copy.deepcopy(v) for v in serv_ombre]
            for v in list(serv_ombre):
                serv_ombre.remove(v)
        self._ombre_create = {}

        for d in z.dispersioni:
            copie = d.quantita if d.is_serramento else 1
            for k in range(copie):
                cont.append(self._dispersione(d, k, copie, proto_se if d.is_serramento else proto_op,
                                              proto_pt, irr))

    def _dispersione(self, d, k, copie, proto, proto_pt, irr):
        """Una dispersione CENED; i serramenti multipli diventano una dispersione ciascuno."""
        e = copy.deepcopy(proto)
        for attr in ("rifTerreno", "rifOpache", "rifSerramenti", "verso", "rifAmbienteConfinante",
                     "rifIrraggiamento", "rifOmbre", "tipoAmbienteConfinante", "area", "areaNetta"):
            e.attrib.pop(attr, None)
        e.set("id", self._nuovo_id("dispersione", f"{d.id}#{k}"))
        e.set("nome", d.nome if copie == 1 else f"{d.nome} ({k + 1}/{copie})")
        ctx = f"dispersione {d.id}"
        if d.is_serramento:
            e.set("verso", "znc" if d.znc is not None else "esterno")  # come negli export CENED
            e.set("rifSerramenti", self.ids[("serramenti", d.elemento.id)])
        elif d.u_terreno is not None:
            e.set("verso", "terreno")
            e.set("rifTerreno", self.ids[("terreno", d.id)])
            e.set("area", _fmt(d.area))
        else:
            e.set("rifOpache", self.ids[("opache", d.elemento.id)])
            e.set("area", _fmt(d.area))
            e.set("areaNetta", _fmt(d.area))
            if "colorazione" in e.attrib:
                e.set("colorazione", str(d.elemento.extra.get("cened_coloreEsterno", COLORE_DEFAULT)))
        if d.znc is not None:
            e.set("rifAmbienteConfinante", self.ids[("znc", d.znc.id)])
        if d.esposizione and d.znc is None and d.u_terreno is None:
            if d.esposizione in irr:
                e.set("rifIrraggiamento", irr[d.esposizione])
                om = self._ombre(irr[d.esposizione], d.esposizione, d.is_serramento)
                if om:
                    e.set("rifOmbre", om)
            else:
                self.avvisi.append(f"{ctx}: esposizione {d.esposizione} da assegnare in CENED")
        for pa in d.ponti:
            if proto_pt is None:
                self.avvisi.append(f"{ctx}: il modello non contiene ponti termici, inserirli in CENED+2.0")
                break
            pt = copy.deepcopy(proto_pt)
            for a in ("tipologiaPonteDm", "codiceTipologiaPonte"):
                pt.attrib.pop(a, None)
            pt.set("rifPonti", self.ids[("ponti", pa.ponte.id)])
            pt.set("lunghezza", _fmt(pa.lunghezza / copie))
            e.append(pt)
        return e

    def verifica_riferimenti(self):
        ids = {e.get("id") for e in self.root.iter() if e.get("id")}
        for e in self.root.iter():
            for k, v in e.attrib.items():
                if k.startswith("rif") and v.isdigit() and v not in ids:
                    self.avvisi.append(f"riferimento {k}='{v}' in <{e.tag.split('}')[-1]}> "
                                       "senza elemento corrispondente")

    def genera(self) -> str:
        self.rimuovi_calcolati()
        self.strutture_opache()
        self.terreno()
        self.serramenti()
        self.ponti()
        self.zone_non_climatizzate()
        self.zona()
        self.verifica_riferimenti()
        ET.indent(self.tree)
        buf = io.BytesIO()
        self.tree.write(buf, encoding="UTF-8", xml_declaration=True)
        return buf.getvalue().decode("utf-8")


def genera_xml(prog: Progetto, template_path: str, output_path: str | None = None):
    """Restituisce (xml, avvisi). Se output_path è dato scrive anche il file."""
    from .schema import valida
    g = _Generatore(prog, template_path)
    xml = g.genera()
    errori = valida(xml)
    if errori is None:
        g.avvisi.append("validazione XSD non eseguita (servono lxml e risorse/SCHEMA_XSD)")
    elif errori:
        g.avvisi.append(f"XSD: {len(errori)} errori di validazione")
        g.avvisi += [f"XSD {x}" for x in errori[:20]]
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml)
    return xml, g.avvisi
