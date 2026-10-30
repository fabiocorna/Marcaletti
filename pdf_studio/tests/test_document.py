import os

import pymupdf
import pytest

from pdfstudio.document import PdfDocument, merge_files, parse_page_ranges


def make_pdf(path, pages=3, text="Pagina"):
    doc = pymupdf.open()
    for i in range(pages):
        p = doc.new_page()
        p.insert_text((72, 100), f"{text} {i + 1} prova di testo", fontsize=14)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def sample(tmp_path):
    return make_pdf(str(tmp_path / "sample.pdf"))


def page_texts(doc):
    return [doc.page(i).get_text().strip() for i in range(doc.page_count)]


def test_open_save_roundtrip(sample, tmp_path):
    d = PdfDocument.open(sample)
    assert d.page_count == 3
    d.add_note(0, pymupdf.Point(50, 50), "ciao")
    d.save()  # sovrascrive il file aperto
    assert not d.modified
    again = pymupdf.open(sample)
    assert len(list(again[0].annots())) == 1


def test_undo_redo(sample):
    d = PdfDocument.open(sample)
    d.delete_pages([1])
    assert d.page_count == 2
    assert d.undo()
    assert d.page_count == 3
    assert d.redo()
    assert d.page_count == 2


def test_page_operations(sample):
    d = PdfDocument.open(sample)
    d.move_page(0, 2)
    assert page_texts(d)[2].startswith("Pagina 1")
    d.move_page(2, 0)
    assert page_texts(d)[0].startswith("Pagina 1")
    d.reorder([2, 1, 0])
    assert page_texts(d)[0].startswith("Pagina 3")
    d.rotate_pages([0], 90)
    assert d.page(0).rotation == 90
    d.insert_blank_page(1)
    assert d.page_count == 4 and page_texts(d)[1] == ""
    d.duplicate_page(0)
    assert d.page_count == 5
    with pytest.raises(ValueError):
        d.delete_pages(range(5))


def test_insert_merge_extract_split(sample, tmp_path):
    other = make_pdf(str(tmp_path / "other.pdf"), 2, "Altro")
    d = PdfDocument.open(sample)
    assert d.insert_file(other, 1) == 2
    assert page_texts(d)[1].startswith("Altro 1")
    out = str(tmp_path / "ext.pdf")
    d.extract_pages([0, 4], out)
    assert pymupdf.open(out).page_count == 2
    paths = d.split([(0, 1), (2, 4)], str(tmp_path), "parte")
    assert [pymupdf.open(p).page_count for p in paths] == [2, 3]
    merged = str(tmp_path / "merged.pdf")
    assert merge_files([sample, other], merged) == 5


def test_images_to_pdf(tmp_path):
    pix = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 100, 50), False)
    pix.clear_with(128)
    img = str(tmp_path / "a.png")
    pix.save(img)
    d = PdfDocument.from_images([img, img])
    assert d.page_count == 2
    assert PdfDocument.open(img).page_count == 1


def test_markup_and_annotations(sample):
    d = PdfDocument.open(sample)
    page = d.page(0)
    word = page.search_for("prova")[0]
    assert d.add_text_markup(0, word, "highlight")
    assert not d.add_text_markup(0, pymupdf.Rect(400, 700, 450, 750), "highlight")
    d.add_shape(0, "rect", pymupdf.Rect(100, 200, 200, 300))
    d.add_shape(0, "arrow", None, start=pymupdf.Point(100, 400), end=pymupdf.Point(200, 450))
    d.add_ink(0, [[(10, 10), (50, 50), (90, 20)]])
    d.add_text_box(0, pymupdf.Rect(100, 500, 300, 540), "Commento", flatten=False)
    kinds = sorted(a.type[1] for a in d.page(0).annots())
    assert kinds == ["FreeText", "Highlight", "Ink", "Line", "Square"]
    assert d.delete_annotation_at(0, pymupdf.Point(150, 250))
    assert len(list(d.page(0).annots())) == 4
    d.flatten_annotations()
    assert len(list(d.page(0).annots())) == 0


