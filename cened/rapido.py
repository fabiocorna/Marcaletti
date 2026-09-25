"""Input rapido: dai pochi dati raccolti al sopralluogo genera il progetto completo.

Dati minimi: clima del comune, anno di costruzione, superficie utile, tipologia e piano,
cosa c'è su ciascun lato (esterno, vano scala, altra unità), impianto. Tutto il resto
(stratigrafie per epoca, serramenti, ponti termici, geometria semplificata, superfici
finestrate) viene ricavato con regole esplicite e finisce nel registro ipotesi: il
certificatore lo verifica e, se ha dati misurati, li inserisce nel file di progetto
generato, che è un normale progetto TOML modificabile.
"""
import math

OPPOSTI = {"S": "N", "N": "S", "E": "O", "O": "E", "SE": "NO", "NO": "SE", "SO": "NE", "NE": "SO"}
TIPI_LATO = ("esterno", "scala", "adiacente")
FINESTRA_TIPO = (1.20, 1.50)
PORTA_INGRESSO = (0.90, 2.10)

# Epoche costruttive (anno massimo incluso) -> soluzioni tipiche lombarde (indicative)
EPOCHE = [
    (1945, "fino al 1945"),
    (1976, "1946-1976"),
    (1991, "1977-1991 (L. 373/76)"),
    (2005, "1992-2005 (L. 10/91)"),
    (2015, "2006-2015 (D.Lgs. 192/05)"),
    (9999, "dal 2016 (DM 26/06/2015)"),
]

INTONACO_INT = {"materiale": "intonaco_calce_cemento", "spessore": 0.015}
INTONACO_EST = {"materiale": "intonaco_calce_cemento", "spessore": 0.02}
RASATURA = {"materiale": "intonaco_calce_cemento", "spessore": 0.01}


def _strato(materiale, spessore=None):
    d = {"materiale": materiale}
    if spessore is not None:
        d["spessore"] = spessore
    return d


PARETE_EST = [
    [INTONACO_INT, _strato("mattone_pieno", 0.45), INTONACO_EST],
    [INTONACO_INT, _strato("forato_8"), _strato("aria", 0.05), _strato("mattone_pieno", 0.12), INTONACO_EST],
    [INTONACO_INT, _strato("forato_8"), _strato("eps", 0.03), _strato("forato_12"), INTONACO_EST],
    [INTONACO_INT, _strato("blocco_alveolato", 0.30), _strato("eps", 0.02), INTONACO_EST],
    [INTONACO_INT, _strato("blocco_alveolato", 0.25), _strato("eps", 0.08), RASATURA],
    [INTONACO_INT, _strato("blocco_alveolato", 0.25), _strato("eps_grafite", 0.12), RASATURA],
]
PARETE_SCALA = [
    [INTONACO_INT, _strato("mattone_pieno", 0.25), INTONACO_INT],
    [INTONACO_INT, _strato("mattone_pieno", 0.25), INTONACO_INT],
    [INTONACO_INT, _strato("forato_8"), _strato("aria", 0.05), _strato("forato_12"), INTONACO_INT],
    [INTONACO_INT, _strato("forato_8"), _strato("aria", 0.05), _strato("forato_12"), INTONACO_INT],
    [INTONACO_INT, _strato("forato_8"), _strato("lana_roccia", 0.06), _strato("forato_12"), INTONACO_INT],
    [INTONACO_INT, _strato("forato_8"), _strato("lana_roccia", 0.08), _strato("forato_12"), INTONACO_INT],
]
ISOLANTE_COPERTURA = [0.0, 0.0, 0.03, 0.05, 0.10, 0.16]  # m di XPS
ISOLANTE_PAVIMENTO = [0.0, 0.0, 0.02, 0.04, 0.08, 0.12]
SERRAMENTI = [("singolo", "legno"), ("singolo", "legno"), ("doppio", "legno"),
              ("doppio", "legno"), ("doppio_basso_emissivo", "pvc"), ("triplo_basso_emissivo", "pvc")]
U_PORTA = [2.8, 2.8, 2.5, 2.2, 1.8, 1.4]
# psi [W/mK] (dimensioni esterne), indicativi: senza cappotto / con cappotto
PSI = {
    "solaio": (0.60, 0.10),
    "serramento": (0.25, 0.08),
    "copertura": (0.50, 0.10),
    "pavimento": (0.50, 0.15),
}

B_TR_SCALA = 0.6
B_TR_CANTINA = 0.5


def epoca(anno: int) -> int:
    for i, (fine, _) in enumerate(EPOCHE):
        if anno <= fine:
            return i
    return len(EPOCHE) - 1


