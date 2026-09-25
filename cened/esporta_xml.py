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

TIPO_STRUTTURA_OPACHE = {"parete": "1", "pavimento": "2", "soffitto": "3", "porta": "5"}
VERSO_DISPERSIONE = {"esterno": "1", "znc": "3"}  # 6 = verso ZNC superiore (sottotetto)
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

    def strutture_opache(self):
        serv, voci = self._servizio("servizioOpache", "opache")
        proto = voci[0]
        self._svuota(serv, voci)
        for s in self.prog.strutture.values():
            e = copy.deepcopy(proto)
            e.set("id", self._nuovo_id("opache", s.id))
            i, o = e.find(f"{D}input"), e.find(f"{D}output")
            ctx = f"struttura {s.id}"
            self._set(i, "nome", s.nome, ctx)
            self._set(i, "tipoStrutturaOpache", TIPO_STRUTTURA_OPACHE[s.tipo], ctx)
            if s.verso in VERSO_DISPERSIONE:
                self._set(i, "versoDispersione", VERSO_DISPERSIONE[s.verso], ctx)
            elif "cened_versoDispersione" not in s.extra:
                self.avvisi.append(f"{ctx}: codice versoDispersione per '{s.verso}' non noto, "
                                   "indicare cened_versoDispersione nel progetto")
            for el in (i, o):
                if el is not None and "u" in el.attrib:
                    el.set("u", _fmt(s.u))
            if s.strati:
                for el in (i, o):
                    if el is not None and "spessore" in el.attrib:
                        el.set("spessore", _fmt(s.spessore))
                    if el is not None and "k_i" in el.attrib:
                        el.set("k_i", _fmt(s.k_i))
            self._set_extra(i, s.extra, ctx)
            serv.append(e)

    def serramenti(self):
        serv, voci = self._servizio("servizioSerramenti", "serramenti")
        proto = voci[0]
        self._svuota(serv, voci)
        for s in self.prog.serramenti.values():
            e = copy.deepcopy(proto)
            e.set("id", self._nuovo_id("serramenti", s.id))
            i, o = e.find(f"{D}input"), e.find(f"{D}output")
            ctx = f"serramento {s.id}"
            self._set(i, "nome", s.nome, ctx)
            valori = {"a_w": s.a_w, "u_w": s.u_w, "g_n": s.g_n, "u_g": s.u_g, "u_f": s.u_f,
                      "larghezza": s.larghezza, "altezza": s.altezza}
            for el in (i, o):
                if el is None:
                    continue
                for k, v in valori.items():
                    if k in el.attrib:
                        el.set(k, _fmt(v))
            self._set(o, "u_w", s.u_w, ctx)
            self._set_extra(i, s.extra, ctx)
            serv.append(e)

    def ponti(self):
        if not self.prog.ponti:
            return
        serv, voci = self._servizio("servizioPonti", "ponti")
        proto = voci[0]
        self._svuota(serv, voci)
        for p in self.prog.ponti.values():
            e = copy.deepcopy(proto)
            e.set("id", self._nuovo_id("ponti", p.id))
            i, o = e.find(f"{D}input"), e.find(f"{D}output")
            ctx = f"ponte {p.id}"
            self._set(i, "nome", p.nome, ctx)
            for el in (i, o):
                if el is not None and "psi_e" in el.attrib:
                    el.set("psi_e", _fmt(p.psi))
            self._set(o, "psi_e", p.psi, ctx)
            self._set_extra(i, p.extra, ctx)
            serv.append(e)

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
        for z in self.prog.znc.values():
            e = copy.deepcopy(proto)
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

        for d in z.dispersioni:
            proto = proto_se if d.is_serramento else proto_op
            e = copy.deepcopy(proto)
            e.set("id", self._nuovo_id("dispersione", d.id))
            e.set("nome", d.nome)
            ctx = f"dispersione {d.id}"
            e.set("verso", VERSO_DISPERSIONE_XSD["znc" if d.znc is not None else d.verso])
            if d.is_serramento:
                e.set("rifSerramenti", self.ids[("serramenti", d.elemento.id)])
                e.set("area", _fmt(d.area))  # area totale (n. serramenti x A_w): lo schema non ha la quantità
            else:
                e.set("rifOpache", self.ids[("opache", d.elemento.id)])
                e.set("area", _fmt(d.area))
            if d.znc is not None:
                e.set("rifAmbienteConfinante", self.ids[("znc", d.znc.id)])
            elif "rifAmbienteConfinante" in e.attrib:
                del e.attrib["rifAmbienteConfinante"]
            if d.esposizione and "rifIrraggiamento" in e.attrib:
                if d.esposizione in irr:
                    e.set("rifIrraggiamento", irr[d.esposizione])
            elif not d.esposizione and "rifIrraggiamento" in e.attrib:
                del e.attrib["rifIrraggiamento"]
            for pa in d.ponti:
                if proto_pt is None:
                    self.avvisi.append(f"{ctx}: il modello non contiene ponti termici, "
                                       "inserirli in CENED+2.0")
                    break
                pt = copy.deepcopy(proto_pt)
                pt.set("rifPonti", self.ids[("ponti", pa.ponte.id)])
                pt.set("lunghezza", _fmt(pa.lunghezza))
                e.append(pt)
            cont.append(e)

    def verifica_riferimenti(self):
        ids = {e.get("id") for e in self.root.iter() if e.get("id")}
        for e in self.root.iter():
            for k, v in e.attrib.items():
                if k.startswith("rif") and v and v not in ids:
                    self.avvisi.append(f"riferimento {k}='{v}' senza elemento corrispondente")

    def genera(self) -> str:
        self.rimuovi_calcolati()
        self.strutture_opache()
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
