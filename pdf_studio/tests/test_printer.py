import os

import pymupdf

from pdfstudio import printer as PR


def make_pdf(path):
    d = pymupdf.open()
    d.new_page().insert_text((72, 72), "stampa di prova")
    d.save(path)


def test_incomplete_pdf_not_collected(tmp_path):
    port = tmp_path / "stampa.pdf"
    port.write_bytes(b"%PDF-1.7\n1 0 obj\n" + b"x" * 200)  # scrittura in corso
    assert not PR.is_complete_pdf(str(port))
    assert PR.collect(str(port), str(tmp_path / "out")) is None
    assert port.exists()


def test_collect_moves_with_unique_names(tmp_path):
    port = str(tmp_path / "stampa.pdf")
    out = str(tmp_path / "Stampe")
    make_pdf(port)
    first = PR.collect(port, out)
    make_pdf(port)
    second = PR.collect(port, out)
    assert first != second and os.path.basename(first).startswith("Stampa ")
    assert not os.path.exists(port)
    assert pymupdf.open(second)[0].get_text().strip() == "stampa di prova"


def test_watcher_emits_when_stable(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtTest import QTest
    app = QCoreApplication.instance() or QCoreApplication([])
    port = str(tmp_path / "stampa.pdf")
    received = []
    w = PR.PrintWatcher(port, str(tmp_path / "Stampe"), interval_ms=50)
    w.pdfReady.connect(received.append)
    w.start()
    QTest.qWait(120)
    make_pdf(port)
    for _ in range(40):
        QTest.qWait(50)
        if received:
            break
    w.stop()
    assert len(received) == 1 and os.path.exists(received[0]) and not os.path.exists(port)


def test_paths():
    assert PR.port_file().endswith(os.path.join("CRN PDF Studio", "spool", "stampa.pdf"))
    assert PR.output_dir().endswith(os.path.join("CRN PDF Studio", "Stampe"))