def _solaio(tipo, isolante, verso):
    if tipo == "soffitto":  # dall'interno (sotto) verso l'esterno (sopra)
        strati = [INTONACO_INT, _strato("solaio_laterocemento_20_4")]
        if isolante:
            strati.append(_strato("xps", isolante))
        strati += [_strato("massetto_cementizio", 0.05), _strato("guaina_bituminosa", 0.005)]
    else:  # pavimento: dall'interno (sopra) verso il basso
        strati = [_strato("piastrelle_ceramica", 0.01), _strato("massetto_cementizio", 0.05)]
        if isolante:
            strati.append(_strato("xps", isolante))
        strati.append(_strato("cls_alleggerito", 0.08))
        strati.append(_strato("calcestruzzo_armato", 0.15) if verso == "terreno"
                      else _strato("solaio_laterocemento_20_4"))
        if verso != "terreno":
            strati.append(INTONACO_INT)
    return strati


def genera_progetto(r: dict) -> dict:
    """Dal dizionario di input rapido restituisce un dizionario di progetto completo."""
    ipotesi = []
    anno = r["anno_costruzione"]
    ep = epoca(anno)
    cappotto = ep >= 4
    ipotesi.append(f"Epoca costruttiva '{EPOCHE[ep][1]}': stratigrafie, serramenti e ponti termici "
                   "tipici dell'epoca (valori indicativi, da verificare al sopralluogo)")

    tipologia = r.get("tipologia", "appartamento")
    if tipologia not in ("appartamento", "villetta"):
        raise ValueError("tipologia: 'appartamento' o 'villetta'")
    n_piani = r.get("numero_piani", 1)
    piano = "unico" if tipologia == "villetta" else r.get("piano", "intermedio")
    if piano not in ("terra", "intermedio", "ultimo", "unico"):
        raise ValueError("piano: terra, intermedio, ultimo (o unico per l'intero edificio)")
    sotto = r.get("sotto", "terreno")  # per piano terra/villetta: terreno o cantina
    if sotto not in ("terreno", "cantina", "adiacente"):
        raise ValueError("sotto: terreno, cantina o adiacente")

    su = r["superficie_utile"]
    h_netta = r.get("altezza_netta", 2.70)
    h_lorda = h_netta + r.get("spessore_solaio", 0.30)
    rap_nl = r.get("rapporto_netto_lordo", 0.85)
    rap_lati = r.get("rapporto_lati", 1.3)
    su_piano = su / n_piani
    a_lorda = su_piano / rap_nl
    lato_corto = math.sqrt(a_lorda / rap_lati)
    lato_lungo = lato_corto * rap_lati
    ipotesi.append(f"Geometria semplificata: pianta rettangolare {lato_lungo:.2f} x {lato_corto:.2f} m "
                   f"(superficie netta/lorda {rap_nl}), altezza lorda di piano {h_lorda:.2f} m")

    lati = r["lati"]
    for esp, t in lati.items():
        if esp not in OPPOSTI:
            raise ValueError(f"lati: esposizione '{esp}' non valida {sorted(OPPOSTI)}")
        if t not in TIPI_LATO:
            raise ValueError(f"lati.{esp}: '{t}' non valido {TIPI_LATO}")
    lungo = r.get("lato_lungo", next(iter(lati)))
    lunghezze = {}
    for esp in lati:
        lunghezze[esp] = lato_lungo if esp in (lungo, OPPOSTI[lungo]) else lato_corto

    # ---------------- libreria ----------------
    strutture = [{"id": "PAR_EST", "nome": f"Parete esterna tipica {EPOCHE[ep][1]}",
                  "tipo": "parete", "verso": "esterno", "strati": PARETE_EST[ep]}]
    ha_scala = "scala" in lati.values()
    if ha_scala:
        strutture.append({"id": "PAR_SCALA", "nome": "Parete verso vano scala", "tipo": "parete",
                          "verso": "znc", "strati": PARETE_SCALA[ep]})
        strutture.append({"id": "PORTA_ING", "nome": "Porta d'ingresso", "tipo": "porta",
                          "verso": "znc", "u": U_PORTA[ep]})
        ipotesi.append(f"Porta d'ingresso {PORTA_INGRESSO[0]}x{PORTA_INGRESSO[1]} m, U={U_PORTA[ep]}")

    vetro, telaio = SERRAMENTI[ep]
    serr_in = r.get("serramenti", {})
    vetro, telaio = serr_in.get("vetro", vetro), serr_in.get("telaio", telaio)
    serramenti = [{"id": "FIN", "nome": f"Finestra {telaio} vetro {vetro}",
                   "larghezza": FINESTRA_TIPO[0], "altezza": FINESTRA_TIPO[1],
                   "vetro": vetro, "telaio": telaio}]

    k = 1 if cappotto else 0
    ponti = [{"id": "PT_SERR", "nome": "Parete - serramento", "psi": PSI["serramento"][k]},
             {"id": "PT_SOLAIO", "nome": "Parete - solaio interpiano", "psi": PSI["solaio"][k]}]
    ipotesi.append("Ponti termici con ψ indicativi per " + ("parete a cappotto" if cappotto
                                                            else "parete non isolata all'esterno"))
    znc = []
    if ha_scala:
        znc.append({"id": "SCALA", "nome": "Vano scala", "b_tr": B_TR_SCALA, "cened_tipoZnc": 2})
        ipotesi.append(f"Vano scala: b_tr = {B_TR_SCALA} (indicativo)")

    disp = []
    perim_est = sum(lunghezze[e] for e, t in lati.items() if t == "esterno")

    # ---------------- superfici verticali ----------------
    rap_fin = r.get("rapporto_finestrato", 0.125)
    a_fin_tot = su * rap_fin
    ipotesi.append(f"Superficie finestrata {a_fin_tot:.1f} m² = {rap_fin} x Su "
                   "(rapporto aeroilluminante), ripartita sui lati esterni in proporzione alla lunghezza")
    a_una = FINESTRA_TIPO[0] * FINESTRA_TIPO[1]
    per_finestra = 2 * sum(FINESTRA_TIPO)
    for esp, tipo in lati.items():
        area_lorda = lunghezze[esp] * h_lorda * n_piani
        if tipo == "esterno":
            quota = a_fin_tot * lunghezze[esp] / perim_est if perim_est else 0
            n_fin = max(1, round(quota / a_una)) if quota > 0 else 0
            disp.append({"nome": f"Parete {esp}", "struttura": "PAR_EST",
                         "area": round(area_lorda - n_fin * a_una, 2), "esposizione": esp,
                         "ponti": [{"ponte": "PT_SOLAIO", "lunghezza": round(lunghezze[esp] * max(1, n_piani - 1), 2)}]
                         if piano == "intermedio" or n_piani > 1 else []})
            if n_fin:
                disp.append({"nome": f"Finestre {esp}", "serramento": "FIN", "quantita": n_fin,
                             "esposizione": esp,
                             "ponti": [{"ponte": "PT_SERR", "lunghezza": round(n_fin * per_finestra, 2)}]})
        elif tipo == "scala":
            a_porta = PORTA_INGRESSO[0] * PORTA_INGRESSO[1]
            disp.append({"nome": f"Parete vano scala ({esp})", "struttura": "PAR_SCALA",
                         "area": round(area_lorda - a_porta, 2), "znc": "SCALA"})
            disp.append({"nome": "Porta d'ingresso", "struttura": "PORTA_ING",
                         "area": round(a_porta, 2), "znc": "SCALA"})
        # lati "adiacente": verso altra unità climatizzata, nessuna dispersione

    # ---------------- superfici orizzontali ----------------
    iso_c = ISOLANTE_COPERTURA[ep]
    iso_p = ISOLANTE_PAVIMENTO[ep]
    if piano in ("ultimo", "unico"):
        strutture.append({"id": "COPERTURA", "nome": "Copertura piana su laterocemento",
                          "tipo": "soffitto", "verso": "esterno", "strati": _solaio("soffitto", iso_c, "esterno")})
        ponti.append({"id": "PT_COP", "nome": "Parete - copertura", "psi": PSI["copertura"][k]})
        disp.append({"nome": "Copertura", "struttura": "COPERTURA", "area": round(a_lorda, 2),
                     "esposizione": "ORIZ", "ponti": [{"ponte": "PT_COP", "lunghezza": round(perim_est, 2)}]})
        ipotesi.append("Chiusura superiore: copertura piana verso esterno "
                       "(per sottotetto non riscaldato modificare verso e ZNC)")
    else:
        strutture.append({"id": "SOL_SUP", "nome": "Solaio verso unità superiore", "tipo": "soffitto",
                          "verso": "adiacente", "strati": _solaio("soffitto", 0, "adiacente")[:2]})
        disp.append({"nome": "Soffitto verso unità superiore", "struttura": "SOL_SUP",
                     "area": round(su_piano, 2)})

    if piano in ("terra", "unico") and sotto != "adiacente":
        strutture.append({"id": "PAVIMENTO", "nome": f"Pavimento verso {sotto}", "tipo": "pavimento",
                          "verso": "terreno" if sotto == "terreno" else "znc",
                          "strati": _solaio("pavimento", iso_p, sotto)})
        ponti.append({"id": "PT_PAV", "nome": "Parete - pavimento", "psi": PSI["pavimento"][k]})
        d = {"nome": f"Pavimento verso {sotto}", "struttura": "PAVIMENTO", "area": round(a_lorda, 2),
             "ponti": [{"ponte": "PT_PAV", "lunghezza": round(perim_est, 2)}]}
        if sotto == "terreno":
            d["perimetro"] = round(perim_est, 2)
            d["spessore_muri"] = round(sum(x.get("spessore", 0) for x in PARETE_EST[ep]
                                           if "spessore" in x), 3) or 0.30
            ipotesi.append("Pavimento su terreno: U equivalente UNI EN ISO 13370 (λ terreno 2,0 W/mK)")
        if sotto == "cantina":
            znc.append({"id": "CANTINA", "nome": "Cantina", "b_tr": B_TR_CANTINA})
            d["znc"] = "CANTINA"
            ipotesi.append(f"Cantina: b_tr = {B_TR_CANTINA} (indicativo)")
        disp.append(d)
    else:
        strutture.append({"id": "SOL_INF", "nome": "Solaio verso unità inferiore", "tipo": "pavimento",
                          "verso": "adiacente", "strati": _solaio("pavimento", 0, "adiacente")})
        disp.append({"nome": "Pavimento verso unità inferiore", "struttura": "SOL_INF",
                     "area": round(su_piano, 2)})

    volume_lordo = a_lorda * h_lorda * n_piani
    clima = r.get("clima")
    if clima is None:  # dati climatici regionali (Allegato H) dal comune e dalla quota
        from dataclasses import asdict
        from .clima_lombardia import clima_comune
        c = clima_comune(r["comune"], r.get("quota"))
        clima = {k2: v for k2, v in asdict(c).items() if v is not None}
        ipotesi.append(f"Dati climatici Allegato H per {c.comune} ({c.provincia}), quota "
                       f"{r.get('quota', 'del capoluogo')} m" + ("" if r.get("quota") else
                                                                  " — indicare la quota del comune"))
    progetto = {
        "progetto": {k2: v for k2, v in r.items()
                     if k2 in ("nome", "comune", "indirizzo", "foglio", "particella", "subalterno")}
        | {"anno_costruzione": anno, "tipologia": tipologia, "piano": piano},
        "clima": clima,
        "zona": {"nome": r.get("nome_zona", "Zona 1"), "destinazione": r.get("destinazione", "E.1(1)"),
                 "superficie_utile": su, "volume_lordo": round(volume_lordo, 2),
                 "altezza_netta": h_netta},
        "strutture": strutture,
        "serramenti": serramenti,
        "ponti": ponti,
        "znc": znc,
        "dispersioni": disp,
        "ipotesi_rapido": ipotesi,
    }
    if "impianto" in r:
        progetto["impianto"] = r["impianto"]
    return progetto


