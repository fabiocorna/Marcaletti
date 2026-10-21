import os
from types import SimpleNamespace as NS

import pymupdf
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pdfstudio import assistant as A
from pdfstudio.document import PdfDocument


def sample(tmp_path=None):
    d = PdfDocument.new(pages=2)
    d.page(0).insert_text((72, 100), "Scadenza pratica: 31/12/2024", fontsize=12)
    d.page(1).insert_text((72, 100), "Il tecnico incaricato è Mario Rossi.", fontsize=12)
    return d


def test_tools_schema_is_strict():
    for t in A.TOOLS:
        schema = t["input_schema"]
        assert t["strict"] and schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


def test_validate_input():
    assert A.validate_input("read_pages", {"start_page": 1, "end_page": 2}) is None
    assert A.validate_input("read_pages", {"start_page": 1}) is not None
    assert A.validate_input("read_pages", {"start_page": "1", "end_page": 2}) is not None
    assert A.validate_input("add_highlight", {"page": 1, "text": "x", "color": "viola"}) is not None
    assert A.validate_input("nope", {}) is not None


def test_document_tools():
    d = sample()
    tools = A.DocumentTools(d)
    assert "31/12/2024" in tools.run("read_pages", {"start_page": 1, "end_page": 2}).text
    res = tools.run("search_text", {"query": "Mario Rossi"})
    assert '"pagina": 2' in res.text
    out = tools.run("replace_text", {"find": "2024", "replace_with": "2025", "page": 0})
    assert out.changed and "31/12/2025" in d.page(0).get_text()
    out = tools.run("add_highlight", {"page": 2, "text": "Mario Rossi", "color": "giallo"})
    assert out.changed and len(list(d.page(1).annots())) == 1
    out = tools.run("add_comment", {"page": 1, "near_text": "Scadenza", "comment": "Verificare"})
    assert out.changed
    out = tools.run("read_pages", {"start_page": 5, "end_page": 6})
    assert out.is_error
    out = tools.run("replace_text", {"find": "inesistente", "replace_with": "x", "page": 0})
    assert out.is_error and not out.changed
    # Tutto annullabile
    while d.can_undo:
        d.undo()
    assert "31/12/2024" in d.page(0).get_text()


def test_request_kwargs_and_pdf_attachment():
    d = sample()
    conv = A.Conversation(model="claude-opus-5-5")
    assert conv.add_user_message("Riassumi", d) is None
    first = conv.messages[0]["content"]
    assert first[0]["type"] == "document" and first[0]["cache_control"] == {"type": "ephemeral"}
    conv.add_user_message("Altro", d)
    assert conv.messages[1]["content"][0]["type"] == "text"  # PDF allegato una sola volta
    kw = conv.request_kwargs()
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default"
    assert kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in kw and kw["output_config"] == {"effort": "medium"}
    conv.model = "claude-haiku-5-5"
    assert "fallbacks" not in conv.request_kwargs()


# ---------------------------------------------------------------- ciclo completo
class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for b in self.message.content:
            if b.type == "text":
                yield NS(type="text", text=b.text)

    def get_final_message(self):
        return self.message


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.beta = NS(messages=NS(stream=self._stream))

    def _stream(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return FakeStream(self.replies.pop(0))


def test_panel_tool_loop(monkeypatch):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    app = QApplication.instance() or QApplication([])
    from pdfstudio import assistant_panel as P

    d = sample()
    replies = [
        NS(stop_reason="tool_use", content=[
            NS(type="text", text="Correggo la data."),
            NS(type="tool_use", id="t1", name="replace_text",
               input={"find": "31/12/2024", "replace_with": "30/06/2025", "page": 1})]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="Fatto: data aggiornata.")]),
    ]
    fake = FakeClient(replies)
    monkeypatch.setattr(A, "make_client", lambda key: fake)
    monkeypatch.setattr(P, "load_api_key", lambda s: "sk-test")
    settings = QSettings("PDFStudioTest", "test")
    settings.clear()
    changed = []
    panel = P.AssistantPanel(settings, lambda: d, lambda: 0)
    panel.documentChanged.connect(lambda p: changed.append(p))
    panel.send("Aggiorna la scadenza al 30/06/2025")
    for _ in range(100):
        QTest.qWait(30)
        if panel._thread is None and not fake.replies:
            break
    assert "30/06/2025" in d.page(0).get_text()
    assert changed
    # Secondo turno: la cronologia contiene il risultato dello strumento
    second = fake.requests[1]["messages"]
    assert second[-1]["role"] == "user" and second[-1]["content"][0]["type"] == "tool_result"
    assert ("assistant", "Fatto: data aggiornata.") in panel._transcript
    panel.deleteLater()
    QTest.qWait(50)
