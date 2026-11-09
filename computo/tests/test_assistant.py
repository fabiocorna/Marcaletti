import json
from decimal import Decimal as D

from crncomputo import assistant as A
from crncomputo.model import ProgettoDoc
from crncomputo.prezzario import Prezzario, VocePrezzario


def prezzari():
    return [Prezzario("Regione 2026", voci=[
        VocePrezzario("1C.07.010", "Intonaco civile per interni su pareti", "m²", D("21.40"), D("55")),
        VocePrezzario("1C.02.050", "Scavo di sbancamento con mezzi meccanici", "m³", D("6.85")),
    ])]


def misura(desc, parti="", l="", w="", h="", ded=False):
    return {"descrizione": desc, "parti": parti, "lunghezza": l, "larghezza": w, "altezza": h, "deduzione": ded}


def test_schemi_strict():
    for t in A.TOOLS:
        s = t["input_schema"]
        assert t["strict"] and s["additionalProperties"] is False
        assert set(s["required"]) == set(s["properties"])


def test_validazione():
    ok = {"capitolo_id": 0, "codice_articolo": "X", "misure": [misura("a", "1")], "nota": ""}
    assert A.validate_input("aggiungi_voce", ok) is None
    bad = dict(ok, misure=[{"descrizione": "a"}])
    assert "mancante" in A.validate_input("aggiungi_voce", bad)
    assert A.validate_input("aggiungi_voce", dict(ok, capitolo_id="1")) is not None
    assert A.validate_input("imposta_dato_generale", {"campo": "colore", "valore": "x"}) is not None
    assert A.validate_input("boh", {}) is not None


def test_flusso_strumenti():
    doc = ProgettoDoc()
    tools = A.ProjectTools(doc, prezzari())
    doc.begin_group("Modifiche dell'assistente")
    res = tools.run("cerca_prezzario", {"testo": "intonaco", "max_risultati": 5})
    assert json.loads(res.text)["risultati"][0]["codice"] == "1C.07.010"
    cap = json.loads(tools.run("aggiungi_capitolo", {"titolo": "Finiture", "codice": "B",
                                                     "capitolo_padre_id": 0}).text)["capitolo_id"]
    out = tools.run("aggiungi_voce", {"capitolo_id": cap, "codice_articolo": "1C.07.010", "nota": "",
                                      "misure": [misura("Parete nord", "", "5", "", "2,70"),
                                                 misura("Finestra", "", "1,2", "", "1,4", True)]})
    assert out.changed and not out.is_error, out.text
    assert json.loads(out.text) == {"numero_voce": 1, "quantita": "11,82", "importo": "252,95"}
    assert doc.p.articoli["1C.07.010"].fonte == "Regione 2026"
    # codice inesistente: errore senza modifiche
    out = tools.run("aggiungi_voce", {"capitolo_id": cap, "codice_articolo": "ZZZ", "nota": "",
                                      "misure": []})
    assert out.is_error and len(doc.p.voci) == 1
    out = tools.run("crea_nuovo_prezzo", {"codice": "NP.01", "descrizione": "Smontaggio caldaia", "um": "cad",
                                          "prezzo": 180.0, "manodopera_pct": 80, "sicurezza": False})
    assert not out.is_error
    tools.run("aggiungi_voce", {"capitolo_id": 0, "codice_articolo": "NP.01", "nota": "",
                                "misure": [misura("Caldaia esistente", "1")]})
    assert doc.p.numero(doc.p.voci[1]) == 1          # fuori capitolo: diventa la n. 1
    out = tools.run("modifica_misura", {"numero_voce": 2, "riga": 1,
                                        "misura": misura("Parete nord", "2", "5", "", "2,70")})
    assert json.loads(out.text)["quantita"] == "25,32"
    assert tools.run("modifica_misura", {"numero_voce": 2, "riga": 9,
                                         "misura": misura("x")}).is_error
    data = json.loads(tools.run("elenca_voci", {"capitolo_id": cap}).text)
    assert len(data) == 1 and data[0]["misure"][1]["deduzione"] is True
    tools.run("imposta_quadro_economico", {"iva_lavori_pct": 22, "sicurezza_modo": "percentuale",
                                           "sicurezza_valore": 2, "ribasso_pct": 0})
    tools.run("imposta_somme_a_disposizione", {"somme": [{"descrizione": "Imprevisti", "modo": "percentuale",
                                                          "valore": 5, "iva_pct": 0}]})
    info = json.loads(tools.run("leggi_progetto", {}).text)
    assert info["capitoli"][0]["titolo"] == "Finiture" and info["voci_totali"] == 2
    assert tools.run("elimina_voci", {"numeri_voce": [1]}).changed
    doc.end_group()
    # tutte le modifiche dell'assistente si annullano con un solo passo
    assert doc.undo_label() == "Modifiche dell'assistente"
    doc.undo()
    assert not doc.p.voci and not doc.p.capitoli and not doc.can_undo


def test_richiesta_e_allegati(tmp_path):
    img = tmp_path / "pianta.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
    conv = A.Conversation()
    conv.add_user_message("Computa la pianta", [str(img)])
    content = conv.messages[0]["content"]
    assert content[0]["type"] == "image" and content[0]["cache_control"]["type"] == "ephemeral"
    assert content[1] == {"type": "text", "text": "Computa la pianta"}
    kw = conv.request_kwargs()
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default"
    assert kw["output_config"] == {"effort": "medium"}
    conv.model = "claude-haiku-5-5"
    assert "fallbacks" not in conv.request_kwargs()
    bad = tmp_path / "x.docx"
    bad.write_bytes(b"x")
    try:
        conv.add_user_message("x", [str(bad)])
        raise AssertionError("allegato non valido accettato")
    except ValueError:
        pass
