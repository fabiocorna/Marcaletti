"""Stampe del progetto: computo metrico estimativo, elenco prezzi, quadro economico.

PDF con ReportLab, Excel con openpyxl.
"""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from xml.sax.saxutils import escape

from .model import Progetto, Voce
from .numeri import fmt, fmt_euro, round2

# ---------------------------------------------------------------- numeri in lettere
_UNITA = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci",
          "undici", "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette", "diciotto",
          "diciannove"]
_DECINE = ["", "", "venti", "trenta", "quaranta", "cinquanta", "sessanta", "settanta", "ottanta", "novanta"]


def _sotto_mille(n: int) -> str:
    out = ""
    c, r = divmod(n, 100)
    if c:
        out = ("cento" if c == 1 else _UNITA[c] + "cento")
    if r:
        if r < 20:
            s = _UNITA[r]
        else:
            d, u = divmod(r, 10)
            s = _DECINE[d]
            if u in (1, 8):
                s = s[:-1]          # ventuno, ventotto
            if u:
                s += "tré" if u == 3 else _UNITA[u]
        if c and s.startswith("o"):  # centotto, centottanta
            out = out[:-1] if out.endswith("o") else out
        out += s
    return out


def in_lettere(n: int) -> str:
    """Numero intero in lettere: 1234 → «milleduecentotrentaquattro»."""
    if n == 0:
        return "zero"
    if n < 0:
        return "meno " + in_lettere(-n)
    parts = []
    for value, sing, plur in ((10 ** 9, "unmiliardo", "miliardi"), (10 ** 6, "unmilione", "milioni"),
                              (1000, "mille", "mila")):
        q, n = divmod(n, value)
        if q:
            parts.append(sing if q == 1 else _sotto_mille(q) + plur)
    if n:
        parts.append(_sotto_mille(n))
    return "".join(parts)


def prezzo_in_lettere(value: Decimal) -> str:
    """12,34 → «euro dodici/34»."""
    v = round2(value)
    intero = int(v)
    cent = int((v - intero) * 100)
    return f"euro {in_lettere(intero)}/{cent:02d}"


# ------------------------------------------------------------------------ PDF
def _styles():
    from reportlab.lib.styles import ParagraphStyle
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=7.5, leading=9.2)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=6.8, leading=8.2, textColor="#333333"),
        "bold": ParagraphStyle("bold", parent=base, fontName="Helvetica-Bold"),
        "right": ParagraphStyle("right", parent=base, alignment=2),
        "rbold": ParagraphStyle("rbold", parent=base, alignment=2, fontName="Helvetica-Bold"),
        "cap": ParagraphStyle("cap", parent=base, fontName="Helvetica-Bold", fontSize=8.5, leading=10.5,
                              textColor="#1f3b63"),
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=15, leading=19,
                                alignment=1, spaceAfter=4),
        "sub": ParagraphStyle("sub", parent=base, fontSize=9, leading=12, alignment=1),
    }


def _p(text, style) -> "object":
    from reportlab.platypus import Paragraph
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def _header(p: Progetto, titolo: str, st) -> list:
    from reportlab.lib.units import mm
    from reportlab.platypus import Spacer
    out = [_p(titolo.upper(), st["title"]), _p(p.dati.titolo, st["sub"])]
    info = [f"{lab}: {val}" for lab, val in (("Committente", p.dati.committente), ("Comune", p.dati.comune),
                                             ("Indirizzo", p.dati.indirizzo), ("Progettista", p.dati.progettista),
                                             ("Prezzario", p.dati.prezzario)) if val]
    if info:
        out.append(_p("  ·  ".join(info), st["sub"]))
    out.append(Spacer(1, 5 * mm))
    return out


def _doc(path: str, p: Progetto, titolo: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColorRGB(0.35, 0.35, 0.35)
        canvas.drawString(15 * mm, 9 * mm, f"{titolo} – {p.dati.titolo}"[:110])
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"Pagina {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                            bottomMargin=16 * mm, title=f"{titolo} – {p.dati.titolo}",
                            author=p.dati.progettista or "", creator="CRN Computo")
    return doc, footer


