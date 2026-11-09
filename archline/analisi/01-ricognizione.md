# ARCHLine.XP — ricognizione iniziale

Analisi di **ARCHLine.XP 2021** (CadLine), Release v210521, build 342, Windows x64.
Obiettivo: interoperabilità per CRN-BIM (leggere/convertire i progetti, capire il
comportamento). Nessun aggiramento di licenza o protezione.

Questa prima fase è stata ricavata **senza scaricare binari**, da artefatti di testo
(un crash log) e dall'elenco dei file di una commessa reale. I file originali
(installer, `.pro`, `.environment`) restano fuori dal repository.

## 1. Architettura del programma (da ERRORLOG.TXT / crash)

- Eseguibile principale: **`ARCHlineXP2021.bin`** in `C:\Program Files\ARCHline.XP 2021\`.
  Non è un `.exe`: il `.bin` è il vero binario, lanciato da un wrapper **`kamu.exe`**.
- Codice **nativo C++**, compilato con **Visual Studio 2010** (runtime MSVCR100/MSVCP100),
  architettura **x64**. Gestore dei crash in `Archline.cpp` (`ArchlineCrashHandler`).
- Rendering **DirectX 11**.
- Librerie di terze parti caricate, rilevanti per i formati:
  | DLL | Libreria | Implicazione |
  |---|---|---|
  | `xerces-c_3_1.dll` | Apache Xerces-C++ 3.1.1 | ArchLine legge/scrive **XML** |
  | `compressx64.dll` | zlib 1.2.7 | dati **compressi con zlib/deflate** |
- Nomi di simboli interni visibili nel dump: oggetto progetto con prefisso `axp`
  (ArchLine XP), più `act2D`, `ndb2dDynArr` (database 2D dinamico), `modify_index`,
  `hPatts` (hatch/retini). Utili come mappa concettuale del modello dati.

## 2. Formato dei file di progetto

- Estensione progetto: **`.pro`** (osservati da 4,5 MB a 253 MB nella stessa commessa).
- File di backup: **`.bak`**.
- Ipotesi forte (da Xerces + zlib): il `.pro` è un **contenitore XML compresso con zlib**
  — da confermare leggendo i primi byte (una firma zlib inizia tipicamente con `0x78`).

### 2.1 Conferme da un secondo crash (commessa FC1162, 2026)

- Stessa versione in uso in più commesse: **2021 build 342** (non 2026).
- Crash avvenuto durante un comando **`import dwg`**, con modulo in errore
  `xerces-c_3_1.dll`: anche l'import DWG passa dallo strato XML/Xerces.
- Stato interno al crash: `axpPro.act2D.ndb2dDynArr: 25429` (25.429 entità nel
  database 2D), a conferma che `act2D` è il contenitore della grafica 2D.
- Attenzione metodologica: i crash log elencano solo i moduli **vicini al punto
  di errore**, non l'elenco completo delle DLL caricate.

## 3. Interoperabilità già disponibile (senza reverse engineering)

Nella commessa reale ArchLine ha già prodotto:

- **`.ifc`** (IFC, BIM openBIM) — es. `FC1259-studior1.ifc`.
- **`.dwg`** (AutoCAD) — più file 2D.

Conseguenza pratica: per far dialogare CRN-BIM con ArchLine **non serve per forza
decodificare il `.pro`**. Leggere/scrivere **IFC** (geometria + dati BIM) e **DWG/DXF**
(2D) copre gran parte dei casi, con formati documentati e aperti. Il reverse del `.pro`
serve solo se occorre il progetto nativo completo di ArchLine.

## 4. Vincolo operativo (perché serve il PC)

REA è pensato per girare **in locale**, dove ci sono ArchLine e i file. In questa
sessione cloud:

- la rete blocca gli host di download di Dropbox → i `.pro`/installer non sono scaricabili;
- il canale testuale di Dropbox non decomprime un `.pro` binario;
- manca un motore di decompilazione (Ghidra/Hopper/IDA) per il `.bin`.

Quindi la fase binaria va fatta sul PC (REA locale) oppure collegando il PC a questa
sessione via Remote Control.

## 5. Prossimi passi proposti

Formato `.pro` (interoperabilità nativa), sul PC:

1. Copiare un `.pro` **piccolo** (es. 4,5 MB) in una cartella di lavoro.
2. Leggere i primi byte (`0x78` ⇒ zlib) e provare `zlib.decompress`/`inflate`.
3. Se esce XML (Xerces), mappare gli elementi: piani, muri, aperture, solai → modello CRN-BIM.

Binario `ARCHlineXP2021.bin`, sul PC con REA + Ghidra:

1. `npx rea-agents setup` sul PC, poi `rea inspect ARCHlineXP2021.bin`.
2. Cercare le funzioni di load/save del progetto e la pipeline Xerces/zlib.

Alternativa consigliata: partire da **IFC/DWG**, che non richiedono reverse engineering.
