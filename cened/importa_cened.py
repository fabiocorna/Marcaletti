"""Lettura di un calcolo.xml di CENED+2.0 come zona per `bilancio_h` (confronto e calibrazione).

Usa i valori calcolati da CENED per i singoli componenti (U, U_w, g, ψ, U del terreno, ombre),
così il confronto misura solo il bilancio della zona.
"""
import xml.etree.ElementTree as ET

from .bilancio_h import ALFA_COLORE, ClimaH, Componente, ZonaH

D = "{http://www.cened.it/cenedplus2/datiCalcolo}"
C = "{http://www.cened.it/cenedplus2/calcolo}"

# Prospetto D.I: capacità termica areica [kJ/m²K] per (intonaco, isolamento, parete, pavimento) e n. piani
# codici CENED: tipoIntonaco 1 gesso / 2 malta; tipoIsolamento 1 interno / 2 assente o esterno;
# tipoPareteEsterna 1 leggera, 2 media, 3 pesante; tipoRivestimentoPavimento 1 tessile, 2 legno, 3 piastrelle
PROSPETTO_D1 = {
    (1, 1, "*", 1): (75, 75, 85), (1, 1, "*", 2): (85, 95, 105), (1, 1, "*", 3): (95, 105, 115),
    (1, 2, 1, 1): (95, 95, 95), (1, 2, 2, 1): (105, 95, 95), (1, 2, 3, 1): (105, 95, 95),
    (1, 2, 1, 2): (115, 115, 115), (1, 2, 2, 2): (115, 125, 125), (1, 2, 3, 2): (115, 125, 125),
    (1, 2, 1, 3): (115, 125, 135), (1, 2, 2, 3): (125, 135, 135), (1, 2, 3, 3): (125, 135, 135),
    (2, 1, "*", 1): (105, 105, 105), (2, 1, "*", 2): (115, 125, 135), (2, 1, "*", 3): (125, 135, 135),
    (2, 2, 1, 1): (125, 125, 115), (2, 2, 2, 1): (135, 135, 125), (2, 2, 3, 1): (145, 135, 125),
    (2, 2, 1, 2): (145, 145, 145), (2, 2, 2, 2): (155, 155, 155), (2, 2, 3, 2): (165, 165, 165),
    (2, 2, 1, 3): (145, 155, 155), (2, 2, 2, 3): (155, 165, 165), (2, 2, 3, 3): (165, 165, 165),
}


