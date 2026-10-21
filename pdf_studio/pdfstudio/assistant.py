"""Assistente Claude: strumenti sul documento e ciclo di conversazione (senza Qt).

Claude legge il PDF (allegato come documento e/o tramite strumenti di lettura) e può
modificarlo con gli strumenti definiti qui. Ogni modifica passa dal modello
``PdfDocument`` e quindi si può annullare con Ctrl+Z.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field

import anthropic
import pymupdf

from .document import PdfDocument

MODELS = {
    "Claude Opus 5.5 — massima qualità": "claude-opus-5-5",
    "Claude Sonnet 5.5 — veloce": "claude-sonnet-5-5",
    "Claude Haiku 5.5 — economico": "claude-haiku-5-5",
}
DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOOL_ROUNDS = 25
# Limiti dell'API per i PDF allegati come documento
PDF_MAX_BYTES = 30 * 1024 * 1024
PDF_MAX_PAGES = 600

QUICK_PROMPTS = {
    "Riassumi il documento": "Fammi un riassunto chiaro e strutturato di questo documento.",
    "Estrai i dati principali": "Estrai in una tabella i dati principali del documento (nomi, date, importi, "
                                "indirizzi, codici, valori numerici rilevanti).",
    "Controlla errori e refusi": "Rileggi il documento e segnala errori di battitura, incoerenze e dati "
                                 "mancanti, indicando la pagina. Non modificare nulla.",
    "Correggi i refusi": "Correggi direttamente nel documento i refusi evidenti, poi elencami le modifiche.",
    "Evidenzia i punti chiave": "Evidenzia nel documento le frasi più importanti (massimo 10).",
    "Compila il modulo": "Elenca i campi del modulo e chiedimi i valori da inserire.",
    "Traduci in inglese": "Traduci in inglese il testo della pagina corrente, mostrando la traduzione qui.",
}

SYSTEM_PROMPT = """Sei l'assistente integrato in PDF Studio, un editor PDF per Windows usato in uno studio \
tecnico italiano. Rispondi in italiano, in modo conciso e pratico.