def _misura_cells(m, st):
    vals = []
    for f in ("parti", "lunghezza", "larghezza", "altezza"):
        try:
            from .numeri import evaluate
            v = evaluate(getattr(m, f))
        except ValueError:
            v = None
        vals.append(_p(fmt(v) if v is not None else "", st["right"]))
    q, err = m.quantita_sicura()
    return vals, _p("ERRORE" if err else fmt(q), st["right"])


def export_computo_pdf(p: Progetto, path: str, dettaglio_misure: bool = True) -> None:
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import LongTable, Spacer, TableStyle

    st = _styles()
    doc, footer = _doc(path, p, "Computo metrico estimativo")
    widths = [9 * mm, 20 * mm, 61 * mm, 11 * mm, 12 * mm, 12 * mm, 12 * mm, 15 * mm, 13 * mm, 15 * mm]
    head = [_p(h, st["bold"]) for h in ("N.", "Tariffa", "Designazione dei lavori", "Par.ug.", "Lung.", "Larg.",
                                        "H/peso", "Quantità", "Prezzo", "Importo")]
    rows = [head]
    style = [("GRID", (0, 0), (-1, 0), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6ecf5")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2),
             ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 1),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]

    def cap_row(text):
        rows.append([_p(text, st["cap"])] + [""] * 9)
        r = len(rows) - 1
        style.extend([("SPAN", (0, r), (-1, r)), ("TOPPADDING", (0, r), (-1, r), 5)])

    def tot_row(text, value):
        rows.append([""] * 2 + [_p(text, st["bold"])] + [""] * 6 + [_p(fmt(value), st["rbold"])])
        r = len(rows) - 1
        style.extend([("SPAN", (2, r), (8, r)), ("LINEABOVE", (2, r), (-1, r), 0.5, colors.black)])

    def voce_rows(v: Voce):
        a = p.articoli.get(v.articolo)
        desc = a.descrizione if a else "(articolo mancante)"
        if v.nota:
            desc += "\n" + v.nota
        rows.append([_p(p.numero(v), st["base"]), _p(v.articolo, st["base"]), _p(desc, st["base"])] + [""] * 7)
        r0 = len(rows) - 1
        style.append(("SPAN", (2, r0), (-1, r0)))
        if dettaglio_misure:
            for m in v.misure:
                vals, q = _misura_cells(m, st)
                rows.append(["", "", _p(m.descrizione, st["small"])] + vals + [q, "", ""])
        um = a.um if a else ""
        rows.append(["", "", _p(f"SOMMANO {um}", st["bold"]), "", "", "", "",
                     _p(fmt(v.quantita()), st["rbold"]), _p(fmt(p.prezzo(v)), st["right"]),
                     _p(fmt(p.importo(v)), st["rbold"])])
        style.append(("LINEBELOW", (0, len(rows) - 1), (-1, len(rows) - 1), 0.25, colors.lightgrey))

    ordinate = p.voci_ordinate()
    for v in [v for v in ordinate if v.capitolo is None]:
        voce_rows(v)

    def emit(c, level):
        ids = set(p.discendenti(c.id))
        if not any(v.capitolo in ids for v in p.voci):
            return
        cap_row(("    " * level) + (f"{c.codice} " if c.codice else "") + c.titolo)
        for v in ordinate:
            if v.capitolo == c.id:
                voce_rows(v)
        for child in p.figli(c.id):
            emit(child, level + 1)
        tot_row(f"Totale {c.titolo}", p.totale_capitolo(c.id))

    for c in p.figli(None):
        emit(c, 0)
    rows.append([""] * 10)
    tot_row("TOTALE COMPUTO", p.totale_voci())
    table = LongTable(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle(style))

    story = _header(p, "Computo metrico estimativo", st) + [table]
    if p.capitoli:
        story += [Spacer(1, 6 * mm)] + _riepilogo(p, st)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def _riepilogo(p: Progetto, st) -> list:
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Table, TableStyle
    tot = p.totale_voci()
    rows = [[_p("Riepilogo per capitoli", st["bold"]), _p("Importo", st["rbold"]), _p("Incidenza", st["rbold"])]]
    for c, level in p.capitoli_ordinati():
        imp = p.totale_capitolo(c.id)
        inc = (imp / tot * 100) if tot else Decimal(0)
        sty = st["bold"] if level == 0 else st["base"]
        rows.append([_p(("    " * level) + (f"{c.codice} " if c.codice else "") + c.titolo, sty),
                     _p(fmt(imp), st["right"]), _p(fmt(inc) + " %", st["right"])])
    senza = sum((p.importo(v) for v in p.voci if v.capitolo is None), Decimal(0))
    if senza:
        rows.append([_p("Voci fuori capitolo", st["base"]), _p(fmt(senza), st["right"]),
                     _p(fmt(senza / tot * 100 if tot else 0) + " %", st["right"])])
    rows.append([_p("TOTALE", st["bold"]), _p(fmt(tot), st["rbold"]), _p("100,00 %", st["rbold"])])
    t = Table(rows, colWidths=[120 * mm, 30 * mm, 25 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                           ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.black),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return [t]


def export_elenco_prezzi_pdf(p: Progetto, path: str, solo_usati: bool = True) -> None:
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import LongTable, TableStyle

    st = _styles()
    doc, footer = _doc(path, p, "Elenco prezzi unitari")
    arts = p.articoli_usati() if solo_usati else list(p.articoli.values())
    arts.sort(key=lambda a: a.codice)
    rows = [[_p(h, st["bold"]) for h in ("N.", "Tariffa", "Descrizione", "U.M.", "Prezzo")]]
    for i, a in enumerate(arts, 1):
        desc = a.descrizione + f"\n{prezzo_in_lettere(a.prezzo)}"
        if a.fonte:
            desc += f"  ({a.fonte})"
        rows.append([_p(i, st["base"]), _p(a.codice, st["base"]), _p(desc, st["base"]), _p(a.um, st["base"]),
                     _p(fmt(a.prezzo), st["right"])])
    t = LongTable(rows, colWidths=[9 * mm, 24 * mm, 115 * mm, 12 * mm, 20 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6ecf5")),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    doc.build(_header(p, "Elenco prezzi unitari", st) + [t], onFirstPage=footer, onLaterPages=footer)


def quadro_rows(p: Progetto) -> list[tuple[str, str, Decimal | None, bool]]:
    """Righe del quadro economico: (sigla, descrizione, importo, grassetto)."""
    q = p.quadro_economico()
    rows = [("A", "LAVORI", None, True),
            ("A.1", "Lavori soggetti a ribasso", q["lavori_soggetti_ribasso"], False),
            ("A.2", "Oneri della sicurezza non soggetti a ribasso", q["oneri_sicurezza"], False),
            ("", "Totale lavori (A)", q["totale_lavori"], True)]
    if p.quadro.ribasso_pct:
        rows += [("", f"Ribasso d'asta ({fmt(p.quadro.ribasso_pct)} %)", -q["ribasso"], False),
                 ("", "Importo contrattuale", q["importo_contrattuale"], True)]
    rows.append(("B", "SOMME A DISPOSIZIONE", None, True))
    for i, r in enumerate(q["somme_disposizione"], 1):
        rows.append((f"B.{i}", r["descrizione"], r["importo"], False))
    rows += [("", "Totale somme a disposizione (B)", q["totale_somme"], True),
             ("", "TOTALE GENERALE (A + B)", q["totale_generale"], True)]
    if q["manodopera"]:
        rows.append(("", "di cui costo della manodopera (stima)", q["manodopera"], False))
    return rows


def export_quadro_pdf(p: Progetto, path: str) -> None:
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Table, TableStyle

    st = _styles()
    doc, footer = _doc(path, p, "Quadro economico")
    rows, style = [], [("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i, (sig, desc, imp, bold) in enumerate(quadro_rows(p)):
        s, sr = (st["bold"], st["rbold"]) if bold else (st["base"], st["right"])
        rows.append([_p(sig, s), _p(desc, s), _p(fmt_euro(imp) if imp is not None else "", sr)])
        if desc.startswith("Totale") or desc.startswith("TOTALE"):
            style.append(("LINEABOVE", (1, i), (-1, i), 0.5, colors.black))
    t = Table(rows, colWidths=[14 * mm, 126 * mm, 40 * mm])
    t.setStyle(TableStyle(style))
    doc.build(_header(p, "Quadro economico", st) + [t], onFirstPage=footer, onLaterPages=footer)


# ---------------------------------------------------------------------- Excel
def export_xlsx(p: Progetto, path: str) -> None:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    bold = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="E6ECF5")
    num = '#,##0.00'

    ws = wb.active
    ws.title = "Computo"
    ws.append([p.dati.titolo])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([f"Committente: {p.dati.committente}" if p.dati.committente else ""])
    ws.append([])
    ws.append(["N.", "Tariffa", "Designazione dei lavori", "Par.ug.", "Lung.", "Larg.", "H/peso", "Quantità",
               "U.M.", "Prezzo", "Importo"])
    for c in ws[4]:
        c.font = bold
        c.fill = head_fill
    from .numeri import evaluate

    def write_voce(v: Voce):
        a = p.articoli.get(v.articolo)
        ws.append([p.numero(v), v.articolo, a.descrizione if a else ""])
        ws.cell(ws.max_row, 3).alignment = Alignment(wrap_text=True, vertical="top")
        for m in v.misure:
            vals = []
            for f in ("parti", "lunghezza", "larghezza", "altezza"):
                try:
                    x = evaluate(getattr(m, f))
                except ValueError:
                    x = None
                vals.append(float(x) if x is not None else None)
            q, err = m.quantita_sicura()
            ws.append([None, None, m.descrizione] + vals + ["ERRORE" if err else float(q)])
        ws.append([None, None, "SOMMANO", None, None, None, None, float(v.quantita()), a.um if a else "",
                   float(p.prezzo(v)), float(p.importo(v))])
        for col in (3, 8, 11):
            ws.cell(ws.max_row, col).font = bold

    ordinate = p.voci_ordinate()
    for v in [x for x in ordinate if x.capitolo is None]:
        write_voce(v)

    def emit(c, level):
        ws.append([None, None, ("   " * level) + (f"{c.codice} " if c.codice else "") + c.titolo])
        ws.cell(ws.max_row, 3).font = Font(bold=True, color="1F3B63")
        for v in ordinate:
            if v.capitolo == c.id:
                write_voce(v)
        for child in p.figli(c.id):
            emit(child, level + 1)
        ws.append([None, None, f"Totale {c.titolo}"] + [None] * 7 + [float(p.totale_capitolo(c.id))])
        ws.cell(ws.max_row, 3).font = bold
        ws.cell(ws.max_row, 11).font = bold

    for c in p.figli(None):
        emit(c, 0)
    ws.append([])
    ws.append([None, None, "TOTALE COMPUTO"] + [None] * 7 + [float(p.totale_voci())])
    ws.cell(ws.max_row, 3).font = bold
    ws.cell(ws.max_row, 11).font = bold
    for row in ws.iter_rows(min_row=5):
        for c in row[3:]:
            if isinstance(c.value, float):
                c.number_format = num
    for col, w in zip("ABCDEFGHIJK", (6, 14, 70, 9, 9, 9, 9, 11, 7, 11, 13)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A5"

    ep = wb.create_sheet("Elenco prezzi")
    ep.append(["Tariffa", "Descrizione", "U.M.", "Prezzo", "% Manodopera", "Sicurezza", "Fonte"])
    for c in ep[1]:
        c.font = bold
        c.fill = head_fill
    for a in sorted(p.articoli.values(), key=lambda a: a.codice):
        ep.append([a.codice, a.descrizione, a.um, float(a.prezzo), float(a.manodopera_pct),
                   "sì" if a.sicurezza else "", a.fonte])
        ep.cell(ep.max_row, 4).number_format = num
    for col, w in zip("ABCDEFG", (14, 90, 7, 12, 12, 10, 25)):
        ep.column_dimensions[col].width = w

    qe = wb.create_sheet("Quadro economico")
    for sig, desc, imp, b in quadro_rows(p):
        qe.append([sig, desc, float(imp) if imp is not None else None])
        if b:
            qe.cell(qe.max_row, 2).font = bold
            qe.cell(qe.max_row, 3).font = bold
        qe.cell(qe.max_row, 3).number_format = num
    qe.column_dimensions["B"].width = 60
    qe.column_dimensions["C"].width = 16
    wb.properties.creator = "CRN Computo"
    wb.properties.created = _dt.datetime.now()
    wb.save(path)
