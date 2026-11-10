# ARCHLine.XP — formato dei disegni `.asc`

Analisi statica (2026-11-09) su copie di disegni reali, senza eseguire ArchLine.
Il disegno 2D decodificato è stato confrontato a vista con l'anteprima bitmap che
ArchLine salva nello stesso file, su due progetti (2020 e 2025): la pianta coincide
(muri, porte con archi di apertura, sanitari, finestre).

## 1. Struttura del file

```
[header fisso, ~0x5C0 byte]
[XML <HeaderExt> ... </HeaderExt>]        ISO-8859-2: build, locale, layer (LayerNames: Key=GUID, Text)
[frame zlib 0]  tabelle (penne/stili; nei file molto vecchi: elenco font)
[frame zlib 1]  tipi linea ("Punteggiata", ...)
[frame zlib 2]  ENTITÀ  ← la grafica
[frame zlib 3]  dizionario proprietà (".linkPolIDs", ".TxtHeiPlot", ".extrhatch", ...)
[frame zlib 4]  blocchi/simboli (se presenti)
[anteprima]     BMP 230×130 (BITMAPFILEHEADER completo; nei 2016 a volte JPEG)
[frame zlib]    <Footer> XML (vuoto o con _FixObjExtensions, fino a 300 KB)
```

**Frame**: `u32 n`, poi `n` byte = `u32 lunghezza_decompressa` + stream zlib (`n-4` byte).
L'anteprima non è in un frame: il lettore salta i byte fino al frame successivo.

**Frame spezzati**: un contenuto lungo è diviso in frame di esattamente 10.000.000 byte
decompressi; il pezzo successivo è nel frame che segue. Il lettore unisce un frame al
precedente quando questo è lungo esattamente 10.000.000 byte.

**Disegni vuoti**: manca il frame delle entità e il frame 2 è già il `<Footer>`; il
disegno ha 0 entità.

