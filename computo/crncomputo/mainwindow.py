"""Finestra principale di CRN Computo."""
from __future__ import annotations

import html
import os
import sys

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import (QAction, QBrush, QColor, QDesktopServices, QFont, QIcon, QKeySequence, QPainter,
                           QPixmap, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
                               QDockWidget, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QTextBrowser, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from . import __version__
from . import export as E
from .assistant_panel import AssistantPanel
from .model import (DATI_LABELS, FILE_EXT, Articolo, Misura, ProgettoDoc, SommaDisposizione)
from .numeri import ZERO, FormulaError, evaluate, fmt, fmt_euro, to_decimal
from .prezzario import Libreria, Prezzario, VocePrezzario, load_any

CAP_ALL = -100     # «Tutto il computo»
CAP_NONE = -1      # «Voci fuori capitolo»
PROJECT_FILTER = f"Progetti CRN Computo (*{FILE_EXT})"
PREZZARIO_FILTER = "Prezzari (*.xlsx *.xlsm *.csv *.txt *.xml *.json);;Tutti i file (*)"
NUM_ALIGN = Qt.AlignRight | Qt.AlignVCenter
MISURA_FIELDS = ("descrizione", "parti", "lunghezza", "larghezza", "altezza")


def icon_pixmap(size: int = 64) -> QPixmap:
    k = size / 64
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#1f3b63"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4 * k, 4 * k, 56 * k, 56 * k, 10 * k, 10 * k)
    p.setPen(QColor("white"))
    f = QFont("Segoe UI" if sys.platform == "win32" else "DejaVu Sans")
    f.setPixelSize(round(22 * k))
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "€m²")
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 32, 48, 64, 256):
        icon.addPixmap(icon_pixmap(s))
    return icon


def _item(text, align=None, editable=False, tooltip=None, data=None, bold=False) -> QTableWidgetItem:
    it = QTableWidgetItem("" if text is None else str(text))
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
    if editable:
        flags |= Qt.ItemIsEditable
    it.setFlags(flags)
    if align is not None:
        it.setTextAlignment(align)
    if tooltip:
        it.setToolTip(tooltip)
    if data is not None:
        it.setData(Qt.UserRole, data)
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    return it


def _table(headers: list[str], stretch: int) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(22)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setAlternatingRowColors(True)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    h.setSectionResizeMode(stretch, QHeaderView.Stretch)
    return t


class CapitoloDialog(QDialog):
    def __init__(self, parent, titolo="", codice="", caption="Capitolo"):
        super().__init__(parent)
        self.setWindowTitle(caption)
        form = QFormLayout(self)
        self.codice = QLineEdit(codice)
        self.codice.setPlaceholderText("facoltativo, es. A o A.1")
        self.titolo = QLineEdit(titolo)
        self.titolo.setMinimumWidth(320)
        form.addRow("Codice:", self.codice)
        form.addRow("Titolo:", self.titolo)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        form.addRow(box)
        self.titolo.setFocus()


