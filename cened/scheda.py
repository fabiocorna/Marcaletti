"""Scheda di compilazione assistita (Markdown): tutti i valori calcolati, nell'ordine in
cui vanno inseriti in CENED+2.0, più il registro delle ipotesi e il pre-calcolo."""
from .bilancio import Risultati
from .modello import Progetto


def _r(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def genera_scheda(prog: Progetto, ris: Risultati) -> str:
    z, c = prog.zona, prog.clima
    L = [f"# Scheda di compilazione CENED+2.0 — {prog.nome}", ""]
    L += ["> Documento di lavoro: i valori ufficiali dell'APE sono quelli calcolati da CENED+2.0.", ""]

    L += ["## 1. Localizzazione e clima", "",
          f"- Comune: **{c.comune}** ({c.provincia or '-'}) — zona climatica **{c.zona_climatica}**"
          f" — GG di legge: {c.gg or '-'}",
          f"- GG ricalcolati sui dati mensili usati nel pre-calcolo: {_r(c.gradi_giorno(), 0)}", ""]
    if c.gg and abs(c.gradi_giorno() - c.gg) / c.gg > 0.10:
        L += ["> ⚠ I GG ricalcolati differiscono di oltre il 10% da quelli di legge: "
              "verificare le temperature mensili.", ""]

    L += ["## 2. Zona termica", "",
          "| Dato | Valore |", "|---|---|",
          f"| Destinazione d'uso | {z.destinazione} |",
          f"| Superficie utile | {_r(z.superficie_utile)} m² |",
          f"| Volume lordo | {_r(z.volume_lordo)} m³ |",
          f"| Volume netto | {_r(z.v_netto)} m³ |",
          f"| Altezza media netta | {_r(z.altezza_netta)} m |", ""]

    L += ["## 3. Strutture opache (libreria)", "",
          "| Codice | Nome | Tipo | Verso | Spessore [m] | U [W/m²K] | k_i [kJ/m²K] | Massa [kg/m²] |",
          "|---|---|---|---|---|---|---|---|"]
    for s in prog.strutture.values():
        L.append(f"| {s.id} | {s.nome} | {s.tipo} | {s.verso} | {_r(s.spessore, 3)} | "
                 f"{_r(s.u, 3)} | {_r(s.k_i, 1)} | {_r(s.massa_superficiale, 0)} |")
    L.append("")
    for s in prog.strutture.values():
        if not s.strati:
            continue
        L += [f"**{s.id} — {s.nome}** (dall'interno; R_si={s.rsi}, R_se={s.rse})", "",
              "| Strato | s [m] | λ [W/mK] | R [m²K/W] |", "|---|---|---|---|"]
        for st in s.strati:
            lam = "-" if st.intercapedine or st.materiale.lambda_ is None else _r(st.materiale.lambda_, 3)
            L.append(f"| {st.materiale.nome} | {_r(st.spessore, 3)} | {lam} | "
                     f"{_r(st.resistenza(s.flusso), 3)} |")
        L += [f"| **Totale** | {_r(s.spessore, 3)} | | {_r(s.r_totale, 3)} |", ""]

    L += ["## 4. Serramenti", "",
          "| Codice | Nome | L×H [m] | A_w [m²] | U_g | U_f | g_n | f. telaio | U_w [W/m²K] |",
          "|---|---|---|---|---|---|---|---|---|"]
    for s in prog.serramenti.values():
        L.append(f"| {s.id} | {s.nome} | {_r(s.larghezza)}×{_r(s.altezza)} | {_r(s.a_w)} | "
                 f"{_r(s.u_g)} | {_r(s.u_f)} | {_r(s.g_n)} | {_r(s.frazione_telaio)} | {_r(s.u_w, 3)} |")
    L.append("")

    if prog.ponti:
        L += ["## 5. Ponti termici", "", "| Codice | Nome | ψ_e [W/mK] |", "|---|---|---|"]
        L += [f"| {p.id} | {p.nome} | {_r(p.psi, 3)} |" for p in prog.ponti.values()]
        L.append("")

    if prog.znc:
        L += ["## 6. Zone non climatizzate", "", "| Codice | Nome | b_tr |", "|---|---|---|"]
        L += [f"| {q.id} | {q.nome} | {_r(q.b_tr)} |" for q in prog.znc.values()]
        L.append("")

    L += ["## 7. Dispersioni della zona", "",
          "| # | Nome | Elemento | Verso | Esposiz. | Area [m²] | Ponti (ψ × L) |",
          "|---|---|---|---|---|---|---|"]
    for n, d in enumerate(z.dispersioni, 1):
        verso = f"ZNC {d.znc.id}" if d.znc else d.verso
        el = d.elemento.id + (f" ×{d.quantita}" if d.is_serramento and d.quantita > 1 else "")
        pt = ", ".join(f"{p.ponte.id} × {_r(p.lunghezza)} m" for p in d.ponti) or "-"
        L.append(f"| {n} | {d.nome} | {el} | {verso} | {d.esposizione or '-'} | {_r(d.area)} | {pt} |")
    L.append("")

    L += ["## 8. Pre-calcolo UNI/TS 11300-1 (controllo)", "",
          f"- H_tr = {_r(ris.h_tr)} W/K — H_ve = {_r(ris.h_ve)} W/K",
          f"- H'_T = {_r(ris.h_t_medio, 3)} W/m²K su {_r(ris.superficie_disperdente)} m² disperdenti",
          f"- Capacità termica interna C_m = {_r(ris.c_m, 0)} kJ/K — τ = {_r(ris.tau, 1)} h",
          f"- Apporti interni Φ_int = {_r(ris.phi_int, 0)} W",
          f"- **Q_H,nd = {_r(ris.q_h_nd, 0)} kWh/anno — EP_H,nd = "
          f"{_r(ris.ep_h_nd(z.superficie_utile), 1)} kWh/m²anno**", "",
          "| Mese | giorni | θe | Q_tr | Q_ve | Q_sol | Q_int | η | Q_H,nd |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m in ris.mesi:
        if m.giorni:
            L.append(f"| {m.mese} | {m.giorni:g} | {_r(m.te, 1)} | {_r(m.q_tr, 0)} | {_r(m.q_ve, 0)} | "
                     f"{_r(m.q_sol, 0)} | {_r(m.q_int, 0)} | {_r(m.eta, 3)} | {_r(m.q_h_nd, 0)} |")
    L.append("")

    L += ["## 9. Registro ipotesi e valori di default", ""]
    L += [f"- {i}" for i in dict.fromkeys(prog.ipotesi)] or ["- nessuna"]
    L.append("")
    return "\n".join(L)
