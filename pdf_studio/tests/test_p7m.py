import pymupdf
import pytest
from cryptography.hazmat.primitives import serialization

from pdfstudio.document import PdfDocument
from pdfstudio.p7m import P7MError, read_p7m
from tests.p7m_helpers import make_cert, sign


def pdf_bytes(text="Documento firmato"):
    d = pymupdf.open()
    d.new_page().insert_text((72, 72), text)
    return d.tobytes()


def test_single_signature():
    data = pdf_bytes()
    r = read_p7m(sign(data), "pratica.pdf.p7m")
    assert r.filename == "pratica.pdf" and r.is_pdf and r.data == data
    s = r.signers[0]
    assert s.integrity_ok and s.name == "Mario Rossi" and s.fiscal_code == "RSSMRA80A01H501U"
    assert s.signing_time is not None and s.cert_valid_at_signing


def test_nested_and_ec_signature():
    data = pdf_bytes()
    cert, key = make_cert("Luigi Bianchi", "BNCLGU70B02F205X", "ec")
    r = read_p7m(sign(sign(data), cert, key), "a.pdf.p7m.p7m")
    assert r.data == data and r.filename == "a.pdf"
    assert [s.name for s in r.signers] == ["Luigi Bianchi", "Mario Rossi"]
    assert r.all_ok


def test_pem_and_base64():
    data = pdf_bytes()
    pem = sign(data, encoding=serialization.Encoding.PEM)
    assert read_p7m(pem, "x.p7m").all_ok
    import base64
    b64 = base64.encodebytes(sign(data))
    assert read_p7m(b64, "x.p7m").data == data


def test_tampered_content_detected():
    raw = bytearray(sign(pdf_bytes()))
    i = raw.find(b"%%EOF")  # modifica un byte del PDF contenuto nella busta
    raw[i - 3] ^= 1
    r = read_p7m(bytes(raw), "x.pdf.p7m")
    assert not r.all_ok and "modificato" in r.signers[0].error


def test_not_a_p7m():
    with pytest.raises(P7MError):
        read_p7m(b"ciao mondo", "x.p7m")


def test_open_as_document(tmp_path):
    path = tmp_path / "relazione.pdf.p7m"
    path.write_bytes(sign(pdf_bytes()))
    d, content = PdfDocument.from_p7m(str(path))
    assert d.page_count == 1 and d.title == "relazione.pdf" and d.path is None
    assert d.signers and d.signers[0].integrity_ok


def test_non_pdf_content(tmp_path):
    path = tmp_path / "fattura.xml.p7m"
    path.write_bytes(sign(b"<FatturaElettronica/>"))
    d, content = PdfDocument.from_p7m(str(path))
    assert d is None and content.filename == "fattura.xml" and content.data == b"<FatturaElettronica/>"
