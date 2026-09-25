"""Riga di comando.

    python -m cened rapido   dati.toml -o progetto.toml [--scheda s.md] [--modello calcolo.xml --xml out.xml]
    python -m cened calcola  progetto.toml               # U, pre-calcolo, riepilogo
    python -m cened scheda   progetto.toml [-o out.md]   # scheda di compilazione CENED+2.0
    python -m cened xml      progetto.toml --modello calcolo.xml -o import.xml
    python -m cened leggi    calcolo.xml [--json]        # analisi di un export CENED
"""
import argparse
import sys

from . import leggi_export
from .bilancio import calcola
from .esporta_xml import ErroreModello, genera_xml
from .progetto import carica
from .scheda import genera_scheda


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cened", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("calcola"); p.add_argument("progetto")
    p = sub.add_parser("scheda"); p.add_argument("progetto"); p.add_argument("-o", "--output")
    p = sub.add_parser("xml"); p.add_argument("progetto")
    p.add_argument("--modello", required=True, help="calcolo.xml esportato da CENED+2.0")
    p.add_argument("-o", "--output", required=True)
    p = sub.add_parser("rapido"); p.add_argument("dati"); p.add_argument("-o", "--output", required=True)
    p.add_argument("--scheda"); p.add_argument("--modello"); p.add_argument("--xml")
    p = sub.add_parser("leggi"); p.add_argument("export"); p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "leggi":
        dati = leggi_export.leggi(a.export)
        if a.json:
            import json
            print(json.dumps(dati, indent=2, ensure_ascii=False))
        else:
            leggi_export.stampa(dati)
        return 0

    if a.cmd == "rapido":
        return _rapido(a)

    try:
        prog = carica(a.progetto)
    except (ValueError, KeyError) as e:
        print(f"Errore nel progetto: {e}", file=sys.stderr)
        return 2
    ris = calcola(prog)

    if a.cmd == "calcola":
        z = prog.zona
        for s in prog.strutture.values():
            print(f"  {s.id:12} U = {s.u:6.3f} W/m2K   {s.nome}")
        for s in prog.serramenti.values():
            print(f"  {s.id:12} Uw= {s.u_w:6.3f} W/m2K   {s.nome}")
        print(f"H_tr = {ris.h_tr:.1f} W/K   H_ve = {ris.h_ve:.1f} W/K   H'_T = {ris.h_t_medio:.3f} W/m2K")
        print(f"Q_H,nd = {ris.q_h_nd:.0f} kWh/anno   EP_H,nd = {ris.ep_h_nd(z.superficie_utile):.1f} kWh/m2anno")
        if prog.ipotesi:
            print(f"({len(set(prog.ipotesi))} ipotesi/default applicati: vedere la scheda)")
    elif a.cmd == "scheda":
        testo = genera_scheda(prog, ris)
        if a.output:
            with open(a.output, "w", encoding="utf-8") as f:
                f.write(testo)
            print(f"Scheda scritta in {a.output}")
        else:
            print(testo)
    elif a.cmd == "xml":
        try:
            _, avvisi = genera_xml(prog, a.modello, a.output)
        except ErroreModello as e:
            print(f"Modello non utilizzabile: {e}", file=sys.stderr)
            return 2
        print(f"XML scritto in {a.output} — da importare con CENED+2.0 > File > Importa file XML")
        for av in avvisi:
            print("  avviso:", av)
    return 0


def _rapido(a):
    import tomllib
    from .progetto import da_dizionario
    from .rapido import a_toml, genera_progetto
    with open(a.dati, "rb") as f:
        dati = tomllib.load(f)
    try:
        progetto = genera_progetto(dati)
        prog = da_dizionario(progetto)
    except (ValueError, KeyError) as e:
        print(f"Errore nei dati: {e}", file=sys.stderr)
        return 2
    with open(a.output, "w", encoding="utf-8") as f:
        f.write(a_toml(progetto))
    ris = calcola(prog)
    z = prog.zona
    print(f"Progetto completo scritto in {a.output} ({len(z.dispersioni)} dispersioni, "
          f"{len(set(prog.ipotesi))} ipotesi da verificare)")
    print(f"Pre-calcolo: EP_H,nd = {ris.ep_h_nd(z.superficie_utile):.1f} kWh/m2anno   "
          f"H'_T = {ris.h_t_medio:.3f} W/m2K")
    if a.scheda:
        with open(a.scheda, "w", encoding="utf-8") as f:
            f.write(genera_scheda(prog, ris))
        print(f"Scheda scritta in {a.scheda}")
    if a.modello and a.xml:
        try:
            _, avvisi = genera_xml(prog, a.modello, a.xml)
        except ErroreModello as e:
            print(f"Modello non utilizzabile: {e}", file=sys.stderr)
            return 2
        print(f"XML per CENED+2.0 scritto in {a.xml}")
        for av in avvisi:
            print("  avviso:", av)
    return 0


if __name__ == "__main__":
    sys.exit(main())
