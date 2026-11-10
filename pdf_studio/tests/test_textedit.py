import os

import pymupdf
import pytest

from pdfstudio import textedit as T
from pdfstudio.document import PdfDocument

FONT_DIR = "/usr/share/fonts/truetype/liberation"
SERIF = os.path.join(FONT_DIR, "LiberationSerif-Regular.ttf")


def word_like_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page()
    if os.path.exists(SERIF):
        arch = pymupdf.Archive(FONT_DIR)
        css = ("@font-face {font-family: L; src: url(LiberationSerif-Regular.ttf);} "
               "* {font-family: L; font-size: 11px; line-height: 1.4} div {text-align: justify}")
    else:
        arch, css = None, "* {font-size: 11px; line-height: 1.4} div {text-align: justify}"
    html = ("<div>Il sottoscritto tecnico, iscritto all'albo degli ingegneri della provincia di Milano, dichiara "
            "che l'edificio sito in via Roma 12 rispetta i requisiti minimi di prestazione energetica previsti "
            "dalla normativa vigente, come risulta dai calcoli allegati alla presente relazione.</div>"
            "<div style='margin-top:20px'>Seconda sezione: valori di trasmittanza conformi.</div>")
    page.insert_htmlbox(pymupdf.Rect(72, 72, 523, 400), html, css=css, archive=arch)
    doc.subset_fonts()
    doc.save(path)
    return path


def origins(doc):
    return [(round(l["spans"][0]["origin"][0], 1), round(l["spans"][0]["origin"][1], 1))
            for b in doc[0].get_text("dict")["blocks"] for l in b.get("lines", [])]


@pytest.fixture
def word_pdf(tmp_path):
    return word_like_pdf(str(tmp_path / "word.pdf"))


def first_block(d):
    r = d.page(0).search_for("sottoscritto")[0]
    return d.block_at(0, pymupdf.Point(r.x0 + 2, (r.y0 + r.y1) / 2))


def test_normalize_font_name():
    assert T.normalize_font_name("ABCDEF+Arial-BoldMT") == "arialbold"
    assert T.normalize_font_name("TimesNewRomanPSMT") == "timesnewroman"
    assert T.normalize_font_name("Calibri,Bold") == "calibribold"


def test_block_detection(word_pdf):
    d = PdfDocument.open(word_pdf)
    b = first_block(d)
    assert b is not None and len(b.lines) >= 3
    assert b.text.startswith("Il sottoscritto") and b.text.endswith("relazione.")
    assert b.align == "justify" and abs(b.line_height - 1.4) < 0.1


def test_identity_edit_keeps_position(word_pdf):
    d = PdfDocument.open(word_pdf)
    before = origins(d.doc)
    b = first_block(d)
    d.replace_block(b, b.text)
    assert sorted(origins(d.doc)) == pytest.approx(sorted(before), abs=0.6)


def test_paragraph_rewrite_reflows(word_pdf):
    d = PdfDocument.open(word_pdf)
    b = first_block(d)
    new = b.text.replace("via Roma 12", "via Giuseppe Garibaldi 145, Milano")
    info = d.replace_block(b, new)
    text = " ".join(d.page(0).get_text().split())
    assert "via Giuseppe Garibaldi 145, Milano rispetta" in text
    assert "Roma 12" not in text and "Seconda sezione" in text
    assert info["source"] in ("incorporato", "sistema", "standard")
    # Nessun font non incorporato aggiunto
    assert all(f[1] != "n/a" for f in d.page(0).get_fonts(full=True))
    d.undo()
    assert "Roma 12" in d.page(0).get_text()


def test_find_replace(word_pdf):
    d = PdfDocument.open(word_pdf)
    assert d.find_replace("Roma 12", "Verdi 7") == 1
    assert "Verdi 7" in d.page(0).get_text() and "Roma 12" not in d.page(0).get_text()
    assert d.find_replace("inesistente", "x") == 0


def test_line_edit_uses_original_font(word_pdf):
    d = PdfDocument.open(word_pdf)
    r = d.page(0).search_for("Seconda")[0]
    span = d.span_at(0, pymupdf.Point(r.x0 + 1, (r.y0 + r.y1) / 2))
    source = d.replace_span(span, "Sezione due: valori conformi.")
    assert source in ("incorporato", "sistema", "standard")
    assert "Sezione due" in d.page(0).get_text()


@pytest.mark.skipif(not os.path.exists(SERIF), reason="font Liberation non installati")
def test_system_font_found():
    choice = T.FontResolver(pymupdf.open()).choose(pymupdf.open().new_page(), "LiberationSerif", 0, "àèìòù €")
    assert choice.source == "sistema"


