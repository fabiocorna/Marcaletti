"""Pannello laterale «Assistente Claude»."""
from __future__ import annotations

import html
import json
import os

from PySide6.QtCore import QObject, QSettings, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QTextBrowser,
                               QToolButton, QVBoxLayout, QWidget)

from . import assistant as A

KEYRING_SERVICE = "CRNComputo-Claude"
# La chiave inserita in CRN PDF Studio vale anche qui
OTHER_SERVICES = ("PDFStudio-Claude",)


def load_api_key(settings: QSettings) -> str:
    try:
        import keyring
        for service in (KEYRING_SERVICE,) + OTHER_SERVICES:
            key = keyring.get_password(service, "api_key")
            if key:
                return key
    except Exception:
        pass
    return settings.value("claude/api_key", "") or ""


def save_api_key(settings: QSettings, key: str) -> None:
    try:
        import keyring
        if key:
            keyring.set_password(KEYRING_SERVICE, "api_key", key)
        else:
            try:
                keyring.delete_password(KEYRING_SERVICE, "api_key")
            except Exception:
                pass
        settings.remove("claude/api_key")
        return
    except Exception:
        pass
    # Senza archivio credenziali di sistema: impostazioni utente
    settings.setValue("claude/api_key", key)


class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Impostazioni Claude")
        self.settings = settings
        form = QFormLayout(self)
        form.addRow(QLabel("Per usare l'assistente serve una chiave API di Anthropic.<br>"
                           "Si crea su <a href='https://console.anthropic.com/settings/keys'>"
                           "console.anthropic.com</a> (il consumo è a pagamento, in base all'uso)."))
        self.key = QLineEdit(load_api_key(settings), echoMode=QLineEdit.Password)
        self.key.setPlaceholderText("sk-ant-…")
        show = QCheckBox("Mostra")
        show.toggled.connect(lambda on: self.key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        row = QHBoxLayout()
        row.addWidget(self.key)
        row.addWidget(show)
        form.addRow("Chiave API:", row)
        self.effort = QComboBox()
        for label, value in [("Bassa (più rapido, meno costoso)", "low"), ("Media (consigliato)", "medium"),
                             ("Alta (computi complessi, disegni)", "high")]:
            self.effort.addItem(label, value)
        self.effort.setCurrentIndex(max(0, self.effort.findData(settings.value("claude/effort", "medium"))))
        form.addRow("Livello di ragionamento:", self.effort)
        form.addRow(QLabel("<small>La chiave è salvata nel Gestore credenziali di Windows. Il progetto e gli "
                           "allegati vengono inviati ad Anthropic solo quando usi l'assistente.</small>"))
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        form.addRow(box)
        for lab in self.findChildren(QLabel):
            lab.setOpenExternalLinks(True)
            lab.setWordWrap(True)

    def accept(self) -> None:
        save_api_key(self.settings, self.key.text().strip())
        self.settings.setValue("claude/effort", self.effort.currentData())
        super().accept()


class _Worker(QObject):
    """Esegue una singola chiamata in streaming fuori dal thread dell'interfaccia."""

    text = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, client, kwargs: dict):
        super().__init__()
        self.client = client
        self.kwargs = kwargs
        self.cancelled = False

    def run(self) -> None:
        try:
            with self.client.beta.messages.stream(**self.kwargs) as stream:
                for event in stream:
                    if self.cancelled:
                        break
                    if event.type == "text":
                        self.text.emit(event.text)
                if self.cancelled:
                    self.failed.emit("")
                    return
                message = stream.get_final_message()
            self.done.emit(message)
        except ValueError as exc:
            # Input di uno strumento non interpretabile (eager streaming): si ripete la richiesta
            self.failed.emit(f"__retry__{exc}")
        except Exception as exc:
            self.failed.emit(A.describe_error(exc))


