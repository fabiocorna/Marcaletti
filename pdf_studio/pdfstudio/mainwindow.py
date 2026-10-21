"""Finestra principale di CRN PDF Studio."""
from __future__ import annotations

import os
import sys

import pymupdf
from PySide6.QtCore import QSettings, QSize, Qt, QUrl
from PySide6.QtGui import (QAction, QActionGroup, QColor, QDesktopServices, QFont, QIcon, QImage,
                           QKeySequence, QPainter, QPixmap)
from PySide6.QtWidgets import (QApplication, QColorDialog, QComboBox, QFileDialog, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressDialog,
                               QSizePolicy, QSpinBox, QSplitter, QStyle, QTabWidget, QToolBar, QToolButton, QWidget)

from . import CLAUDE_ENABLED, __version__
from . import viewer as V
from .dialogs import (CompressDialog, DxfDialog, ExportImagesDialog, FindReplaceDialog, FormFieldDialog, MergeDialog,
                      MetadataDialog, PdfADialog, SignaturesDialog,
                      NewDocumentDialog, PageNumbersDialog, PasswordPrompt, SecurityDialog, SignatureDialog,
                      SplitDialog, TextDialog, WatermarkDialog)
from .document import IMAGE_EXTENSIONS, PdfDocument, merge_files
from .thumbnails import ThumbnailList
from .viewer import PageView

OPEN_FILTER = ("Documenti supportati (*.pdf *.p7m *.xps *.oxps *.epub *.cbz *.fb2 *.svg "
               + " ".join("*" + e for e in IMAGE_EXTENSIONS) + ");;PDF (*.pdf);;PDF firmati (*.p7m);;Tutti i file (*)")
IMAGE_FILTER = "Immagini (" + " ".join("*" + e for e in IMAGE_EXTENSIONS) + ")"

TOOLS = [
    (V.HAND, "Mano", "✋", "Scorri il documento, compila i moduli, doppio clic per modificare un commento", "H"),
    (V.SELECT, "Seleziona testo", "⌶", "Trascina per copiare il testo negli appunti", "V"),
    (V.EDIT_TEXT, "Modifica testo", "✎", "Clicca su un testo esistente per modificarlo", "E"),
    (V.TEXT, "Aggiungi testo", "T", "Clicca o trascina un riquadro per inserire testo", "T"),
    (V.HIGHLIGHT, "Evidenzia", "▌", "Trascina sul testo per evidenziarlo", "U"),
    (V.UNDERLINE, "Sottolinea", "U̲", "Trascina sul testo per sottolinearlo", None),
    (V.STRIKEOUT, "Barra", "S̶", "Trascina sul testo per barrarlo", None),
    (V.NOTE, "Nota", "💬", "Clicca per aggiungere una nota adesiva", "N"),
    (V.INK, "Disegna", "✍", "Disegno a mano libera", "D"),
    (V.RECT, "Rettangolo", "▭", "Trascina per disegnare un rettangolo", None),
    (V.ELLIPSE, "Ellisse", "◯", "Trascina per disegnare un'ellisse", None),
    (V.LINE, "Linea", "╱", "Trascina per disegnare una linea", None),
    (V.ARROW, "Freccia", "➔", "Trascina per disegnare una freccia", None),
    (V.IMAGE, "Immagine", "🖼", "Clicca o trascina per inserire un'immagine", None),
    (V.SIGNATURE, "Firma", "✒", "Clicca o trascina per apporre una firma", "S"),
    (V.WHITEOUT, "Bianchetto", "▯", "Copri un'area con il bianco", None),
    (V.REDACT, "Oscura", "■", "Rimuovi definitivamente il contenuto sotto il riquadro", None),
    (V.CROP, "Ritaglia", "⛶", "Trascina per ritagliare la pagina", None),
    (V.ERASER, "Gomma", "⌫", "Clicca su un commento o disegno per eliminarlo", None),
]


def glyph_icon(glyph: str, color: str = "#2b2b2b") -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    f = QFont("Segoe UI Symbol" if sys.platform == "win32" else "DejaVu Sans", 34)
    f.setBold(glyph in ("T",))
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(pm.rect(), Qt.AlignCenter, glyph)
    p.end()
    return QIcon(pm)


