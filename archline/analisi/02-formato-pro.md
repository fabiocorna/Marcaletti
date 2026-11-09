# ARCHLine.XP — formato del file `.pro`

Analisi fatta in locale sul PC (2026-11-09), su **copie** di `.pro` reali, in sola
lettura. Campioni: progetti salvati con ARCHLine 2016, 2025 e 2026 (build 468).

## 1. Il `.pro` è un archivio ZIP (non zlib grezzo)

L'ipotesi di `01-ricognizione.md` ("XML compresso zlib") era vicina ma non esatta:
i primi byte sono `50 4B 03 04` (`PK\x03\x04`), cioè un **ZIP standard**. Si apre
con qualunque libreria zip (es. `zipfile` di Python), metodo 8 (deflate) per i
dati, metodo 0 (store) per le immagini già compresse.

- Stesso schema in tutte le versioni osservate (2016 → 2026).
- I nomi delle voci sono **percorsi assoluti della cartella temporanea** di chi ha
  salvato, es. `C:/Users/<utente>/AppData/Roaming/CadLine/ARCHlineXP2026/Temp<n>/...`
  (nel 2016: `C:/ProgramData/Cadline/ARCHlineXP2016/Temp/...`). Un lettore deve
  quindi riconoscere le voci per **nome finale/estensione**, non per percorso.
- Le maiuscole/minuscole dei percorsi non sono coerenti (alcune voci tutte minuscole).
- Esempio misurato: 85 voci in un `.pro` da 5,7 MB.

## 2. Contenuto dell'archivio

| Voce | Formato | Ruolo |
|---|---|---|
| `prosavetmp.pro` | XML, ISO-8859-2 | **indice del progetto**: radice `<ARCHLine.XP_Project>`, versione (`<Version>5.07</Version>`), layer, gruppi, filtri, fasi, finestre/viste, elenco file |
| `<nome>_pro/*.asc` | **binario proprietario** | **disegni 2D/3D** (la geometria). Header testuale: data, firma `CAD_UNO` (2D) o `CadLn3D` (3D), `WIN31`, versione `15.05` |
| `<nome>_pro/*.3as` | binario, stesso header (`1.29`) | piccolo file associato al modello 3D |
| `<nome>_pro/<nome>.set` | XML `<Attributes>` | attributi/stili di default per tipo di elemento (punti, linee, muri, …) |
| `<nome>_pro/material.mtr` | XML `<archlinelist>` | libreria materiali del progetto |
| `set.tex/*.jpg|png`, `material.tex/*` | immagini | texture dei materiali |
| `*.oli` | binario, magic `PRGA` + `.ol3` | tipi linea/retini utente |
| `*.pat`, `*.ext` | testo `BEGIN … END` | elenchi di pattern/estensioni |
| `User/*.xml` | XML UTF-8 | impostazioni: `schedules`, `tags`, `filters`, `mep`, `ifctranslators`, `revisions`, `labels`, … |
| `SharedCoordinates*.xml` | XML | punto di rilievo / coordinate condivise (utile per IFC) |
| `Thumbnail.bmp` | BMP 230×130 | anteprima |
| `User/ARCHlineXP.log` | testo | log di sessione (incluso nel salvataggio) |

Alcune voci di `User/` compaiono **due volte** (stesso nome, percorsi diversi).

## 3. Note per scrivere un lettore

L'XML di ArchLine **non è ben formato**. Difetti trovati, tutti gestiti da
`archline/tools/leggi_pro.py`:

- tag che iniziano con una cifra (es. `<3DDatabase>`, `<3DDatabaseFile>`);
- testo non escapato: `&` nude (`<name>V&B_Chrom1</name>`) e perfino `<` `>`
  (`<longname><Charcoal></longname>`) nei materiali;
- codifica dichiarata ISO-8859-2 (indice, `.set`, `.mtr`), che expat non gestisce
  in modo nativo: va decodificata prima; UTF-8 per `User/*.xml`.

Struttura utile dell'indice (`<ARCHLine.XP_Project MinorVersion Build ID>`):

- `Version` (sempre `5.07` nei campioni), `Time`, `ProjectName`, `3DDatabaseFile` (il `.3as`).
- `Layers/Layer` con `GUID`, `Index`, `Name`/`NameW`, `Description`, `Colour`,
  `Type`, `Thickness`, `IsPrintable`, attributo `IsHidden`; `LayerGroups`, `FilterGroups`.
- `File` = un disegno o una vista: `Pseudo_file_name` (nome mostrato), `Path`
  (il file nell'archivio), `WindowClass`, `Visible_Phases` (una per fase),
  `Crt*` (finestre), `Alaprajz` (ungherese "pianta"). Oltre ai `.asc` può puntare
  a un **`.pef`** (tavola di stampa / layout).
- `GlobalProjectSettings`: altro XML **codificato in base64**.
- `ProjectMetaData`, `CALVersions`: XML escapato dentro il testo.

### 3.1 Intestazione dei `.asc` / `.3as`

| Offset | Lunghezza | Contenuto |
|---|---|---|
| 0 | 24 | data di salvataggio, testo (`gio 15.10.2026  05:56`) |
| 34 | 10 | firma: `CAD_UNO` = 2D, `CadLn3D` = 3D |
| 44 | 10 | `WIN31` |
| 54 | 10 | versione formato (`15.05`, `15.07`, `5.06`; `1.29` nel `.3as`) |
| 108 | 4 | uint32 LE: **ID del disegno** (= `MetFileID` della voce `File`, = `FileIDOfMain2DWindow` per la pianta principale); è anche un timestamp Unix |
| 120 | 32 | 4 double LE: probabili estremi del disegno (BLX, BLY, TRX, TRY) — da verificare |

Il collegamento `File` → `.asc` va fatto **per nome** (`Path`): `MetFileID`
nell'indice manca nelle versioni vecchie (2016), mentre l'ID nell'header c'è sempre.

### 3.2 Verifica

`leggi_pro.py` letto su **tutti gli 87 `.pro` locali** della cartella LAVORI
(build da 175 a 835, salvati dal 2016 al 2026): 87 su 87 senza errori.

## 4. Cosa si ottiene già e cosa resta

Già leggibile senza reverse del binario: struttura del progetto, layer, fasi,
materiali e texture, attributi, abachi/etichette, coordinate condivise, anteprima.

Resta da decodificare: i file **`.asc`** (`CAD_UNO` / `CadLn3D`), che contengono
muri, aperture, solai e grafica 2D. È qui che serve l'analisi del binario
(`ARCHlineXp2026.bin` + REA/Ghidra) oppure, in alternativa, l'export **IFC/DWG**.

## 5. Installazione sul PC

- Presenti `C:\Program Files\ARCHline.XP 2024\` e `C:\Program Files\ARCHline.XP 2026\`.
- Nel 2026: `ARCHlineXp2026.exe` + `ARCHlineXp2026.bin`, componenti .NET
  (`ALDOTNet*`, `ACCBridge.dll`) e moduli **ODA** `*_26.9_17.tx` (librerie Open
  Design Alliance per DWG/IFC/BCF), versione ODA 26.9.

## 6. Prossimi passi

1. ~~Lettore Python minimo del `.pro`~~ — fatto: `archline/tools/leggi_pro.py`.
2. Studio dell'header `.asc` confrontando due salvataggi dello stesso progetto con
   una sola modifica (es. un muro spostato) → differenze binarie mirate.
3. Solo se serve: `rea inspect` su `ARCHlineXp2026.bin` per le routine di
   lettura/scrittura `.asc`.