Hai a disposizione strumenti per leggere e modificare il PDF aperto. Indicazioni:
- Il PDF allegato all'inizio della conversazione mostra il documento com'era in quel momento; dopo le \
modifiche usa read_pages per vedere lo stato aggiornato.
- Modifica il documento solo quando l'utente lo chiede o lo approva esplicitamente. Per domande, analisi e \
riassunti rispondi senza toccare il file.
- Per correzioni brevi (parole, numeri, date, nomi) usa replace_text; per riscrivere un intero paragrafo \
usa rewrite_paragraph, che mantiene font e impaginazione. Il testo da cercare deve essere copiato \
esattamente dal documento.
- I numeri di pagina negli strumenti partono da 1.
- Dopo una modifica descrivi in breve cosa hai cambiato: l'utente può annullare con Ctrl+Z.
- Se un'operazione non riesce, spiega il motivo invece di riprovare all'infinito."""


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "eager_input_streaming": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False,
        },
    }


_PAGE = {"type": "integer", "description": "Numero di pagina, a partire da 1"}
TOOLS = [
    _tool("get_document_info", "Informazioni sul documento: titolo, numero di pagine, pagina visualizzata, "
                               "metadati e presenza di campi modulo.", {}),
    _tool("read_pages", "Legge il testo attuale (dopo eventuali modifiche) di un intervallo di pagine.",
          {"start_page": _PAGE, "end_page": _PAGE}),
    _tool("search_text", "Cerca un testo nel documento e restituisce le pagine e il contesto di ogni occorrenza.",
          {"query": {"type": "string"}}),
    _tool("replace_text", "Sostituisce un testo esistente mantenendo font, dimensione e colore. Adatto a parole, "
                          "numeri, date e frasi brevi all'interno di una riga.",
          {"find": {"type": "string", "description": "Testo esatto da cercare"},
           "replace_with": {"type": "string"},
           "page": {"type": "integer", "description": "Pagina (da 1) oppure 0 per tutto il documento"}}),
    _tool("rewrite_paragraph", "Riscrive un intero paragrafo con a capo automatico, mantenendo stile e "
                               "allineamento. Identifica il paragrafo con le sue prime parole.",
          {"page": _PAGE,
           "paragraph_start": {"type": "string", "description": "Le prime parole del paragrafo, copiate esatte"},
           "new_text": {"type": "string", "description": "Testo completo del nuovo paragrafo"}}),
    _tool("add_highlight", "Evidenzia un testo in una pagina.",
          {"page": _PAGE, "text": {"type": "string"},
           "color": {"type": "string", "enum": ["giallo", "verde", "rosso", "azzurro"]}}),
    _tool("add_comment", "Aggiunge una nota (commento adesivo) vicino a un testo della pagina.",
          {"page": _PAGE, "near_text": {"type": "string", "description": "Testo accanto a cui mettere la nota; "
                                                                       "stringa vuota per l'angolo in alto"},
           "comment": {"type": "string"}}),
    _tool("add_text", "Scrive testo nuovo in una posizione della pagina (misure in millimetri dall'angolo in "
                      "alto a sinistra).",
          {"page": _PAGE, "x_mm": {"type": "number"}, "y_mm": {"type": "number"},
           "text": {"type": "string"}, "font_size": {"type": "number"}}),
    _tool("list_form_fields", "Elenca i campi del modulo PDF con nome, tipo, valore attuale e opzioni.", {}),
    _tool("fill_form_field", "Compila un campo del modulo PDF. Per le caselle di controllo usare 'si' o 'no'.",
          {"name": {"type": "string"}, "value": {"type": "string"}}),
    _tool("go_to_page", "Mostra all'utente una pagina del documento.", {"page": _PAGE}),
    _tool("rotate_pages", "Ruota pagine in senso orario.",
          {"pages": {"type": "array", "items": {"type": "integer"}},
           "degrees": {"type": "integer", "enum": [90, 180, 270]}}),
    _tool("delete_pages", "Elimina pagine dal documento.",
          {"pages": {"type": "array", "items": {"type": "integer"}}}),
]
_TOOL_SCHEMAS = {t["name"]: t["input_schema"] for t in TOOLS}
_COLORS = {"giallo": (1, 0.92, 0), "verde": (0.5, 1, 0.4), "rosso": (1, 0.45, 0.45), "azzurro": (0.5, 0.8, 1)}
_TYPES = {"string": str, "integer": int, "number": (int, float), "array": list, "boolean": bool}


def validate_input(name: str, data) -> str | None:
    """Controllo dello schema (con l'eager streaming l'API non valida gli input)."""
    schema = _TOOL_SCHEMAS.get(name)
    if schema is None:
        return f"strumento sconosciuto: {name}"
    if not isinstance(data, dict):
        return "input non valido"
    for key in schema["required"]:
        if key not in data:
            return f"parametro mancante: {key}"
    for key, value in data.items():
        prop = schema["properties"].get(key)
        if prop is None:
            return f"parametro non previsto: {key}"
        expected = _TYPES[prop["type"]]
        if isinstance(value, bool) and prop["type"] in ("integer", "number"):
            return f"tipo errato per {key}"
        if not isinstance(value, expected):
            return f"tipo errato per {key}"
        if "enum" in prop and value not in prop["enum"]:
            return f"valore non ammesso per {key}"
    return None


@dataclass
class ToolOutcome:
    text: str
    changed: bool = False
    page: int | None = None      # pagina da mostrare (base 0)
    summary: str = ""            # riga mostrata nella chat
    is_error: bool = False


class DocumentTools:
    def __init__(self, document: PdfDocument, current_page: int = 0):
        self.d = document
        self.current_page = current_page

    def _page(self, n: int) -> int:
        if not 1 <= n <= self.d.page_count:
            raise ValueError(f"pagina {n} inesistente (il documento ha {self.d.page_count} pagine)")
        return n - 1

    def run(self, name: str, data: dict) -> ToolOutcome:
        try:
            return getattr(self, "t_" + name)(**data)
        except Exception as exc:
            return ToolOutcome(f"Errore: {exc}", is_error=True, summary=f"⚠ {name}: {exc}")

    # ---------------------------------------------------------------- lettura
    def t_get_document_info(self) -> ToolOutcome:
        meta = {k: v for k, v in self.d.get_metadata().items() if v}
        info = {"titolo_file": self.d.title, "pagine": self.d.page_count,
                "pagina_visualizzata": self.current_page + 1, "metadati": meta,
                "campi_modulo": self.d.has_forms(),
                "formato_prima_pagina_mm": [round(self.d.page(0).rect.width * 25.4 / 72),
                                            round(self.d.page(0).rect.height * 25.4 / 72)]}
        return ToolOutcome(json.dumps(info, ensure_ascii=False))

    def t_read_pages(self, start_page: int, end_page: int) -> ToolOutcome:
        a, b = self._page(start_page), self._page(min(max(end_page, start_page), self.d.page_count))
        b = min(b, a + 29)
        parts, total = [], 0
        for i in range(a, b + 1):
            t = self.d.page(i).get_text("text", sort=True).strip()
            parts.append(f"=== Pagina {i + 1} ===\n{t or '(nessun testo: pagina vuota o scansionata)'}")
            total += len(t)
            if total > 120_000:
                parts.append(f"(interrotto: testo troppo lungo, continuare dalla pagina {i + 2})")
                break
        return ToolOutcome("\n\n".join(parts), summary=f"📖 Letto pagine {start_page}–{b + 1}")

    def t_search_text(self, query: str) -> ToolOutcome:
        hits = []
        for i in range(self.d.page_count):
            page = self.d.page(i)
            for r in page.search_for(query)[:20]:
                ctx = page.get_text("text", clip=pymupdf.Rect(page.rect.x0, r.y0 - 2, page.rect.x1, r.y1 + 2))
                hits.append({"pagina": i + 1, "riga": " ".join(ctx.split())[:200]})
            if len(hits) > 100:
                break
        return ToolOutcome(json.dumps({"occorrenze": len(hits), "risultati": hits}, ensure_ascii=False),
                           summary=f"🔍 Cercato «{query}»: {len(hits)} risultati")

    def t_list_form_fields(self) -> ToolOutcome:
        fields = []
        for i in range(self.d.page_count):
            for w in self.d.page(i).widgets() or []:
                fields.append({"nome": w.field_name, "tipo": w.field_type_string, "valore": w.field_value,
                               "pagina": i + 1, "etichetta": w.field_label or "",
                               "opzioni": w.choice_values or []})
        return ToolOutcome(json.dumps(fields, ensure_ascii=False, default=str) if fields else
                           "Il documento non contiene campi modulo.")

    # -------------------------------------------------------------- modifiche
    def t_replace_text(self, find: str, replace_with: str, page: int) -> ToolOutcome:
        pages = None if page == 0 else [self._page(page)]
        n = self.d.find_replace(find, replace_with, pages)
        if not n:
            return ToolOutcome(f"Testo «{find}» non trovato. Usa search_text per verificare la forma esatta.",
                               is_error=True, summary=f"⚠ «{find}» non trovato")
        first = next((i for i in (pages or range(self.d.page_count)) if self.d.page(i).search_for(replace_with)),
                     None)
        return ToolOutcome(f"Sostituite {n} occorrenze.", changed=True, page=first,
                           summary=f"✏ «{find}» → «{replace_with}» ({n})")

    def t_rewrite_paragraph(self, page: int, paragraph_start: str, new_text: str) -> ToolOutcome:
        p = self._page(page)
        hits = self.d.page(p).search_for(paragraph_start.strip()[:60]) or \
            self.d.page(p).search_for(" ".join(paragraph_start.split()[:4]))
        if not hits:
            return ToolOutcome(f"Paragrafo che inizia con «{paragraph_start}» non trovato a pagina {page}.",
                               is_error=True, summary="⚠ Paragrafo non trovato")
        r = hits[0]
        block = self.d.block_at(p, pymupdf.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
        if block is None:
            return ToolOutcome("Il testo trovato non appartiene a un paragrafo modificabile.", is_error=True)
        info = self.d.replace_block(block, new_text)
        note = "" if info.get("fits", True) else " (il testo non entrava: riduci la lunghezza)"
        return ToolOutcome(f"Paragrafo riscritto con font {info['font']} ({info['source']}){note}.",
                           changed=True, page=p, summary=f"✏ Riscritto paragrafo a pagina {page}")

    def t_add_highlight(self, page: int, text: str, color: str) -> ToolOutcome:
        p = self._page(page)
        hits = self.d.page(p).search_for(text)
        if not hits:
            return ToolOutcome(f"Testo non trovato a pagina {page}.", is_error=True,
                               summary=f"⚠ «{text[:40]}» non trovato")
        rect = hits[0]
        for h in hits[1:]:
            rect |= h
        self.d.add_text_markup(p, rect, "highlight", _COLORS[color])
        return ToolOutcome("Evidenziato.", changed=True, page=p, summary=f"🖍 Evidenziato «{text[:50]}»")

    def t_add_comment(self, page: int, near_text: str, comment: str) -> ToolOutcome:
        p = self._page(page)
        point = pymupdf.Point(20, 20)
        if near_text:
            hits = self.d.page(p).search_for(near_text)
            if hits:
                point = pymupdf.Point(hits[0].x1 + 4, hits[0].y0)
        self.d.add_note(p, point, comment)
        return ToolOutcome("Nota aggiunta.", changed=True, page=p, summary=f"💬 Nota a pagina {page}")

    def t_add_text(self, page: int, x_mm: float, y_mm: float, text: str, font_size: float) -> ToolOutcome:
        p = self._page(page)
        pg = self.d.page(p)
        x, y = x_mm * 72 / 25.4, y_mm * 72 / 25.4
        vis = pymupdf.Rect(x, y, min(pg.rect.x1 - 10, x + 400), y + font_size * (text.count("\n") + 3))
        self.d.add_text_box(p, vis * pg.derotation_matrix, text, fontsize=max(4, min(font_size, 72)))
        return ToolOutcome("Testo aggiunto.", changed=True, page=p, summary=f"🅣 Testo aggiunto a pagina {page}")

    def t_fill_form_field(self, name: str, value: str) -> ToolOutcome:
        for i in range(self.d.page_count):
            for w in self.d.page(i).widgets() or []:
                if w.field_name == name:
                    v = value
                    if w.field_type in (pymupdf.PDF_WIDGET_TYPE_CHECKBOX, pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON):
                        v = w.on_state() if value.strip().lower() in ("si", "sì", "yes", "true", "1", "x") \
                            else "Off"
                    self.d.set_widget_value(i, w.xref, v)
                    return ToolOutcome("Campo compilato.", changed=True, page=i,
                                       summary=f"☑ {name} = {value}")
        return ToolOutcome(f"Campo «{name}» inesistente.", is_error=True, summary=f"⚠ Campo «{name}» inesistente")

    def t_go_to_page(self, page: int) -> ToolOutcome:
        return ToolOutcome("Fatto.", page=self._page(page))

    def t_rotate_pages(self, pages: list, degrees: int) -> ToolOutcome:
        idx = [self._page(p) for p in pages]
        self.d.rotate_pages(idx, degrees)
        return ToolOutcome("Pagine ruotate.", changed=True, page=idx[0] if idx else None,
                           summary=f"⟳ Ruotate pagine {', '.join(map(str, pages))}")

    def t_delete_pages(self, pages: list) -> ToolOutcome:
        idx = [self._page(p) for p in pages]
        self.d.delete_pages(idx)
        return ToolOutcome("Pagine eliminate.", changed=True,
                           summary=f"🗑 Eliminate pagine {', '.join(map(str, pages))}")


# ------------------------------------------------------------------ conversazione
@dataclass
class Conversation:
    model: str = DEFAULT_MODEL
    effort: str = "medium"
    messages: list = field(default_factory=list)
    attach_pdf: bool = True
    pdf_attached: bool = False

    def reset(self) -> None:
        self.messages.clear()
        self.pdf_attached = False

    def add_user_message(self, text: str, document: PdfDocument | None) -> str | None:
        """Aggiunge il messaggio; al primo turno allega il PDF. Ritorna un avviso, se serve."""
        content: list = []
        warning = None
        if document is not None and self.attach_pdf and not self.pdf_attached:
            data = document.to_bytes(garbage=3, encryption=False)
            if len(data) <= PDF_MAX_BYTES and document.page_count <= PDF_MAX_PAGES:
                content.append({
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf",
                               "data": base64.standard_b64encode(data).decode("ascii")},
                    "title": document.title,
                    "cache_control": {"type": "ephemeral"},
                })
            else:
                warning = ("Documento troppo grande per essere allegato: Claude lo leggerà "
                           "tramite il testo delle pagine.")
            self.pdf_attached = True
        content.append({"type": "text", "text": text})
        self.messages.append({"role": "user", "content": content})
        return warning

    def request_kwargs(self) -> dict:
        kwargs = dict(
            model=self.model,
            max_tokens=16000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=self.messages,
            output_config={"effort": self.effort},
        )
        # Fallback automatico lato server in caso di rifiuto (non disponibile su Haiku)
        if not self.model.startswith("claude-haiku"):
            kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        return kwargs


def make_client(api_key: str | None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


def describe_error(exc: Exception) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "Chiave API non valida. Controllala in Impostazioni Claude."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "La chiave API non ha i permessi necessari per questo modello."
    if isinstance(exc, anthropic.RateLimitError):
        return "Troppe richieste in poco tempo: riprova tra qualche secondo."
    if isinstance(exc, anthropic.BadRequestError):
        return f"Richiesta non accettata: {exc.message}"
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code >= 500:
            return f"Servizio Claude temporaneamente non disponibile ({exc.status_code}). Riprova più tardi."
        return f"Errore dal servizio Claude: {exc.message}"
    if isinstance(exc, anthropic.APIConnectionError):
        return "Impossibile collegarsi a Claude: controlla la connessione internet."
    return f"Errore: {exc}"


def has_api_key(stored: str | None) -> bool:
    return bool(stored or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