def test_text_insert_and_edit(sample):
    d = PdfDocument.open(sample)
    d.add_text_box(1, pymupdf.Rect(72, 300, 400, 340), "Testo aggiunto", fontsize=12)
    assert "Testo aggiunto" in d.page(1).get_text()
    r = d.page(0).search_for("prova")[0]
    span = d.span_at(0, pymupdf.Point(r.x0 + 2, (r.y0 + r.y1) / 2))
    assert span is not None and "prova" in span.text
    d.replace_span(span, "Pagina 1 testo modificato")
    text = d.page(0).get_text()
    assert "modificato" in text and "prova" not in text


def test_whiteout_redact(sample):
    d = PdfDocument.open(sample)
    r = d.page(0).search_for("prova")[0]
    d.redact(0, r)
    assert "prova" not in d.page(0).get_text()
    d.whiteout(1, pymupdf.Rect(0, 0, 100, 100))


def test_search_watermark_numbers_metadata(sample):
    d = PdfDocument.open(sample)
    res = d.search("prova")
    assert [p for p, _ in res] == [0, 1, 2]
    d.add_watermark("BOZZA")
    d.add_page_numbers()
    assert "Pagina 2 di 3" in d.page(1).get_text()
    d.set_metadata({"title": "Titolo di prova", "author": "Io"})
    assert d.get_metadata()["author"] == "Io"


def test_encryption(sample, tmp_path):
    d = PdfDocument.open(sample)
    d.encryption = ("owner", "segreta")
    out = str(tmp_path / "enc.pdf")
    d.save(out)
    e = PdfDocument.open(out)
    assert e.needs_password
    assert not e.authenticate("sbagliata")
    assert e.authenticate("segreta")
    assert e.page_count == 3
    e.encryption = None
    e.save()
    assert not PdfDocument.open(out).needs_password


def test_compress_and_export(sample, tmp_path):
    d = PdfDocument.open(sample)
    out = str(tmp_path / "small.pdf")
    before, after = d.save_compressed(out)
    assert os.path.exists(out) and after > 0
    imgs = d.export_images(str(tmp_path), dpi=50)
    assert len(imgs) == 3 and all(os.path.exists(p) for p in imgs)
    txt = str(tmp_path / "t.txt")
    d.export_text(txt)
    assert "Pagina 3" in open(txt, encoding="utf-8").read()


