"""Crea file PDF/A di esempio (usato in CI per la validazione con veraPDF).

Uso: python tests/make_pdfa_samples.py <cartella_output>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf  # noqa: E402

from pdfstudio import pdfa  # noqa: E402
from pdfstudio.document import PdfDocument  # noqa: E402


def build(transparency: bool = True) -> PdfDocument:
    d = PdfDocument.new(pages=2)
    p = d.page(0)
    p.insert_text((72, 90), "Relazione tecnica - prova PDF/A", fontsize=18)
    d.add_text_box(0, pymupdf.Rect(72, 120, 520, 300),
                   "Testo aggiunto con CRN PDF Studio: àèìòù €. " * 6, fontsize=11)
    d.add_note(0, pymupdf.Point(400, 90), "Nota di prova")
    d.add_shape(0, "rect", pymupdf.Rect(72, 320, 300, 400), color=(1, 0, 0))
    d.add_ink(0, [[(80, 450), (150, 500), (220, 440)]])
    d.add_page_numbers()
    if transparency:  # non ammessa in PDF/A-1
        d.add_watermark("BOZZA")
        d.add_text_markup(0, d.page(0).search_for("Relazione")[0])
    blk = d.block_at(0, pymupdf.Point(80, 125))
    if blk:
        d.replace_block(blk, blk.text.replace("prova", "verifica"))
    return d


def main(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for level in (1, 2, 3):
        d = build(transparency=level > 1)
        out = os.path.join(out_dir, f"sample_pdfa{level}.pdf")
        issues = pdfa.convert_to_pdfa(d.to_bytes(), out, level)
        print(out, pdfa.pdfa_part(out), issues)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "pdfa_samples")
