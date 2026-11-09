import os
from decimal import Decimal as D

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QStandardPaths, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)
    a = QApplication.instance() or QApplication([])
    a.setOrganizationName("CRN")
    a.setApplicationName("CRN Computo Test")
    return a


@pytest.fixture
def win(app, tmp_path):
    from crncomputo.mainwindow import MainWindow
    from crncomputo.prezzario import Libreria, Prezzario, VocePrezzario
    w = MainWindow()
    w.libreria = Libreria(str(tmp_path / "lib"))
    w.libreria.add(Prezzario("Prova", voci=[VocePrezzario("B.01", "Intonaco civile", "m²", D("20"))]))
    w._prezzari = None
    w.pz_combo.clear()
    w._search_prezzari()
    yield w
    w.doc.modified = False
    w.close()


def test_inserimento_e_misure(win):
    assert win.pz_table.rowCount() == 1
    cap = win.doc.add_capitolo("Finiture")
    win.sel_cap = cap.id
    win.refresh()
    win.pz_table.setCurrentCell(0, 0)
    win.insert_from_prezzario()
    p = win.doc.p
    assert len(p.voci) == 1 and p.voci[0].capitolo == cap.id and p.articoli["B.01"].fonte == "Prova"
    # modifica delle misure dalla tabella, con formule
    win.misure.item(0, 0).setText("Parete")
    win.misure.item(0, 2).setText("4+1")
    win.misure.item(0, 4).setText("2,70")
    assert p.voci[0].quantita() == D("13.50")
    assert win.voci.item(0, 6).text() == "270,00"
    assert win.misure.item(0, 6).text() == "13,50"
    # formula errata: rifiutata, il valore resta quello di prima
    win.misure.item(0, 2).setText("4+")
    assert win.doc.p.voci[0].misure[0].lunghezza == "4+1"
    assert win.misure.item(0, 2).text() == "4+1"
    win.add_misura(True)
    win.misure.item(1, 2).setText("1")
    win.misure.item(1, 4).setText("2")
    assert win.doc.p.voci[0].quantita() == D("11.50")
    win.misure.item(1, 5).setCheckState(Qt.Unchecked)
    assert win.doc.p.voci[0].quantita() == D("15.50")
    win.undo()
    assert win.doc.p.voci[0].quantita() == D("11.50")
    assert "11,50" in win.voce_tot.text()


def test_elenco_e_quadro(win):
    from crncomputo.model import Articolo, Misura
    win.doc.set_articolo(Articolo("A", "Voce", "m", D("10")))
    win.doc.add_voce("A", None, [Misura("", "", "3")])
    win.refresh()
    assert win.cap_tree.topLevelItemCount() == 2       # tutto + fuori capitolo
    win.tabs.setCurrentIndex(1)
    win.elenco.item(0, 3).setText("12,5")
    assert win.doc.p.articoli["A"].prezzo == D("12.5")
    win.elenco.item(0, 0).setText("A.1")
    assert win.doc.p.voci[0].articolo == "A.1"
    win.qe_iva.setText("22")
    win._on_quadro()
    assert win.doc.p.quadro_economico()["totale_generale"] == D("45.75")
    win.add_somma()
    win.somme.item(0, 2).setText("0")
    assert win.doc.p.quadro.somme[0].valore == 0
    assert "TOTALE GENERALE" in win.qe_view.toPlainText()


def test_salva_e_apri(win, tmp_path):
    from crncomputo.model import Articolo, Misura
    win.doc.set_articolo(Articolo("A", "Voce", "m", D("10")))
    win.doc.add_voce("A", None, [Misura("", "", "3")])
    path = str(tmp_path / "p.crcm")
    win.doc.save(path)
    win.new_project()
    assert not win.doc.p.voci
    win.open_project(path)
    assert win.doc.p.totale_voci() == D("30.00") and win.windowTitle().startswith("p.crcm")