# Prospetto 3.I: F_T per tipo di locale non climatizzato. tipoZnc = numero di riga (dedotto;
# verificato per 2 = "non climatizzato con una parete esterna" = 0,40 su due export reali)
F_T_ZNC = {1: 1.00, 2: 0.40, 3: 0.50, 4: 0.60, 5: 0.80, 6: 0.50, 7: 0.80, 8: 1.00, 9: 0.90, 10: 0.70,
           11: 0.00, 12: 1.00, 13: 0.45, 14: 0.80}


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def leggi_zona(percorso: str):
    """Restituisce (ZonaH, ClimaH, riferimento CENED) per la prima zona del primo subalterno."""
    r = ET.parse(percorso).getroot()
    cert = r.find(f"{C}datiInput/{D}certificazione")
    diz = cert.find(f"{D}dizionario")
    idx = lambda tag: {e.get("id"): e for e in diz.iter(f"{D}{tag}")}  # noqa: E731
    opache, serr, ponti, terreno = idx("opache"), idx("serramenti"), idx("ponti"), idx("terreno")
    irr, ombre = idx("irraggiamento"), idx("ombre")

    clima_out = diz.find(f"{D}servizioDatiClimatici/{D}output")
    mesi = sorted(clima_out.iter(f"{D}datiMensili"), key=lambda x: int(x.get("mese")))
    i0 = next(iter(irr.values())).find(f"{D}input")
    clima = ClimaH(te=[_f(m.get("theta_e")) for m in mesi], hb=[_f(m.get("h_bh")) for m in mesi],
                   hd=[_f(m.get("h_dh")) for m in mesi], pv=[_f(m.get("p_v")) for m in mesi],
                   lat=int(i0.get("phi_gradi")) + int(i0.get("phi_primi")) / 60,
                   zona=clima_out.get("zonaClimatica", "E")[:1])

    zona = cert.find(f".//{D}subalterni/{D}subalterno/{D}zone/{D}zona")
    geo = zona.find(f"{D}geometria")
    su = _f(geo.get("superficieUtile"))
    vn = _f(geo.get("volumeNetto")) or su * _f(geo.get("altezzaMediaNetta"))

    # locali non climatizzati: F_T tabellato (metodo semplificato) oppure, con il metodo analitico,
    # b = (θi − θu)/(θi − θe) dalla temperatura θu calcolata da CENED
    cfg = cert.find(f"{D}configurazioneCalcolo")
    analitico = cfg is not None and cfg.get("metodoAnaliticoZNCTerreno") == "true"
    vi = r.find(f"{C}valoriIntermedi")
    b_znc = {z.get("id"): F_T_ZNC.get(int(z.get("tipoZnc") or 2), 0.4)
             for z in cert.iter(f"{D}zonaNonClimatizzata")}
    for z in (vi.findall(f"{C}zonaNonClimatizzata") if vi is not None and analitico else []):
        tu = [_f(m.get("theta_u_h"), 20.0) for m in z]
        stagione = (0, 1, 2, 3, 9, 10, 11)
        b_znc[z.get("id")] = sum((20 - tu[m]) / (20 - clima.te[m]) for m in stagione) / len(stagione)

    comp = []
    a_vert = 0.0
    for d in zona.iter(f"{D}dispersione"):
        psi_l = sum(_f(ponti[p.get("rifPonti")].find(f"{D}output").get("psi_e")) * _f(p.get("lunghezza"))
                    for p in d.findall(f"{D}ponteTermico") if p.get("rifPonti") in ponti)
        ir = irr.get(d.get("rifIrraggiamento"))
        beta = _f(ir.find(f"{D}input").get("beta"), 90) if ir is not None else 90.0
        gamma = _f(ir.find(f"{D}input").get("gamma")) if ir is not None else 0.0
        om = ombre.get(d.get("rifOmbre"))
        f_s = f_s_d = None
        if om is not None and om.find(f"{D}output") is not None:
            o = om.find(f"{D}output")
            f_s = [_f(m.get("f_s"), 1.0) for m in sorted(o, key=lambda x: int(x.get("mese")))] or None
            f_s_d = _f(o.get("f_s_d"), 1.0)
        b = b_znc.get(d.get("rifAmbienteConfinante"), 1.0) if d.get("rifAmbienteConfinante") else 1.0
        if d.get("rifSerramenti"):
            s = serr[d.get("rifSerramenti")]
            o, i = s.find(f"{D}output"), s.find(f"{D}input")
            area = _f(o.get("a_w"))
            comp.append(Componente(d.get("nome") or "serramento", area, _f(o.get("u_w")), b, ir is not None,
                                   True, beta, gamma, g_n=_f(o.get("g_n")), frazione_telaio=_f(o.get("f_f"), 0.2),
                                   f_s=f_s, f_s_d=f_s_d or 1.0, psi_l=psi_l,
                                   g_sh_b=_f(o.get("g_n_sh_b")) if o.get("g_n_sh_b") else None,
                                   g_sh_d=_f(o.get("g_n_sh_d")) if o.get("g_n_sh_d") else None))
        elif d.get("rifTerreno"):
            t = terreno[d.get("rifTerreno")]
            comp.append(Componente("terreno", _f(d.get("area")), _f(t.find(f"{D}output").get("u_b")), 1.0,
                                   psi_l=psi_l))
            continue
        else:
            op = opache[d.get("rifOpache")]
            i, o = op.find(f"{D}input"), op.find(f"{D}output")
            verso = i.get("versoDispersione")
            if verso in ("5", "6"):  # verso altre zone climatizzate / interne
                b = 0.0
            area = _f(d.get("area"))
            comp.append(Componente(i.get("nome") or "opaca", area, _f(o.get("u")), b,
                                   verso == "1" and ir is not None, False, beta, gamma,
                                   alfa=ALFA_COLORE.get(int(d.get("colorazione") or i.get("coloreEsterno") or 2), 0.6),
                                   f_s=f_s, f_s_d=f_s_d or 1.0, psi_l=psi_l))
        if beta > 45 and b > 0:
            a_vert += comp[-1].area

    # capacità termica
    ct = zona.find(f"{D}capacitaTermica")
    if ct is not None and cfg.get("metodoCapacitaTermicaPuntuale") != "true":
        k = (int(ct.get("tipoIntonaco")), int(ct.get("tipoIsolamento")), int(ct.get("tipoPareteEsterna")),
             int(ct.get("tipoRivestimentoPavimento")))
        valori = PROSPETTO_D1.get(k) or PROSPETTO_D1.get((k[0], k[1], "*", k[3]))
        piani = 1
        c_m = valori[0]
        capacita = c_m * (a_vert + 2 * su * piani)
    else:
        capacita = sum(_f(opache[d.get("rifOpache")].find(f"{D}output").get("k_i")) * _f(d.get("area"))
                       for d in zona.iter(f"{D}dispersione") if d.get("rifOpache"))

    rif = {}
    zr = r.find(f"{C}valoriIntermedi/{C}risultati/{C}subalterno/{C}zona")
    if zr is not None:
        rm = sorted((m for m in zr if m.tag.endswith("risultatiMensili")), key=lambda x: int(x.get("mese")))
        rif = {"h_t": [_f(m.get("h_t")) for m in rm], "q_nh": [_f(m.get("q_n_h_fraz")) for m in rm],
               "giorni": [_f(m.get("delta_t_h")) * 1000 / 24 for m in rm],
               "gamma": [_f(m.get("gamma_h_adj")) for m in rm], "eta": [_f(m.get("eta_g_h_adj")) for m in rm],
               "a_c": [_f(m.get("a_c")) for m in rm]}
    out = r.find(f"{C}datiOutput")
    if out is not None:
        rif["ep_h_nd"] = _f(out.get("ep_h_nd"))
    return ZonaH(superficie_utile=su, volume_netto=vn, capacita=capacita, componenti=comp), clima, rif
