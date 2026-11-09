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
└── analisi/         output di REA e note di analisi (versionati)
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

- [ ] Caricare i binari di ARCHLine.XP in `binari/`
- [ ] Caricare qualche progetto di esempio in `esempi/`
- [ ] Panoramica con `rea analyze`
- [ ] Analisi del formato di progetto
- [ ] Documentare in `analisi/`
