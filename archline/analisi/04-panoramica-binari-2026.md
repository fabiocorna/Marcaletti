# ARCHLine.XP 2026 — panoramica statica dei binari (REA)

Analisi **solo statica** dell'installazione locale `C:\Program Files\ARCHline.XP 2026`
con REA 6.8.0 (`inspect_desktop_application`, `inspect_pe_imports`,
`inspect_native_exports`). Nessun programma eseguito, nessun file modificato,
nessun decompilatore (Ghidra/IDA non configurati). Obiettivo invariato:
interoperabilità sui formati (`.pro`, `.asc`), niente licenze/protezioni.

## 1. Installazione

- 988 file, ~2,1 GB. Binario principale **`ARCHlineXp2026.bin`** (101 MB, PE32+ x64),
  SHA-256 `8b7fd6f8aa53dc621050c6e4ec9dfe055f3f632196e0577595672e3ae41e0722`;
  `ARCHlineXp2026.exe` (630 KB) è il lanciatore, come nel 2021.
- Differenze rispetto alla 2021 (`01-ricognizione.md`): runtime **MSVC 14x**
  (`mfc140`, `MSVCP140`) invece di VS2010; **Xerces-C 3.2** invece di 3.1.
- 104 assembly **.NET**, quasi tutti di terze parti (Autodesk ACC/Forge, Google Drive,
  OneDrive, CefSharp, Xceed, SautinSoft). Propri di ArchLine: `ALDOTNet2Dll.dll`,
  `ALDOTNETDialogsDll2026.dll`, `ALIpcClient.dll`, `ACCBridge.dll`, `MSDriveDll.dll`.
  Il nucleo (modello dati, I/O dei progetti) resta **C++ nativo**.

## 2. Dipendenze del binario principale (95 DLL importate)

| Area | DLL (n. funzioni importate) | Nota |
|---|---|---|
| IFC | `IfcParse` (4287), `IfcGeom` (91) | IfcOpenShell: export/import IFC |
| DWG/DGN | `TD_*`, `TB_*`, `Teigha` (ODA SDK 26.9) | import/export DWG, DGN |
| UI | `ProfUIS3406mx64` (2572), `mfc140` (1013) | interfaccia MFC |
| Modello/IO proprietari | `ToolsDll` (770), `TYPES` (563), `GEOMETRY`, `Resource` | vedi §3 |
| XML | `xerces-c_3_2` (58) | indice XML del `.pro` |
| Altri formati | `libfbxsdk`, `SketchUpAPI`, `lib3ds`, `gbXML`, `proj_9`, OpenCascade `TK*` | FBX, SKP, 3DS, gbXML |
| Script | `v8` | motore JavaScript incorporato |

Non c'è import diretto di zlib: la compressione passa da un'altra DLL
(nel 2021 era `compressx64.dll`). `TYPES.dll` esporta
`getExtractZipFileFunction`, coerente con il `.pro` come ZIP (`02-formato-pro.md`).

## 3. `TYPES.dll`: lo strato di I/O dei file (986 export)

Classi più rilevanti per i formati:

- **`TypesDll::CALFileID`** (20 metodi): `Open`/`Create`/`Close`,
  `Read(void*, int)`, `Write(const void*, size_t)`, `SetPosition`,
  `GetCurrentPosition`, `GetAndSetPositionTo`, `saveTo`, più `_fnSetIoBinErr`
  e il globale `actFileId`. È un file binario a lettura sequenziale con
  posizionamento esplicito: compatibile con i record dei `.asc` (`03-formato-asc.md`).
- **`TypesDll::MEMBuffer`**: buffer in memoria (`add`, `get`, `setBuffer`), usato da
  `Parameters::Entities::load/save(MEMBuffer)` per i parametri delle entità.
- **`TypesDll::File`** (141 metodi): utility su percorsi e file (`load_file`, `save_to_file`).
- `ToolsDll::AML::Stream` (`fromFile`/`toFile`, `toStream`/`fromStream`): un formato a
  blocchi con parole chiave (`ReadBlock`, `Find(keywords)`) per elementi MEP,
  aperture, classificazioni, comandi IPC.

## 4. Prossimi passi

1. Con Ghidra (`GHIDRA_INSTALL_DIR` su Ghidra 12.1.x) aprire `TYPES.dll` (piccola) e
   seguire i chiamanti di `CALFileID::Read` nel `.bin` per dare un nome ai record `.asc`
   ancora ignoti (layer, testi, quote, blocchi, retini).
2. Stringhe del `.bin` vicino alle routine di load dei `.asc` per i nomi dei tipi di entità.
3. In alternativa, senza decompilatore: confronto differenziale tra `.asc` salvati da
   ArchLine con una sola entità di tipo noto (un testo, una quota) — più rapido e
   del tutto lecito.
