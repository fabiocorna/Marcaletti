from decimal import Decimal as D

import pytest

from crncomputo.model import Articolo, Misura, Progetto, ProgettoDoc, SommaDisposizione
from crncomputo.numeri import FormulaError, evaluate, fmt, to_decimal


def test_formule():
    assert evaluate("3,20+0,15") == D("3.35")
    assert evaluate("2*(4,5+3)") == D("15.0")
    assert evaluate("2x3") == D("6")
    assert evaluate("1.234,5") == D("1234.5")
    assert evaluate("12.5/2") == D("6.25")
    assert evaluate("-2") == D("-2")
    assert evaluate("2^2") == D("4")
    assert evaluate("") is None and evaluate("  ") is None
    for bad in ("abc", "__import__('os')", "1/0", "2**100", "(1"):
        with pytest.raises(FormulaError):
            evaluate(bad)


def test_formato_italiano():
    assert fmt(D("1234567.891")) == "1.234.567,89"
    assert fmt(D("0.005")) == "0,01"
    assert to_decimal("€ 1.234,50") == D("1234.50")


def progetto_esempio() -> ProgettoDoc:
    doc = ProgettoDoc()
    doc.set_articolo(Articolo("A.01", "Scavo di sbancamento", "m³", D("12.50"), D("40")))
    doc.set_articolo(Articolo("B.01", "Intonaco civile", "m²", D("18.30")))
    doc.set_articolo(Articolo("S.01", "Recinzione di cantiere", "m", D("10"), sicurezza=True))
    cap = doc.add_capitolo("Opere edili")
    sub = doc.add_capitolo("Intonaci", parent=cap.id)
    doc.add_voce("A.01", cap.id, [Misura("Scavo", "", "10", "5", "1,5")])
    doc.add_voce("B.01", sub.id, [Misura("Pareti", "2", "4,20", "", "2,70"),
                                  Misura("Porta", "1", "0,90", "", "2,10", deduzione=True)])
    doc.add_voce("S.01", None, [Misura("Lato strada", "", "20")])
    return doc


def test_importi_e_numerazione():
    doc = progetto_esempio()
    p = doc.p
    scavo, intonaco, recinzione = p.voci
    assert scavo.quantita() == D("75.00")
    assert p.importo(scavo) == D("937.50")
    assert intonaco.quantita() == D("20.79")          # 22,68 − 1,89
    assert p.importo(intonaco) == D("380.46")
    # le voci fuori capitolo vengono prima
    assert p.numero(recinzione) == 1 and p.numero(scavo) == 2 and p.numero(intonaco) == 3
    cap = p.capitoli[0]
    assert p.totale_capitolo(cap.id) == D("1317.96")
    assert p.totale_voci() == D("1517.96")
    assert p.totale_manodopera() == D("375.00")


def test_quadro_economico():
    doc = progetto_esempio()
    doc.set_quadro(iva_lavori_pct="10", ribasso_pct="5")
    doc.set_somme([SommaDisposizione("Spese tecniche", "percentuale", D("8"), D("22")),
                   SommaDisposizione("Imprevisti", "importo", D("100"))])
    q = doc.p.quadro_economico()
    assert q["oneri_sicurezza"] == D("200.00")
    assert q["lavori_soggetti_ribasso"] == D("1317.96")
    assert q["totale_lavori"] == D("1517.96")
    assert q["ribasso"] == D("65.90")
    tecniche = D("121.44")
    assert [r["importo"] for r in q["somme_disposizione"]] == [D("151.80"), tecniche, D("26.72"), D("100.00")]
    assert q["totale_generale"] == D("1517.96") + D("151.80") + tecniche + D("26.72") + D("100")
    doc.set_quadro(sicurezza_modo="percentuale", sicurezza_valore="3")
    assert doc.p.quadro_economico()["oneri_sicurezza"] == D("200") + D("39.54")


def test_annulla_ripeti_e_salvataggio(tmp_path):
    doc = progetto_esempio()
    totale = doc.p.totale_voci()
    vid = doc.p.voci[0].id
    doc.update_misura(vid, 0, lunghezza="20")
    assert doc.p.totale_voci() == totale + D("937.50")
    doc.undo()
    assert doc.p.totale_voci() == totale
    doc.redo()
    doc.undo()
    with pytest.raises(FormulaError):
        doc.update_misura(vid, 0, lunghezza="10+")
    path = str(tmp_path / "prova.crcm")
    doc.save(path)
    again = ProgettoDoc.open(path)
    assert again.p.totale_voci() == totale
    assert again.p.numero(again.p.voci[2]) == 1
    assert again.p.articoli["S.01"].sicurezza


def test_eliminazioni():
    doc = progetto_esempio()
    with pytest.raises(ValueError):
        doc.delete_articolo("A.01")
    cap = doc.p.capitoli[0]
    assert doc.delete_capitolo(cap.id) == 2
    assert len(doc.p.voci) == 1 and not doc.p.capitoli
    doc.delete_articolo("A.01")
    dup = doc.duplicate_voce(doc.p.voci[0].id)
    assert doc.p.importo(dup) == D("200.00")


def test_from_dict_rifiuta_altri_file():
    with pytest.raises(ValueError):
        Progetto.from_dict({"formato": "altro"})
