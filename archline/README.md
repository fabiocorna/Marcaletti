# Reverse engineering di ARCHLine.XP

Cartella di lavoro per l'analisi di **ARCHLine.XP** (CAD architettonico di CadLine)
con lo strumento **REA – Reverse Engineer Anything** (`rea-agents`, MIT).

## Scopo e limiti

Obiettivo: **interoperabilità**. Capire il formato dei file di progetto e il
comportamento del programma per poterli leggere o convertire (es. verso DXF/IFC),
e documentare i risultati con le prove a supporto.

Fuori ambito, non si fa:

- aggirare licenza, attivazione, dongle o altre protezioni;
- riprodurre codice o asset protetti del programma;
- qualunque uso vietato dalla licenza d'uso di ARCHLine.XP o dalla legge.

Lo stesso progetto REA esclude questi usi (vedi il suo `DISCLAIMER.md`).

## Struttura

```
archline/
├── README.md        questo file
├── binari/          .exe/.dll dell'installazione (NON versionati)
├── esempi/          file di progetto di esempio (NON versionati: dati reali)
├── analisi/         output di REA e note di analisi (versionati)
└── tools/           script propri (versionati)
```

## Leggere un `.pro`

`tools/leggi_pro.py` (Python 3.10+, solo libreria standard) legge indice,
layer, disegni, materiali e intestazioni dei `.asc`. Formato: `analisi/02-formato-pro.md`.

```
python tools/leggi_pro.py progetto.pro                riepilogo
python tools/leggi_pro.py progetto.pro --json         tutto in JSON
python tools/leggi_pro.py progetto.pro --estrai DIR   estrae il contenuto
```

Il file originale viene solo letto, mai modificato.

## Convertire un progetto per CRN-BIM

`tools/converti_pro.py` scrive un DXF per ogni disegno 2D (linee, polilinee, archi,
cerchi, ellissi, testi, sui layer di ArchLine), più `progetto.json` e l'anteprima.
Il DXF si apre in CRN-BIM con **Importa DWG**: i muri si generano dal layer "Murature".
Formato: `analisi/03-formato-asc.md`.

```
python tools/converti_pro.py progetto.pro            cartella <progetto>_crnbim
python tools/leggi_asc.py progetto.pro --dxf pianta.dxf   solo la pianta principale
```

`binari/` ed `esempi/` sono esclusi da git: contengono software proprietario
e possibili dati di commesse reali.

## Come si usa REA qui

REA è installato in una cartella temporanea fuori dal repository. I comandi tipici:

```
# panoramica di una cartella/app installata
rea analyze /percorso/archline/binari --json

# ispezione di un singolo binario (header, tipo, marcatori)
rea inspect /percorso/archline/binari/ARCHLine.exe --json

# inventario dei tipi .NET (se presenti assembly gestiti)
rea compare-managed-members ...   # vedi `rea --help`
```

La decompilazione del codice nativo (pseudocodice/assembly) richiede un motore
esterno: Ghidra, Hopper o IDA. In questo ambiente non è ancora installato.

## Stato

- [x] Contenitore `.pro` (ZIP), indice XML, layer, materiali — `analisi/02-formato-pro.md`
- [x] Lettore Python `tools/leggi_pro.py`, verificato su 87 progetti reali
- [x] Struttura dei `.asc` 2D e geometria di base (linee, polilinee, archi, ellissi) → DXF
- [x] Testi (tipo 9) nei `.asc` → DXF TEXT — `analisi/03-formato-asc.md` §3.1
- [x] Layer dei `.asc` (tag 8) e convertitore `tools/converti_pro.py`, provato in CRN-BIM 0.78
- [ ] Geometria di quote, blocchi, retini nei `.asc`
- [ ] `.pro` di formato vecchio (non ZIP)
- [ ] Viste 3D (`CadLn3D`) e `.3as`
- [x] Panoramica statica dei binari 2026 con REA — `analisi/04-panoramica-binari-2026.md`
