#!/usr/bin/env python3
"""Converte un progetto ARCHLine.XP (.pro) in file aperti per CRN-BIM.

Scrive in una cartella:

    progetto.json     info, layer, disegni, materiali (dall'indice del .pro)
    <disegno>.dxf     un DXF R12 per ogni disegno 2D, con i layer di ArchLine
    anteprima.bmp     miniatura salvata da ArchLine (se c'e')

Il DXF si importa in CRN-BIM con Importa DWG; i muri si generano dai layer
"Mur*" come per qualunque DWG. Il .pro viene solo letto.

Formati: archline/analisi/02-formato-pro.md e 03-formato-asc.md.
Solo libreria standard. Uso:

    python converti_pro.py progetto.pro                 cartella <progetto>_crnbim accanto al .pro
    python converti_pro.py progetto.pro -o cartella
    python converti_pro.py progetto.pro --solo-principale
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leggi_asc import layers_da_pro, leggi_disegno, scrivi_dxf  # noqa: E402
from leggi_pro import ProFile  # noqa: E402


def _nome_file(nome: str, usati: set[str]) -> str:
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome).strip(" .") or "disegno"
    n, k = base, 2
    while n.lower() in usati:
        n, k = f"{base}~{k}", k + 1
    usati.add(n.lower())
    return n


def converti(pro: Path, uscita: Path, solo_principale: bool = False) -> dict:
    uscita.mkdir(parents=True, exist_ok=True)
    with ProFile(pro) as p:
        layers = layers_da_pro(p)
        fid = (p.indice().findtext("FileIDOfMain2DWindow") or "").strip()
        disegni = [d for d in p.disegni() if d.get("tipo") == "2D"]
        disegni.sort(key=lambda d: str(d.get("file_id")) != fid)  # pianta principale per prima
        if solo_principale:
            disegni = disegni[:1]

        usati: set[str] = set()
        risultati = []
        for d in disegni:
            voci = p.cerca(d.get("Path", ""))
            r = {
                "nome": d.get("Pseudo_file_name") or d.get("Path"),
                "asc": d.get("Path"),
                "principale": str(d.get("file_id")) == fid,
            }
            risultati.append(r)
            if not voci:
                r["errore"] = "disegno non trovato nell'archivio"
                continue
            try:
                dis = leggi_disegno(p.leggi(voci[0]), d["Path"])
            except (ValueError, IndexError) as e:
                r["errore"] = f"lettura non riuscita: {e}"
                continue
            r["versione"] = dis.versione
            r["entita"] = dict(Counter(e.nome_tipo for e in dis.entita))
            if not dis.entita:
                continue
            nome = _nome_file(str(r["nome"]).rsplit(".", 1)[0] if str(r["nome"]).lower().endswith(".asc")
                              else str(r["nome"]), usati) + ".dxf"
            fatti = scrivi_dxf(dis.entita, uscita / nome, layers)
            r["dxf"] = nome
            r["convertite"] = dict(fatti)
            r["layer_usati"] = sorted({layers[e.layer].nome if e.layer in layers else f"AL_{e.layer}"
                                       for e in dis.entita})

        bmp = p.anteprima()
        if bmp:
            (uscita / "anteprima.bmp").write_bytes(bmp)

        dati = {
            "sorgente": str(pro),
            "info": p.info(),
            "layers": p.layers(),
            "gruppi_layer": p.gruppi_layer(),
            "materiali": p.materiali(),
            "disegni": risultati,
            "note": "Convertiti: linee, polilinee, archi, cerchi, ellissi, testi. "
                    "Non ancora: quote, retini, blocchi, viste 3D.",
        }
    (uscita / "progetto.json").write_text(json.dumps(dati, ensure_ascii=False, indent=2, default=str),
                                          encoding="utf-8")
    return dati


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Converte un .pro di ARCHLine.XP in DXF + JSON per CRN-BIM.")
    ap.add_argument("file", type=Path, help="progetto .pro")
    ap.add_argument("-o", "--uscita", type=Path, help="cartella di uscita (default: <nome>_crnbim)")
    ap.add_argument("--solo-principale", action="store_true", help="solo la pianta principale")
    a = ap.parse_args(argv)
    uscita = a.uscita or a.file.with_name(a.file.stem + "_crnbim")
    try:
        dati = converti(a.file, uscita, a.solo_principale)
    except Exception as e:  # .pro di formato vecchio (non ZIP) o danneggiato
        print(f"{a.file}: {e}", file=sys.stderr)
        return 1
    for r in dati["disegni"]:
        stato = r.get("errore") or (f"{r['dxf']}: {sum(r['convertite'].values())} entita'" if "dxf" in r
                                    else "vuoto")
        print(f"{'*' if r['principale'] else ' '} {r['nome']}: {stato}")
    print(f"scritto in {uscita}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
