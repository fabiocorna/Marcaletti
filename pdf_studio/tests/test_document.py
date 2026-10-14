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
