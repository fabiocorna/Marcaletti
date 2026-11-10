import os

import pymupdf
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pdfstudio import print_dialog as P
from pdfstudio.document import PdfDocument


def opts(**kw):
    return P.PrintOptions(**kw)


def test_compute_pages():
    assert P.compute_pages(opts(), 5, 0, []) == [0, 1, 2, 3, 4]
    assert P.compute_pages(opts(pages_mode=P.CURRENT), 5, 3, []) == [3]
    assert P.compute_pages(opts(pages_mode=P.SELECTED), 5, 0, [4, 1]) == [1, 4]
    assert P.compute_pages(opts(pages_mode=P.RANGE, ranges="2-4, 1"), 5, 0, []) == [1, 2, 3, 0]
    assert P.compute_pages(opts(pages_mode=P.RANGE, ranges="1-"), 5, 0, [], ) == [0, 1, 2, 3, 4]
    assert P.compute_pages(opts(subset="odd"), 5, 0, []) == [0, 2, 4]          # pagine 1, 3, 5
    assert P.compute_pages(opts(subset="even", reverse=True), 5, 0, []) == [3, 1]
    with pytest.raises(ValueError):
        P.compute_pages(opts(pages_mode=P.RANGE, ranges="7-9"), 5, 0, [])


def test_placement():
    a4, printable = (595, 842), (18, 18, 559, 806)
    rot, x, y, w, h, s = P.placement(595, 842, *a4, printable, P.FIT)
    assert not rot and s == pytest.approx(559 / 595)
    rot, *_r, s = P.placement(1191, 842, *a4, printable, P.FIT)             # A3 orizzontale su A4
    assert rot and s < 0.7
    rot, *_r, s = P.placement(1191, 842, *a4, printable, P.FIT, auto_rotate=False)
    assert not rot and s == pytest.approx(559 / 1191)
    *_r, s = P.placement(300, 400, *a4, printable, P.SHRINK)                # piccola: resta al 100%
    assert s == 1.0
    *_r, s = P.placement(595, 842, *a4, printable, P.ACTUAL)
    assert s == 1.0
    *_r, s = P.placement(595, 842, *a4, printable, P.CUSTOM, scale=50)
    assert s == 0.5


def test_sheets():
    assert P.sheets_needed(5, 1, False) == 5
    assert P.sheets_needed(5, 2, True) == 6


def test_print_to_pdf(tmp_path):
    from PySide6.QtPrintSupport import QPrinter
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    doc = pymupdf.open()
    for w, h in [(595, 842), (1191, 842), (595, 842)]:
        doc.new_page(width=w, height=h).insert_text((50, 80), "Prova di stampa", fontsize=20)
    path = str(tmp_path / "src.pdf")
    doc.save(path)
    d = PdfDocument.open(path)
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    out = str(tmp_path / "stampa.pdf")
    printer.setOutputFileName(out)
    o = opts(grayscale=True)
    P.configure_printer(printer, o, "prova")
    pages = P.compute_pages(opts(pages_mode=P.RANGE, ranges="2-3"), 3, 0, [])
    assert P.print_pages(d, pages, printer, o) == 2
    res = pymupdf.open(out)
    assert res.page_count == 2
    assert res[0].rect.height > res[0].rect.width  # tavola orizzontale ruotata sul foglio verticale


def test_dialog_summary():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    d = PdfDocument.new(pages=4)
    dlg = P.PrintDialog(d, 1, [0, 2])
    assert dlg._pages == [0, 2]                    # pagine selezionate nelle miniature
    dlg.r_current.setChecked(True)
    assert dlg._pages == [1]
    dlg.r_range.setChecked(True)
    dlg.range_edit.setText("9")
    dlg._refresh()
    assert dlg._pages == [] and dlg.range_error.text()
    dlg.deleteLater()


def _pdf_printer(tmp_path, name="out.pdf"):
    from PySide6.QtPrintSupport import QPrinter
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(str(tmp_path / name))
    return printer


def test_margins_same_in_preview_and_print(tmp_path):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    printer = _pdf_printer(tmp_path)
    before = P.paper_geometry(printer)
    P.configure_printer(printer, opts(), "x")
    d = PdfDocument.new()
    P.print_pages(d, [0], printer, opts())
    after = P.paper_geometry(printer)
    assert before == after and after[2][0] > 0  # i margini restano anche in modalità pagina intera


def test_cancel_raises_and_prints_nothing(tmp_path):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    d = PdfDocument.new(pages=5)
    printer = _pdf_printer(tmp_path, "annullata.pdf")
    with pytest.raises(P.PrintCancelled):
        P.print_pages(d, list(range(5)), printer, opts(), progress=lambda n, tot: n < 2)
    out = tmp_path / "annullata.pdf"
    assert not out.exists() or out.stat().st_size == 0 or pymupdf.open(str(out)).page_count < 5


def test_render_resolution_follows_scale(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    doc = pymupdf.open()
    doc.new_page(width=2384, height=3370)  # A0
    path = str(tmp_path / "a0.pdf")
    doc.save(path)
    d = PdfDocument.open(path)
    used = []
    real = P.render_page
    monkeypatch.setattr(P, "render_page", lambda page, dpi, g, a: (used.append(dpi), real(page, dpi, g, a))[1])
    P.print_pages(d, [0], _pdf_printer(tmp_path), opts())
    assert used and used[0] < 120  # A0 su A4: circa un quarto della risoluzione piena
    img = real(d.page(0), 1200, False, False)
    assert img.width() * img.height() <= P.MAX_RENDER_PIXELS * 1.01


def test_dialog_pdf_target_and_paper_kept():
    from PySide6.QtGui import QPageLayout, QPageSize
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    d = PdfDocument.new(pages=2)
    dlg = P.PrintDialog(d, 0, [])
    assert dlg.printer_combo.findText(P.PDF_FILE_TARGET) >= 0
    dlg.printer_combo.setCurrentText(P.PDF_FILE_TARGET)
    assert dlg.print_btn.isEnabled() and dlg.print_btn.text() == "Salva PDF…"
    dlg.printer.setPageSize(QPageSize(QPageSize.A3))
    dlg.printer.setPageOrientation(QPageLayout.Landscape)
    dlg._paper_chosen = True
    dlg._printer_changed()  # come se si cambiasse stampante
    w, h, _p = P.paper_geometry(dlg.printer)
    assert w > h and round(w) == 1191
    dlg.deleteLater()
