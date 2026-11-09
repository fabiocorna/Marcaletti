import pymupdf

from pdfstudio.textselect import PageText


def page_with_text():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(72, 72, 300, 200),
                        "Il tecnico incaricato dichiara che l'edificio rispetta i requisiti minimi previsti.",
                        fontsize=11)
    page.insert_text((72, 260), "Seconda sezione: valori conformi.", fontsize=11)
    return doc, page


def point_in(page, text, end=False):
    r = page.search_for(text)[0]
    return pymupdf.Point((r.x1 - 1) if end else (r.x0 + 1), (r.y0 + r.y1) / 2)


def test_drag_selection_joins_paragraph_lines():
    _doc, page = page_with_text()
    pt = PageText(page)
    a = pt.char_at(point_in(page, "tecnico"))
    b = pt.nearest(point_in(page, "requisiti", end=True))
    text = pt.text(a, b)
    assert text.startswith("tecnico incaricato") and text.endswith("requisiti")
    assert "\n" not in text  # stesso paragrafo: una riga sola
    assert len(pt.rects(a, b)) >= 2  # evidenziazione su più righe


def test_word_line_and_all():
    _doc, page = page_with_text()
    pt = PageText(page)
    i = pt.char_at(point_in(page, "edificio"))
    assert pt.text(*pt.word_at(i)) == "l'edificio"
    j = pt.char_at(point_in(page, "Seconda"))
    assert pt.text(*pt.line_at(j)) == "Seconda sezione: valori conformi."
    full = pt.text(*pt.all())
    assert full.startswith("Il tecnico") and full.endswith("conformi.") and "\n" in full


def test_hit_testing():
    _doc, page = page_with_text()
    pt = PageText(page)
    assert pt.is_over_text(point_in(page, "tecnico"))
    assert not pt.is_over_text(pymupdf.Point(500, 700))
    assert pt.char_at(pymupdf.Point(500, 700)) is None
    assert pt.nearest(pymupdf.Point(500, 700)) is not None  # trascinando oltre il testo


def test_rectangle_selection_and_empty_page():
    _doc, page = page_with_text()
    pt = PageText(page)
    assert pt.in_rect(pymupdf.Rect(60, 245, 400, 270)) == "Seconda sezione: valori conformi."
    empty = PageText(pymupdf.open().new_page())
    assert empty.empty and empty.all() is None