class AssistantPanel(QWidget):
    projectChanged = Signal()
    selectVoce = Signal(int)

    def __init__(self, settings: QSettings, get_doc, get_prezzari, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.get_doc = get_doc
        self.get_prezzari = get_prezzari
        self.conv = A.Conversation()
        self._doc_id = None
        self._doc = None
        self._thread: QThread | None = None
        self._worker: _Worker | None = None
        self._rounds = 0
        self._json_retries = 0
        self._transcript: list[tuple[str, str]] = []  # (ruolo, testo)
        self._streaming = ""
        self._attachments: list[str] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        top = QHBoxLayout()
        self.model = QComboBox()
        for label, mid in A.MODELS.items():
            self.model.addItem(label, mid)
        self.model.setCurrentIndex(max(0, self.model.findData(settings.value("claude/model", A.DEFAULT_MODEL))))
        self.model.currentIndexChanged.connect(lambda: settings.setValue("claude/model", self.model.currentData()))
        top.addWidget(self.model, 1)
        new_btn = QToolButton(text="Nuova")
        new_btn.setToolTip("Nuova conversazione")
        new_btn.clicked.connect(self.new_conversation)
        cfg = QToolButton(text="⚙")
        cfg.setToolTip("Impostazioni Claude (chiave API)")
        cfg.clicked.connect(self.open_settings)
        top.addWidget(new_btn)
        top.addWidget(cfg)
        lay.addLayout(top)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        lay.addWidget(self.view, 1)

        self.status = QLabel()
        self.status.setStyleSheet("color:#666")
        lay.addWidget(self.status)

        att = QHBoxLayout()
        self.attach_label = QLabel()
        self.attach_label.setWordWrap(True)
        self.attach_label.setStyleSheet("color:#1f3b63")
        att.addWidget(self.attach_label, 1)
        self.clear_att = QToolButton(text="✕")
        self.clear_att.setToolTip("Togli gli allegati")
        self.clear_att.clicked.connect(self.clear_attachments)
        att.addWidget(self.clear_att)
        lay.addLayout(att)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("Chiedi a Claude di computare, cercare voci, controllare…\n"
                                      "(Ctrl+Invio per inviare)")
        self.input.setMaximumHeight(110)
        lay.addWidget(self.input)
        QShortcut(QKeySequence("Ctrl+Return"), self.input, activated=self.send)
        QShortcut(QKeySequence("Ctrl+Enter"), self.input, activated=self.send)

        row = QHBoxLayout()
        attach = QPushButton("📎 Allega")
        attach.setToolTip("Allega disegni, piante, relazioni (PDF o immagini) da cui ricavare le misure")
        attach.clicked.connect(self.pick_attachments)
        row.addWidget(attach)
        quick = QPushButton("Azioni rapide ▾")
        menu = QMenu(quick)
        for label, prompt in A.QUICK_PROMPTS.items():
            menu.addAction(label, lambda p=prompt: self.send(p))
        quick.setMenu(menu)
        row.addWidget(quick)
        row.addStretch()
        self.stop_btn = QPushButton("Interrompi")
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setVisible(False)
        self.send_btn = QPushButton("Invia")
        self.send_btn.setDefault(True)
        self.send_btn.clicked.connect(lambda: self.send())
        row.addWidget(self.stop_btn)
        row.addWidget(self.send_btn)
        lay.addLayout(row)
        self._update_attachments()
        self._render()

    @property
    def busy(self) -> bool:
        return self._thread is not None

    # ------------------------------------------------------------- interfaccia
    def open_settings(self) -> None:
        SettingsDialog(self.settings, self).exec()
        self._render()

    def new_conversation(self) -> None:
        self.stop()
        self.conv.reset()
        self._transcript.clear()
        self._render()

    def pick_attachments(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Allega disegni o documenti",
                                                self.settings.value("dir/attach", ""),
                                                "PDF e immagini (*.pdf *.png *.jpg *.jpeg *.gif *.webp)")
        if files:
            self.settings.setValue("dir/attach", os.path.dirname(files[0]))
            self.add_attachments(files)

    def add_attachments(self, files: list[str]) -> None:
        for f in files:
            if f not in self._attachments:
                self._attachments.append(f)
        self._update_attachments()

    def clear_attachments(self) -> None:
        self._attachments.clear()
        self._update_attachments()

    def _update_attachments(self) -> None:
        names = ", ".join(os.path.basename(f) for f in self._attachments)
        self.attach_label.setText(f"📎 {names}" if names else "")
        self.attach_label.setVisible(bool(names))
        self.clear_att.setVisible(bool(names))

    def _render(self) -> None:
        if not self._transcript and not self._streaming:
            if A.has_api_key(load_api_key(self.settings)):
                intro = ("<p style='color:#555'>Chiedi a Claude di <b>impostare i capitoli</b>, <b>cercare "
                         "voci</b> nei prezzari, <b>inserire misure</b> o <b>controllare</b> il computo. "
                         "Con <b>📎 Allega</b> puoi dargli piante e sezioni da cui ricavare le quantità."
                         "<br><br>Esempi:<br>"
                         "• «Crea i capitoli per una ristrutturazione di un bagno»<br>"
                         "• «Aggiungi l'intonaco civile per le pareti di una stanza 4×5 m, h 2,70, "
                         "con una porta 80×210»<br>"
                         "• «Dalla pianta allegata computa i massetti e i pavimenti»<br>"
                         "• «Imposta spese tecniche al 10% con IVA 22% e imprevisti al 5%»</p>")
            else:
                intro = ("<p>Per usare l'assistente inserisci la tua chiave API di Anthropic con il pulsante "
                         "<b>⚙</b> in alto.</p>")
            self.view.setHtml(intro)
            return
        parts = []
        for role, text in self._transcript:
            if role == "user":
                parts.append(f"<div style='background:#e8f0fe;padding:6px;margin:6px 0;border-radius:6px'>"
                             f"<b>Tu:</b> {html.escape(text).replace(chr(10), '<br>')}</div>")
            elif role == "tool":
                parts.append(f"<div style='color:#555;font-size:small;margin:2px 0'>{html.escape(text)}</div>")
            elif role == "error":
                parts.append(f"<div style='color:#b00020;margin:4px 0'>{html.escape(text)}</div>")
            else:
                parts.append(f"<div style='margin:6px 0'>{_markdown_to_html(text)}</div>")
        if self._streaming:
            parts.append(f"<div style='margin:6px 0'>{_markdown_to_html(self._streaming)}▌</div>")
        self.view.setHtml("".join(parts))
        self.view.moveCursor(QTextCursor.End)

    def _busy(self, busy: bool, status: str = "") -> None:
        self.send_btn.setEnabled(not busy)
        self.stop_btn.setVisible(busy)
        self.input.setReadOnly(busy)
        self.status.setText(status)

    # ------------------------------------------------------------ conversazione
    def send(self, text: str | None = None) -> None:
        if self._thread is not None:
            return
        text = (text or self.input.toPlainText()).strip()
        if not text:
            return
        key = load_api_key(self.settings)
        if not A.has_api_key(key):
            self.open_settings()
            key = load_api_key(self.settings)
            if not A.has_api_key(key):
                return
        doc = self.get_doc()
        if self._doc_id != id(doc):
            # Progetto diverso: nuova conversazione
            self.conv.reset()
            self._doc_id = id(doc)
        self.conv.model = self.model.currentData()
        self.conv.effort = self.settings.value("claude/effort", "medium")
        try:
            self.conv.add_user_message(text, self._attachments)
        except (OSError, ValueError) as exc:
            self._transcript.append(("error", str(exc)))
            self._render()
            return
        names = ", ".join(os.path.basename(f) for f in self._attachments)
        self.input.clear()
        self._transcript.append(("user", text + (f"\n📎 {names}" if names else "")))
        self.clear_attachments()
        self._doc = doc
        doc.begin_group("Modifiche dell'assistente")
        self._client = A.make_client(key or None)
        self._rounds = 0
        self._json_retries = 0
        self._step()

    def _step(self) -> None:
        self._rounds += 1
        if self._rounds > A.MAX_TOOL_ROUNDS:
            self._transcript.append(("error", "Interrotto: troppe operazioni consecutive."))
            self._finish()
            return
        self._busy(True, "Claude sta lavorando…")
        self._streaming = ""
        self._render()
        self._thread = QThread(self)
        self._worker = _Worker(self._client, self.conv.request_kwargs())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.text.connect(self._on_text)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        # Il worker viene distrutto nel suo thread quando questo termina
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
            self._thread.deleteLater()
        self._thread = None
        self._worker = None

    def _on_text(self, chunk: str) -> None:
        self._streaming += chunk
        self._render()

    def _on_failed(self, message: str) -> None:
        self._cleanup_thread()
        if message.startswith("__retry__") and self._json_retries < 2:
            self._json_retries += 1
            self._step()
            return
        if message:
            self._transcript.append(("error", message.replace("__retry__", "Risposta non valida: ")))
        # Il messaggio dell'utente resta nella cronologia solo se ha avuto risposta
        if self.conv.messages and self.conv.messages[-1]["role"] == "user" and \
                not any(isinstance(b, dict) and b.get("type") == "tool_result"
                        for b in self.conv.messages[-1]["content"]):
            self.conv.messages.pop()
        self._finish()

    def _on_done(self, message) -> None:
        self._cleanup_thread()
        self._json_retries = 0
        if self._streaming.strip():
            self._transcript.append(("assistant", self._streaming))
        self._streaming = ""
        # La risposta va rimandata intatta (inclusi blocchi di ragionamento e fallback)
        self.conv.messages.append({"role": "assistant", "content": message.content})
        if message.stop_reason == "refusal":
            self._transcript.append(("error", "Claude ha rifiutato questa richiesta."))
            self._finish()
            return
        tool_uses = [b for b in message.content if b.type == "tool_use"]
        if message.stop_reason == "max_tokens":
            self._transcript.append(("error", "Risposta interrotta perché troppo lunga."))
            if tool_uses:  # input probabilmente troncato: non si eseguono gli strumenti
                self.conv.messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                     "content": "Input troncato: operazione non eseguita."} for b in tool_uses]})
            self._finish()
            return
        if message.stop_reason == "pause_turn":
            self._step()
            return
        if not tool_uses:
            self._finish()
            return
        tools = A.ProjectTools(self._doc, self.get_prezzari())
        results, changed, select = [], False, None
        for b in tool_uses:
            error = A.validate_input(b.name, b.input)
            if error:
                results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                                "content": json.dumps({"INVALID_JSON": str(b.input), "errore": error},
                                                      ensure_ascii=False)})
                continue
            out = tools.run(b.name, b.input)
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": out.text,
                            **({"is_error": True} if out.is_error else {})})
            if out.summary:
                self._transcript.append(("tool", out.summary))
            changed = changed or out.changed
            if out.select is not None:
                select = out.select
        self.conv.messages.append({"role": "user", "content": results})
        if changed:
            self.projectChanged.emit()
        if select is not None:
            self.selectVoce.emit(select)
        self._step()

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancelled = True
            self.status.setText("Interruzione…")

    def _finish(self) -> None:
        if self._doc is not None:
            self._doc.end_group()
            self._doc = None
        self._streaming = ""
        self._busy(False)
        self._render()
        self.projectChanged.emit()


def _markdown_to_html(text: str) -> str:
    from PySide6.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setMarkdown(text)
    body = doc.toHtml()
    start, end = body.find("<body"), body.rfind("</body>")
    if start >= 0 and end > start:
        body = body[body.find(">", start) + 1:end]
    return body