def app_icon() -> QIcon:
    """Icona di CRN PDF Studio: «CRN» su fondo rosso con la dicitura PDF."""
    pm = QPixmap(256, 256)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#c62828"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(12, 12, 232, 232, 44, 44)
    p.setPen(QColor("white"))
    f = QFont("Arial", 66)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect().adjusted(0, -34, 0, -34), Qt.AlignCenter, "CRN")
    p.setBrush(QColor("white"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(52, 150, 152, 58, 12, 12)
    f2 = QFont("Arial", 34)
    f2.setBold(True)
    p.setFont(f2)
    p.setPen(QColor("#c62828"))
    p.drawText(52, 150, 152, 58, Qt.AlignCenter, "PDF")
    p.end()
    return QIcon(pm)


class DocumentTab(QWidget):
    """Una scheda: miniature + visualizzatore per un documento."""

    def __init__(self, document: PdfDocument, parent=None):
        super().__init__(parent)
        self.document = document
        self.search_results: list = []
        self.search_index = -1
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Horizontal)
        self.thumbs = ThumbnailList()
        self.view = PageView()
        self.splitter.addWidget(self.thumbs)
        self.splitter.addWidget(self.view)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([180, 1000])
        lay.addWidget(self.splitter)
        self.thumbs.pageClicked.connect(self.view.go_to_page)
        self.view.pageChanged.connect(self.thumbs.select_page)
        self.thumbs.set_document(document)
        self.view.set_document(document)

    def refresh(self, full: bool = True, page: int | None = None) -> None:
        if full:
            self.view.reload()
            self.thumbs.set_document(self.document)
            self.thumbs.select_page(self.view.current_page)
        else:
            self.view.refresh_page(page)
            self.thumbs.refresh(page)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CRN PDF Studio")
        self.setWindowIcon(app_icon())
        self.resize(1280, 860)
        self.setAcceptDrops(True)
        self.settings = QSettings("PDFStudio", "PDFStudio")
        self.tool_color = QColor(self.settings.value("tool_color", "#e53935"))
        self.highlight_color = QColor(self.settings.value("highlight_color", "#ffeb3b"))
        self.line_width = float(self.settings.value("line_width", 2.0))
        self.signature_png: bytes | None = None
        self.pending_image: str | None = None

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)
        self._welcome()

        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_statusbar()
        if CLAUDE_ENABLED:
            self._create_assistant()
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        self._really_quit = False
        self.watcher = None
        self._create_tray()
        self._update_ui()

    # ================================================================== interfaccia
    def _welcome(self) -> None:
        self.welcome = QLabel(
            "<div style='color:#666'><h1 style='color:#d32f2f'>CRN PDF Studio</h1>"
            "<p style='font-size:14px'>Apri un PDF con <b>Ctrl+O</b>, crea un documento con <b>Ctrl+N</b><br>"
            "oppure trascina qui i file (PDF o immagini).</p></div>")
        self.welcome.setAlignment(Qt.AlignCenter)

    def _std(self, sp) -> QIcon:
        return self.style().standardIcon(sp)

    def _act(self, text, slot, shortcut=None, icon=None, tip=None, checkable=False) -> QAction:
        a = QAction(text, self)
        if icon is not None:
            a.setIcon(icon)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setStatusTip(tip)
            a.setToolTip(tip)
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        return a

    def _create_actions(self) -> None:
        S = QStyle.StandardPixmap
        self.a_new = self._act("&Nuovo documento vuoto…", self.new_document, QKeySequence.New, self._std(S.SP_FileIcon))
        self.a_open = self._act("&Apri…", self.open_dialog, QKeySequence.Open, self._std(S.SP_DialogOpenButton))
        self.a_from_images = self._act("Crea PDF da &immagini…", self.create_from_images, None, glyph_icon("🖼"))
        self.a_merge = self._act("&Unisci file…", self.merge_dialog, "Ctrl+Shift+M", glyph_icon("⧉"),
                                 "Combina più PDF e immagini in un unico documento")
        self.a_save = self._act("&Salva", self.save, QKeySequence.Save, self._std(S.SP_DialogSaveButton))
        self.a_save_as = self._act("Salva &con nome…", self.save_as, QKeySequence.SaveAs)
        self.a_compress = self._act("Riduci &dimensione file…", self.compress)
        self.a_export_img = self._act("Esporta come &immagini…", self.export_images)
        self.a_export_txt = self._act("Esporta come &testo…", self.export_text)
        self.a_export_docx = self._act("Esporta in &Word (.docx)…", self.export_docx)
        self.a_export_dxf = self._act("Esporta in &DXF (CAD)…", self.export_dxf, None, glyph_icon("⌖"),
                                      "Esporta i disegni vettoriali in DXF per AutoCAD e altri CAD")
        self.a_print = self._act("S&tampa…", self.print_document, QKeySequence.Print, glyph_icon("🖶"))
        self.a_props = self._act("&Proprietà…", self.properties, "Ctrl+D")
        self.a_security = self._act("Proteggi con &password…", self.security, None, glyph_icon("🔒"))
        self.a_pdfa = self._act("Salva come PDF/&A…", self.save_pdfa, None, glyph_icon("Ⓐ"),
                                "Converte in PDF/A per archiviazione e conservazione")
        self.a_signatures = self._act("Verifica &firme digitali…", self.show_signatures, None, glyph_icon("✔"))
        self.a_claude = self._act("Assistente &Claude", self.toggle_assistant, "Ctrl+Shift+A", glyph_icon("✳", "#d97757"),
                                  "Chiedi a Claude di analizzare o modificare il documento", checkable=True)
        self.a_claude_settings = self._act("Impostazioni Claude…", self.claude_settings)
        self.a_close = self._act("&Chiudi scheda", lambda: self.close_tab(self.tabs.currentIndex()), QKeySequence.Close)
        self.a_quit = self._act("&Esci", self.quit_app, QKeySequence.Quit)
        self.a_printer = self._act("Stampante virtuale «CRN PDF»…", self.printer_settings, None, glyph_icon("🖨"),
                                   "Crea PDF stampando da qualsiasi programma")

        self.a_undo = self._act("&Annulla", self.undo, QKeySequence.Undo, glyph_icon("↶"))
        self.a_redo = self._act("&Ripeti", self.redo, QKeySequence.Redo, glyph_icon("↷"))
        self.a_find = self._act("&Trova…", self.focus_search, QKeySequence.Find)
        self.a_replace = self._act("Trova e &sostituisci…", self.find_replace, "Ctrl+H")
        self.a_copy_page_text = self._act("Copia testo della pagina", self.copy_page_text)

        self.a_zoom_in = self._act("Ingrandisci", lambda: self._zoom(1.25), QKeySequence.ZoomIn, glyph_icon("+"))
        self.a_zoom_out = self._act("Riduci", lambda: self._zoom(0.8), QKeySequence.ZoomOut, glyph_icon("−"))
        self.a_fit_w = self._act("Adatta alla larghezza", lambda: self._fit("width"), "Ctrl+2", glyph_icon("↔"))
        self.a_fit_p = self._act("Pagina intera", lambda: self._fit("page"), "Ctrl+1", glyph_icon("⤢"))
        self.a_actual = self._act("Dimensioni reali (100%)", lambda: self._set_zoom(1.0), "Ctrl+0")
        self.a_thumbs = self._act("Pannello miniature", self.toggle_thumbs, "F4", checkable=True)
        self.a_thumbs.setChecked(True)
        self.a_fullscreen = self._act("Schermo intero", self.toggle_fullscreen, "F11")
        self.a_first = self._act("Prima pagina", lambda: self._goto(0), "Home")
        self.a_prev = self._act("Pagina precedente", lambda: self._goto_rel(-1), "PgUp", glyph_icon("▲"))
        self.a_next = self._act("Pagina successiva", lambda: self._goto_rel(1), "PgDown", glyph_icon("▼"))
        self.a_last = self._act("Ultima pagina", lambda: self._goto(10 ** 6), "End")
        for a in (self.a_first, self.a_last):
            a.setShortcutContext(Qt.WidgetWithChildrenShortcut)

        self.a_rot_l = self._act("Ruota a sinistra", lambda: self.rotate(-90), "Ctrl+Shift+-", glyph_icon("⟲"),
                                 "Ruota le pagine selezionate di 90° in senso antiorario")
        self.a_rot_r = self._act("Ruota a destra", lambda: self.rotate(90), "Ctrl+Shift++", glyph_icon("⟳"),
                                 "Ruota le pagine selezionate di 90° in senso orario")
        self.a_del_page = self._act("Elimina pagine", self.delete_pages, "Ctrl+Del", glyph_icon("🗑"),
                                    "Elimina le pagine selezionate nelle miniature")
        self.a_ins_blank = self._act("Inserisci pagina vuota", self.insert_blank, None, glyph_icon("📄"))
        self.a_ins_file = self._act("Inserisci da file…", self.insert_file, None, glyph_icon("⊕"),
                                    "Inserisci pagine di un altro PDF o immagini dopo la pagina corrente")
        self.a_dup = self._act("Duplica pagina", self.duplicate_page)
        self.a_move_up = self._act("Sposta pagina su", lambda: self.move_page(-1), "Ctrl+Shift+Up")
        self.a_move_down = self._act("Sposta pagina giù", lambda: self.move_page(1), "Ctrl+Shift+Down")
        self.a_extract = self._act("Estrai pagine…", self.extract_pages, None, glyph_icon("⇱"),
                                   "Salva le pagine selezionate in un nuovo PDF")
        self.a_split = self._act("Dividi documento…", self.split_document, None, glyph_icon("✂"))
        self.a_uncrop = self._act("Annulla ritaglio pagina", self.uncrop)

        self.a_watermark = self._act("Filigrana…", self.watermark)
        self.a_pagenums = self._act("Numeri di pagina…", self.page_numbers)
        self.a_flatten = self._act("Appiattisci commenti", self.flatten)
        self.a_ocr = self._act("Riconoscimento testo (OCR)…", self.ocr)
        self.a_color = self._act("Colore strumenti…", self.pick_tool_color)
        self.a_hl_color = self._act("Colore evidenziatore…", self.pick_highlight_color)

        self.a_about = self._act("Informazioni su CRN PDF Studio", self.about)

        self.tool_group = QActionGroup(self)
        self.tool_actions: dict[str, QAction] = {}
        for key, label, glyph, tip, sc in TOOLS:
            a = QAction(glyph_icon(glyph), label, self)
            a.setCheckable(True)
            a.setToolTip(f"{label}{f' ({sc})' if sc else ''}\n{tip}")
            a.setStatusTip(tip)
            if sc:
                a.setShortcut(QKeySequence(sc))
            a.triggered.connect(lambda checked, k=key: self.set_tool(k))
            self.tool_group.addAction(a)
            self.tool_actions[key] = a
        self.tool_actions[V.HAND].setChecked(True)
        self.a_escape = self._act("Strumento mano", self._escape, "Esc")
        self.addAction(self.a_escape)

        self.recent_menu = None

    def _create_menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("&File")
        for a in (self.a_new, self.a_open):
            m.addAction(a)
        self.recent_menu = m.addMenu("File &recenti")
        self._update_recent()
        m.addSeparator()
        m.addAction(self.a_from_images)
        m.addAction(self.a_merge)
        m.addSeparator()
        for a in (self.a_save, self.a_save_as, self.a_pdfa, self.a_compress):
            m.addAction(a)
        exp = m.addMenu("&Esporta")
        for a in (self.a_export_img, self.a_export_txt, self.a_export_docx, self.a_export_dxf):
            exp.addAction(a)
        m.addSeparator()
        m.addAction(self.a_print)
        m.addAction(self.a_props)
        m.addAction(self.a_security)
        m.addAction(self.a_signatures)
        m.addSeparator()
        m.addAction(self.a_printer)
        m.addSeparator()
        m.addAction(self.a_close)
        m.addAction(self.a_quit)

        m = mb.addMenu("&Modifica")
        for a in (self.a_undo, self.a_redo):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_find)
        m.addAction(self.a_replace)
        m.addAction(self.a_copy_page_text)
        m.addSeparator()
        m.addAction(self.a_color)
        m.addAction(self.a_hl_color)

        m = mb.addMenu("&Visualizza")
        for a in (self.a_zoom_in, self.a_zoom_out, self.a_actual, self.a_fit_w, self.a_fit_p):
            m.addAction(a)
        m.addSeparator()
        for a in (self.a_first, self.a_prev, self.a_next, self.a_last):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_thumbs)
        m.addAction(self.a_fullscreen)

        m = mb.addMenu("&Pagine")
        for a in (self.a_rot_l, self.a_rot_r, None, self.a_ins_blank, self.a_ins_file, self.a_dup, None,
                  self.a_move_up, self.a_move_down, None, self.a_del_page, self.a_extract, self.a_split,
                  self.a_uncrop):
            m.addSeparator() if a is None else m.addAction(a)

        m = mb.addMenu("&Strumenti")
        for key, *_ in TOOLS:
            m.addAction(self.tool_actions[key])
        m.addSeparator()
        for a in (self.a_watermark, self.a_pagenums, self.a_flatten, self.a_ocr):
            m.addAction(a)

        if CLAUDE_ENABLED:
            m = mb.addMenu("&Claude")
            m.addAction(self.a_claude)
            m.addAction(self.a_claude_settings)

        m = mb.addMenu("&?")
        m.addAction(self.a_about)

    def _create_toolbars(self) -> None:
        tb = QToolBar("Principale")
        tb.setObjectName("main")
        tb.setIconSize(QSize(22, 22))
        self.addToolBar(tb)
        for a in (self.a_new, self.a_open, self.a_save, self.a_print, None, self.a_undo, self.a_redo, None,
                  self.a_prev, self.a_next):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setKeyboardTracking(False)
        self.page_spin.valueChanged.connect(lambda v: self._goto(v - 1))
        self.page_total = QLabel(" / 0 ")
        tb.addWidget(self.page_spin)
        tb.addWidget(self.page_total)
        tb.addSeparator()
        tb.addAction(self.a_zoom_out)
        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.addItems(["Adatta larghezza", "Pagina intera", "50%", "75%", "100%", "125%", "150%",
                                  "200%", "300%", "400%"])
        self.zoom_combo.setMinimumWidth(130)
        self.zoom_combo.activated.connect(self._zoom_combo_changed)
        self.zoom_combo.lineEdit().returnPressed.connect(self._zoom_combo_changed)
        tb.addWidget(self.zoom_combo)
        tb.addAction(self.a_zoom_in)
        tb.addSeparator()
        for a in (self.a_rot_l, self.a_rot_r, self.a_ins_file, self.a_del_page, self.a_extract, self.a_merge):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.a_pdfa)
        if CLAUDE_ENABLED:
            tb.addAction(self.a_claude)
        btn = tb.widgetForAction(self.a_claude) if CLAUDE_ENABLED else None
        if btn is not None:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Cerca nel documento…  (Ctrl+F)")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMaximumWidth(260)
        self.search_edit.returnPressed.connect(self.search_next)
        self.search_edit.textChanged.connect(self._search_text_changed)
        tb.addWidget(self.search_edit)
        self.search_label = QLabel("  ")
        tb.addWidget(self.search_label)

        tt = QToolBar("Strumenti di modifica")
        tt.setObjectName("tools")
        tt.setIconSize(QSize(20, 20))
        tt.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tt.setStyleSheet("QToolButton { padding: 2px 6px; text-align: left; }")
        self.addToolBar(Qt.LeftToolBarArea, tt)
        for key, *_ in TOOLS:
            tt.addAction(self.tool_actions[key])
            if key in (V.EDIT_TEXT, V.STRIKEOUT, V.NOTE, V.ARROW, V.SIGNATURE):
                tt.addSeparator()
        tt.addSeparator()
        self.color_btn = QToolButton()
        self.color_btn.setToolTip("Colore di disegno e forme")
        self.color_btn.clicked.connect(self.pick_tool_color)
        tt.addWidget(self.color_btn)
        self.width_spin = QSpinBox(minimum=1, maximum=20, value=int(self.line_width))
        self.width_spin.setToolTip("Spessore linee")
        self.width_spin.setSuffix(" pt")
        self.width_spin.valueChanged.connect(self._width_changed)
        tt.addWidget(self.width_spin)
        self._update_color_button()
        self.tools_toolbar = tt
        state = self.settings.value("window_state")
        if state is not None:
            self.restoreState(state)

    def _create_statusbar(self) -> None:
        self.status_info = QLabel()
        self.statusBar().addPermanentWidget(self.status_info)

    # ================================================================== utilità
    def tab(self) -> DocumentTab | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, DocumentTab) else None

    def doc(self) -> PdfDocument | None:
        t = self.tab()
        return t.document if t else None

    def _require_doc(self) -> PdfDocument | None:
        d = self.doc()
        if d is None:
            self.statusBar().showMessage("Nessun documento aperto", 3000)
        return d

    def _error(self, title: str, exc: Exception | str) -> None:
        QMessageBox.critical(self, title, str(exc))

    def _changed(self, full: bool = True, page: int | None = None) -> None:
        t = self.tab()
        if not t:
            return
        if full or page is None:
            t.refresh(True)
        else:
            t.refresh(False, page)
        if t.search_results:
            t.view.show_search_results(t.search_results, t.search_index)
        self._update_ui()

    def _update_ui(self) -> None:
        t = self.tab()
        d = t.document if t else None
        has = d is not None
        for a in (self.a_save, self.a_save_as, self.a_compress, self.a_export_img, self.a_export_txt,
                  self.a_export_docx, self.a_print, self.a_props, self.a_security, self.a_close, self.a_find,
                  self.a_zoom_in, self.a_zoom_out, self.a_fit_p, self.a_fit_w, self.a_actual, self.a_rot_l,
                  self.a_rot_r, self.a_del_page, self.a_ins_blank, self.a_ins_file, self.a_dup, self.a_extract,
                  self.a_split, self.a_watermark, self.a_pagenums, self.a_flatten, self.a_ocr, self.a_move_up,
                  self.a_move_down, self.a_prev, self.a_next, self.a_copy_page_text, self.a_uncrop,
                  self.a_pdfa, self.a_replace, self.a_export_dxf,
                  *self.tool_actions.values()):
            a.setEnabled(has)
        self.a_undo.setEnabled(bool(d and d.can_undo))
        self.a_redo.setEnabled(bool(d and d.can_redo))
        self.a_signatures.setEnabled(bool(d and d.signers))
        self.page_spin.setEnabled(has)
        self.zoom_combo.setEnabled(has)
        self.search_edit.setEnabled(has)
        if has:
            self.page_spin.blockSignals(True)
            self.page_spin.setMaximum(d.page_count)
            self.page_spin.setValue(t.view.current_page + 1)
            self.page_spin.blockSignals(False)
            self.page_total.setText(f" / {d.page_count} ")
            star = "*" if d.modified else ""
            idx = self.tabs.indexOf(t)
            self.tabs.setTabText(idx, star + d.title)
            self.tabs.setTabToolTip(idx, d.path or "Non salvato")
            self.setWindowTitle(f"{star}{d.title} — CRN PDF Studio")
            page = d.page(min(t.view.current_page, d.page_count - 1))
            w_mm, h_mm = page.rect.width * 25.4 / 72, page.rect.height * 25.4 / 72
            lock = "  🔒" if d.encryption else ""
            badges = (f"  PDF/A-{d.pdfa}" if d.pdfa else "") + \
                     (("  ✔ firmato" if all(x.integrity_ok for x in d.signers) else "  ✘ firma non valida")
                      if d.signers else "")
            self.status_info.setText(f"{w_mm:.0f} × {h_mm:.0f} mm   {t.view.zoom * 100:.0f}%{lock}{badges}")
        else:
            self.page_total.setText(" / 0 ")
            self.setWindowTitle("CRN PDF Studio")
            self.status_info.setText("")

    def _on_tab_changed(self, _index: int) -> None:
        t = self.tab()
        if t:
            t.view.set_tool(self._current_tool())
            self._apply_tool_style(t.view)
            self._sync_zoom_combo(t.view.zoom)
        self._update_ui()

    def _current_tool(self) -> str:
        for k, a in self.tool_actions.items():
            if a.isChecked():
                return k
        return V.HAND

    # ================================================================== file
    def new_document(self) -> None:
        dlg = NewDocumentDialog(self)
        if dlg.exec():
            w, h, n = dlg.values()
            self._add_tab(PdfDocument.new(w, h, n))

    def open_dialog(self) -> None:
        start = self.settings.value("last_dir", os.path.expanduser("~"))
        paths, _ = QFileDialog.getOpenFileNames(self, "Apri", start, OPEN_FILTER)
        for p in paths:
            self.open_file(p)

    def open_file(self, path: str) -> None:
        path = os.path.abspath(path)
        # Già aperto? Passa alla scheda
        key = os.path.normcase(path)
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DocumentTab) and w.document.path and \
                    os.path.normcase(os.path.abspath(w.document.path)) == key:
                self.tabs.setCurrentIndex(i)
                return
        if path.lower().endswith((".p7m", ".p7s")):
            self._open_p7m(path)
            return
        try:
            d = PdfDocument.open(path)
        except Exception as exc:
            self._error("Impossibile aprire il file", f"{os.path.basename(path)}:\n{exc}")
            return
        retry = False
        while d.needs_password:
            dlg = PasswordPrompt(os.path.basename(path), self, retry)
            if not dlg.exec():
                d.close()
                return
            if d.authenticate(dlg.pw.text()):
                break
            retry = True
        self.settings.setValue("last_dir", os.path.dirname(path))
        self._add_recent(path)
        self._add_tab(d)

    def _open_p7m(self, path: str) -> None:
        from .p7m import P7MError
        try:
            d, content = PdfDocument.from_p7m(path)
        except P7MError as exc:
            self._error("File firmato non leggibile", f"{os.path.basename(path)}:\n{exc}")
            return
        except Exception as exc:
            self._error("File firmato non leggibile", f"{os.path.basename(path)}:\n{exc}")
            return
        self.settings.setValue("last_dir", os.path.dirname(path))
        self._add_recent(path)
        if d is None:
            # Il contenuto firmato non è un PDF (es. XML, Word): si offre di salvarlo
            SignaturesDialog(content.filename, content.signers, self).exec()
            out, _ = QFileDialog.getSaveFileName(self, "Salva il documento estratto",
                                                 os.path.join(os.path.dirname(path), content.filename))
            if out:
                with open(out, "wb") as f:
                    f.write(content.data)
                QDesktopServices.openUrl(QUrl.fromLocalFile(out))
            return
        self._add_tab(d)
        ok = content.all_ok
        self.statusBar().showMessage(
            f"Documento firmato digitalmente da {', '.join(s.name for s in content.signers)} — "
            + ("firme integre" if ok else "ATTENZIONE: firma non valida"), 10000)
        if not ok:
            SignaturesDialog(content.filename, content.signers, self).exec()

    def show_signatures(self) -> None:
        d = self.doc()
        if d and d.signers:
            SignaturesDialog(d.title, d.signers, self).exec()

    def _add_tab(self, d: PdfDocument) -> None:
        t = DocumentTab(d)
        t.view.pageChanged.connect(lambda _p: self._update_ui())
        t.view.zoomChanged.connect(self._sync_zoom_combo)
        t.view.toolAction.connect(self.on_tool_action)
        t.view.inlineEditFinished.connect(self._inline_edit_done)
        t.thumbs.orderChanged.connect(self.reorder_pages)
        t.thumbs.setContextMenuPolicy(Qt.ActionsContextMenu)
        for a in (self.a_rot_l, self.a_rot_r, self.a_dup, self.a_ins_blank, self.a_ins_file, self.a_extract,
                  self.a_del_page):
            t.thumbs.addAction(a)
        t.thumbs.setVisible(self.a_thumbs.isChecked())
        i = self.tabs.addTab(t, d.title)
        self.tabs.setCurrentIndex(i)
        t.view.setFocus()
        self._apply_tool_style(t.view)
        t.view.set_tool(self._current_tool())
        self._update_ui()

    def create_from_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Scegli le immagini", self.settings.value("last_dir", ""),
                                                IMAGE_FILTER)
        if not paths:
            return
        try:
            self._add_tab(PdfDocument.from_images(sorted(paths) if len(paths) > 1 else paths))
        except Exception as exc:
            self._error("Errore", exc)

    def merge_dialog(self) -> None:
        initial = []
        d = self.doc()
        if d and d.path and not d.modified:
            initial.append(d.path)
        dlg = MergeDialog(self, initial)
        if not dlg.exec() or len(dlg.files()) < 1:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Salva PDF unito", "Unito.pdf", "PDF (*.pdf)")
        if not out:
            return
        try:
            n = merge_files(dlg.files(), out)
        except Exception as exc:
            self._error("Errore durante l'unione", exc)
            return
        self.statusBar().showMessage(f"Creato {os.path.basename(out)} ({n} pagine)", 5000)
        self.open_file(out)

    def save(self) -> bool:
        d = self._require_doc()
        if not d:
            return False
        if not d.path:
            return self.save_as()
        try:
            d.save()
        except Exception as exc:
            self._error("Errore di salvataggio", exc)
            return False
        self.statusBar().showMessage(f"Salvato: {d.path}", 4000)
        self._update_ui()
        return True

    def save_as(self) -> bool:
        d = self._require_doc()
        if not d:
            return False
        start = d.path or os.path.join(self.settings.value("last_dir", os.path.expanduser("~")), d.title)
        path, _ = QFileDialog.getSaveFileName(self, "Salva con nome", start, "PDF (*.pdf)")
        if not path:
            return False
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            d.save(path)
        except Exception as exc:
            self._error("Errore di salvataggio", exc)
            return False
        self._add_recent(path)
        self.settings.setValue("last_dir", os.path.dirname(path))
        self._update_ui()
        return True

    def compress(self) -> None:
        d = self._require_doc()
        if not d:
            return
        dlg = CompressDialog(self)
        if not dlg.exec():
            return
        base = os.path.splitext(d.path or d.title)[0]
        out, _ = QFileDialog.getSaveFileName(self, "Salva copia ridotta", base + "_ridotto.pdf", "PDF (*.pdf)")
        if not out:
            return
        dpi, quality = dlg.settings()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            before, after = d.save_compressed(out, dpi, quality)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._error("Errore", exc)
            return
        QApplication.restoreOverrideCursor()
        perc = 100 * (1 - after / before) if before else 0
        QMessageBox.information(self, "Riduci dimensione",
                                f"Dimensione originale: {before / 1024:.0f} KB\n"
                                f"Nuova dimensione: {after / 1024:.0f} KB\nRiduzione: {perc:.0f}%")

    def export_images(self) -> None:
        d = self._require_doc()
        if not d:
            return
        dlg = ExportImagesDialog(self)
        if not dlg.exec():
            return
        folder = QFileDialog.getExistingDirectory(self, "Cartella di destinazione",
                                                  os.path.dirname(d.path) if d.path else "")
        if not folder:
            return
        pages = self.tab().thumbs.selected_pages() if dlg.only_selected.isChecked() else None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            paths = d.export_images(folder, dlg.dpi.value(), dlg.fmt.currentText(), pages)
        finally:
            QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"Esportate {len(paths)} immagini in {folder}", 5000)

    def export_text(self) -> None:
        d = self._require_doc()
        if not d:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Esporta testo", os.path.splitext(d.title)[0] + ".txt",
                                             "Testo (*.txt)")
        if out:
            d.export_text(out)
            self.statusBar().showMessage(f"Testo esportato in {out}", 5000)

    def export_docx(self) -> None:
        d = self._require_doc()
        if not d:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Esporta in Word", os.path.splitext(d.title)[0] + ".docx",
                                             "Documento Word (*.docx)")
        if not out:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            d.export_docx(out)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._error("Esportazione in Word", exc)
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"Creato {out}", 5000)

    def export_dxf(self) -> None:
        d = self._require_doc()
        if not d:
            return
        from . import dxf_export
        cur = self.tab().view.current_page
        n_vec, n_img = dxf_export.page_vector_stats(d.page(cur))
        if n_vec == 0 and n_img:
            info = ("⚠ La pagina corrente sembra <b>scansionata</b> (solo immagini): non contiene linee "
                    "vettoriali da esportare. Verranno esportati solo eventuali testi.")
        elif n_vec == 0:
            info = "⚠ La pagina corrente non contiene disegni vettoriali."
        else:
            info = f"La pagina corrente contiene <b>{n_vec}</b> tracciati vettoriali."
        dlg = DxfDialog(d.page_count, cur, info, self)
        if not dlg.exec():
            return
        try:
            pages = dlg.page_list()
        except ValueError as exc:
            self._error("Esporta in DXF", exc)
            return
        base = os.path.splitext(d.path or os.path.join(self.settings.value("last_dir", ""), d.title))[0]
        out, _ = QFileDialog.getSaveFileName(self, "Esporta in DXF", base + ".dxf", "Disegno DXF (*.dxf)")
        if not out:
            return
        if not out.lower().endswith(".dxf"):
            out += ".dxf"
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            reports = dxf_export.export(d.doc, pages, out, dlg.options())
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._error("Esporta in DXF", exc)
            return
        QApplication.restoreOverrideCursor()
        tot = lambda attr: sum(getattr(r, attr) for r in reports)
        layers = sorted(set().union(*(r.layers for r in reports)))
        text = (f"Creati {len(reports)} file DXF.\n\n" if len(reports) > 1 else f"Creato {os.path.basename(out)}.\n\n")
        text += (f"Linee e polilinee: {tot('lines')}\nCurve: {tot('curves')}\nCerchi: {tot('circles')}\n"
                 f"Riempimenti: {tot('hatches')}\nTesti: {tot('texts')}\nLayer: {', '.join(layers) or '-'}")
        if any(r.raster_only for r in reports):
            text += "\n\nAttenzione: alcune pagine sono scansionate e non contengono linee vettoriali."
        QMessageBox.information(self, "Esporta in DXF", text)

    def print_document(self) -> None:
        d = self._require_doc()
        if not d:
            return
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        printer = QPrinter(QPrinter.HighResolution)
        printer.setDocName(d.title)
        dlg = QPrintDialog(printer, self)
        dlg.setMinMax(1, d.page_count)
        dlg.setFromTo(1, d.page_count)
        if not dlg.exec():
            return
        first, last = printer.fromPage() or 1, printer.toPage() or d.page_count
        dpi = min(printer.resolution(), 300)
        painter = QPainter()
        if not painter.begin(printer):
            self._error("Stampa", "Impossibile avviare la stampa")
            return
        progress = QProgressDialog("Stampa in corso…", "Annulla", first - 1, last, self)
        progress.setWindowModality(Qt.WindowModal)
        try:
            for i in range(first - 1, last):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                if i > first - 1:
                    printer.newPage()
                pix = d.page(i).get_pixmap(dpi=dpi, annots=True, alpha=False)
                img = V.pixmap_to_qimage(pix)
                area = painter.viewport()
                size = img.size()
                size.scale(area.size(), Qt.KeepAspectRatio)
                painter.setViewport(area.x() + (area.width() - size.width()) // 2,
                                    area.y() + (area.height() - size.height()) // 2,
                                    size.width(), size.height())
                painter.setWindow(img.rect())
                painter.drawImage(0, 0, img)
                painter.setViewport(area)
                painter.setWindow(area)
        finally:
            painter.end()
            progress.close()

    def properties(self) -> None:
        d = self._require_doc()
        if not d:
            return
        size = os.path.getsize(d.path) / 1024 if d.path and os.path.exists(d.path) else 0
        p0 = d.page(0).rect
        info = (f"<small>File: {d.path or '(non salvato)'}<br>Dimensione: {size:.0f} KB<br>"
                f"Pagine: {d.page_count}<br>Formato prima pagina: {p0.width * 25.4 / 72:.0f} × "
                f"{p0.height * 25.4 / 72:.0f} mm<br>Versione PDF: {d.doc.metadata.get('format', '')}<br>"
                f"Moduli compilabili: {'sì' if d.has_forms() else 'no'}<br>"
                f"Protezione: {'sì' if d.encryption else 'no'}</small>")
        dlg = MetadataDialog(d.get_metadata(), info, self)
        if dlg.exec():
            d.set_metadata(dlg.values())
            self._update_ui()

    def security(self) -> None:
        d = self._require_doc()
        if not d:
            return
        dlg = SecurityDialog(self, protected=bool(d.encryption))
        if not dlg.exec():
            return
        d.checkpoint()
        if dlg.remove.isChecked():
            d.encryption = None
            self.statusBar().showMessage("La protezione verrà rimossa al salvataggio", 5000)
        else:
            d.encryption = (dlg.owner.text() or dlg.user.text(), dlg.user.text())
            self.statusBar().showMessage("Il documento verrà protetto al salvataggio", 5000)
        self._update_ui()

    # ------------------------------------------------------------- file recenti
    def _add_recent(self, path: str) -> None:
        recent = [p for p in (self.settings.value("recent") or []) if p != path]
        recent.insert(0, path)
        self.settings.setValue("recent", recent[:10])
        self._update_recent()

    def _update_recent(self) -> None:
        if self.recent_menu is None:
            return
        self.recent_menu.clear()
        recent = self.settings.value("recent") or []
        if isinstance(recent, str):
            recent = [recent]
        for p in recent:
            a = self.recent_menu.addAction(p)
            a.triggered.connect(lambda checked=False, path=p: self.open_file(path))
        self.recent_menu.setEnabled(bool(recent))

    # ================================================================== chiusura
    def _confirm_close(self, t: DocumentTab) -> bool:
        if not t.document.modified:
            return True
        self.tabs.setCurrentWidget(t)
        r = QMessageBox.question(self, "Modifiche non salvate",
                                 f"Salvare le modifiche a «{t.document.title}»?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    def close_tab(self, index: int) -> None:
        w = self.tabs.widget(index)
        if not isinstance(w, DocumentTab) or not self._confirm_close(w):
            return
        self.tabs.removeTab(index)
        w.document.close()
        w.deleteLater()
        self._update_ui()

    def closeEvent(self, event) -> None:
        if self.tray is not None and not self._really_quit and self._keep_in_tray():
            # Resta attivo nell'area di notifica per ricevere le stampe
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("window_state", self.saveState())
            self.hide()
            if not self.settings.value("tray_hint_shown", False, type=bool):
                self.tray.showMessage("CRN PDF Studio", "Il programma resta attivo qui per ricevere le stampe "
                                      "dalla stampante «CRN PDF». Per chiuderlo: clic destro → Esci.",
                                      app_icon(), 8000)
                self.settings.setValue("tray_hint_shown", True)
            event.ignore()
            return
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DocumentTab) and not self._confirm_close(w):
                event.ignore()
                return
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        if self.tray is not None:
            self.tray.hide()
        event.accept()
        QApplication.quit()

    # ------------------------------------------------------------ trascina file
    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        images = [p for p in paths if p.lower().endswith(IMAGE_EXTENSIONS)]
        others = [p for p in paths if p not in images]
        for p in others:
            self.open_file(p)
        if len(images) > 1:
            self._add_tab(PdfDocument.from_images(images))
        elif images:
            self.open_file(images[0])

    # ================================================================== modifica
    def undo(self) -> None:
        d = self.doc()
        if d and d.undo():
            self._changed()

    def redo(self) -> None:
        d = self.doc()
        if d and d.redo():
            self._changed()

    def copy_page_text(self) -> None:
        t = self.tab()
        if t:
            QApplication.clipboard().setText(t.document.page(t.view.current_page).get_text())
            self.statusBar().showMessage("Testo della pagina copiato negli appunti", 3000)

    # ------------------------------------------------------------------ ricerca
    def focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _search_text_changed(self, _text: str) -> None:
        t = self.tab()
        if t:
            t.search_results = []
            t.search_index = -1
            t.view.show_search_results([])
            self.search_label.setText("  ")

    def search_next(self) -> None:
        t = self.tab()
        q = self.search_edit.text().strip()
        if not t or not q:
            return
        if not t.search_results:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            t.search_results = t.document.search(q)
            QApplication.restoreOverrideCursor()
            t.search_index = -1
            if not t.search_results:
                self.search_label.setText("  nessun risultato ")
                return
        back = QApplication.keyboardModifiers() & Qt.ShiftModifier
        t.search_index = (t.search_index + (-1 if back else 1)) % len(t.search_results)
        page, rect = t.search_results[t.search_index]
        t.view.show_search_results(t.search_results, t.search_index)
        t.view.go_to_page(page, rect)
        self.search_label.setText(f"  {t.search_index + 1} di {len(t.search_results)} ")

    # ================================================================ visualizza
    def _zoom(self, factor: float) -> None:
        t = self.tab()
        if t:
            t.view.set_zoom(t.view.zoom * factor)

    def _set_zoom(self, z: float) -> None:
        t = self.tab()
        if t:
            t.view.set_zoom(z)

    def _fit(self, mode: str) -> None:
        t = self.tab()
        if t:
            t.view.set_zoom(t.view.zoom, fit=mode)

    def _zoom_combo_changed(self, *_args) -> None:
        text = self.zoom_combo.currentText()
        if text.startswith("Adatta"):
            self._fit("width")
        elif text.startswith("Pagina"):
            self._fit("page")
        else:
            try:
                self._set_zoom(float(text.replace("%", "").replace(",", ".").strip()) / 100)
            except ValueError:
                pass

    def _sync_zoom_combo(self, zoom: float) -> None:
        t = self.tab()
        if t and t.view.fit_mode == "width":
            txt = "Adatta larghezza"
        elif t and t.view.fit_mode == "page":
            txt = "Pagina intera"
        else:
            txt = f"{zoom * 100:.0f}%"
        self.zoom_combo.setEditText(txt)
        self._update_ui()

    def _goto(self, index: int) -> None:
        t = self.tab()
        if t:
            t.view.go_to_page(index)

    def _goto_rel(self, delta: int) -> None:
        t = self.tab()
        if t:
            t.view.go_to_page(t.view.current_page + delta)

    def toggle_thumbs(self, checked: bool) -> None:
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DocumentTab):
                w.thumbs.setVisible(checked)

    def toggle_fullscreen(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    # =================================================================== pagine
    def _selected(self) -> list[int]:
        t = self.tab()
        if not t:
            return []
        sel = t.thumbs.selected_pages()
        return sel if sel else [t.view.current_page]

    def rotate(self, delta: int) -> None:
        d = self._require_doc()
        if d:
            d.rotate_pages(self._selected(), delta)
            self._changed()

    def delete_pages(self) -> None:
        d = self._require_doc()
        if not d:
            return
        pages = self._selected()
        msg = f"Eliminare la pagina {pages[0] + 1}?" if len(pages) == 1 else f"Eliminare {len(pages)} pagine?"
        if QMessageBox.question(self, "Elimina pagine", msg) != QMessageBox.Yes:
            return
        try:
            d.delete_pages(pages)
        except ValueError as exc:
            self._error("Elimina pagine", exc)
            return
        self._changed()

    def insert_blank(self) -> None:
        d = self._require_doc()
        if d:
            d.insert_blank_page(self.tab().view.current_page + 1)
            self._changed()
            self._goto(self.tab().view.current_page + 1)

    def insert_file(self) -> None:
        d = self._require_doc()
        if not d:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Inserisci da file", self.settings.value("last_dir", ""),
                                                OPEN_FILTER)
        if not paths:
            return
        pos = self.tab().view.current_page + 1
        try:
            for p in paths:
                pos += d.insert_file(p, pos)
        except Exception as exc:
            self._error("Inserimento", exc)
        self._changed()

    def duplicate_page(self) -> None:
        d = self._require_doc()
        if d:
            d.duplicate_page(self.tab().view.current_page)
            self._changed()

    def move_page(self, delta: int) -> None:
        d = self._require_doc()
        if not d:
            return
        cur = self.tab().view.current_page
        new = cur + delta
        if 0 <= new < d.page_count:
            d.move_page(cur, new)
            self._changed()
            self._goto(new)

    def reorder_pages(self, order: list) -> None:
        d = self.doc()
        if d:
            d.reorder(order)
            self._changed()

    def extract_pages(self) -> None:
        d = self._require_doc()
        if not d:
            return
        pages = self._selected()
        text, ok = QInputDialog.getText(self, "Estrai pagine", "Pagine da estrarre (es. 1-3, 5):",
                                        text=", ".join(str(p + 1) for p in pages))
        if not ok:
            return
        from .document import parse_page_ranges
        try:
            ranges = parse_page_ranges(text, d.page_count)
        except ValueError as exc:
            self._error("Estrai pagine", exc)
            return
        indices = [i for a, b in ranges for i in range(a, b + 1)]
        base = os.path.splitext(d.path or d.title)[0]
        out, _ = QFileDialog.getSaveFileName(self, "Salva pagine estratte", base + "_estratto.pdf", "PDF (*.pdf)")
        if out:
            d.extract_pages(indices, out)
            if QMessageBox.question(self, "Estrai pagine", "File creato. Aprirlo ora?") == QMessageBox.Yes:
                self.open_file(out)

    def split_document(self) -> None:
        d = self._require_doc()
        if not d:
            return
        dlg = SplitDialog(d.page_count, self)
        if not dlg.exec():
            return
        try:
            ranges = dlg.ranges_list()
        except ValueError as exc:
            self._error("Dividi", exc)
            return
        folder = QFileDialog.getExistingDirectory(self, "Cartella di destinazione",
                                                  os.path.dirname(d.path) if d.path else "")
        if folder:
            paths = d.split(ranges, folder, os.path.splitext(d.title)[0])
            QMessageBox.information(self, "Dividi", f"Creati {len(paths)} file in:\n{folder}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def uncrop(self) -> None:
        d = self._require_doc()
        if d:
            d.crop_page(self.tab().view.current_page, None)
            self._changed()

    # ================================================================= strumenti
    def watermark(self) -> None:
        d = self._require_doc()
        if not d:
            return
        dlg = WatermarkDialog(self)
        if dlg.exec() and dlg.values()["text"]:
            d.add_watermark(**dlg.values())
            self._changed()

    def page_numbers(self) -> None:
        d = self._require_doc()
        if not d:
            return
        dlg = PageNumbersDialog(self)
        if dlg.exec():
            try:
                d.add_page_numbers(**dlg.values())
            except (KeyError, IndexError, ValueError) as exc:
                self._error("Formato non valido", f"Usare {{n}} e {{tot}}: {exc}")
                return
            self._changed()

    def flatten(self) -> None:
        d = self._require_doc()
        if d and QMessageBox.question(
                self, "Appiattisci", "I commenti e i disegni diventeranno parte delle pagine e non saranno più "
                                     "modificabili. Continuare?") == QMessageBox.Yes:
            d.flatten_annotations()
            self._changed()

    def ocr(self) -> None:
        d = self._require_doc()
        if not d:
            return
        if QMessageBox.question(
                self, "OCR",
                "L'OCR trasforma le pagine in immagini con uno strato di testo ricercabile.\n"
                "È indicato per documenti scansionati. Richiede Tesseract OCR installato "
                "(variabile TESSDATA_PREFIX).\n\nContinuare?") != QMessageBox.Yes:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            d.ocr()
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            d.undo()
            self._error("OCR non riuscito", f"{exc}\n\nVerificare che Tesseract sia installato.")
            return
        QApplication.restoreOverrideCursor()
        self._changed()

    def pick_tool_color(self) -> None:
        c = QColorDialog.getColor(self.tool_color, self, "Colore strumenti")
        if c.isValid():
            self.tool_color = c
            self.settings.setValue("tool_color", c.name())
            self._update_color_button()

    def pick_highlight_color(self) -> None:
        c = QColorDialog.getColor(self.highlight_color, self, "Colore evidenziatore")
        if c.isValid():
            self.highlight_color = c
            self.settings.setValue("highlight_color", c.name())
            self._update_color_button()

    def _width_changed(self, v: int) -> None:
        self.line_width = float(v)
        self.settings.setValue("line_width", self.line_width)
        self._update_color_button()

    def _update_color_button(self) -> None:
        pm = QPixmap(20, 20)
        pm.fill(self.tool_color)
        self.color_btn.setIcon(QIcon(pm))
        t = self.tab()
        if t:
            self._apply_tool_style(t.view)

    def _apply_tool_style(self, view: PageView) -> None:
        view.tool_color = self.tool_color
        view.highlight_color = self.highlight_color
        view.line_width = self.line_width

    def set_tool(self, tool: str) -> None:
        self.tool_actions[tool].setChecked(True)
        t = self.tab()
        if t:
            self._apply_tool_style(t.view)
            t.view.set_tool(tool)
        if tool == V.SIGNATURE and self.signature_png is None:
            self._new_signature()
        tips = {k: tip for k, _l, _g, tip, _s in TOOLS}
        self.statusBar().showMessage(tips.get(tool, ""), 6000)

    def _new_signature(self) -> bool:
        dlg = SignatureDialog(self)
        if dlg.exec():
            png = dlg.png()
            if png:
                self.signature_png = png
                return True
        if self.signature_png is None:
            self.set_tool(V.HAND)
        return False

    def _rgb(self, c: QColor) -> tuple[float, float, float]:
        return (c.redF(), c.greenF(), c.blueF())

    def on_tool_action(self, tool: str, page: int, data) -> None:
        d = self.doc()
        if not d:
            return
        color = self._rgb(self.tool_color)
        width = self.line_width
        changed = True
        try:
            if tool == V.SELECT:
                text = d.text_in_rect(page, data)
                if text:
                    QApplication.clipboard().setText(text)
                    preview = text[:60].replace("\n", " ")
                    self.statusBar().showMessage(f"Copiato negli appunti: «{preview}…»", 5000)
                else:
                    self.statusBar().showMessage("Nessun testo nell'area selezionata", 3000)
                changed = False
            elif tool in (V.HIGHLIGHT, V.UNDERLINE, V.STRIKEOUT):
                kind = {V.HIGHLIGHT: "highlight", V.UNDERLINE: "underline", V.STRIKEOUT: "strikeout"}[tool]
                c = self._rgb(self.highlight_color) if tool == V.HIGHLIGHT else color
                if not d.add_text_markup(page, data, kind, c):
                    if tool == V.HIGHLIGHT and data.width > 4 and data.height > 4:
                        d.add_area_highlight(page, data, c)
                    else:
                        self.statusBar().showMessage("Nessun testo trovato: trascina sopra le parole", 4000)
                        changed = False
            elif tool == V.TEXT:
                dlg = TextDialog(self, color=QColor("black"))
                if dlg.exec() and dlg.values()["text"].strip():
                    v = dlg.values()
                    d.add_text_box(page, data, v["text"], v["fontsize"], v["color"], v["fontname"], v["flatten"],
                                   v["align"])
                else:
                    changed = False
            elif tool == V.EDIT_TEXT:
                block = d.block_at(page, data)
                if block is not None:
                    self.tab().view.start_inline_edit(page, block)
                    msg = "Modifica il testo, poi clicca fuori dal riquadro (Ctrl+Invio) per applicare, Esc per annullare"
                    if block.extra.get("mixed_styles"):
                        msg += " — il paragrafo ha stili misti: verrà usato lo stile prevalente"
                    self.statusBar().showMessage(msg, 15000)
                    return
                tool = "edit_text_dialog"
            if tool == "edit_text_dialog":
                span = d.span_at(page, data)
                if span is None:
                    self.statusBar().showMessage("Nessun testo in questo punto", 3000)
                    changed = False
                else:
                    from .document import guess_base14
                    c = QColor.fromRgbF(*span.color)
                    dlg = TextDialog(self, "Modifica riga di testo", span.text, span.size, c,
                                     guess_base14(span.font, span.flags), show_flatten=False, allow_original=True)
                    if dlg.exec():
                        v = dlg.values()
                        src = d.replace_span(span, v["text"].replace("\n", " "), v["fontsize"], v["color"],
                                             v["fontname"])
                        self._font_message(src)
                    else:
                        changed = False
            elif tool == V.NOTE:
                text, ok = QInputDialog.getMultiLineText(self, "Nota", "Testo della nota:")
                if ok and text.strip():
                    d.add_note(page, data, text)
                else:
                    changed = False
            elif tool in (V.RECT, V.ELLIPSE):
                d.add_shape(page, "rect" if tool == V.RECT else "ellipse", data, color, width)
            elif tool in (V.LINE, V.ARROW):
                d.add_shape(page, tool, None, color, width, start=data[0], end=data[1])
            elif tool == V.INK:
                d.add_ink(page, data, color, width)
            elif tool == V.IMAGE:
                path, _ = QFileDialog.getOpenFileName(self, "Inserisci immagine",
                                                      self.settings.value("last_dir", ""), IMAGE_FILTER)
                if path:
                    d.insert_image(page, data, filename=path)
                else:
                    changed = False
            elif tool == V.SIGNATURE:
                if self.signature_png is None and not self._new_signature():
                    return
                d.insert_image(page, data, stream=self.signature_png)
            elif tool == V.WHITEOUT:
                d.whiteout(page, data)
            elif tool == V.REDACT:
                if QMessageBox.question(self, "Oscura",
                                        "Il contenuto sotto il riquadro verrà rimosso definitivamente "
                                        "(testo e immagini). Continuare?") == QMessageBox.Yes:
                    d.redact(page, data)
                else:
                    changed = False
            elif tool == V.CROP:
                if data.width > 20 and data.height > 20:
                    d.crop_page(page, data)
                    self._changed()
                    return
                changed = False
            elif tool == V.ERASER:
                if not d.delete_annotation_at(page, data):
                    self.statusBar().showMessage("Nessun commento in questo punto", 3000)
                    changed = False
            elif tool == "form":
                dlg = FormFieldDialog(data, self)
                if dlg.exec():
                    d.set_widget_value(page, data.xref, dlg.value())
                else:
                    changed = False
            elif tool == "edit_annot":
                text, ok = QInputDialog.getMultiLineText(self, "Commento", "Testo:", data.info.get("content", ""))
                if ok:
                    d.set_annotation_text(page, data.xref, text)
                else:
                    changed = False
        except Exception as exc:
            self._error("Operazione non riuscita", exc)
            return
        if changed:
            self._changed(full=False, page=page)

    # =========================================================== testo e PDF/A
    def _escape(self) -> None:
        t = self.tab()
        if t and t.view.inline_editing:
            t.view.cancel_inline_edit()
            return
        self.set_tool(V.HAND)

    def _font_message(self, source: str) -> None:
        msg = {"incorporato": "Testo modificato con il font originale del documento",
               "sistema": "Testo modificato con lo stesso font, installato nel sistema",
               "standard": "Font originale non disponibile: usato il font standard più simile"}.get(source)
        if msg:
            self.statusBar().showMessage(msg, 6000)

    def _inline_edit_done(self, page: int, block, text: str) -> None:
        d = self.doc()
        if not d:
            return
        try:
            info = d.replace_block(block, text)
        except Exception as exc:
            self._error("Modifica non riuscita", exc)
            return
        self._changed(full=False, page=page)
        self._font_message(info.get("source", ""))
        if not info.get("fits", True):
            self.statusBar().showMessage("Il testo è più lungo dello spazio disponibile: è stato ridotto", 8000)
        elif info.get("scale", 1) < 0.99:
            self.statusBar().showMessage(f"Testo leggermente ridotto ({info['scale'] * 100:.0f}%) per "
                                         "rientrare nello spazio del paragrafo", 8000)

    def find_replace(self) -> None:
        d = self._require_doc()
        if not d:
            return
        dlg = FindReplaceDialog(self, self.search_edit.text())
        if not dlg.exec() or not dlg.find.text():
            return
        pages = [self.tab().view.current_page] if dlg.current_only.isChecked() else None
        try:
            n = d.find_replace(dlg.find.text(), dlg.replace.text(), pages, dlg.case.isChecked())
        except Exception as exc:
            self._error("Sostituzione non riuscita", exc)
            return
        if n:
            self._changed()
        QMessageBox.information(self, "Trova e sostituisci",
                                f"Sostituzioni effettuate: {n}" if n else "Testo non trovato.")

    def save_pdfa(self) -> None:
        d = self._require_doc()
        if not d:
            return
        from . import pdfa
        if not pdfa.find_ghostscript():
            self._error("PDF/A", "Per creare file PDF/A serve Ghostscript, incluso nell'installer completo di "
                                 "CRN PDF Studio.\nIn alternativa installarlo da https://ghostscript.com/releases/")
            return
        dlg = PdfADialog(self)
        if not dlg.exec():
            return
        base = os.path.splitext(d.path or os.path.join(self.settings.value("last_dir", ""), d.title))[0]
        out, _ = QFileDialog.getSaveFileName(self, "Salva come PDF/A", base + "_pdfa.pdf", "PDF (*.pdf)")
        if not out:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            issues = pdfa.convert_to_pdfa(d.to_bytes(encryption=False), out, dlg.level.currentData(),
                                          d.get_metadata().get("title") or None)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._error("PDF/A", exc)
            return
        QApplication.restoreOverrideCursor()
        part = pdfa.pdfa_part(out) or "?"
        text = f"Creato {os.path.basename(out)} (PDF/A-{part})."
        if issues:
            text += "\n\nAttenzione:\n• " + "\n• ".join(issues)
        box = QMessageBox(QMessageBox.Warning if issues else QMessageBox.Information, "PDF/A", text,
                          QMessageBox.Open | QMessageBox.Close, self)
        box.button(QMessageBox.Open).setText("Apri il file")
        box.button(QMessageBox.Close).setText("Chiudi")
        if box.exec() == QMessageBox.Open:
            self.open_file(out)

    # ===================================================== stampante virtuale
    def _keep_in_tray(self) -> bool:
        return self.settings.value("keep_in_tray", True, type=bool)

    def _create_tray(self) -> None:
        from PySide6.QtWidgets import QMenu, QSystemTrayIcon
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(app_icon(), self)
        tray.setToolTip("CRN PDF Studio — stampante «CRN PDF» pronta")
        menu = QMenu(self)
        menu.addAction("Apri CRN PDF Studio", self.bring_to_front)
        menu.addAction("Apri un PDF…", lambda: (self.bring_to_front(), self.open_dialog()))
        menu.addAction("Cartella delle stampe", self.open_prints_folder)
        menu.addAction("Stampante virtuale…", lambda: (self.bring_to_front(), self.printer_settings()))
        menu.addSeparator()
        menu.addAction("Esci", self.quit_app)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda reason: self.bring_to_front()
                               if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
        tray.messageClicked.connect(self.bring_to_front)
        tray.show()
        self.tray = tray

    def start_print_watcher(self) -> None:
        from .printer import PrintWatcher
        if self.watcher is None:
            self.watcher = PrintWatcher(parent=self)
            self.watcher.pdfReady.connect(self._print_received)
            self.watcher.start()

    def _print_received(self, path: str) -> None:
        self.open_file(path)
        self.bring_to_front()
        if self.tray is not None:
            self.tray.showMessage("Nuovo PDF creato", os.path.basename(path), app_icon(), 4000)

    def bring_to_front(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def open_prints_folder(self) -> None:
        from .printer import output_dir
        os.makedirs(output_dir(), exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(output_dir()))

    def quit_app(self) -> None:
        self._really_quit = True
        if not self.isVisible():
            self.show()
        if not self.close():
            self._really_quit = False

    def printer_settings(self) -> None:
        from .dialogs import PrinterDialog
        PrinterDialog(self.settings, self).exec()

    # ================================================================ Claude
    def _create_assistant(self) -> None:
        from PySide6.QtWidgets import QDockWidget
        from .assistant_panel import AssistantPanel
        self.assistant = AssistantPanel(self.settings, self.doc,
                                        lambda: self.tab().view.current_page if self.tab() else 0)
        self.assistant.documentChanged.connect(lambda _p: self._changed())
        self.assistant.showPage.connect(self._goto)
        dock = QDockWidget("Assistente Claude", self)
        dock.setObjectName("claude")
        dock.setWidget(self.assistant)
        dock.setMinimumWidth(320)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.visibilityChanged.connect(self.a_claude.setChecked)
        dock.hide()
        self.assistant_dock = dock

    def toggle_assistant(self, checked: bool) -> None:
        self.assistant_dock.setVisible(checked)
        if checked:
            self.assistant.input.setFocus()

    def claude_settings(self) -> None:
        self.assistant.open_settings()

    # ==================================================================== info
    def about(self) -> None:
        QMessageBox.about(self, "CRN PDF Studio",
                          f"<h3>CRN PDF Studio {__version__}</h3>"
                          "<p>Lettore ed editor PDF per Windows.</p>"
                          f"<p>Motore: PyMuPDF {pymupdf.VersionBind} / MuPDF {pymupdf.VersionFitz}<br>"
                          "Interfaccia: Qt (PySide6)</p>")