def test_forms(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w.field_name = "nome"
    w.rect = pymupdf.Rect(100, 100, 300, 130)
    page.add_widget(w)
    path = str(tmp_path / "form.pdf")
    doc.save(path)
    d = PdfDocument.open(path)
    assert d.has_forms()
    widget = d.widget_at(0, pymupdf.Point(150, 115))
    d.set_widget_value(0, widget.xref, "Mario")
    assert next(d.page(0).widgets()).field_value == "Mario"


def test_rotated_page_text_is_upright():
    d = PdfDocument.new()
    page = d.page(0)
    page.set_rotation(90)
    vis = pymupdf.Rect(50, 50, 300, 100)
    d.add_text_box(0, vis * page.derotation_matrix, "Dritto")
    line = d.page(0).get_text("dict")["blocks"][0]["lines"][0]
    # direzione del testo nello spazio non ruotato compensa la rotazione della pagina
    assert tuple(round(c) for c in line["dir"]) == (0, -1)


def test_parse_ranges():
    assert parse_page_ranges("1-3, 5, 8-", 10) == [(0, 2), (4, 4), (7, 9)]
    with pytest.raises(ValueError):
        parse_page_ranges("0-2", 10)
    with pytest.raises(ValueError):
        parse_page_ranges("", 10)


# ------------------------------------------------------------------ moduli
def _form_with_radio(path):
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas")
    from reportlab.lib.colors import black, white
    c = reportlab.Canvas(path)
    c.drawString(72, 780, "Modulo di prova")
    f = c.acroForm
    f.textfield(name="nome", x=180, y=735, width=250, height=18, value="Mario", borderColor=black, fillColor=white)
    f.textfield(name="note", x=180, y=630, width=250, height=60, fieldFlags="multiline")
    f.checkbox(name="privacy", x=200, y=597, size=14)
    f.choice(name="comune", x=180, y=565, width=150, height=18, options=["Milano", "Bergamo"], value="Milano")
    f.radio(name="tipo", value="nuovo", x=180, y=537, size=14, selected=True)
    f.radio(name="tipo", value="ristr", x=260, y=537, size=14)
    c.save()
    return path


def _add_xfa(doc):
    """Aggiunge una chiave XFA all'AcroForm (simula un modulo Adobe LiveCycle)."""
    xfa = doc.get_new_xref()
    doc.update_object(xfa, "<<>>")
    doc.update_stream(xfa, b"<xdp:xdp xmlns:xdp='http://ns.adobe.com/xdp/'/>")
    cat = doc.pdf_catalog()
    if doc.xref_get_key(cat, "AcroForm")[0] == "null":
        af = doc.get_new_xref()
        doc.update_object(af, "<< /Fields [] >>")
        doc.xref_set_key(cat, "AcroForm", f"{af} 0 R")
    af = int(doc.xref_get_key(cat, "AcroForm")[1].split()[0])
    doc.xref_set_key(af, "XFA", f"{xfa} 0 R")


def test_form_fields_and_filling(tmp_path):
    path = _form_with_radio(str(tmp_path / "modulo.pdf"))
    d = PdfDocument.open(path)
    fields = d.form_fields()
    kinds = [(f.name, f.kind) for f in fields]
    assert ("note", "multiline") in kinds and ("privacy", "checkbox") in kinds and ("comune", "combo") in kinds
    by = {f.name: f for f in fields}
    d.set_widget_value(0, by["privacy"].xref, True)
    d.set_widget_value(0, by["comune"].xref, "Bergamo")
    radios = [f for f in fields if f.kind == "radio"]
    assert radios[0].checked and not radios[1].checked
    d.set_widget_value(0, radios[1].xref, True)
    after = {(f.name, f.xref): f for f in d.form_fields()}
    assert after[("privacy", by["privacy"].xref)].checked
    assert after[("comune", by["comune"].xref)].value == "Bergamo"
    assert after[("tipo", radios[1].xref)].checked and not after[("tipo", radios[0].xref)].checked
    out = str(tmp_path / "compilato.pdf")
    d.save(out)
    saved = {w.field_name: w.field_value for w in pymupdf.open(out)[0].widgets() if w.field_value not in ("Off",)}
    assert saved["comune"] == "Bergamo" and saved["privacy"] != "Off" and saved["tipo"] == "ristr"


def test_xfa_detection_and_conversion(tmp_path):
    path = _form_with_radio(str(tmp_path / "ibrido.pdf"))
    doc = pymupdf.open(path)
    _add_xfa(doc)
    doc.save(str(tmp_path / "ibrido_xfa.pdf"))
    d = PdfDocument.open(str(tmp_path / "ibrido_xfa.pdf"))
    assert d.xfa_kind() == "hybrid"
    f = d.form_fields()[0]
    d.set_widget_value(f.page, f.xref, "Luigi")
    assert d.xfa_kind() is None  # i valori restano nei campi standard

    dyn = pymupdf.open()
    dyn.new_page().insert_text((72, 72), "Please wait... this document requires Adobe Reader")
    _add_xfa(dyn)
    dyn.save(str(tmp_path / "dinamico.pdf"))
    assert PdfDocument.open(str(tmp_path / "dinamico.pdf")).xfa_kind() == "dynamic"