# ---------------- scrittura TOML (sottoinsieme sufficiente per i progetti) ----------------
def _val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(round(v, 4)) if isinstance(v, float) else str(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            return "[\n" + "".join(f"  {_val(x)},\n" for x in v) + "]"
        return "[" + ", ".join(_val(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_val(x)}" for k, x in v.items()) + " }"
    raise TypeError(type(v))


def _tabella(nome, d, righe):
    semplici = {k: v for k, v in d.items() if not isinstance(v, dict)}
    righe.append(f"[{nome}]")
    righe += [f"{k} = {_val(v)}" for k, v in semplici.items()]
    righe.append("")
    for k, v in d.items():
        if isinstance(v, dict):
            _tabella(f"{nome}.{k}", v, righe)


def a_toml(progetto: dict) -> str:
    righe = ["# Progetto generato da input rapido: verificare e correggere i valori ipotizzati.", ""]
    for chiave, val in progetto.items():
        if isinstance(val, dict):
            _tabella(chiave, val, righe)
    for chiave, val in progetto.items():
        if isinstance(val, list) and (not val or isinstance(val[0], dict)):
            for voce in val:
                righe.append(f"[[{chiave}]]")
                righe += [f"{k} = {_val(v)}" for k, v in voce.items()]
                righe.append("")
        elif isinstance(val, list):
            righe.insert(2, f"{chiave} = {_val(val)}")
    return "\n".join(righe)
