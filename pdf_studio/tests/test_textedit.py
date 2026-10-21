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