# ---------------------------------------------- formattazione mista (PDF da Word/LibreOffice)
def mixed_pdf(path):
    """Ogni riga è un pezzo separato (come nei PDF di Word) con grassetto, corsivo e colore."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 100
    lines = [
        [("Il sottoscritto ", "helv", (0, 0, 0)), ("Ing. Mario Rossi", "hebo", (0, 0, 0)),
         (", iscritto all'albo di ", "helv", (0, 0, 0)), ("Milano", "heit", (0, 0, 0))],
        [("dichiara che l'edificio sito in via Roma 12 rispetta i ", "helv", (0, 0, 0)),
         ("requisiti minimi", "helv", (0.75, 0, 0))],
        [("previsti dalla normativa vigente.", "helv", (0, 0, 0))],
    ]
    for parts in lines:
        x = 72
        for text, font, color in parts:
            page.insert_text((x, y), text, fontname=font, fontsize=11, color=color)
            x += pymupdf.get_text_length(text, font, 11)
        y += 14
    page.insert_text((72, y + 20), "Paragrafo successivo separato.", fontsize=11)
    doc.save(path)
    return path


def spans_of(doc, word):
    for b in doc[0].get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                if word in s["text"]:
                    return s
    return None


def test_paragraph_spans_separate_lines(tmp_path):
    d = PdfDocument.open(mixed_pdf(str(tmp_path / "m.pdf")))
    r = d.page(0).search_for("sottoscritto")[0]
    b = d.block_at(0, pymupdf.Point(r.x0 + 1, (r.y0 + r.y1) / 2))
    assert len(b.lines) == 3                      # le tre righe, non solo la prima
    assert b.text.endswith("normativa vigente.") and "successivo" not in b.text
    assert len(b.styles) == 4                     # normale, grassetto, corsivo, rosso


def test_edit_keeps_bold_italic_and_color(tmp_path):
    d = PdfDocument.open(mixed_pdf(str(tmp_path / "m.pdf")))
    r = d.page(0).search_for("sottoscritto")[0]
    b = d.block_at(0, pymupdf.Point(r.x0 + 1, (r.y0 + r.y1) / 2))
    d.replace_block(b, b.text.replace("Mario Rossi", "Mario Rossi Junior").replace("Roma 12", "Verdi 7"))
    bold = spans_of(d.doc, "Junior")
    assert bold is not None and bold["flags"] & 16 or "Bold" in bold["font"]
    assert "Italic" in spans_of(d.doc, "Milano")["font"] or spans_of(d.doc, "Milano")["flags"] & 2
    red = spans_of(d.doc, "requisiti")
    assert (red["color"] >> 16) & 255 > 150      # ancora rosso
    assert "Verdi 7" in d.page(0).get_text() and "Paragrafo successivo" in d.page(0).get_text()


def test_map_styles_inherits_neighbour_style(tmp_path):
    d = PdfDocument.open(mixed_pdf(str(tmp_path / "m.pdf")))
    r = d.page(0).search_for("sottoscritto")[0]
    b = d.block_at(0, pymupdf.Point(r.x0 + 1, (r.y0 + r.y1) / 2))
    bold_id = next(i for i, s in enumerate(b.styles) if "Bold" in s.font or s.flags & 16)
    runs = T.map_styles(b, b.text.replace("Rossi", "Rossi Junior"))
    assert any("Junior" in t and sid == bold_id for t, sid in runs)


def test_fallback_family_from_name():
    from pdfstudio.document import guess_base14
    assert guess_base14("Calibri", 4) == "helv"          # flag «serif» errato nei PDF di Word
    assert guess_base14("Calibri-Bold", 4) == "hebo"
    assert guess_base14("TimesNewRomanPSMT", 0) == "tiro"


@pytest.mark.skipif(not any(os.path.exists(p) for p in ("/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",)),
                    reason="font con legature non disponibile")
def test_edited_text_stays_searchable():
    path = "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf"
    buf = T.without_ligatures(open(path, "rb").read())
    doc = pymupdf.open()
    page = doc.new_page()
    arch = pymupdf.Archive()
    arch.add(buf, "f.ttf")
    page.insert_htmlbox(pymupdf.Rect(50, 50, 500, 200), "<div>Il sottoscritto, requisiti, l'edificio</div>",
                        css="@font-face {font-family: F; src: url(f.ttf);} div {font-family: F;}", archive=arch)
    assert page.search_for("sottoscritto") and page.search_for("requisiti")