class ArticoloDialog(QDialog):
    """Nuovo prezzo (articolo non presente nei prezzari)."""

    def __init__(self, parent, codice: str):
        super().__init__(parent)
        self.setWindowTitle("Nuovo prezzo")
        form = QFormLayout(self)
        self.codice = QLineEdit(codice)
        self.descr = QPlainTextEdit()
        self.descr.setMinimumSize(420, 110)
        self.um = QComboBox(editable=True)
        self.um.addItems(["m²", "m³", "m", "kg", "cad", "a corpo", "h", "t", "l"])
        self.prezzo = QLineEdit()
        self.prezzo.setPlaceholderText("es. 125,50")
        self.mdo = QLineEdit()
        self.mdo.setPlaceholderText("facoltativo")
        self.sic = QComboBox()
        self.sic.addItems(["No", "Sì – onere della sicurezza (non soggetto a ribasso)"])
        form.addRow("Codice:", self.codice)
        form.addRow("Descrizione:", self.descr)
        form.addRow("Unità di misura:", self.um)
        form.addRow("Prezzo (€):", self.prezzo)
        form.addRow("Manodopera (%):", self.mdo)
        form.addRow("Sicurezza:", self.sic)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        form.addRow(box)

    def articolo(self) -> Articolo:
        return Articolo(self.codice.text().strip(), self.descr.toPlainText().strip(), self.um.currentText().strip(),
                        to_decimal(self.prezzo.text()), to_decimal(self.mdo.text() or "0"),
                        self.sic.currentIndex() == 1, "Nuovo prezzo")

    def accept(self) -> None:
        try:
            a = self.articolo()
        except ValueError as exc:
            QMessageBox.warning(self, "Nuovo prezzo", str(exc))
            return
        if not a.codice or not a.descrizione:
            QMessageBox.warning(self, "Nuovo prezzo", "Codice e descrizione sono obbligatori.")
            return
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings()
        self.doc = self._new_doc()
        data_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.path.expanduser("~")
        self.libreria = Libreria(os.path.join(data_dir, "prezzari"))
        self._prezzari: list[Prezzario] | None = None
        self.sel_cap = CAP_ALL
        self.sel_voce: int | None = None
        self._updating = False
        self.setWindowIcon(app_icon())
        self.resize(1400, 860)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_computo(), "Computo")
        self.tabs.addTab(self._build_elenco(), "Elenco prezzi")
        self.tabs.addTab(self._build_quadro(), "Quadro economico")
        self.tabs.addTab(self._build_dati(), "Dati generali")
        self.setCentralWidget(self.tabs)
        self._build_prezzari_dock()
        self.assistant = AssistantPanel(self.settings, lambda: self.doc, self.prezzari)
        self.assistant.projectChanged.connect(self.refresh)
        self.assistant.selectVoce.connect(self.select_voce)
        self.ai_dock = QDockWidget("Assistente Claude", self)
        self.ai_dock.setObjectName("assistente")
        self.ai_dock.setWidget(self.assistant)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_dock)
        self.tabifyDockWidget(self.pz_dock, self.ai_dock)
        self.pz_dock.raise_()
        self._build_menus()
        self.status_total = QLabel()
        self.statusBar().addPermanentWidget(self.status_total)
        geo = self.settings.value("window/geometry")
        if geo:
            self.restoreGeometry(geo)
        state = self.settings.value("window/state")
        if state:
            self.restoreState(state)
        self.refresh()
        self._search_prezzari()

    # ================================================================ costruzione
    def _new_doc(self) -> ProgettoDoc:
        doc = ProgettoDoc()
        doc.p.dati.progettista = self.settings.value("dati/progettista", "") or ""
        return doc

    def _build_computo(self) -> QWidget:
        split = QSplitter(Qt.Horizontal)
        # --- capitoli
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.cap_tree = QTreeWidget()
        self.cap_tree.setHeaderLabels(["Capitoli", "Importo"])
        self.cap_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.cap_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.cap_tree.header().setStretchLastSection(False)
        self.cap_tree.currentItemChanged.connect(self._on_cap_changed)
        self.cap_tree.itemDoubleClicked.connect(lambda *_: self.edit_capitolo())
        self.cap_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cap_tree.customContextMenuRequested.connect(self._cap_menu)
        ll.addWidget(self.cap_tree)
        row = QHBoxLayout()
        for text, tip, slot in (("＋", "Nuovo capitolo", self.new_capitolo),
                                ("＋↳", "Nuovo sottocapitolo del capitolo selezionato", self.new_sottocapitolo),
                                ("✎", "Rinomina capitolo", self.edit_capitolo),
                                ("▲", "Sposta su", lambda: self.move_capitolo(-1)),
                                ("▼", "Sposta giù", lambda: self.move_capitolo(1)),
                                ("🗑", "Elimina capitolo e le sue voci", self.delete_capitolo)):
            b = QToolButton(text=text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        ll.addLayout(row)
        split.addWidget(left)

        # --- voci e misure
        right = QSplitter(Qt.Vertical)
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.voci_title = QLabel()
        self.voci_title.setStyleSheet("font-weight:bold;color:#1f3b63")
        bar.addWidget(self.voci_title, 1)
        for text, tip, slot in (("Duplica", "Duplica la voce selezionata", self.duplicate_voce),
                                ("Cambia articolo…", "Sostituisci l'articolo dell'elenco prezzi", self.change_articolo),
                                ("Sposta in…", "Sposta la voce in un altro capitolo", self.move_voce_capitolo),
                                ("▲", "Sposta su", lambda: self.move_voce(-1)),
                                ("▼", "Sposta giù", lambda: self.move_voce(1)),
                                ("Elimina", "Elimina le voci selezionate", self.delete_voci)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            bar.addWidget(b)
        tl.addLayout(bar)
        self.voci = _table(["N.", "Tariffa", "Designazione dei lavori", "U.M.", "Quantità", "Prezzo €",
                            "Importo €"], 2)
        self.voci.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.voci.setWordWrap(False)
        self.voci.currentItemChanged.connect(self._on_voce_changed)
        self.voci.setContextMenuPolicy(Qt.CustomContextMenu)
        self.voci.customContextMenuRequested.connect(self._voce_menu)
        tl.addWidget(self.voci)
        hint = QLabel("Per aggiungere voci: cerca nel pannello <b>Prezzari</b> e fai doppio clic, oppure chiedi "
                      "all'<b>Assistente Claude</b>.")
        hint.setStyleSheet("color:#666")
        tl.addWidget(hint)
        right.addWidget(top)

        box = QGroupBox("Righe di misura")
        bl = QVBoxLayout(box)
        self.voce_desc = QLabel()
        self.voce_desc.setWordWrap(True)
        self.voce_desc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.voce_desc.setMaximumHeight(70)
        bl.addWidget(self.voce_desc)
        self.misure = _table(["Descrizione", "Par.ug.", "Lung.", "Larg.", "H/peso", "Deduz.", "Quantità"], 0)
        for c in range(1, 5):
            self.misure.horizontalHeader().setSectionResizeMode(c, QHeaderView.Interactive)
            self.misure.setColumnWidth(c, 90)
        self.misure.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.misure.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                                    | QAbstractItemView.AnyKeyPressed | QAbstractItemView.SelectedClicked)
        self.misure.itemChanged.connect(self._on_misura_edited)
        self.misure.setToolTip("Ogni campo accetta espressioni con la virgola decimale, es. 3,20+0,15 o 2*(4+3)")
        bl.addWidget(self.misure)
        ins = QShortcut(QKeySequence(Qt.Key_Insert), self.misure)
        ins.activated.connect(lambda: self.add_misura(False))
        canc = QShortcut(QKeySequence(QKeySequence.Delete), self.misure)
        canc.setContext(Qt.WidgetShortcut)
        canc.activated.connect(self.delete_misure)
        mrow = QHBoxLayout()
        for text, tip, slot in (("＋ Riga", "Nuova riga di misura (Ins)", lambda: self.add_misura(False)),
                                ("＋ Deduzione", "Nuova riga da sottrarre (vani, vuoti)", lambda: self.add_misura(True)),
                                ("Elimina righe", "Elimina le righe selezionate (Canc)", self.delete_misure)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            mrow.addWidget(b)
        mrow.addSpacing(20)
        mrow.addWidget(QLabel("Nota:"))
        self.voce_nota = QLineEdit()
        self.voce_nota.setPlaceholderText("Specifica della voce (stampata sotto la descrizione)")
        self.voce_nota.editingFinished.connect(self._on_nota)
        mrow.addWidget(self.voce_nota, 1)
        self.voce_tot = QLabel()
        self.voce_tot.setStyleSheet("font-weight:bold")
        mrow.addWidget(self.voce_tot)
        bl.addLayout(mrow)
        right.addWidget(box)
        right.setSizes([480, 320])
        split.addWidget(right)
        split.setSizes([340, 1000])
        return split

    def _build_elenco(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("Articoli usati nel progetto. Doppio clic su una cella per modificarla."))
        row.addStretch()
        b = QPushButton("Nuovo prezzo…")
        b.clicked.connect(self.new_prezzo)
        row.addWidget(b)
        b = QPushButton("Elimina")
        b.clicked.connect(self.delete_articoli)
        row.addWidget(b)
        lay.addLayout(row)
        self.elenco = _table(["Tariffa", "Descrizione", "U.M.", "Prezzo €", "% Manod.", "Sicurezza", "Fonte",
                              "Voci"], 1)
        self.elenco.setWordWrap(False)
        self.elenco.itemChanged.connect(self._on_articolo_edited)
        lay.addWidget(self.elenco)
        return w

    def _build_quadro(self) -> QWidget:
        w = QSplitter(Qt.Horizontal)
        left = QWidget()
        form = QFormLayout(left)
        self.qe_iva = QLineEdit()
        self.qe_sic_modo = QComboBox()
        self.qe_sic_modo.addItem("Solo voci di sicurezza del computo", "voci")
        self.qe_sic_modo.addItem("Voci + percentuale sui lavori", "percentuale")
        self.qe_sic_modo.addItem("Voci + importo a corpo", "importo")
        self.qe_sic_val = QLineEdit()
        self.qe_ribasso = QLineEdit()
        for wd in (self.qe_iva, self.qe_sic_val, self.qe_ribasso):
            wd.editingFinished.connect(self._on_quadro)
        self.qe_sic_modo.activated.connect(self._on_quadro)
        form.addRow("IVA sui lavori (%):", self.qe_iva)
        form.addRow("Oneri della sicurezza:", self.qe_sic_modo)
        form.addRow("Valore (% o €):", self.qe_sic_val)
        form.addRow("Ribasso d'asta (%):", self.qe_ribasso)
        form.addRow(QLabel("<b>Somme a disposizione</b> (oltre all'IVA sui lavori)"))
        self.somme = _table(["Descrizione", "Modo", "Valore", "IVA %"], 0)
        self.somme.itemChanged.connect(self._on_somme_edited)
        form.addRow(self.somme)
        row = QHBoxLayout()
        b = QPushButton("＋ Aggiungi")
        b.clicked.connect(self.add_somma)
        row.addWidget(b)
        b = QPushButton("Elimina")
        b.clicked.connect(self.delete_somma)
        row.addWidget(b)
        row.addStretch()
        form.addRow(row)
        form.addRow(QLabel("<small>Modo: «importo» (€) oppure «percentuale» (% del totale lavori).</small>"))
        w.addWidget(left)
        self.qe_view = QTextBrowser()
        w.addWidget(self.qe_view)
        w.setSizes([520, 700])
        return w

    def _build_dati(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.dati_edits: dict[str, QLineEdit | QPlainTextEdit] = {}
        for campo, label in DATI_LABELS.items():
            if campo == "note":
                ed = QPlainTextEdit()
                ed.setMaximumHeight(120)
            else:
                ed = QLineEdit()
                ed.editingFinished.connect(lambda c=campo: self._on_dato(c))
            self.dati_edits[campo] = ed
            form.addRow(label + ":", ed)
        b = QPushButton("Salva note")
        b.clicked.connect(lambda: self._on_dato("note"))
        form.addRow("", b)
        return w

    def _build_prezzari_dock(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        row = QHBoxLayout()
        self.pz_combo = QComboBox()
        self.pz_combo.currentIndexChanged.connect(lambda: self._search_prezzari())
        row.addWidget(self.pz_combo, 1)
        b = QToolButton(text="Importa…")
        b.setToolTip("Importa un prezzario (Excel, CSV o XML SIX)")
        b.clicked.connect(self.import_prezzario)
        row.addWidget(b)
        b = QToolButton(text="🗑")
        b.setToolTip("Rimuovi il prezzario selezionato dalla libreria")
        b.clicked.connect(self.remove_prezzario)
        row.addWidget(b)
        lay.addLayout(row)
        self.pz_search = QLineEdit()
        self.pz_search.setPlaceholderText("Cerca per codice o parole (es. intonaco civile)")
        self.pz_search.setClearButtonEnabled(True)
        self._pz_timer = QTimer(self, singleShot=True, interval=250)
        self._pz_timer.timeout.connect(self._search_prezzari)
        self.pz_search.textChanged.connect(lambda: self._pz_timer.start())
        lay.addWidget(self.pz_search)
        self.pz_table = _table(["Codice", "Descrizione", "U.M.", "Prezzo"], 1)
        self.pz_table.setWordWrap(False)
        self.pz_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pz_table.itemDoubleClicked.connect(lambda *_: self.insert_from_prezzario())
        lay.addWidget(self.pz_table)
        self.pz_info = QLabel()
        self.pz_info.setStyleSheet("color:#666")
        self.pz_info.setWordWrap(True)
        lay.addWidget(self.pz_info)
        b = QPushButton("Inserisci nel computo")
        b.setToolTip("Aggiunge una voce con l'articolo selezionato nel capitolo corrente (doppio clic)")
        b.clicked.connect(self.insert_from_prezzario)
        lay.addWidget(b)
        self.pz_dock = QDockWidget("Prezzari", self)
        self.pz_dock.setObjectName("prezzari")
        self.pz_dock.setWidget(w)
        self.addDockWidget(Qt.RightDockWidgetArea, self.pz_dock)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("&File")
        self._act(m, "Nuovo progetto", self.new_project, QKeySequence.New)
        self._act(m, "Apri…", self.open_project, QKeySequence.Open)
        self.recent_menu = m.addMenu("Progetti recenti")
        self._act(m, "Salva", self.save, QKeySequence.Save)
        self._act(m, "Salva con nome…", self.save_as, QKeySequence.SaveAs)
        m.addSeparator()
        ex = m.addMenu("Esporta")
        self._act(ex, "Computo metrico estimativo (PDF)…", lambda: self.export("computo"), "Ctrl+P")
        self._act(ex, "Computo metrico senza misure (PDF)…", lambda: self.export("computo_sintetico"))
        self._act(ex, "Elenco prezzi unitari (PDF)…", lambda: self.export("elenco"))
        self._act(ex, "Quadro economico (PDF)…", lambda: self.export("quadro"))
        ex.addSeparator()
        self._act(ex, "Tutto in Excel (.xlsx)…", lambda: self.export("xlsx"))
        m.addSeparator()
        self._act(m, "Esci", self.close, QKeySequence.Quit)

        m = mb.addMenu("&Modifica")
        self.undo_act = self._act(m, "Annulla", self.undo, QKeySequence.Undo)
        self.redo_act = self._act(m, "Ripeti", self.redo, "Ctrl+Y")
        m.addSeparator()
        self._act(m, "Nuovo capitolo", self.new_capitolo)
        self._act(m, "Nuovo prezzo…", self.new_prezzo)
        self._act(m, "Duplica voce", self.duplicate_voce, "Ctrl+D")

        m = mb.addMenu("&Prezzari")
        self._act(m, "Importa prezzario…", self.import_prezzario)
        self._act(m, "Cerca nei prezzari", self.focus_prezzari, "Ctrl+F")
        self._act(m, "Apri cartella dei prezzari", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(self.libreria.folder)))

        m = mb.addMenu("&Claude")
        self._act(m, "Mostra assistente", self.focus_assistant, "Ctrl+K")
        self._act(m, "Allega disegno o documento…", self.assistant.pick_attachments)
        self._act(m, "Impostazioni Claude…", self.assistant.open_settings)

        m = mb.addMenu("&Aiuto")
        self._act(m, "Informazioni su CRN Computo", self.about)
        self._update_recent()

    def _act(self, menu: QMenu, text: str, slot, shortcut=None) -> QAction:
        a = menu.addAction(text)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        self.addAction(a)
        return a

    # ================================================================== aggiorna
    def refresh(self, keep_misure: bool = False) -> None:
        if self.sel_cap not in (CAP_ALL, CAP_NONE) and self.doc.p.capitolo(self.sel_cap) is None:
            self.sel_cap = CAP_ALL
        if self.sel_voce is not None and self.doc.p.voce(self.sel_voce) is None:
            self.sel_voce = None
        self._updating = True
        try:
            self._fill_tree()
            self._fill_voci()
            if not keep_misure:
                self._fill_misure()
            else:
                self._update_misure_values()
            self._fill_elenco()
            self._fill_quadro()
            self._fill_dati()
        finally:
            self._updating = False
        p = self.doc.p
        qe = p.quadro_economico()
        self.status_total.setText(f"Totale computo {fmt_euro(p.totale_voci())}   ·   "
                                  f"Totale generale {fmt_euro(qe['totale_generale'])}  ")
        star = " *" if self.doc.modified else ""
        self.setWindowTitle(f"{self.doc.title}{star} – CRN Computo")
        self.undo_act.setEnabled(self.doc.can_undo)
        self.undo_act.setText(f"Annulla {self.doc.undo_label().lower()}".strip())
        self.redo_act.setEnabled(self.doc.can_redo)
        self.redo_act.setText(f"Ripeti {self.doc.redo_label().lower()}".strip())

    def _fill_tree(self) -> None:
        p = self.doc.p
        t = self.cap_tree
        t.blockSignals(True)
        t.clear()
        root = QTreeWidgetItem(["Tutto il computo", fmt(p.totale_voci())])
        root.setData(0, Qt.UserRole, CAP_ALL)
        f = root.font(0)
        f.setBold(True)
        root.setFont(0, f)
        root.setFont(1, f)
        root.setTextAlignment(1, NUM_ALIGN)
        t.addTopLevelItem(root)
        items = {CAP_ALL: root}
        senza = [v for v in p.voci if v.capitolo is None]
        if senza or self.sel_cap == CAP_NONE:
            it = QTreeWidgetItem(["Voci fuori capitolo", fmt(sum((p.importo(v) for v in senza), ZERO))])
            it.setData(0, Qt.UserRole, CAP_NONE)
            it.setForeground(0, QBrush(QColor("#666")))
            it.setTextAlignment(1, NUM_ALIGN)
            t.addTopLevelItem(it)
            items[CAP_NONE] = it

        def add(parent_item, parent_id):
            for c in p.figli(parent_id):
                it = QTreeWidgetItem([(f"{c.codice}  " if c.codice else "") + c.titolo, fmt(p.totale_capitolo(c.id))])
                it.setData(0, Qt.UserRole, c.id)
                it.setTextAlignment(1, NUM_ALIGN)
                parent_item.addChild(it)
                items[c.id] = it
                add(it, c.id)
        add(root, None)
        t.expandAll()
        t.setCurrentItem(items.get(self.sel_cap, root))
        t.blockSignals(False)

    def _voci_visibili(self):
        p = self.doc.p
        voci = p.voci_ordinate()
        if self.sel_cap == CAP_NONE:
            return [v for v in voci if v.capitolo is None]
        if self.sel_cap != CAP_ALL:
            ids = set(p.discendenti(self.sel_cap))
            return [v for v in voci if v.capitolo in ids]
        return voci

    def _fill_voci(self) -> None:
        p = self.doc.p
        t = self.voci
        t.blockSignals(True)
        voci = self._voci_visibili()
        t.setRowCount(len(voci))
        sel_row = None
        cap_names = {c.id: c.titolo for c in p.capitoli}
        numeri = p.numeri()
        for r, v in enumerate(voci):
            a = p.articoli.get(v.articolo)
            desc = a.descrizione_breve if a else "⚠ articolo mancante"
            if self.sel_cap == CAP_ALL and v.capitolo is not None:
                desc = f"[{cap_names.get(v.capitolo, '')}]  {desc}"
            tip = (a.descrizione if a else "") + (f"\n\nNota: {v.nota}" if v.nota else "")
            errs = v.errori()
            cells = [_item(numeri[v.id], NUM_ALIGN, data=v.id), _item(v.articolo), _item(desc, tooltip=tip),
                     _item(a.um if a else ""), _item(fmt(v.quantita()), NUM_ALIGN),
                     _item(fmt(p.prezzo(v)), NUM_ALIGN), _item(fmt(p.importo(v)), NUM_ALIGN, bold=True)]
            if not v.misure or errs:
                for c in cells:
                    c.setForeground(QBrush(QColor("#b00020")))
                cells[4].setToolTip("Formula errata: " + errs[0] if errs else "Voce senza misure")
            for c, it in enumerate(cells):
                t.setItem(r, c, it)
            if v.id == self.sel_voce:
                sel_row = r
        tot = sum((p.importo(v) for v in voci), ZERO)
        if self.sel_cap == CAP_ALL:
            name = "Tutto il computo"
        elif self.sel_cap == CAP_NONE:
            name = "Voci fuori capitolo"
        else:
            name = cap_names.get(self.sel_cap, "")
        self.voci_title.setText(f"{html.escape(name)} — {len(voci)} voci — {fmt_euro(tot)}")
        if sel_row is None and voci:
            sel_row = 0
        if sel_row is not None:
            t.setCurrentCell(sel_row, 2)
            self.sel_voce = voci[sel_row].id
        else:
            self.sel_voce = None
        t.blockSignals(False)

    def _fill_misure(self) -> None:
        p = self.doc.p
        t = self.misure
        t.blockSignals(True)
        v = p.voce(self.sel_voce) if self.sel_voce is not None else None
        if v is None:
            t.setRowCount(0)
            t.setEnabled(False)
            self.voce_desc.setText("<i>Seleziona una voce del computo.</i>")
            self.voce_nota.setText("")
            self.voce_nota.setEnabled(False)
            self.voce_tot.setText("")
            t.blockSignals(False)
            return
        t.setEnabled(True)
        self.voce_nota.setEnabled(True)
        a = p.articoli.get(v.articolo)
        self.voce_desc.setText(f"<b>N. {p.numero(v)} – {html.escape(v.articolo)}</b> "
                               f"{html.escape(a.descrizione if a else '')}")
        self.voce_desc.setToolTip(a.descrizione if a else "")
        self.voce_nota.setText(v.nota)
        t.setRowCount(len(v.misure))
        for r, m in enumerate(v.misure):
            t.setItem(r, 0, _item(m.descrizione, editable=True))
            for c, f in enumerate(MISURA_FIELDS[1:], 1):
                t.setItem(r, c, _item(getattr(m, f), NUM_ALIGN, editable=True))
            ded = _item("")
            ded.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            ded.setCheckState(Qt.Checked if m.deduzione else Qt.Unchecked)
            t.setItem(r, 5, ded)
            t.setItem(r, 6, _item("", NUM_ALIGN, bold=True))
        self._update_misure_values()
        t.blockSignals(False)

    def _update_misure_values(self) -> None:
        p = self.doc.p
        v = p.voce(self.sel_voce) if self.sel_voce is not None else None
        if v is None:
            return
        t = self.misure
        t.blockSignals(True)
        for r, m in enumerate(v.misure):
            if r >= t.rowCount():
                break
            q, err = m.quantita_sicura()
            it = t.item(r, 6)
            if it is None:
                continue
            it.setText("errore" if err else fmt(q))
            it.setToolTip(err or "")
            color = "#b00020" if err or m.deduzione else "#000000"
            it.setForeground(QBrush(QColor(color)))
            for c, f in enumerate(MISURA_FIELDS[1:], 1):
                cell = t.item(r, c)
                try:
                    val = evaluate(getattr(m, f))
                    cell.setToolTip(f"= {fmt(val, 4)}" if val is not None and getattr(m, f) != fmt(val) else "")
                    cell.setForeground(QBrush(QColor("#000000")))
                except FormulaError as exc:
                    cell.setToolTip(str(exc))
                    cell.setForeground(QBrush(QColor("#b00020")))
        a = p.articoli.get(v.articolo)
        self.voce_tot.setText(f"Quantità {fmt(v.quantita())} {a.um if a else ''} × {fmt(p.prezzo(v))} = "
                              f"{fmt_euro(p.importo(v))}")
        t.blockSignals(False)

    def _fill_elenco(self) -> None:
        p = self.doc.p
        t = self.elenco
        t.blockSignals(True)
        arts = sorted(p.articoli.values(), key=lambda a: a.codice)
        uso = {}
        for v in p.voci:
            uso[v.articolo] = uso.get(v.articolo, 0) + 1
        t.setRowCount(len(arts))
        for r, a in enumerate(arts):
            t.setItem(r, 0, _item(a.codice, editable=True, data=a.codice))
            t.setItem(r, 1, _item(" ".join(a.descrizione.split()), editable=True, tooltip=a.descrizione))
            t.setItem(r, 2, _item(a.um, editable=True))
            t.setItem(r, 3, _item(fmt(a.prezzo), NUM_ALIGN, editable=True))
            t.setItem(r, 4, _item(fmt(a.manodopera_pct, empty_zero=True), NUM_ALIGN, editable=True))
            sic = _item("")
            sic.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            sic.setCheckState(Qt.Checked if a.sicurezza else Qt.Unchecked)
            t.setItem(r, 5, sic)
            t.setItem(r, 6, _item(a.fonte))
            t.setItem(r, 7, _item(uso.get(a.codice, 0), NUM_ALIGN))
        t.blockSignals(False)

    def _fill_quadro(self) -> None:
        q = self.doc.p.quadro
        self.qe_iva.setText(fmt(q.iva_lavori_pct))
        self.qe_sic_modo.setCurrentIndex(max(0, self.qe_sic_modo.findData(q.sicurezza_modo)))
        self.qe_sic_val.setText(fmt(q.sicurezza_valore))
        self.qe_sic_val.setEnabled(q.sicurezza_modo != "voci")
        self.qe_ribasso.setText(fmt(q.ribasso_pct))
        t = self.somme
        t.blockSignals(True)
        t.setRowCount(len(q.somme))
        for r, s in enumerate(q.somme):
            t.setItem(r, 0, _item(s.descrizione, editable=True))
            t.setItem(r, 1, _item(s.modo, editable=True, tooltip="importo oppure percentuale"))
            t.setItem(r, 2, _item(fmt(s.valore), NUM_ALIGN, editable=True))
            t.setItem(r, 3, _item(fmt(s.iva_pct), NUM_ALIGN, editable=True))
        t.blockSignals(False)
        rows = []
        for sig, desc, imp, bold in E.quadro_rows(self.doc.p):
            style = "font-weight:bold;" if bold else ""
            border = "border-top:1px solid #333;" if desc.lower().startswith("totale") else ""
            rows.append(f"<tr><td style='{style}padding:3px 8px'>{sig}</td>"
                        f"<td style='{style}{border}padding:3px 8px'>{html.escape(desc)}</td>"
                        f"<td align='right' style='{style}{border}padding:3px 8px'>"
                        f"{fmt_euro(imp) if imp is not None else ''}</td></tr>")
        self.qe_view.setHtml(f"<h3>Quadro economico</h3><p>{html.escape(self.doc.p.dati.titolo)}</p>"
                             f"<table cellspacing='0' width='100%'>{''.join(rows)}</table>")

    def _fill_dati(self) -> None:
        for campo, ed in self.dati_edits.items():
            val = getattr(self.doc.p.dati, campo)
            if isinstance(ed, QPlainTextEdit):
                if ed.toPlainText() != val:
                    ed.setPlainText(val)
            elif ed.text() != val:
                ed.setText(val)

    # ============================================================ selezione
    def _on_cap_changed(self, cur, _prev) -> None:
        if cur is None or self._updating:
            return
        self.sel_cap = cur.data(0, Qt.UserRole)
        self.sel_voce = None
        self._updating = True
        try:
            self._fill_voci()
            self._fill_misure()
        finally:
            self._updating = False

    def _on_voce_changed(self, cur, _prev) -> None:
        if cur is None or self._updating:
            return
        self.sel_voce = self.voci.item(cur.row(), 0).data(Qt.UserRole)
        self._updating = True
        try:
            self._fill_misure()
        finally:
            self._updating = False

    def select_voce(self, vid: int) -> None:
        v = self.doc.p.voce(vid)
        if v is None:
            return
        if self.sel_cap != CAP_ALL:
            visible = {x.id for x in self._voci_visibili()}
            if vid not in visible:
                self.sel_cap = CAP_ALL
        self.sel_voce = vid
        self.tabs.setCurrentIndex(0)
        self.refresh()

    def _selected_voci(self) -> list[int]:
        rows = sorted({i.row() for i in self.voci.selectedItems()})
        return [self.voci.item(r, 0).data(Qt.UserRole) for r in rows] or \
            ([self.sel_voce] if self.sel_voce is not None else [])

    def _current_cap_for_insert(self) -> int | None:
        return None if self.sel_cap in (CAP_ALL, CAP_NONE) else self.sel_cap

    # ============================================================== modifiche
    def _do(self, fn, *args, **kwargs):
        """Esegue una modifica mostrando gli errori; poi aggiorna la finestra."""
        try:
            result = fn(*args, **kwargs)
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "CRN Computo", str(exc))
            self.refresh()
            return None
        self.refresh()
        return result

    def undo(self) -> None:
        if self.doc.can_undo:
            self.doc.undo()
            self.refresh()

    def redo(self) -> None:
        if self.doc.can_redo:
            self.doc.redo()
            self.refresh()

    # --- capitoli
    def new_capitolo(self, parent: int | None = None) -> None:
        dlg = CapitoloDialog(self, caption="Nuovo sottocapitolo" if parent else "Nuovo capitolo")
        if dlg.exec() and dlg.titolo.text().strip():
            c = self._do(self.doc.add_capitolo, dlg.titolo.text(), parent, dlg.codice.text().strip())
            if c:
                self.sel_cap = c.id
                self.refresh()

    def new_sottocapitolo(self) -> None:
        if self.sel_cap in (CAP_ALL, CAP_NONE):
            QMessageBox.information(self, "Sottocapitolo", "Seleziona prima il capitolo in cui crearlo.")
            return
        self.new_capitolo(self.sel_cap)

    def edit_capitolo(self) -> None:
        c = self.doc.p.capitolo(self.sel_cap)
        if c is None:
            return
        dlg = CapitoloDialog(self, c.titolo, c.codice, "Rinomina capitolo")
        if dlg.exec() and dlg.titolo.text().strip():
            self._do(self.doc.update_capitolo, c.id, dlg.titolo.text().strip(), dlg.codice.text().strip())

    def move_capitolo(self, delta: int) -> None:
        if self.doc.p.capitolo(self.sel_cap):
            self._do(self.doc.move_capitolo, self.sel_cap, delta)

    def delete_capitolo(self) -> None:
        c = self.doc.p.capitolo(self.sel_cap)
        if c is None:
            return
        ids = set(self.doc.p.discendenti(c.id))
        n = sum(1 for v in self.doc.p.voci if v.capitolo in ids)
        msg = f"Eliminare il capitolo «{c.titolo}»"
        msg += f" con i sottocapitoli e {n} voci?" if n or len(ids) > 1 else "?"
        if QMessageBox.question(self, "Elimina capitolo", msg) == QMessageBox.Yes:
            self._do(self.doc.delete_capitolo, c.id)

    def _cap_menu(self, pos) -> None:
        m = QMenu(self)
        m.addAction("Nuovo capitolo", self.new_capitolo)
        m.addAction("Nuovo sottocapitolo", self.new_sottocapitolo)
        if self.doc.p.capitolo(self.sel_cap):
            m.addAction("Rinomina…", self.edit_capitolo)
            m.addAction("Elimina", self.delete_capitolo)
        m.exec(self.cap_tree.viewport().mapToGlobal(pos))

    # --- voci
    def _voce_menu(self, pos) -> None:
        if self.sel_voce is None:
            return
        m = QMenu(self)
        m.addAction("Duplica", self.duplicate_voce)
        m.addAction("Cambia articolo…", self.change_articolo)
        m.addAction("Sposta in altro capitolo…", self.move_voce_capitolo)
        m.addAction("Elimina", self.delete_voci)
        m.addSeparator()
        m.addAction("Chiedi a Claude di controllare questa voce", self.ask_claude_voce)
        m.exec(self.voci.viewport().mapToGlobal(pos))

    def duplicate_voce(self) -> None:
        if self.sel_voce is not None:
            v = self._do(self.doc.duplicate_voce, self.sel_voce)
            if v:
                self.select_voce(v.id)

    def delete_voci(self) -> None:
        ids = self._selected_voci()
        if not ids:
            return
        msg = "Eliminare la voce selezionata?" if len(ids) == 1 else f"Eliminare le {len(ids)} voci selezionate?"
        if QMessageBox.question(self, "Elimina voci", msg) == QMessageBox.Yes:
            self.sel_voce = None
            self._do(self.doc.delete_voci, ids)

    def move_voce(self, delta: int) -> None:
        if self.sel_voce is not None:
            self._do(self.doc.move_voce, self.sel_voce, delta)

    def move_voce_capitolo(self) -> None:
        ids = self._selected_voci()
        if not ids:
            return
        caps = self.doc.p.capitoli_ordinati()
        labels = ["(nessun capitolo)"] + [("    " * lvl) + c.titolo for c, lvl in caps]
        choice, ok = QInputDialog.getItem(self, "Sposta voci", "Capitolo di destinazione:", labels, 0, False)
        if not ok:
            return
        target = None if choice == labels[0] else caps[labels.index(choice) - 1][0].id
        self.doc.begin_group("Sposta voci")
        try:
            for vid in ids:
                self.doc.set_voce_capitolo(vid, target)
        finally:
            self.doc.end_group()
        self.refresh()

    def change_articolo(self) -> None:
        if self.sel_voce is None:
            return
        arts = sorted(self.doc.p.articoli.values(), key=lambda a: a.codice)
        labels = [f"{a.codice} — {a.descrizione_breve}" for a in arts]
        cur = self.doc.p.voce(self.sel_voce).articolo
        idx = next((i for i, a in enumerate(arts) if a.codice == cur), 0)
        choice, ok = QInputDialog.getItem(self, "Cambia articolo", "Articolo dell'elenco prezzi:", labels, idx,
                                          False)
        if ok:
            self._do(self.doc.set_voce_articolo, self.sel_voce, arts[labels.index(choice)].codice)

    def _on_nota(self) -> None:
        if self._updating or self.sel_voce is None:
            return
        v = self.doc.p.voce(self.sel_voce)
        if v and v.nota != self.voce_nota.text():
            self._do(self.doc.set_voce_nota, v.id, self.voce_nota.text())

    def ask_claude_voce(self) -> None:
        v = self.doc.p.voce(self.sel_voce)
        if v is None:
            return
        self.focus_assistant()
        self.assistant.input.setPlainText(f"Controlla la voce n. {self.doc.p.numero(v)}: misure, unità di misura "
                                          f"e prezzo sono coerenti?")
        self.assistant.input.setFocus()

    # --- misure
    def add_misura(self, deduzione: bool) -> None:
        if self.sel_voce is None:
            return
        v = self.doc.p.voce(self.sel_voce)
        rows = sorted({i.row() for i in self.misure.selectedItems()})
        index = rows[-1] + 1 if rows else len(v.misure)
        m = Misura("Deduzione" if deduzione else "", deduzione=deduzione)
        self._do(self.doc.add_misure, v.id, [m], index)
        self.misure.setCurrentCell(index, 0)
        self.misure.editItem(self.misure.item(index, 0))

    def delete_misure(self) -> None:
        if self.sel_voce is None:
            return
        rows = sorted({i.row() for i in self.misure.selectedItems()})
        if rows:
            self._do(self.doc.delete_misure, self.sel_voce, rows)

    def _on_misura_edited(self, item: QTableWidgetItem) -> None:
        if self._updating or self.sel_voce is None:
            return
        r, c = item.row(), item.column()
        v = self.doc.p.voce(self.sel_voce)
        if r >= len(v.misure):
            return
        if c == 5:
            values = {"deduzione": item.checkState() == Qt.Checked}
        elif c < 5:
            values = {MISURA_FIELDS[c]: item.text().strip()}
        else:
            return
        if getattr(v.misure[r], next(iter(values))) == next(iter(values.values())):
            return
        try:
            self.doc.update_misura(v.id, r, **values)
        except FormulaError as exc:
            self.statusBar().showMessage(f"⚠ {exc}", 6000)
            QApplication.beep()
            self._updating = True
            self.misure.blockSignals(True)
            item.setText(getattr(v.misure[r], MISURA_FIELDS[c]))
            self.misure.blockSignals(False)
            self._updating = False
            return
        self.refresh(keep_misure=True)

    # --- elenco prezzi
    def _on_articolo_edited(self, item: QTableWidgetItem) -> None:
        if self._updating:
            return
        r, c = item.row(), item.column()
        codice = self.elenco.item(r, 0).data(Qt.UserRole)
        a = self.doc.p.articoli.get(codice)
        if a is None:
            return
        try:
            if c == 0:
                new = item.text().strip()
                if new and new != codice:
                    self.doc.rename_articolo(codice, new)
            else:
                b = Articolo(a.codice, a.descrizione, a.um, a.prezzo, a.manodopera_pct, a.sicurezza, a.fonte)
                text = item.text().strip()
                if c == 1:
                    b.descrizione = text
                elif c == 2:
                    b.um = text
                elif c == 3:
                    b.prezzo = to_decimal(text)
                elif c == 4:
                    b.manodopera_pct = to_decimal(text or "0")
                elif c == 5:
                    b.sicurezza = item.checkState() == Qt.Checked
                if b != a:
                    self.doc.set_articolo(b, "Modifica elenco prezzi")
        except ValueError as exc:
            QMessageBox.warning(self, "Elenco prezzi", str(exc))
        self.refresh()

    def new_prezzo(self) -> None:
        n = 1
        while f"NP.{n:02d}" in self.doc.p.articoli:
            n += 1
        dlg = ArticoloDialog(self, f"NP.{n:02d}")
        if not dlg.exec():
            return
        a = dlg.articolo()
        if a.codice in self.doc.p.articoli:
            QMessageBox.warning(self, "Nuovo prezzo", f"Il codice {a.codice} esiste già.")
            return
        self._do(self.doc.set_articolo, a, "Nuovo prezzo")
        if QMessageBox.question(self, "Nuovo prezzo", "Inserire subito una voce con questo prezzo nel computo?") \
                == QMessageBox.Yes:
            v = self._do(self.doc.add_voce, a.codice, self._current_cap_for_insert(), [Misura()],
                         after=self.sel_voce)
            if v:
                self.select_voce(v.id)

    def delete_articoli(self) -> None:
        rows = sorted({i.row() for i in self.elenco.selectedItems()})
        codes = [self.elenco.item(r, 0).data(Qt.UserRole) for r in rows]
        if not codes:
            return
        used = [c for c in codes if any(v.articolo == c for v in self.doc.p.voci)]
        if used:
            QMessageBox.warning(self, "Elenco prezzi", "Questi articoli sono usati nel computo e non si possono "
                                                       "eliminare: " + ", ".join(used))
            return
        self.doc.begin_group("Elimina articoli")
        try:
            for c in codes:
                self.doc.delete_articolo(c)
        finally:
            self.doc.end_group()
        self.refresh()

    # --- quadro economico
    def _on_quadro(self) -> None:
        if self._updating:
            return
        q = self.doc.p.quadro
        try:
            values = {"iva_lavori_pct": to_decimal(self.qe_iva.text() or "0"),
                      "sicurezza_modo": self.qe_sic_modo.currentData(),
                      "sicurezza_valore": to_decimal(self.qe_sic_val.text() or "0"),
                      "ribasso_pct": to_decimal(self.qe_ribasso.text() or "0")}
        except ValueError as exc:
            QMessageBox.warning(self, "Quadro economico", str(exc))
            self.refresh()
            return
        if any(getattr(q, k) != v for k, v in values.items()):
            self._do(self.doc.set_quadro, **values)

    def _somme_from_table(self) -> list[SommaDisposizione]:
        out = []
        for r in range(self.somme.rowCount()):
            txt = lambda c: (self.somme.item(r, c).text() if self.somme.item(r, c) else "").strip()  # noqa: E731
            modo = "percentuale" if txt(1).lower().startswith("perc") or txt(1) == "%" else "importo"
            out.append(SommaDisposizione(txt(0) or "Somma a disposizione", modo, to_decimal(txt(2) or "0"),
                                         to_decimal(txt(3) or "0")))
        return out

    def _on_somme_edited(self, _item) -> None:
        if self._updating:
            return
        try:
            somme = self._somme_from_table()
        except ValueError as exc:
            QMessageBox.warning(self, "Somme a disposizione", str(exc))
            self.refresh()
            return
        self._do(self.doc.set_somme, somme)

    def add_somma(self) -> None:
        somme = list(self.doc.p.quadro.somme) + [SommaDisposizione("Spese tecniche", "percentuale", to_decimal("10"),
                                                                   to_decimal("22"))]
        self._do(self.doc.set_somme, somme)

    def delete_somma(self) -> None:
        rows = {i.row() for i in self.somme.selectedItems()}
        if rows:
            self._do(self.doc.set_somme, [s for i, s in enumerate(self.doc.p.quadro.somme) if i not in rows])

    # --- dati generali
    def _on_dato(self, campo: str) -> None:
        if self._updating:
            return
        ed = self.dati_edits[campo]
        val = ed.toPlainText() if isinstance(ed, QPlainTextEdit) else ed.text()
        if val != getattr(self.doc.p.dati, campo):
            self._do(self.doc.set_dato, campo, val)
            if campo == "progettista":
                self.settings.setValue("dati/progettista", val)

    # ================================================================ prezzari
    def prezzari(self) -> list[Prezzario]:
        if self._prezzari is None:
            self._prezzari = self.libreria.tutti()
        return self._prezzari

    def _fill_pz_combo(self) -> None:
        cur = self.pz_combo.currentData()
        self.pz_combo.blockSignals(True)
        self.pz_combo.clear()
        self.pz_combo.addItem("Tutti i prezzari", "*")
        for z in self.prezzari():
            self.pz_combo.addItem(f"{z.nome} ({len(z.voci)})", z.nome)
        self.pz_combo.addItem("Elenco prezzi del progetto", "@")
        self.pz_combo.setCurrentIndex(max(0, self.pz_combo.findData(cur)))
        self.pz_combo.blockSignals(False)

    def _search_prezzari(self) -> None:
        if self.pz_combo.count() == 0:
            self._fill_pz_combo()
        which = self.pz_combo.currentData()
        query = self.pz_search.text()
        if which == "@":
            sources = [Prezzario("Elenco prezzi del progetto",
                                 voci=[VocePrezzario(a.codice, a.descrizione, a.um, a.prezzo, a.manodopera_pct,
                                                     a.sicurezza) for a in self.doc.p.articoli.values()])]
        elif which == "*":
            sources = self.prezzari()
        else:
            sources = [z for z in self.prezzari() if z.nome == which]
        results = []
        for z in sources:
            results += [(z.nome, v) for v in z.search(query, 200)]
        results = results[:300]
        t = self.pz_table
        t.setRowCount(len(results))
        for r, (nome, v) in enumerate(results):
            t.setItem(r, 0, _item(v.codice, data=(nome, v.codice)))
            t.setItem(r, 1, _item(" ".join(v.descrizione.split()), tooltip=f"{v.descrizione}\n\n({nome})"))
            t.setItem(r, 2, _item(v.um))
            t.setItem(r, 3, _item(fmt(v.prezzo), NUM_ALIGN))
        if not self.prezzari() and which != "@":
            self.pz_info.setText("Nessun prezzario nella libreria. Usa <b>Importa…</b> per caricare il prezzario "
                                 "regionale (Excel, CSV o XML SIX).")
        else:
            self.pz_info.setText(f"{len(results)} risultati" + (" (mostrati i primi 300)" if len(results) == 300
                                                                else ""))

    def _pz_lookup(self, nome: str, codice: str) -> tuple[str, VocePrezzario | None]:
        if nome == "Elenco prezzi del progetto":
            return nome, None
        z = next((z for z in self.prezzari() if z.nome == nome), None)
        return nome, z.get(codice) if z else None

    def insert_from_prezzario(self) -> None:
        r = self.pz_table.currentRow()
        if r < 0:
            return
        nome, codice = self.pz_table.item(r, 0).data(Qt.UserRole)
        _, v = self._pz_lookup(nome, codice)
        self.doc.begin_group("Nuova voce dal prezzario")
        try:
            if v is not None:
                existing = self.doc.p.articoli.get(v.codice)
                if existing is None:
                    self.doc.set_articolo(Articolo(v.codice, v.descrizione, v.um, v.prezzo, v.manodopera_pct,
                                                   v.sicurezza, nome))
                elif existing.prezzo != v.prezzo and existing.fonte != nome:
                    QMessageBox.information(self, "Elenco prezzi",
                                            f"Il codice {v.codice} è già nell'elenco prezzi del progetto con prezzo "
                                            f"{fmt(existing.prezzo)}: viene usato quello.")
            voce = self.doc.add_voce(codice, self._current_cap_for_insert(), [Misura()], after=self.sel_voce)
        except ValueError as exc:
            QMessageBox.warning(self, "CRN Computo", str(exc))
            return
        finally:
            self.doc.end_group()
        self.select_voce(voce.id)
        self.misure.setFocus()
        self.misure.setCurrentCell(0, 0)

    def import_prezzario(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importa prezzario", self.settings.value("dir/prezzari", ""),
                                              PREZZARIO_FILTER)
        if not path:
            return
        self.settings.setValue("dir/prezzari", os.path.dirname(path))
        nome, ok = QInputDialog.getText(self, "Importa prezzario", "Nome del prezzario nella libreria:",
                                        text=os.path.splitext(os.path.basename(path))[0])
        if not ok or not nome.strip():
            return
        if nome.strip() in self.libreria.nomi() and QMessageBox.question(
                self, "Importa prezzario", f"Il prezzario «{nome}» esiste già. Sostituirlo?") != QMessageBox.Yes:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            z = load_any(path, nome.strip())
            z.nome = nome.strip()
            self.libreria.add(z)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Importa prezzario", f"Importazione non riuscita:\n{exc}")
            return
        QApplication.restoreOverrideCursor()
        self._prezzari = None
        self._fill_pz_combo()
        self.pz_combo.setCurrentIndex(self.pz_combo.findData(z.nome))
        self._search_prezzari()
        if not self.doc.p.dati.prezzario:
            self.doc.set_dato("prezzario", z.nome)
            self.refresh()
        QMessageBox.information(self, "Importa prezzario", f"Importate {len(z.voci)} voci da «{z.nome}».")

    def remove_prezzario(self) -> None:
        nome = self.pz_combo.currentData()
        if nome in ("*", "@", None):
            return
        if QMessageBox.question(self, "Prezzari", f"Rimuovere «{nome}» dalla libreria? Le voci già inserite nei "
                                                  "progetti restano.") == QMessageBox.Yes:
            self.libreria.remove(nome)
            self._prezzari = None
            self._fill_pz_combo()
            self._search_prezzari()

    def focus_prezzari(self) -> None:
        self.pz_dock.show()
        self.pz_dock.raise_()
        self.pz_search.setFocus()
        self.pz_search.selectAll()

    def focus_assistant(self) -> None:
        self.ai_dock.show()
        self.ai_dock.raise_()
        self.assistant.input.setFocus()

    # =================================================================== file
    def _confirm_discard(self) -> bool:
        if self.assistant.busy:
            QMessageBox.information(self, "CRN Computo", "Attendi che l'assistente finisca (o interrompilo).")
            return False
        if not self.doc.modified:
            return True
        ans = QMessageBox.question(self, "CRN Computo", f"Salvare le modifiche a «{self.doc.title}»?",
                                   QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if ans == QMessageBox.Save:
            return self.save()
        return ans == QMessageBox.Discard

    def new_project(self) -> None:
        if self._confirm_discard():
            self.doc = self._new_doc()
            self.sel_cap, self.sel_voce = CAP_ALL, None
            self.assistant.new_conversation()
            self.refresh()

    def open_project(self, path: str | None = None) -> None:
        if not self._confirm_discard():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Apri progetto", self.settings.value("dir/progetti", ""),
                                                  PROJECT_FILTER)
            if not path:
                return
        try:
            self.doc = ProgettoDoc.open(path)
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Apri progetto", f"Impossibile aprire il progetto:\n{exc}")
            return
        self.settings.setValue("dir/progetti", os.path.dirname(path))
        self._add_recent(path)
        self.sel_cap, self.sel_voce = CAP_ALL, None
        self.assistant.new_conversation()
        self.refresh()

    def save(self) -> bool:
        if not self.doc.path:
            return self.save_as()
        try:
            self.doc.save()
        except OSError as exc:
            QMessageBox.warning(self, "Salva", f"Salvataggio non riuscito:\n{exc}")
            return False
        self._add_recent(self.doc.path)
        self.statusBar().showMessage("Progetto salvato.", 3000)
        self.refresh()
        return True

    def save_as(self) -> bool:
        base = self.doc.path or os.path.join(self.settings.value("dir/progetti", "") or os.path.expanduser("~"),
                                             _safe(self.doc.p.dati.titolo) + FILE_EXT)
        path, _ = QFileDialog.getSaveFileName(self, "Salva progetto", base, PROJECT_FILTER)
        if not path:
            return False
        if not path.lower().endswith(FILE_EXT):
            path += FILE_EXT
        self.doc.path = path
        self.settings.setValue("dir/progetti", os.path.dirname(path))
        return self.save()

    def _add_recent(self, path: str) -> None:
        rec = [p for p in (self.settings.value("recent", []) or []) if p != path]
        self.settings.setValue("recent", [path] + rec[:9])
        self._update_recent()

    def _update_recent(self) -> None:
        self.recent_menu.clear()
        rec = [p for p in (self.settings.value("recent", []) or []) if isinstance(p, str)]
        for p in rec:
            self.recent_menu.addAction(os.path.basename(p), lambda p=p: self.open_project(p)).setToolTip(p)
        self.recent_menu.setEnabled(bool(rec))

    def export(self, kind: str) -> None:
        names = {"computo": ("Computo metrico", "pdf"), "computo_sintetico": ("Computo metrico sintetico", "pdf"),
                 "elenco": ("Elenco prezzi", "pdf"), "quadro": ("Quadro economico", "pdf"),
                 "xlsx": ("Computo", "xlsx")}
        label, ext = names[kind]
        folder = os.path.dirname(self.doc.path) if self.doc.path else self.settings.value("dir/export", "")
        base = os.path.join(folder or os.path.expanduser("~"), f"{label} - {_safe(self.doc.p.dati.titolo)}.{ext}")
        flt = "PDF (*.pdf)" if ext == "pdf" else "Excel (*.xlsx)"
        path, _ = QFileDialog.getSaveFileName(self, "Esporta", base, flt)
        if not path:
            return
        self.settings.setValue("dir/export", os.path.dirname(path))
        p = self.doc.p
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if kind == "computo":
                E.export_computo_pdf(p, path)
            elif kind == "computo_sintetico":
                E.export_computo_pdf(p, path, dettaglio_misure=False)
            elif kind == "elenco":
                E.export_elenco_prezzi_pdf(p, path)
            elif kind == "quadro":
                E.export_quadro_pdf(p, path)
            else:
                E.export_xlsx(p, path)
        except OSError as exc:
            QMessageBox.warning(self, "Esporta", f"Esportazione non riuscita (il file è aperto in un altro "
                                                 f"programma?):\n{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def about(self) -> None:
        QMessageBox.about(self, "CRN Computo",
                          f"<b>CRN Computo {__version__}</b><br>Computo metrico estimativo con assistente Claude."
                          "<br><br>Prezzari importabili da Excel, CSV e XML SIX. Stampe in PDF ed Excel.")

    def closeEvent(self, ev) -> None:
        if not self._confirm_discard():
            ev.ignore()
            return
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())
        self.settings.sync()
        ev.accept()


def _safe(name: str) -> str:
    return "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "Computo"
