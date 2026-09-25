"""Legge un export XML di CENED+ 2.0 (calcolo.xml) e ne stampa un riepilogo.

Uso:
    python cened/leggi_export.py percorso/calcolo.xml [--json]

I dati personali (nomi, codici fiscali, indirizzi dei proprietari) non vengono
riportati nel riepilogo.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET

NS_D = "{http://www.cened.it/cenedplus2/datiCalcolo}"
NS_C = "{http://www.cened.it/cenedplus2/calcolo}"


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _index(root, servizio, elemento):
    """Mappa id -> (attributi input, attributi output) per un servizio del dizionario."""
    out = {}
    serv = root.find(f".//{NS_D}dizionario/{NS_D}{servizio}")
    if serv is None:
        return out
    for e in serv.findall(f"{NS_D}{elemento}"):
        i = e.find(f"{NS_D}input")
        o = e.find(f"{NS_D}output")
        out[e.get("id")] = (
            dict(i.attrib) if i is not None else {},
            dict(o.attrib) if o is not None else {},
        )
    return out


def leggi(path):
    root = ET.parse(path).getroot()
    cert = root.find(f"{NS_C}datiInput/{NS_D}certificazione")
    sw = cert.find(f"{NS_D}software")
    clima = cert.find(f".//{NS_D}servizioDatiClimatici/{NS_D}output")
    edificio = cert.find(f"{NS_D}datiEdificio")

    opache = _index(cert, "servizioOpache", "opache")
    serramenti = _index(cert, "servizioSerramenti", "serramenti")
    ponti = _index(cert, "servizioPonti", "ponti")
    znc = {
        z.get("id"): dict(z.attrib)
        for z in edificio.findall(f"{NS_D}ambientiConfinanti/{NS_D}zonaNonClimatizzata")
    }

    ris = {
        "software": dict(sw.attrib) if sw is not None else {},
        "clima": {
            k: clima.get(k)
            for k in ("nome", "siglaProvincia", "z", "zonaClimatica", "gg", "theta_e_p")
        }
        if clima is not None
        else {},
        "edificio": {
            k: edificio.get(k)
            for k in ("comune", "numeroPiani", "foglio", "particella", "f_p_nren_th")
        },
        "zone_non_climatizzate": znc,
        "subalterni": [],
    }

    for sub in edificio.findall(f"{NS_D}subalterni/{NS_D}subalterno"):
        s = {
            k: sub.get(k)
            for k in ("id", "periodoCostruzione", "intervalloTemporale", "subalternoNumero")
        }
        s["zone"] = []
        for z in sub.findall(f"{NS_D}zone/{NS_D}zona"):
            geo = z.find(f"{NS_D}geometria")
            zona = {
                "nome": z.get("nome"),
                "destinazioneUso": z.get("destinazioneUso"),
                "servizi": {
                    k: z.get(k) for k in ("riscAttivo", "acsAttivo", "rafAttivo", "ventAttivo")
                },
                "geometria": dict(geo.attrib) if geo is not None else {},
                "dispersioni": [],
            }
            h_tr = 0.0
            for d in z.findall(f"{NS_D}dispersioni/{NS_D}dispersione"):
                voce = {"id": d.get("id"), "nome": d.get("nome")}
                if d.get("rifOpache"):
                    inp, outp = opache.get(d.get("rifOpache"), ({}, {}))
                    u = _f(outp.get("u", inp.get("u")))
                    area = _f(d.get("area"))
                    voce.update(
                        tipo="opaca",
                        struttura=inp.get("nome"),
                        tipoStrutturaOpache=inp.get("tipoStrutturaOpache"),
                        versoDispersione=inp.get("versoDispersione"),
                        verso_znc=d.get("rifAmbienteConfinante"),
                        area=area,
                        U=u,
                    )
                    h_tr += u * area
                elif d.get("rifTerreno"):
                    voce.update(tipo="terreno", struttura=f"terreno #{d.get('rifTerreno')}", area=0.0, U=0.0)
                elif d.get("rifSerramenti"):
                    inp, outp = serramenti.get(d.get("rifSerramenti"), ({}, {}))
                    area = _f(outp.get("a_w"))
                    u = _f(outp.get("u_w"))
                    voce.update(
                        tipo="serramento",
                        struttura=inp.get("nome"),
                        area=area,
                        U=u,
                        g_n=_f(outp.get("g_n")),
                    )
                    h_tr += u * area
                voce["ponti"] = []
                for p in d.findall(f"{NS_D}ponteTermico"):
                    pin, pout = ponti.get(p.get("rifPonti"), ({}, {}))
                    lung = _f(p.get("lunghezza"))
                    psi = _f(pout.get("psi_e"))
                    voce["ponti"].append({"nome": pin.get("nome"), "L": lung, "psi_e": psi})
                    h_tr += psi * lung
                zona["dispersioni"].append(voce)
            zona["somma_UxA_psixL_W_K"] = round(h_tr, 2)
            s["zone"].append(zona)
        ris["subalterni"].append(s)

    impianti = edificio.find(f"{NS_D}impianti")
    gen = []
    if impianti is not None:
        for g in impianti.iter():
            tag = re.sub(r"\{.*?\}", "", g.tag)
            if tag.startswith("gruppo") or tag in (
                "generatoreCombustione",
                "pompaFreddo",
                "pompaCalore",
            ):
                gen.append({"elemento": tag, **g.attrib})
    ris["generatori"] = gen

    out = root.find(f"{NS_C}datiOutput")
    if out is not None:
        ris["risultati"] = {
            k: out.get(k)
            for k in (
                "classe",
                "ep_gl_nren",
                "ep_gl_ren",
                "ep_gl_nren_rif_ape",
                "ep_h_nd",
                "ep_c_nd",
                "s_u_h",
                "indicatorePrestazioneInvernale",
                "indicatorePrestazioneEstiva",
            )
        }
    ris["messaggi"] = [
        {**m.attrib, "tag": [t.attrib for t in m]}
        for m in root.iter("{http://www.cened.it/cenedplus2/struttureDati}messaggio")
    ]
    return ris


def stampa(r):
    c = r["clima"]
    print(f"Comune: {c.get('nome')} ({c.get('siglaProvincia')})  zona {c.get('zonaClimatica')}  "
          f"GG {c.get('gg')}  quota {c.get('z')} m")
    print(f"Software: {r['software'].get('nomeSoftware')} v{r['software'].get('versioneMotore')}")
    for s in r["subalterni"]:
        print(f"\nSubalterno {s['subalternoNumero']} (periodo costruzione cod. {s['periodoCostruzione']})")
        for z in s["zone"]:
            g = z["geometria"]
            print(f"  Zona {z['nome']}: Su={g.get('superficieUtile')} m2  V lordo={g.get('volumeLordo')} m3  "
                  f"h={g.get('altezzaMediaNetta')} m")
            for d in z["dispersioni"]:
                ponti = "".join(f"  +ponte {p['nome']} L={p['L']} psi={p['psi_e']}" for p in d["ponti"])
                print(f"    [{d.get('tipo', '?'):10}] {str(d.get('struttura'))[:45]:45} "
                      f"A={d.get('area', 0):7.2f}  U={d.get('U', 0):5.2f}{ponti}")
            print(f"    Somma U*A + psi*L = {z['somma_UxA_psixL_W_K']} W/K")
    print("\nGeneratori:")
    for g in r["generatori"]:
        print("  ", {k: v for k, v in g.items() if k not in ("id",)})
    if "risultati" in r:
        print("\nRisultati:", r["risultati"])
    for m in r["messaggi"]:
        print("Messaggio:", [t.get("key") for t in m["tag"]], m.get("nodo", "")[-60:])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    dati = leggi(sys.argv[1])
    if "--json" in sys.argv:
        print(json.dumps(dati, indent=2, ensure_ascii=False))
    else:
        stampa(dati)
