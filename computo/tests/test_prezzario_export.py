from decimal import Decimal as D

import openpyxl
import pytest

from crncomputo import export as E
from crncomputo import prezzario as PZ
from tests.test_model import progetto_esempio


def test_xlsx_con_gruppi(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Prezzario Regionale 2026"])
    ws.append([])
    ws.append(["Codice", "Descrizione", "U.M.", "Prezzo €", "% Manodopera"])
    ws.append(["1C.02", "Scavi", None, None, None])
    ws.append(["1C.02.050", "Scavo di sbancamento con mezzi meccanici", None, None, None])
    ws.append(["1C.02.050.0010", "in terreno di qualsiasi natura", "m³", 6.85, 0.32])
    ws.append(["1C.02.050.0020", "in roccia", "m³", "45,10", 28])
    ws.append(["1C.07", "Intonaci", None, None, None])
    ws.append(["1C.07.010.0010", "Intonaco civile per interni", "m²", 21.4, None])
    path = tmp_path / "prezzario.xlsx"
    wb.save(path)
    pz = PZ.load_any(str(path))
    assert pz.nome == "prezzario" and len(pz.voci) == 3
    v = pz.get("1C.02.050.0010")
    assert v.descrizione == "Scavi – Scavo di sbancamento con mezzi meccanici – in terreno di qualsiasi natura"
    assert v.prezzo == D("6.85") and v.um == "m³" and v.manodopera_pct == D("32.00")
    assert pz.get("1C.02.050.0020").prezzo == D("45.10")
    assert pz.get("1C.07.010.0010").descrizione.startswith("Intonaci – ")
    # ricerca senza accenti e con varianti
    assert [x.codice for x in pz.search("sbancamento roccia")] == ["1C.02.050.0020"]
    assert pz.search("intonaci civili")[0].codice == "1C.07.010.0010"
    assert pz.search("1C.02")[0].codice.startswith("1C.02")


def test_csv(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text("Tariffa;Descrizione;UM;Prezzo\nE.01;Muratura in mattoni pieni;m³;310,00\n", encoding="cp1252")
    pz = PZ.load_any(str(path))
    assert pz.voci[0].prezzo == D("310.00")


def test_six(tmp_path):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<PRT:Prezzario xmlns:PRT="six.xsd">
  <PRT:intestazione titolo="Prezzario prova"/>
  <PRT:unitaDiMisura unitaDiMisuraId="1" simbolo="m²"/>
  <PRT:gruppo grpValore="01"><PRT:grpDescrizione lingua="it" breve="Opere murarie"/></PRT:gruppo>
  <PRT:prodotto prdId="10" voce="01.A01.005" unitaDiMisuraId="1">
    <PRT:prdDescrizione lingua="it" breve="Tramezza" estesa="Tramezza in laterizio forato sp. 8 cm"/>
    <PRT:prdGrpValore grpValore="01"/>
    <PRT:prdQuotazione listaQuotazioneId="1" valore="38.20"/>
  </PRT:prodotto>
  <PRT:prodotto prdId="11" voce="01.A01.010"><PRT:prdDescrizione breve="Senza prezzo"/></PRT:prodotto>
</PRT:Prezzario>"""
    path = tmp_path / "six.xml"
    path.write_text(xml, encoding="utf-8")
    pz = PZ.load_any(str(path))
    assert pz.nome == "Prezzario prova" and len(pz.voci) == 1
    v = pz.voci[0]
    assert (v.codice, v.um, v.prezzo) == ("01.A01.005", "m²", D("38.20"))
    assert v.descrizione == "Opere murarie – Tramezza in laterizio forato sp. 8 cm"


def test_errori_importazione(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("a;b\n1;2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        PZ.load_any(str(path))
    with pytest.raises(ValueError):
        PZ.load_any(str(tmp_path / "x.xls"))


def test_libreria(tmp_path):
    lib = PZ.Libreria(str(tmp_path / "lib"))
    lib.add(PZ.Prezzario("Lombardia 2026", voci=[PZ.VocePrezzario("A", "Voce «A»", "m", D("1.5"))]))
    assert lib.nomi() == ["Lombardia 2026"]
    lib2 = PZ.Libreria(str(tmp_path / "lib"))
    assert lib2.get("Lombardia 2026").voci[0].prezzo == D("1.5")
    lib2.remove("Lombardia 2026")
    assert lib2.nomi() == []


def test_in_lettere():
    assert E.in_lettere(21) == "ventuno"
    assert E.in_lettere(108) == "centotto"
    assert E.in_lettere(180) == "centottanta"
    assert E.in_lettere(1234) == "milleduecentotrentaquattro"
    assert E.in_lettere(23000) == "ventitrémila"
    assert E.in_lettere(2_500_000) == "duemilionicinquecentomila"
    assert E.prezzo_in_lettere(D("12.34")) == "euro dodici/34"


def test_stampe(tmp_path):
    import pymupdf  # noqa: F401  (solo se disponibile)
    doc = progetto_esempio()
    for fn, name in ((E.export_computo_pdf, "c.pdf"), (E.export_elenco_prezzi_pdf, "e.pdf"),
                     (E.export_quadro_pdf, "q.pdf")):
        fn(doc.p, str(tmp_path / name))
    text = "".join(pg.get_text() for pg in pymupdf.open(str(tmp_path / "c.pdf")))
    assert "SOMMANO m²" in text and "1.517,96" in text and "Totale Opere edili" in text
    assert "euro dodici/50" in pymupdf.open(str(tmp_path / "e.pdf"))[0].get_text()
    assert "TOTALE GENERALE" in pymupdf.open(str(tmp_path / "q.pdf"))[0].get_text()
    E.export_xlsx(doc.p, str(tmp_path / "c.xlsx"))
    wb = openpyxl.load_workbook(tmp_path / "c.xlsx")
    assert wb.sheetnames == ["Computo", "Elenco prezzi", "Quadro economico"]
    values = [c.value for row in wb["Computo"].iter_rows() for c in row]
    assert 1517.96 in values
