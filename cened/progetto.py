"""Caricamento del progetto da file TOML, con registro dei valori di default applicati."""
import tomllib

from .involucro import (TELAI, VETRI, PonteTermico, Serramento, Strato, StrutturaOpaca,
                        ZonaNonClimatizzata, ARIA)
from .materiali import LIBRERIA, Materiale
from .modello import Clima, Dispersione, PonteApplicato, Progetto, Zona


def _materiali(dati):
    lib = dict(LIBRERIA)
    for m in dati.get("materiali", []):
        lib[m["id"]] = Materiale(
            m.get("nome", m["id"]), lambda_=m.get("lambda"), rho=m.get("rho", 0.0),
            c=m.get("c", 1000.0), r=m.get("r"), spessore_fisso=m.get("spessore"),
            isolante=m.get("isolante", False), fonte=m.get("fonte", "utente"),
            mu=m.get("mu", 10.0))
    return lib


def _struttura(s, lib, ipotesi):
    strati = []
    for st in s.get("strati", []):
        if st.get("materiale") == "aria":
            strati.append(Strato(ARIA, st["spessore"], intercapedine=True))
            continue
        mid = st["materiale"]
        if mid not in lib:
            raise ValueError(f"struttura {s['id']}: materiale '{mid}' sconosciuto")
        mat = lib[mid]
        sp = st.get("spessore", mat.spessore_fisso)
        if sp is None:
            raise ValueError(f"struttura {s['id']}: spessore mancante per '{mid}'")
        if mat.fonte == "indicativo":
            val = f"λ={mat.lambda_} W/mK" if mat.r is None else f"R={mat.r} m²K/W"
            ipotesi.append(f"Materiale '{mat.nome}': valore di libreria indicativo ({val})")
        strati.append(Strato(mat, sp))
    extra = {k: v for k, v in s.items() if k.startswith("cened_")}
    return StrutturaOpaca(s["id"], s["nome"], s["tipo"], s["verso"], strati,
                          u_imposta=s.get("u"), k_i_imposta=s.get("k_i"), extra=extra)


def _serramento(s, ipotesi):
    vetro = VETRI.get(s.get("vetro", ""), {})
    telaio = TELAI.get(s.get("telaio", ""), {})
    val = {}
    for chiave, fonte, nome_fonte in (("u_g", vetro, "vetro"), ("g_n", vetro, "vetro"),
                                      ("u_f", telaio, "telaio"), ("psi_g", telaio, "telaio")):
        if chiave in s:
            val[chiave] = s[chiave]
        elif chiave in fonte:
            val[chiave] = fonte[chiave]
            ipotesi.append(f"Serramento '{s['nome']}': {chiave}={fonte[chiave]} da tabella "
                           f"({nome_fonte} '{s.get(nome_fonte)}')")
        elif "u_w" not in s or chiave == "g_n":
            raise ValueError(f"serramento {s['id']}: manca '{chiave}' (o indicare vetro/telaio)")
        else:
            val[chiave] = 0.0
    if "frazione_telaio" not in s:
        ipotesi.append(f"Serramento '{s['nome']}': frazione di telaio 0.25 (default)")
    extra = {k: v for k, v in s.items() if k.startswith("cened_")}
    return Serramento(s["id"], s["nome"], s["larghezza"], s["altezza"],
                      val["u_g"], val["u_f"], val["g_n"], val["psi_g"],
                      s.get("frazione_telaio", 0.25), s.get("u_w"), extra)


def carica(percorso: str) -> Progetto:
    with open(percorso, "rb") as f:
        dati = tomllib.load(f)
    return da_dizionario(dati)


def da_dizionario(dati: dict) -> Progetto:
    ipotesi: list[str] = list(dati.get("ipotesi_rapido", []))
    lib = _materiali(dati)

    c = dati["clima"]
    clima = Clima(comune=c["comune"], zona_climatica=c["zona_climatica"], te=c["te"],
                  irradianza=c.get("irradianza", {}), gg=c.get("gg"),
                  codice_istat=c.get("codice_istat"), provincia=c.get("provincia"), ur=c.get("ur"))

    strutture = {s["id"]: _struttura(s, lib, ipotesi) for s in dati.get("strutture", [])}
    serramenti = {s["id"]: _serramento(s, ipotesi) for s in dati.get("serramenti", [])}
    ponti = {p["id"]: PonteTermico(p["id"], p["nome"], p["psi"],
                                   {k: v for k, v in p.items() if k.startswith("cened_")})
             for p in dati.get("ponti", [])}
    znc = {z["id"]: ZonaNonClimatizzata(z["id"], z["nome"], z["b_tr"],
                                        {k: v for k, v in z.items() if k.startswith("cened_")})
           for z in dati.get("znc", [])}

    zd = dati["zona"]
    if "ricambi_orari" not in zd:
        ipotesi.append("Ventilazione naturale: 0.5 ricambi/h (UNI/TS 11300-1, residenziale)")
    zona = Zona(nome=zd["nome"], superficie_utile=zd["superficie_utile"],
                volume_lordo=zd["volume_lordo"], altezza_netta=zd["altezza_netta"],
                destinazione=zd.get("destinazione", "E.1(1)"),
                volume_netto=zd.get("volume_netto"),
                ricambi_orari=zd.get("ricambi_orari", 0.5),
                temperatura_interna=zd.get("temperatura_interna", 20.0),
                capacita_areica=zd.get("capacita_areica"))

    for n, d in enumerate(dati.get("dispersioni", []), 1):
        did = d.get("id", f"D{n}")
        if "struttura" in d:
            el = strutture[d["struttura"]]
            area = d["area"]
        elif "serramento" in d:
            el = serramenti[d["serramento"]]
            area = el.a_w * d.get("quantita", 1)
        else:
            raise ValueError(f"dispersione {did}: indicare 'struttura' o 'serramento'")
        z = znc[d["znc"]] if "znc" in d else None
        if not isinstance(el, Serramento) and el.verso == "znc" and z is None:
            raise ValueError(f"dispersione {did}: struttura verso ZNC senza 'znc'")
        esp = d.get("esposizione")
        verso_est = z is None and (isinstance(el, Serramento) or el.verso == "esterno")
        if verso_est and esp is None:
            raise ValueError(f"dispersione {did}: serve 'esposizione' per superfici verso esterno")
        pa = [PonteApplicato(ponti[p["ponte"]], p["lunghezza"]) for p in d.get("ponti", [])]
        zona.dispersioni.append(Dispersione(
            did, d.get("nome", el.nome), el, area, esp, z, d.get("quantita", 1),
            d.get("f_sh_ob", 1.0), pa, d.get("perimetro"), d.get("spessore_muri", 0.30)))

    return Progetto(nome=dati.get("progetto", {}).get("nome", "senza nome"), clima=clima,
                    zona=zona, strutture=strutture, serramenti=serramenti, ponti=ponti,
                    znc=znc, anagrafica=dati.get("progetto", {}), ipotesi=ipotesi,
                    impianto=dati.get("impianto", {}))
