"""Test delle correzioni della revisione del codice (versione 1.5.1)."""
import os

import pymupdf
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pdfstudio import printer as PR
from pdfstudio.document import PdfDocument


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def form_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 80), "Modulo con testo da evidenziare")
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w.field_name = "nome"
    w.rect = pymupdf.Rect(72, 120, 300, 140)
    page.add_widget(w)
    doc.save(path)
    return path


def test_save_commits_field_being_edited(app, tmp_path):
    from PySide6.QtTest import QTest
    from pdfstudio.mainwindow import MainWindow
    path = form_pdf(str(tmp_path / "m.pdf"))
    win = MainWindow()
    win.open_file(path)
    view = win.tab().view
    field = next(f for f in view._fields if f.name == "nome")
    view.activate_field(field)
    QTest.keyClicks(view._field_editor[2], "Mario Rossi")
    assert win.save()  # Ctrl+S senza Invio né Tab
    saved = {w.field_name: w.field_value for w in pymupdf.open(path)[0].widgets()}
    assert saved["nome"] == "Mario Rossi"
    win.tab().document.modified = False
    win.deleteLater()


def test_escape_cancels_field_and_selection(app, tmp_path):
    from PySide6.QtTest import QTest
    from pdfstudio.mainwindow import MainWindow
    win = MainWindow()
    win.open_file(form_pdf(str(tmp_path / "m.pdf")))
    view = win.tab().view
    view.activate_field(next(f for f in view._fields if f.name == "nome"))
    QTest.keyClicks(view._field_editor[2], "per errore")
    win._escape()
    assert not view.field_editing
    assert not win.tab().document.modified
    view.select_all_page()
    assert view.has_selection
    win._escape()
    assert not view.has_selection
    win.deleteLater()


def test_double_click_on_highlight_edits_comment(app, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QInputDialog
    asked = []
    monkeypatch.setattr(QInputDialog, "getMultiLineText",
                        staticmethod(lambda *a, **k: (asked.append(a), ("", False))[1]))
    from PySide6.QtTest import QTest
    from pdfstudio.mainwindow import MainWindow
    path = str(tmp_path / "h.pdf")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 80), "Testo evidenziato con un commento")
    page.add_highlight_annot(page.search_for("evidenziato")[0])
    doc.save(path)
    win = MainWindow()
    win.show()
    win.open_file(path)
    QTest.qWait(100)
    view = win.tab().view
    actions = []
    view.toolAction.connect(lambda tool, page, data: actions.append(tool))
    r = win.tab().document.page(0).search_for("evidenziato")[0]
    pos = view.mapFromScene(view._doc_rect_to_scene(0, r).center())
    QTest.mouseDClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, pos)
    assert "edit_annot" in actions and asked
    win.deleteLater()


def test_locked_print_leaves_no_duplicates(tmp_path, monkeypatch):
    port = str(tmp_path / "stampa.pdf")
    out = str(tmp_path / "Stampe")
    d = pymupdf.open()
    d.new_page()
    d.save(port)
    real_remove = os.remove

    def locked(path):
        if path == port:
            raise PermissionError("bloccato dallo spooler")
        return real_remove(path)

    monkeypatch.setattr(os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError("bloccato")))
    monkeypatch.setattr(os, "remove", locked)
    for _ in range(3):
        assert PR.collect(port, out) is None
    assert os.listdir(out) == []  # nessuna copia lasciata a ogni tentativo
    assert os.path.exists(port)


def test_undo_memory_is_capped():
    d = PdfDocument.new()
    pix = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 400, 400), False)
    d.page(0).insert_image(pymupdf.Rect(0, 0, 400, 400), pixmap=pix)
    size = len(d.doc.tobytes())
    d.MAX_UNDO_BYTES = size * 3
    for i in range(10):
        d.add_note(0, pymupdf.Point(10 + i, 10), f"nota {i}")
    assert 1 <= len(d._undo) <= 3
    assert d.undo()


def test_find_replace_case_mismatch_is_not_a_change():
    d = PdfDocument.new()
    d.page(0).insert_text((72, 72), "Sede in ROMA")
    d.modified = False
    assert d.find_replace("Roma", "Milano", match_case=True) == 0
    assert not d.modified and not d.can_undo
    assert d.find_replace("Roma", "Milano", match_case=False) == 1
