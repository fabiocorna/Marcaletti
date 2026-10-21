import pymupdf
import pytest

from pdfstudio import pdfa
from pdfstudio.document import PdfDocument

pytestmark = pytest.mark.skipif(pdfa.find_ghostscript() is None, reason="Ghostscript non installato")


def sample():
    d = PdfDocument.new()
    d.page(0).insert_text((72, 100), "Relazione tecnica", fontsize=16)
    d.add_note(0, pymupdf.Point(300, 100), "nota")
    d.add_shape(0, "rect", pymupdf.Rect(100, 200, 300, 300))
    return d


@pytest.mark.parametrize("level", [2, 3])
def test_convert(tmp_path, level):
    out = str(tmp_path / f"a{level}.pdf")
    issues = pdfa.convert_to_pdfa(sample().to_bytes(), out, level)
    assert issues == []
    assert pdfa.pdfa_part(out) == f"{level}B"
    doc = pymupdf.open(out)
    assert "Relazione tecnica" in doc[0].get_text()
    assert len(list(doc[0].annots())) == 2


def test_pdfa1_flags_rasterized_pages(tmp_path):
    d = sample()
    d.add_text_markup(0, d.page(0).search_for("Relazione")[0])  # trasparenza
    out = str(tmp_path / "a1.pdf")
    issues = pdfa.convert_to_pdfa(d.to_bytes(), out, 1)
    assert pdfa.pdfa_part(out) == "1B"
    assert any("PDF/A-2b" in i for i in issues)


def test_encrypted_refused(tmp_path):
    d = sample()
    d.encryption = ("a", "b")
    with pytest.raises(pdfa.PdfAError):
        pdfa.convert_to_pdfa(d.to_bytes(), str(tmp_path / "x.pdf"), 2)


def test_check_detects_plain_pdf():
    issues = pdfa.check_pdfa(sample().to_bytes())
    assert any("XMP" in i for i in issues)
