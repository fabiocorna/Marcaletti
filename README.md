# Marcaletti — preparazione dati per APE in Lombardia (CENED+2.0)

Strumento per preparare, calcolare e trasferire in **CENED+2.0** i dati di un Attestato di
Prestazione Energetica, come fanno i software commerciali (Termolog, Edilclima, Namirial Termo…).

In Lombardia l'APE va **calcolato dal motore regionale CENED+2.0** e depositato al Catasto
Energetico (CEER). Questo progetto quindi **non sostituisce** CENED: prepara i dati
(involucro, strutture, serramenti, ponti termici), li verifica con un pre-calcolo UNI/TS 11300-1
e genera un XML da importare con *File > Importa file XML* di CENED+2.0, dove il certificatore
completa, calcola e deposita. Dettagli in [docs/ROADMAP.md](docs/ROADMAP.md).

## Uso

```
python -m cened calcola progetti/esempio_appartamento.toml
python -m cened scheda  progetti/esempio_appartamento.toml -o scheda.md
python -m cened xml     progetti/esempio_appartamento.toml --modello esempi/calcolo.xml -o import.xml
python -m cened leggi   esempi/calcolo.xml [--json]
python -m unittest discover tests
```

Serve solo Python 3.11+ (nessuna dipendenza esterna).

- `calcola`: U delle strutture (UNI EN ISO 6946), U_w serramenti (UNI EN ISO 10077-1),
  H_tr, H_ve, H'_T, fabbisogno mensile Q_H,nd ed EP_H,nd (UNI/TS 11300-1).
- `scheda`: scheda di compilazione in Markdown, nell'ordine delle maschere CENED, con
  stratigrafie, pre-calcolo e **registro di tutte le ipotesi/default applicati**.
- `xml`: XML di input per CENED+2.0 costruito su un `calcolo.xml` esportato da CENED
  (il "modello"), di cui riusa i codici validi. Blocchi calcolati e firma vengono tolti:
  li rigenera CENED.
- `leggi`: analisi di un export CENED esistente (vedi [docs/ANALISI_XML_CENED.md](docs/ANALISI_XML_CENED.md)).

## Struttura

| File | Contenuto |
|---|---|
| `cened/materiali.py` | libreria materiali (valori indicativi), intercapedini d'aria |
| `cened/involucro.py` | strutture opache, serramenti, ponti termici, ZNC |
| `cened/modello.py` | clima, stagione di riscaldamento (DPR 412/93), zona, dispersioni |
| `cened/bilancio.py` | bilancio mensile UNI/TS 11300-1 |
| `cened/progetto.py` | lettura del progetto TOML e registro ipotesi |
| `cened/scheda.py` | scheda di compilazione |
| `cened/esporta_xml.py` | generatore XML per l'import in CENED+2.0 |
| `progetti/` | progetti di esempio (formato di input) |
| `esempi/` | export reali CENED (**esclusi da git**: contengono dati personali) |