Header fisso: vedi `02-formato-pro.md` §3.1 (data, firma `CAD_UNO`/`CadLn3D`,
versione, ID disegno all'offset 108, estremi).

## 2. Record di entità (frame 2)

Un record dopo l'altro, senza tabella indice. Formato a tag (versione disegno ≥ 15):

| Tag | Dim. | Significato (✓ verificato, ? ipotesi) |
|---|---|---|
| 0 | u16 | ? (0..3 nei 2020, sempre 1 nei 2025) |
| 1 | u16 | ✓ **tipo di entità** (tabella sotto) |
| 2 | u16 | ? sempre 0 (nei vecchi 0xFFFF) |
| 3 | u32 | ? gruppo/oggetto padre (0 = nessuno; valori ripetuti per gruppi) |
| 4 | u32 | ✓ **ID univoco** progressivo |
| 5 | u32 | ? gruppo/oggetto (un valore per vano: retino + etichetta). **Non** è il layer |
| 6 | u32 | ? colore/penna (256 frequente) |
| 7 | u32 | ? (-1 frequente) |
| 8 | i16 | ✓ **layer**: vale −(`Index` + 1), con `Index` dei `Layers` nell'indice del `.pro` (§2.1) |
| 9 | i16 | ? |
| 10 | u16 | ? flag (0x81 frequente) |
| 11 | u16 | ✓ **numero di proprietà** (coppie u32) |
| 12 | u32 | ? |
| 13 | u32 | ✓ **lunghezza della geometria** in byte |
| 14 | u32 | ? |
| 15 | 16 B | ✓ GUID dell'entità |
| 0x10 | 16 B | opzionale: GUID (probabile oggetto padre, es. muro/porta) |
| 0x11 | 16 B | opzionale (file 2016) |
| 0x25 | u32 | opzionale: timestamp Unix di modifica |
| 0x2B | u8 | opzionale |
| 0xFFFF | — | ✓ fine header |

Dopo l'header: tag 11 coppie u32 di proprietà, poi tag 13 byte di geometria.

**Dati in coda non dichiarati**: i retini sfumati (tipo 11) possono portare dopo la
geometria un blocco non contato dal tag 13 (FC1334: 1.000.360 × 32 = 32.011.520 byte; il
numero è nella proprietà 2 e in un u32 della geometria, ma la chiave 2 non è un conteggio
negli altri tipi). Il lettore, se il record successivo non si legge, cerca in avanti il
prossimo inizio di record valido (tag 0..5 nell'ordine, seguito da un altro record
leggibile) e mette i byte saltati in `Entita.extra`.

### 2.1 Layer (tag 8)

`layer = −tag8 − 1` è l'`Index` di un `Layer` in `prosavetmp.pro`. Verificato su progetti
2016 (anche formato vecchio 5.06), 2020 e 2025: i testi cadono su "Testi" / "TOPONIMI",
i tipi 10 su "Quote", i tipi 11 su "Retini" / "Campiture", le linee dei muri su "Murature",
i layer catastali importati (`03080200`, …) mantengono il loro codice. I `LayerNames`
dell'header XML del `.asc` non servono: spesso elencano un solo layer.

Colore del layer (`Colour`): con il bit `0x01000000` il byte basso è un indice ACI
(osservati 7, 8, 253); 0 = predefinito.

Poi `tag11 × (u32 chiave, u32 valore)` di proprietà e `tag13` byte di geometria.
Con questa regola il parser consuma il frame **esattamente** fino all'ultimo byte.

**Formato vecchio** (versione disegno < 10, es. `5.06`, 2016): gli stessi campi
0..14 **senza tag**, senza GUID e senza tag opzionali (header fisso di 46 byte).

## 3. Geometria per tipo

Coordinate in **double** (mm, coordinate del progetto). Tutte le geometrie
decodificate iniziano con 4 float = bbox locale (xmin, ymin, xmax, ymax) relativa al
primo punto/centro.

| Tipo | Entità | Geometria dopo la bbox | Stato |
|---|---|---|---|
| 2 | linea | P1, P2 (2×2 double) | ✓ |
| 3 | polilinea | N punti (2 double ciascuno), N = (len−16)/16 | ✓ |
| 5 | arco/cerchio | cx, cy, r, angolo iniziale, **ampiezza** (gradi, antiorario) | ✓ |
| 6 | ellisse | cx, cy, rx, ry, rotazione (gradi; rotazione non ancora vista ≠ 0 con rx≠ry) | ✓ parziale |
| 14 | blocco inserito | scala (double 1.0), punto d'inserimento, nome (`A$C…`) | da completare |
| 9 | **testo** | vedi §3.1 | ✓ |
| 10 | **quota** | sempre sul layer delle quote; ha il GUID padre (tag 0x10) | geometria da fare |
| 11 | **retino** | sempre sul layer dei retini/campiture | geometria da fare |
| 1 | probabili **punti** (79.151 nel rilievo FC975) | | da fare |
| 4, 20 | ? | | da fare |

### 3.1 Testo (tipo 9)

Ricavato confrontando 7.063 testi di 80 progetti reali e verificato a vista con
l'anteprima di ArchLine (cartello di cantiere e pianta FC1227).

| Offset | Tipo | Significato |
|---|---|---|
| 0 | 4×f32 | bbox locale (xmin, ymin, xmax, ymax) del blocco di testo, già ruotata |
| 16 | 2×f64 | ✓ punto d'inserimento (x, y) |
| 32 | 16 B | ? quasi sempre zero |
| 48 | u8 | ✓ **allineamento** 1..9: `(a−1)//3` = 0 sinistra, 1 centro, 2 destra; `(a−1)%3` = 0 basso, 1 centro, 2 alto |
| 49 | u8 | ? 16 o 32 (font/stile?) |
| 52 | u8 | ? 0 / 1 / 128 |
| 56 | u8 | ? 0 / 4 / 7 (colore o font?) |
| 66 | i16 | ? −3..0 |
| 68 | f32 | ✓ **altezza** del carattere (unità del disegno) |
| 72 | f32 | ? larghezza/fattore (spesso 0) |
| 76 | f32 | ? sempre 90.0 (probabile inclinazione: 90° = carattere dritto) |
| 84 | f32 | ✓ **rotazione** in gradi antiorari |
| 88 | f32 | ✓ spazio extra fra righe: interlinea = altezza + questo valore (verificato su testi da 2, 4, 5 righe) |
| 92 | u32 | ✓ **numero di righe** n |
| 96 | n×f32 | ✓ larghezza di ogni riga |
| 96+4n | byte | ✓ **testo**, righe separate da LF (0x0A), nessun terminatore (finisce col record) |

Codifica del testo: **cp1252** nei progetti italiani (`à` = 0xE0, `°` = 0xB0, `²` = 0xB2).
Probabilmente segue la lingua di Windows con cui è stato salvato il file.

Limiti noti:

- **Etichette dei locali** (hanno il GUID padre, tag 0x10, e dichiarano ~68 righe di cui
  ~10 usate): testo e posizione sono corretti, ma ArchLine le impagina su due colonne
  ("S.U." | "18.90 m²"). Il record non descrive questa impaginazione, quindi nel DXF le
  righe risultano strette e sovrapposte.
- Alcuni testi figli (es. `A1/1`) hanno coordinate (0, 0) o piccole: probabilmente sono
  relative all'oggetto padre. Non ancora risolto.

## 4. Verifica

- Rendering delle entità 2/3/5/6 confrontato con l'anteprima del file: coincidono
  (Document9 2025, Document1 2020).
- DXF esportato e riletto: pianta 2025 e planimetria catastale 2016 corrette.
- Testi: 7.063 testi di 80 progetti estratti a caso, tutti decodificati, nessun carattere
  non valido, 95 DXF scritti e riletti da ezdxf senza errori. Posizione, rotazione e
  allineamento confrontati con l'anteprima (cartello, pianta FC1227).
- Nello stesso campione 51 `.pro` su 80 **non sono ZIP**: sono progetti di formato vecchio
  (iniziano con `78 01 03 00`, archivio "ALTRI STUDI"). Contenitore da studiare a parte.
- Test su tutti i `.pro` ZIP della cartella LAVORI (2026-11-10): **482 disegni 2D letti fino
  all'ultimo byte, 2.357.153 entità**; 34 disegni non letti, in tre casi:
  disegni vuoti, frame spezzati a 10.000.000 byte, retino sfumato con dati in coda (§1, §2).
  Dopo la correzione **tutti i 34 si leggono**: 27 vuoti (0 entità) e 7 con frame spezzati
  (98.521–311.873 entità, in totale 995.760). FC1334, rimasto fuori dalla seconda raccolta,
  provato a parte: 14 entità, con un retino che ha 32 MB di dati in coda. I disegni già letti
  (Document9, Document1, FC140, Fc1378) danno gli stessi numeri di prima.

## 5. Strumento

`archline/tools/leggi_asc.py`:

```
python leggi_asc.py progetto.pro                   entità per tipo, per ogni disegno 2D
python leggi_asc.py progetto.pro --dxf pianta.dxf  esporta la pianta principale in DXF R12
python leggi_asc.py progetto.pro --disegno Sezioni.asc --dxf sezioni.dxf
```

Il DXF (R12, codepage ANSI_1252) contiene linee, polilinee, archi, cerchi, ellissi e testi
(una entità TEXT per riga), sui layer di ArchLine con i loro nomi e colori
(i layer nascosti sono spenti). Unità dichiarate: millimetri (`$INSUNITS` = 4).

`archline/tools/converti_pro.py` converte un intero progetto per CRN-BIM: un DXF per
ogni disegno 2D, `progetto.json` (info, layer, materiali, disegni) e `anteprima.bmp`.

```
python converti_pro.py progetto.pro                  -> cartella <progetto>_crnbim
python converti_pro.py progetto.pro -o cartella --solo-principale
```

Prova in CRN-BIM 0.78 (`dwg.import_file` + `genera.da_dwg` con freecadcmd): la pianta
di Document1 (2020) si importa in mm, CRN-BIM sceglie da solo il layer "Murature" e
genera **22 muri e 4 aperture**. La planimetria catastale FC140 (2016) si importa con i
suoi 29 layer; nessun muro, com'è giusto (è un rilievo, non una pianta).

## 6. Prossimi passi

1. ~~Layer~~ — fatto: tag 8 (§2.1).
2. Geometria delle quote (tipo 10) → DIMENSION o linee + testo.
3. Blocchi (tipo 14 + frame 4) e retini (tipo 11).
4. Viste 3D (`CadLn3D`) e database `.3as`: struttura diversa, non ancora studiata.
