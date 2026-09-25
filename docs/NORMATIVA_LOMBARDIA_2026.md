# Normativa Lombardia 2026 — sintesi tecnica per l'implementazione software

Sintesi dei testi presenti in `risorse/normativa/` (estratti da PDF):

| Sigla usata qui | File | Documento |
|---|---|---|
| **ALL** | `allegato_decreto_6437_2026.txt` | Allegato al Decreto 6437 del 15/05/2026 «Disposizioni per l'efficienza energetica degli edifici» (solo il testo principale, §1–§19) |
| **DEC** | `decreto_6437_2026.txt` | Decreto n. 6437 del 15/05/2026 (atto di approvazione) |
| **DGR** | `dgr_6153_2026.txt` | D.G.R. XII/6153 dell'11/05/2026 + Allegato A (incremento obblighi FER) |
| **RT** | `modello_relazione_tecnica_2026.txt` | Modello di relazione tecnica (Allegato C), «Versione 03/06/2026 – rif. Decreto 6437/2026» |
| **MF** | `modulo_F.txt` | Manuale CENED+2.0, Modulo F «Calcolo APE, interventi e verifiche NZEB», **versione del 15.10.2019** |

Le citazioni seguono il formato `ALL §6.14.c.ii`, `DGR All. A`, `RT p.9` ecc. I numeri sono riportati
come compaiono nel testo. Quando un dato non è nei file lo dichiaro esplicitamente e non lo ricostruisco.

> **AVVISO IMPORTANTE — Allegato B mancante.** Nessuno dei file contiene l'**Allegato B**
> («Caratteristiche dell'edificio di riferimento, requisiti di prestazione e classificazione energetica»)
> né l'**Allegato H** (metodologia di calcolo). Di conseguenza nel materiale fornito **non ci sono**:
> le tabelle delle trasmittanze U limite e di riferimento per zona climatica (strutture opache verticali,
> coperture, pavimenti, chiusure trasparenti), i limiti di H'_T per S/V e zona, i limiti di
> A_sol,est/A_sup,utile, i fattori g_gl+sh limite, i parametri dell'edificio di riferimento (U, efficienze
> dei sottosistemi, rendimenti dei generatori: Tabelle 7, 8, 8 bis, 9), i requisiti di generatori e pompe
> di calore (§3.3 punti 1 e 3) e i fattori di conversione in energia primaria f_P. L'ALL si limita a
> **rimandarvi** (vedi §2.10, dove sono elencati tutti i rimandi). Per implementare queste verifiche
> bisogna procurarsi il testo dell'Allegato B e dell'Allegato H del Decreto 6437/2026.

---

## 1. Ambito

### 1.1 Date e decorrenze

| Evento / obbligo | Data | Fonte |
|---|---|---|
| Adozione della DGR 6153 (incremento obblighi FER) | 11/05/2026 | DGR, intestazione |
| Firma del Decreto 6437 e del relativo Allegato | 15/05/2026 | DEC, firma digitale `2026-05-15T21:30:54+0200` |
| Il DM 28/10/2025 (aggiornamento del DM 26/06/2015) si applica ai titoli abilitativi richiesti **a partire dal** | 03/06/2026 | DEC, premesse («DATO ATTO che il Ministero…») |
| Messa a disposizione su CENED del modello di relazione tecnica aggiornato, **entro** il | 03/06/2026 | DEC punto 3 del dispositivo; RT «Versione 03/06/2026» |
| Termine ultimo per usare la procedura di calcolo del decreto 5796/2009 (solo APE di fine lavori per titoli presentati entro il 31/12/2015) | fino al 02/06/2026 | ALL §4.3 |
| BACS classe B o superiore negli edifici non residenziali con impianti termici > 290 kW, **entro** il | 03/06/2026 | ALL §5.10 |
| Incremento degli obblighi FER regionali (65% nuove costruzioni; K = 0,06 / 0,08) | dall'01/01/2027 | DGR punto 1 del dispositivo; ALL §6.14.c.iv e §6.27 |
| Punti di ricarica negli edifici non residenziali esistenti: 50% (arrotondato per difetto) dei valori di tabella | entro 01/01/2025 | ALL Tab. 1 e Tab. 2 |
| Punti di ricarica negli edifici non residenziali esistenti: 100% dei valori di tabella | entro 01/01/2030 | ALL Tab. 1 e Tab. 2 |
| Edifici NZEB obbligatori (nuove costruzioni e ristrutturazioni importanti di 1° livello) | dal 01/01/2016 | ALL §6.14 |
| Metodologia dell'Allegato H obbligatoria per le verifiche dei punti 5–9 / per gli indicatori APE | dal 01/01/2016 / dal 01/10/2015 | ALL §4.2 |
| **Data di entrata in vigore del Decreto 6437** | **non indicata** nel testo: il DEC dispone solo la pubblicazione sul BURL (punto 5) | DEC |

**Regola per determinare la norma applicabile (fondamentale per il software):** i requisiti si
individuano in base alla **data di richiesta del titolo abilitativo**. Se il titolo è scaduto, le opere
di completamento seguono la norma vigente alla data di richiesta del nuovo titolo (ALL §4.7).

### 1.2 Cosa sostituisce

Fonte: DEC premesse e dispositivo, punti 1–4.

| Parte della disciplina regionale | Prima (versione vigente) | Con il Decreto 6437/2026 |
|---|---|---|
| «Disposizioni per l'efficienza energetica degli edifici» | DDUO 18546/2019 | **sostituita** (nuovo Allegato) |
| All. A «Definizioni» | decreto 2456/2017 | **sostituito** (aggiornato) |
| All. B «Descrizione dell'edificio di riferimento e parametri di verifica» | DDUO 18546/2019 | **sostituito** (aggiornato) — *testo non presente nei file* |
| All. C «Relazione tecnica» | DDUO 18546/2019 | **non ancora sostituito**: rinviato a un provvedimento successivo, dopo il format nazionale previsto dal DM 28/10/2025 (DEC punto 2). Nel frattempo c'è il modello su CENED (DEC punto 3 → file RT) |
| All. D «APE» | decreto 2456/2017 | **sostituito** (con i loghi di ARIA S.p.A. al posto di quelli di Infrastrutture Lombarde) |
| All. E «Targa energetica» | decreto 2456/2017 | **sostituito** (stessa modifica dei loghi) |
| All. F «Titoli di studio», All. G «Annunci» | decreto 2456/2017 | allegati invariati, «a scopo ricognitivo» (DEC punto 4) |
| All. H «Metodologia di calcolo» | DDUO 18546/2019 | **sostituito** (aggiornato) — *testo non presente nei file* |

Il **DM 26/06/2015 non viene sostituito dal decreto regionale**. Il decreto **recepisce** il DM
28/10/2025, che aggiorna il DM 26/06/2015, e recepisce anche il D.Lgs. 199/2021 come modificato dal
D.Lgs. 5/2026 e la DGR 6153/2026 (DEC premesse, «CONSIDERATO che si rende necessario…»).

Temi recepiti dal DM 28/10/2025, secondo DEC:
- modifica dei parametri di riferimento per l'isolamento termico e dei requisiti tecnici degli impianti;
- obbligo di BACS negli edifici non residenziali con impianti termici > 290 kW;
- aggiornamento dei parametri per il calcolo delle prestazioni energetiche;
- obblighi di installazione di infrastrutture di ricarica per veicoli elettrici.

Temi recepiti dal D.Lgs. 199/2021 e D.Lgs. 5/2026:
- modifica degli obblighi FER;
- obbligo FER esteso alle ristrutturazioni di 2° livello e alle ristrutturazioni dell'impianto termico;
- deroga per impossibilità tecnica, economica o funzionale.

### 1.3 Campo di applicazione ed esclusioni (ALL §3)

- **Si applica** all'edilizia pubblica e privata, per: nuova costruzione, ristrutturazioni importanti,
  riqualificazione energetica, infrastrutture di ricarica, APE e uso delle FER (§3.1).
- **Esclusi dall'applicazione integrale** (§3.2):
  - a) edifici industriali e artigianali climatizzati per esigenze del processo produttivo o con reflui di processo;
  - b) edifici rurali non residenziali senza impianti;
  - c) fabbricati isolati con superficie utile totale **< 50 m²**;
  - d) edifici non compresi nelle categorie del DPR 412/93 il cui uso standard non prevede climatizzazione (box, cantine, autorimesse, depositi, ecc.); resta fermo l'obbligo sulle infrastrutture di ricarica;
  - e) luoghi di culto;
  - f) strutture temporanee autorizzate per **≤ 6 mesi**;
  - g) subalterni con superficie utile **< 10 m²**.
- **Esclusi dai soli requisiti di prestazione** (§3.3):
  - a) beni vincolati (D.Lgs. 42/2004, parte II e art. 136 c.1 lett. b, c), se l'autorità competente giudica che i requisiti ne altererebbero carattere o aspetto;
  - b) immobili in piani di recupero, alle stesse condizioni;
  - c) interventi sui soli strati di finitura ininfluenti dal punto di vista termico, o rifacimento di intonaco su **< 10%** della superficie disperdente lorda;
  - d) manutenzione ordinaria degli impianti termici.
- **Obblighi FER** (§3.5): valgono anche per gli edifici di §3.2 a–d e §3.3 a–b, quando si tratta di
  nuova costruzione, ristrutturazione importante o ristrutturazione dell'impianto termico.
  L'inosservanza comporta il diniego del titolo edilizio.
- **Esenzioni dagli obblighi FER** (§3.6, §6.26):
  - edifici temporanei da rimuovere entro **24 mesi** dalla fine lavori (la temporaneità deve risultare nel titolo);
  - edifici pubblici in uso ai corpi armati, se l'obbligo è incompatibile con la destinazione.
- **Edifici composti da parti di categorie diverse**: le parti si valutano separatamente; l'edificio si
  classifica in base alla destinazione prevalente in volume climatizzato (§4.6).
- **Sostituzione di un generatore < 50 kW**: la relazione tecnica è dovuta solo se cambia il combustibile
  o la tipologia di generatore. Il passaggio fra caldaie di tipo diverso (condensazione, modulante, ecc.)
  **non** conta come cambio di tipologia (§4.10).

### 1.4 Categorie di intervento → verifiche applicabili

Le definizioni delle categorie (1° e 2° livello, riqualificazione) sono nell'**Allegato A, che non è nei file**.
Le soglie del 25% e del 50% compaiono solo nel caso degli ampliamenti ≤ 15% (ALL §9.6), non come
definizione generale.

| Intervento | Base di calcolo della verifica | Verifiche richieste | Fonte |
|---|---|---|---|
| **Nuova costruzione** | intero edificio, con edificio di riferimento (§5.1.a, §6.13) | tutte le verifiche di §5 (termoigrometriche, cool roof, BACS, ecc.) + §6.14.b: H'_T < limite (Tab. 10 o 11 All. B); A_sol,est/A_sup,utile < limite (Tab. 12 All. B **[numerazione incoerente, vedi §6]**); EP_H,nd, EP_C,nd, EP_gl,tot < valori di riferimento; η_H, η_W, η_C > valori di riferimento + FER §6.14.c + requisiti estivi §6.22 + U divisori ≤ 0,8 (§6.23) + teleriscaldamento a < 1000 m (§6.2) + regolazione con compensazione climatica (§6.8) + smart metering (§6.9) + contabilizzazione (§6.10) + BACS classe B se non residenziale (§6.11) + ricarica veicoli (§5.12–5.16) + valutazione di fattibilità dei sistemi ad alta efficienza (§4.16) | ALL §5, §6 |
| **Ristrutturazione importante di 1° livello** | intero edificio, con edificio di riferimento | come la nuova costruzione (NZEB dal 2016); FER con percentuali proprie (50%) e K = 0,025 | ALL §6.1, §6.14 |
| **Ristrutturazione importante di 2° livello** | solo le porzioni di involucro interessate (§5.1.b) | requisiti di §8 (U limite, g_gl+sh, ecc.) + U comprensiva dei ponti termici (All. B §3.1 punto 2) + FER 15% (H+C) e P = 0,025·S + §5 pertinenti | ALL §7.2 |
| **Riqualificazione energetica dell'involucro** | componenti oggetto di intervento (§5.1.c) | U_sc pareti (Tab. 12), coperture (Tab. 13, esclusa la E.8), pavimenti (Tab. 14), chiusure trasparenti (Tab. 15, esclusa la E.8), g_gl+sh (Tab. 16/17, esclusa la E.8); +30% sui limiti in caso di isolamento dall'interno o in intercapedine (§8.3); valvole termostatiche con impianti non autonomi (§8.4); verifiche termoigrometriche (§5.3) | ALL §8.2–8.4 |
| **Riqualificazione degli impianti** (nuova installazione, ristrutturazione, sostituzione del generatore) | sottosistemi oggetto di intervento | η globale media stagionale > limite dell'edificio di riferimento (inverno §8.6.a, estate §8.9.a, ACS §8.11); regolazione e contabilizzazione; esonero dal calcolo se sono rispettati i requisiti di All. B §3.3 (§8.6.d, §8.9.c); diagnosi energetica se ≥ 100 kW (§8.5); se è una **ristrutturazione dell'impianto** si aggiunge l'obbligo FER di §7.2.b (§8.8, §8.10) | ALL §8.5–8.13 |
| **Ampliamento > 15% del volume esistente o > 500 m³, servito dagli impianti esistenti** | nuova porzione | H'_T (Tab. 10), A_sol,est/A_sup,utile (Tab. 11), verifiche di §5 | ALL §9.2 |
| **Ampliamento > 15% o > 500 m³ con nuovo impianto dedicato** | nuova porzione | come sopra + EP_H,nd, EP_C,nd, EP_gl,tot, η_H/W/C rispetto all'edificio di riferimento + FER come §6.14.c | ALL §9.3 |
| **Recupero di volume prima non climatizzato, con estensione degli impianti** | volume recuperato | H'_T, A_sol,est/A_sup,utile, verifiche di §5 | ALL §9.4 |
| **Recupero di volume prima non climatizzato, con nuovo impianto** | volume recuperato | come §9.3 lett. a–e (senza FER) | ALL §9.5 |
| **Ampliamento ≤ 15% e ≤ 500 m³** | edificio risultante | come 1° livello se l'intervento interessa > 50% della superficie disperdente lorda **e** comporta la ristrutturazione dell'impianto; come 2° livello se > 25%; come riqualificazione se ≤ 25% | ALL §9.6 |
| **Sostituzione dei soli serramenti** | serramenti | relazione tecnica parziale (permeabilità, U nuova ed esistente, g_gl+sh); in presenza di chiusure oscuranti basta la dichiarazione dell'impresa + marcatura CE | ALL §8.2 (coda) |
| **NZEB** (definizione) | — | edificio (escluse le categorie di §3.2) che rispetta tutti i requisiti minimi delle nuove costruzioni, compreso §6.14 | ALL §6.28 |

---

## 2. Valori limite e requisiti numerici

### 2.1 Trasmittanze U limite (opache verticali, coperture, pavimenti, trasparenti)

**NON PRESENTI NEI FILE.** L'ALL rimanda alle tabelle dell'Allegato B, che non è incluso:

| Grandezza | Tabella dell'All. B citata | Dove è citata | Note |
|---|---|---|---|
| U_sc strutture opache verticali verso l'esterno o locali non climatizzati | **Tab. 12** | ALL §8.2.a | RT p.20 cita invece «tabella 13» |
| U_sc coperture | **Tab. 13** (esclusa la E.8) | ALL §8.2.b | RT p.20 cita «tabelle 14 e 15» per le strutture orizzontali |
| U_sc pavimenti | **Tab. 14** | ALL §8.2.b | come sopra |
| U chiusure tecniche trasparenti e opache apribili (infisso compreso, senza oscurante) | **Tab. 15** (esclusa la E.8), «in funzione della fascia climatica» | ALL §8.2.c | RT p.20 cita «tabella 16» |
| g_gl+sh delle componenti finestrate orientate da E a O passando per S, e orizzontali | **Tab. 16** (§8.2.d) / **Tab. 17** (coda di §8.2) / «Tabella 8 dell'Appendice B dell'Allegato 1» (§8.2, sostituzione serramenti) | ALL §8.2 | tre riferimenti diversi; RT p.20 cita «tabella 17» |
| U comprensiva dei ponti termici (2° livello) | All. B «paragrafo 1, punto 2» (§5.1.b) / «paragrafo 3.1, punto 2» (§7.2.c) | ALL §5.1.b, §7.2.c | riferimenti non coerenti fra loro |
| Correzione dei limiti (non specificata) | All. B §3.1 punto 5 | ALL §8.3 | contenuto non disponibile |
| Parametri di trasmittanza dell'edificio di riferimento | All. B punto 1.1 | ALL §10.1.b | contenuto non disponibile |

**Unici valori U presenti nei file:**

| Requisito | Valore | Ambito | Fonte |
|---|---|---|---|
| U delle strutture divisorie (verticali, orizzontali, inclinate) fra edifici o unità immobiliari climatizzati confinanti | **≤ 0,8 W/m²K** | nuova costruzione; demolizione e ricostruzione o nuova realizzazione di pareti di separazione fra unità; esclusa la E.8; fatto salvo il DPCM 5/12/1997 (acustica) | ALL §6.23; RT p.9 e p.20 |
| U delle strutture opache che delimitano verso l'esterno ambienti non climatizzati adiacenti a quelli climatizzati | **≤ 0,8 W/m²K** | se oggetto di intervento | ALL §6.23 |
| Maggiorazione dei limiti U di Tab. 12, 13 e 14 | **+30%** | isolamento dall'interno o in intercapedine, qualunque sia la superficie; si somma all'eventuale correzione di All. B §3.1 punto 5 | ALL §8.3 |

### 2.2 H'_T limite (per S/V e zona climatica)

**NON PRESENTE NEI FILE.** Il limite è nella **Tab. 10** o **11** dell'All. B (ALL §6.14.b.i; §9.2–9.5
citano solo la Tab. 10; RT p.9 cita «Tabella 10 e 11»; MF cita la Tab. 10 del decreto 2456/2017).
Verifica richiesta: **H'_T < H'_T,limite**, sulla **singola unità immobiliare** (ALL §6.25).

### 2.3 A_sol,est / A_sup,utile limite

**NON PRESENTE NEI FILE.** ALL §6.14.b.ii cita la **Tab. 12** dell'All. B; ALL §9.2–9.5, RT p.9 e MF
citano la **Tab. 11**. Il metodo di calcolo è in All. B §2.2 (non disponibile). I limiti sono distinti per:
(a) categoria E.1, esclusi collegi, conventi, case di pena, caserme ed E.1(3); (b) tutte le altre categorie.
Verifica: valore < limite, sulla singola unità immobiliare (ALL §6.25).

### 2.4 Edificio di riferimento

- Si usa per nuova costruzione, ristrutturazione di 1° livello, ampliamenti e recuperi con nuovo impianto
  (ALL §6.13, §9.3, §9.5), e per la scala delle classi APE (§16.2).
- Indici e parametri si calcolano **con gli stessi metodi** per l'edificio di progetto e per quello di
  riferimento (ALL §6.24).
- Parametri (U, efficienze dei sottosistemi di utilizzazione Tab. 7, generatori Tab. 8, efficienze di
  generazione in energia primaria non rinnovabile Tab. 8 bis, ventilazione Tab. 9, illuminazione §1.2.2):
  **non presenti nei file**.

Tecnologie standard dell'edificio di riferimento per la classificazione APE — **ALL Tabella 2** (§16):

| Servizio | Tecnologia standard |
|---|---|
| Climatizzazione invernale | Generatore a combustibile gassoso (gas naturale) conforme alla tabella 8 dell'Allegato B, con l'efficienza dei sottosistemi di utilizzazione della tabella 7 dello stesso Allegato |
| Climatizzazione estiva | Macchina frigorifera a compressione di vapore con motore elettrico conforme alla tabella 8 dell'Allegato B, con l'efficienza dei sottosistemi di utilizzazione della tabella 7 |
| Ventilazione | Ventilazione meccanica a semplice flusso per estrazione conforme alla tabella 9 dell'Allegato B |
| Acqua calda sanitaria | Generatore a combustibile gassoso (gas naturale) conforme alla tabella 8 dell'Allegato B, con l'efficienza dei sottosistemi di utilizzazione della tabella 7 |
| Illuminazione | Requisiti del paragrafo 1.2.2 dell'Allegato B |
| Trasporto di persone o cose | «Rispetto dei requisiti di cui al punto 5.10» (vedi ambiguità in §6) |

### 2.5 Indici e parametri da calcolare (ALL Tabella 4, §6.14.a)

| Simbolo | Unità | Definizione (sintesi) |
|---|---|---|
| H'_T | W/m²K | coefficiente medio globale di scambio termico per trasmissione, per unità di superficie disperdente |
| A_sol,est/A_sup utile | – | area solare equivalente estiva per unità di superficie utile |
| EP_H,nd | kWh/m² | indice di prestazione termica utile per la climatizzazione invernale |
| η_H | – | efficienza media stagionale dell'impianto di climatizzazione invernale |
| EP_H | kWh/m² | indice di prestazione energetica per la climatizzazione invernale (nren o tot) |
| EP_W,nd | kWh/m² | indice di prestazione termica utile per l'ACS |
| η_W | – | efficienza media stagionale dell'impianto ACS |
| EP_W | kWh/m² | indice di prestazione energetica per l'ACS (nren o tot) |
| EP_V | kWh/m² | indice di prestazione energetica per la ventilazione (nren o tot) |
| EP_C,nd | kWh/m² | indice di prestazione termica utile per la climatizzazione estiva |
| η_C | – | efficienza media stagionale dell'impianto di climatizzazione estiva (compreso l'eventuale controllo dell'umidità) |
| EP_C | kWh/m² | indice di prestazione energetica per la climatizzazione estiva (nren o tot) |
| EP_L | kWh/m² | illuminazione; **non si calcola per la E.1**, salvo collegi, conventi, case di pena, caserme ed E.1(3) |
| EP_T | kWh/m² | trasporto di persone e cose; stessa eccezione della E.1 |
| EP_gl = EP_H + EP_W + EP_V + EP_C + EP_L + EP_T | kWh/m² | indice globale, espresso come EP_gl,tot e EP_gl,nren |

Verifiche di §6.14.b per nuova costruzione e 1° livello:
- i. H'_T < limite;
- ii. A_sol,est/A_sup,utile < limite;
- iii. EP_H,nd < EP_H,nd,limite, EP_C,nd < EP_C,nd,limite ed EP_gl,tot < EP_gl,tot,limite (limiti calcolati sull'edificio di riferimento; EP_gl,tot con i fattori di conversione in **energia primaria totale**, §6.15);
- iv. η_H > η_H,limite, η_W > η_W,limite, η_C > η_C,limite.

### 2.6 Requisiti estivi

**Verifiche di inerzia e massa superficiale** (ALL §6.22; ripresi in RT p.5 e MF F|3.2).
Si applicano se tutte le condizioni sono vere:
- categoria diversa da E.6 ed E.8;
- zona climatica diversa dalla F;
- località con irradianza media mensile sul piano orizzontale, nel mese di massima insolazione, **I_m,s ≥ 290 W/m²**.

| Elementi | Verifica | Valore | Fonte |
|---|---|---|---|
| Tutte le pareti verticali opache, **escluse** quelle nel quadrante NO / N / NE | **almeno una** delle due: M_s **>** 230 kg/m², **oppure** \|Y_IE\| **<** 0,10 W/m²K | 230 kg/m²; 0,10 W/m²K | ALL §6.22.b.i |
| Tutte le pareti opache orizzontali e inclinate | \|Y_IE\| **<** 0,18 W/m²K | 0,18 W/m²K | ALL §6.22.b.ii |
| Alternativa (tecniche o materiali innovativi, coperture a verde) | documentazione e certificazione dell'equivalenza | — | ALL §6.22.c |
| Sistemi schermanti delle superfici vetrate | valutazione puntuale e documentata della loro efficacia | — | ALL §6.22.a |

**Coperture: cool roof e climatizzazione passiva** (ALL §5.4, vale per tutti gli interventi sulle
coperture). È obbligatoria una verifica costi-benefici dell'uso di:

| Soluzione | Requisito | Fonte |
|---|---|---|
| Materiali ad elevata riflettanza solare, coperture piane | riflettanza solare «non inferiore a» **0,65** | ALL §5.4.a (RT scrive «> 0.65») |
| Materiali ad elevata riflettanza solare, coperture a falde | riflettanza solare «non inferiore a» **0,30** | ALL §5.4.a (RT scrive «> 0.30») |
| Climatizzazione passiva (free cooling, coperture a verde, …) | valutazione | ALL §5.4.b |

**Fattore solare dei serramenti (g_gl+sh)**: limiti in Tab. 16/17 dell'All. B, **non presenti**.
- Si verifica per le chiusure trasparenti orientate da E a O passando per S e per quelle orizzontali, esclusa la E.8.
- Si può omettere per i serramenti non esposti alla radiazione diretta.
- Si può verificare come g_t (g_tot) secondo UNI EN 13363-1/-2 e UNI EN 14501.
- Si possono considerare schermature mobili e chiusure oscuranti.
- In presenza di chiusure oscuranti la verifica si considera automaticamente soddisfatta (ALL §8.2).

### 2.7 Rendimenti η_H, η_W, η_C

- Non ci sono valori numerici nei file. Il limite è sempre l'efficienza dell'edificio di riferimento,
  calcolata con i valori dell'All. B (ALL §6.14.b.iv, §8.6.a, §8.9.a, §8.11).
- **Esonero dal calcolo** in caso di sostituzione del generatore (§8.6.d). Tutte le disposizioni si
  intendono rispettate se coesistono queste condizioni:
  - i. rendimento termico utile nominale ≥ quello di All. B §3.3 punto 1 (*non disponibile*);
  - ii. pompe di calore conformi ad All. B §3.3 punto 3 (*non disponibile*);
  - iii. se la potenza del focolare supera quella esistente di **oltre il 10%**, dimensionamento secondo UNI EN 12831-1:2018;
  - iv. con impianti a servizio di più unità o non residenziali: regolazione per ambiente o per unità con compensazione climatica, e contabilizzazione.
- Esonero analogo per le macchine frigorifere: §8.9.c, con rimando ad All. B «paragrafo 3.3, comma 3».
- **Scaldacqua unifamiliari**: esclusi dalla verifica di η_W (§8.11).
- **Biomassa < 5 kW** a integrazione dell'impianto esistente, senza altri interventi: esclusa dai requisiti di §8 (§8.7).
- **Biomassa in nuova costruzione o 1° livello**: si calcola l'efficienza globale media stagionale
  (§8.6.a); le lettere b–d di §8.6 valgono solo se tecnicamente possibili (§6.12).

### 2.8 Fattori di conversione in energia primaria

**NON PRESENTI NEI FILE.**
- f_P,tot e f_P,nren sono «definiti dalla metodologia di calcolo di cui al punto 4.2», cioè dall'Allegato H (ALL §4.5).
- **Teleriscaldamento e teleraffrescamento**: i gestori certificano i fattori f_P (rinnovabile, non
  rinnovabile, totale) al punto di consegna (§6.3):
  - certificato rilasciato da un ente accreditato ACCREDIA o equivalente EA (§6.4);
  - **validità 2 anni** (§6.5);
  - pubblicazione sul sito del gestore (§6.6);
  - con cogenerazione, allocazione secondo l'Allegato H (§6.7).
- **Pompe di calore, energia rinnovabile per le verifiche FER** (ALL §6.16.viii, rimando all'allegato 1 del D.Lgs. 199/2021):
  `Q_gn,amb = Q_gn,out · (1 − 1/SPF)`
  - SPF = prestazione media stagionale / η;
  - **η = 1** per le pompe di calore elettriche;
  - **η = 0,46** per le pompe di calore a gas.

### 2.9 Quote minime da fonti rinnovabili

#### 2.9.1 Quadro della DGR 6153/2026 — Allegato A: nazionale e Lombardia

| Caso (Allegato III D.Lgs. 199/2021, Sez. B) | D.Lgs. 199/2021 come modificato dal D.Lgs. 5/2026 | Lombardia dal 01/01/2027 (l.r. 11/2025) |
|---|---|---|
| 1.a Nuova costruzione (in Lombardia **compresa la demolizione e ricostruzione totale**) | 60% ACS **e** 60% di (ACS + riscaldamento + raffrescamento) | **65%** ACS **e** **65%** di (ACS + riscaldamento + raffrescamento) |
| 1.b Ristrutturazione importante di 1° livello | 40% ACS **e** 40% di (ACS + H + C) | **50%** ACS **e** **50%** di (ACS + H + C) («confermare», già previsto dalla DGR 2480/2019) |
| 1.c Ristrutturazione importante di 2° livello | 15% di (H + C) | 15% di (H + C) (invariato; «ove tecnicamente possibile», DGR considerando c) |
| 1.d Ristrutturazione dell'impianto termico | 15% di (H + C) | 15% di (H + C) (invariato) |
| 3. Potenza elettrica FER P = k·S [kW] | k = **0,025** edifici esistenti; k = **0,05** nuova costruzione | punto 3 invariato, più i valori di K in 2.9.3 |
| 5. Edifici pubblici | +5 punti percentuali sul punto 1; +10% sul punto 3 | +5 punti percentuali sul punto 1 (**sui valori già incrementati**); sul punto 3 «+10%» nell'All. A e «ulteriori dieci punti percentuali» nel dispositivo (vedi §6) |

Obblighi comuni:
- gli obblighi del punto 1.a non si possono assolvere con FER **solo elettriche** che alimentano
  dispositivi ad effetto Joule (DGR premesse; ALL §6.16.i, esteso a tutto §6.14.c);
- l'obbligo di potenza elettrica **non si applica** se l'edificio è allacciato a un teleriscaldamento o
  teleraffrescamento efficiente (D.Lgs. 102/2014, art. 2 c.2 lett. tt) che copre l'intero fabbisogno
  (DGR premesse). **Attenzione**: l'ALL §6.16.iii dice il contrario, cioè che con il teleriscaldamento
  decadono solo i punti i–ii e **resta** l'obbligo di potenza elettrica (iii). Vedi §6.

#### 2.9.2 Come le recepisce l'Allegato al Decreto 6437 (norma operativa per la verifica)

| Intervento | Quota ACS | Quota ACS + H + C | Quota H + C | K [kW/m²] per P = K·S | Fonte |
|---|---|---|---|---|---|
| Nuova costruzione (fino al 31/12/2026) | 60% | 60% | — | 0,05 | ALL §6.14.c.i–iii |
| Nuova costruzione (dal 01/01/2027) | **65%** | **65%** | — | 0,05, oppure 0,06 / 0,08 per le categorie di §6.27 | ALL §6.14.c.iv, §6.27 |
| Ristrutturazione importante di 1° livello | 50% | 50% | — | 0,025 | ALL §6.14.c.i–iii |
| Ristrutturazione importante di 2° livello | — | — | 15% | 0,025 | ALL §7.2.b |
| Ristrutturazione dell'impianto termico | — | — | 15% | 0,025 (tramite il rimando a §7.2.b) | ALL §8.8, §8.10 |
| Ampliamento > 15% o > 500 m³ con nuovo impianto | come §6.14.c, su fabbisogni e potenza della nuova porzione | | | | ALL §9.3.f |
| Edifici pubblici | +5 punti percentuali (su i, ii e iv); **+10%** sull'obbligo di potenza (iii) | | | | ALL §6.16.iv |

- **S** è la superficie in pianta al livello del terreno: la proiezione al suolo della copertura «così
  come visto da foto aerea», esclusi i balconi non coperti e le pertinenze (sulle quali però gli impianti
  si possono installare) (ALL §6.14.c.iii, §7.2.b.ii).
- **Base di calcolo delle quote termiche**:
  - intero edificio, se tutti i servizi sono soddisfatti da impianti comuni a tutte le unità;
  - singola unità, se ci sono anche impianti a servizio esclusivo di singole unità.
- La **potenza elettrica** si calcola sempre sull'intero edificio.
- Per ripartire gli obblighi FER (termici ed elettrici) fra le unità si usano i **millesimi di proprietà** (ALL §6.14, §7.2.b).
- **Solare termico e fotovoltaico sui tetti**: aderenti o integrati, con la stessa inclinazione e lo stesso orientamento della falda (§6.16.ii).
- **Impossibilità tecnica o economica** (§6.16.v–vii):
  - va motivata nella relazione tecnica esaminando tutte le opzioni tecnologiche;
  - in quel caso si deve ottenere EP_H,C,W,nren < EP_H,C,W,nren,limite, calcolato sui servizi effettivamente presenti;
  - il limite deriva da EP_H,C,W,nren,rif,standard (edificio di riferimento con Tab. 7 e Tab. 8 bis dell'All. B, *non disponibili*);
  - **non si applica** al 2° livello (§7.2.b.iii esclude §6.16 vi e vii).
- **Impianti installati su un altro edificio in Lombardia** (§6.17–6.20):
  - servono il consenso del proprietario e i dati nella relazione tecnica;
  - quella produzione **non** entra nell'EP né nella classe APE dell'edificio obbligato;
  - vietata l'installazione su aree agricole o a verde;
  - l'APE deve riportare tipo e caratteristiche degli impianti e i dati catastali dell'edificio ospitante;
  - la produzione non è riutilizzabile per gli obblighi dell'edificio ospitante.
- **Biomassa legnosa**: ammessa per §6.14.c punti i, ii e iv, se rispetta la DGR 4767/2025 (§6.21).

#### 2.9.3 Coefficiente K dal 01/01/2027 (ALL §6.27; DGR punto d; DGR All. A)

| Caso (nuova costruzione o ampliamento di qualsiasi entità) | K |
|---|---|
| Grandi strutture di vendita (art. 9 D.Lgs. 114/1998) | **0,06** |
| Piattaforme logistiche non intermodali, depositi di merci o veicoli, centri di magazzinaggio e simili, con superficie operativa **≤ 3 ettari** | **0,06** |
| Stesse categorie con superficie operativa **> 3 ettari** (insediamenti di rilevanza sovracomunale, art. 1 c.2 l.r. 15/2024) | **0,08** |
| Centri dati (Reg. delegato UE 2024/1364, artt. 1 e 2, numeri 1, 2 e 3) | **0,08** |

In caso di **ampliamento**, K si applica alla proiezione al suolo della sola porzione ampliata.

### 2.10 Requisiti NZEB / edificio a energia quasi zero

- **Definizione** (ALL §6.28): tutti gli edifici, nuovi o esistenti ed esclusi quelli di §3.2, che
  rispettano tutti i requisiti minimi delle nuove costruzioni, compreso §6.14 (b: H'_T, A_sol,
  EP_H,nd/EP_C,nd/EP_gl,tot, η; c: FER).
- **Obbligo**: dal 01/01/2016 per tutte le nuove costruzioni e le ristrutturazioni importanti di 1° livello (ALL §6.14).
- **Edificio a energia zero** (distinto dall'NZEB): **non indicato** nei testi.
- In RT (p.9) il progettista dichiara che l'edificio è NZEB secondo §6.28.

Tutti i rimandi all'All. B presenti nei file, **nessuno dei quali ha contenuto disponibile**:

| Rimando | Contenuto atteso secondo il testo che lo cita |
|---|---|
| Cap. 1 / punto 1 / 1.1 | edificio di riferimento: parametri energetici, caratteristiche termiche e impiantistiche |
| 1.2 / 1.2.2 | efficienze dell'edificio di riferimento / illuminazione |
| §2.2 | metodo di calcolo di A_sol,est/A_sup,utile |
| §3.1 punto 2 (o «paragrafo 1, punto 2») | U comprensiva dei ponti termici per il 2° livello |
| §3.1 punto 5 | correzione dei limiti U |
| §3.3 punti 1 e 3 | rendimento dei generatori; pompe di calore e macchine frigorifere |
| Tab. 7 | efficienze dei sottosistemi di utilizzazione |
| Tab. 8 / 8 bis | requisiti dei generatori / efficienze di generazione in energia primaria non rinnovabile |
| Tab. 9 | ventilazione |
| Tab. 10, 11, 12 | H'_T; A_sol,est/A_sup,utile; U delle pareti verticali (numerazione incoerente) |
| Tab. 13, 14 | U di coperture e pavimenti |
| Tab. 15 | U delle chiusure apribili |
| Tab. 16 / 17 | g_gl+sh |

### 2.11 Verifiche termoigrometriche (ALL §5.3)

- **Quando**: per ogni intervento sulle strutture opache che delimitano il volume climatizzato verso l'esterno.
- **Cosa**: si verifica l'assenza di:
  - a) rischio di muffe, con attenzione ai ponti termici nelle nuove costruzioni;
  - b) condensazioni interstiziali.
- **Dove**: sia sulla sezione corrente sia sul ponte termico.
- **Norme**: UNI EN ISO 13788 e UNI EN ISO 10211. Sono ammessi metodi più dettagliati previsti dalla 13788.
- **Condizioni interne**: quelle dell'appendice della 13788, metodo delle **classi di concentrazione**.
  Sono ammesse condizioni diverse se c'è un controllo dell'umidità interna di cui si tiene conto nel
  calcolo dei fabbisogni.
- **Criterio di superamento**: la quantità massima ammissibile non è superata e **non c'è residuo alla fine del ciclo annuale**.
- **Documentazione** (RT, allegati obbligatori): tabelle delle caratteristiche termiche, termoigrometriche
  e di massa efficace dei componenti opachi, con la verifica di muffe e condense.

### 2.12 Infrastrutture di ricarica per veicoli elettrici

Nell'estrazione i simboli del font Symbol sono diventati caratteri privati. Li ho interpretati così
(**interpretazione mia**):
- U+F0B3 → «≥» (es. «P_n ≥ 7,4 kW», «d ≥ 25 mm»);
- U+F0B8 → «÷» (es. «11÷20»).

Le celle unite delle colonne sono state ricostruite dalla sequenza del testo; vedi §6.

**ALL Tabella 1 — edifici non residenziali, parcheggi ad accesso pubblico** (§5.12, che però rimanda alla «Tabella 4»)

- Tipologia A: P_n ≥ 7,4 kW e almeno 32 A per fase.
- Tipologia B: corrente continua, P_n ≥ 50 kW.

| Caso | N. posti auto | Punti tipo A (minimo) | Punti tipo B (minimo) |
|---|---|---|---|
| Nuova costruzione | 11÷20 | 2 | – |
| | 21÷100 | 2 ogni 20 posti | – |
| | 101÷250 | 2 ogni 50 posti | 1 |
| | 251÷500 | (2 ogni 50, cella unita?) | 2 |
| | 501÷1000 | (idem) | 3 |
| | >1000 | (idem) | 4 |
| | >10 | canalizzazione per almeno 1 posto su 5: interna alle murature d ≥ 25 mm; interrata d ≥ 90 mm | |
| Ristrutturazione importante (solo se il parcheggio è interno e l'intervento riguarda il parcheggio o gli impianti elettrici dell'edificio, oppure se il parcheggio è adiacente e l'intervento riguarda il parcheggio o i suoi impianti elettrici) | 11÷20 | 1 | – |
| | 21÷100 | 1 ogni 20 posti | – |
| | 101÷250 | 1 ogni 50 posti | – |
| | 251÷500 | (1 ogni 50?) | 1 |
| | 501÷1000 | (idem) | 2 |
| | >1000 | (idem) | 3 |
| | >10 | canalizzazione come sopra | |
| Tutti i non residenziali esistenti: 50% (arrotondato per difetto) entro il 01/01/2025, 100% entro il 01/01/2030 | 21÷100 | 2 ogni 20 posti | – |
| | 101÷250 | 2 ogni 50 posti | 1 |
| | 251÷500 | (idem) | 2 |
| | 501÷1000 | (idem) | 3 |
| | >1000 | (idem) | 4 |

**ALL Tabella 2 — edifici non residenziali, parcheggi ad accesso privato** (§5.13)

| Caso | N. posti auto | Punti tipo A (minimo) | Punti tipo B (minimo) |
|---|---|---|---|
| Nuova costruzione | 11÷20 | 3 | – |
| | 21÷100 | 3 ogni 20 posti | – |
| | 101÷500 | 3 ogni 50 posti | 1 |
| | 501÷1000 | (idem?) | 2 |
| | >1000 | (idem?) | 3 |
| | >10 | canalizzazione per almeno 1 posto su 5: interna d ≥ 25 mm; interrata d ≥ 90 mm | |
| Ristrutturazione importante (stesse condizioni della Tab. 1) | 11÷20 | 2 | – |
| | 21÷100 | 2 ogni 20 posti | – |
| | 101÷500 | 2 ogni 50 posti | – |
| | 501÷1000 | (idem?) | 1 |
| | >1000 | (idem?) | 2 |
| | >10 | canalizzazione come sopra | |
| Tutti i non residenziali esistenti: 50% entro il 01/01/2025, 100% entro il 01/01/2030 | 21÷100 | 3 ogni 20 posti | – |
| | 101÷500 | 3 ogni 50 posti | 1 |
| | 501÷1000 | (idem?) | 2 |
| | >1000 | (idem?) | 3 |

**ALL Tabella 3 — edifici residenziali** (§5.15)

| Caso | N. posti auto | Obbligo |
|---|---|---|
| Nuova costruzione | >10 | canalizzazione per **tutti** i posti auto, con tubi corrugati: interna alle murature d ≥ 25 mm; interrata d ≥ 90 mm |
| Ristrutturazione importante (solo se il parcheggio è interno o adiacente e l'intervento lo riguarda) | >10 | come sopra (l'associazione dei diametri ai due casi non è chiara nell'estrazione) |

**Equivalenze ammesse** (§5.14.b):

| Invece di | si può installare |
|---|---|
| 10 punti di tipo A | 1 sistema di tipo B |
| 2 sistemi di tipo B | 1 sistema ultraveloce ≥ 150 kW |
| 4 sistemi di tipo B | 1 sistema ultraveloce ≥ 350 kW |
| 1 sistema di tipo B (**solo parcheggi ad accesso privato**) | 10 punti di tipo A |

Requisiti di funzione e sicurezza (§5.14 c–f):
- i punti devono supportare V1G / smart charging, oppure V2G;
- prevenzione incendi e sicurezza di manutentori e soccorritori;
- per i punti pubblici, invio dei dati alla PUN (PNIRE).

### 2.13 Altre soglie numeriche utili al software

| Requisito | Valore | Fonte |
|---|---|---|
| BACS negli edifici non residenziali con impianti termici | P_n > **290 kW** → classe **B** o superiore (UNI EN ISO 52120-1), se il tempo di ritorno semplice, al netto degli incentivi, è **< 6 anni**; altrimenti motivare nella relazione tecnica | ALL §5.10 |
| BACS nelle nuove costruzioni e 1° livello non residenziali | classe B minima (Tab. 1 UNI EN ISO 52120-1) | ALL §6.11 |
| Regolazione per singolo vano o zona alla sostituzione del generatore | obbligatoria se il tempo di ritorno è **< 6 anni**; altrimenti motivare | ALL §5.11 |
| Contatori di volume ACS e acqua di reintegro | impianti combinati nuovi con generatore **> 35 kW** | ALL §5.7 |
| Microcogenerazione | PES **≥ 0** (RT aggiunge «0,15 per impianti di cogenerazione»); dati prestazionali secondo UNI ISO 3046 | ALL §5.8; RT p.7 |
| Deroga all'altezza minima dei locali (pannelli radianti, isolamento interno) | fino a **10 cm**; nei comuni sopra **1.000 m** s.l.m. altezza minima **2,55 m** | ALL §5.5 |
| Teleriscaldamento vicino | rete a < **1.000 m** → predisposizione obbligatoria se la valutazione tecnico-economica è favorevole | ALL §6.2 |
| Diagnosi energetica | impianto con P_n ≥ **100 kW** (nuovo, ristrutturato o distacco dal centralizzato); opzioni obbligatorie da confrontare: a–f; non serve l'APE | ALL §8.5 |
| Sostituzione del generatore con aumento di potenza | > **10%** → dimensionamento UNI EN 12831-1:2018 | ALL §8.6.d.iii |
| Serra bioclimatica come volume tecnico | superficie ≤ **15%** della superficie utile del subalterno; riduzione ≥ **10%** di EP nren H; superficie disperdente ≥ **50%** trasparente; nessun impianto | ALL §10.2 |
| Scomputi volumetrici (l.r. 31/2014) | riduzione rispetto a EP_gl,tot dell'edificio di riferimento, oppure rispetto a tutte le U di All. B §1.1 | ALL §10.1 |
| Validità dell'APE | massimo **10 anni** dalla registrazione nel CEER; decade con interventi che cambiano la prestazione o la destinazione d'uso, o per mancati controlli degli impianti (31/12 dell'anno successivo) | ALL §12.8 |
| Costi | deposito APE **10 €**; targa **50,00 €**; iscrizione certificatore **120,00 €**/anno (metà nel 2° semestre) | ALL §12.5, §13.1, §17.7 |
| Affissione dell'APE | edifici pubblici o aperti al pubblico con superficie utile > **500 m²** | ALL §12.10 |
| APE obbligatorio per edifici della PA aperti al pubblico | superficie utile > **250 m²** | ALL §11.2.a |
| Controlli sugli APE | entro **4 anni** dalla registrazione | ALL §15.1 |
| Controlli comunali sulla conformità dei lavori | in corso d'opera o entro **5 anni** dalla fine lavori | ALL §4.14 |
| Incarico al certificatore (nuova costruzione, 1° e 2° livello) | prima dell'inizio lavori ed entro **30 giorni** dal titolo; va dichiarato nella relazione tecnica | ALL §12.11 |
| Corsi per certificatori | ≥ **80 h** (27 h in FAD), frequenza > **85%** | ALL §17.2, §17.4 |

### 2.14 Classificazione APE (ALL §16)

- **Classe**: si determina da EP_gl,nren confrontato con EP_gl,nren,rif,standard, cioè l'edificio di
  riferimento con gli elementi di All. B §1 e le tecnologie standard di Tab. 2, **senza FER**.
  EP_gl,nren,rif,standard è il limite fra le classi A1 e B.
- **Servizi considerati**: solo quelli presenti nell'edificio reale. La climatizzazione invernale e,
  nel **solo residenziale**, l'ACS si considerano **sempre presenti** (§16.4).

**ALL Tabella 3 — scala delle classi**

| Classe | Intervallo (rapporto EP_gl,nren / EP_gl,nren,rif) |
|---|---|
| A4 | ≤ 0,40 |
| A3 | > 0,40 e ≤ 0,60 |
| A2 | > 0,60 e ≤ 0,80 |
| A1 | > 0,80 e ≤ 1,00 |
| B | > 1,00 e ≤ 1,20 |
| C | > 1,20 e ≤ 1,50 |
| D | > 1,50 e ≤ 2,00 |
| E | > 2,00 e ≤ 2,60 |
| F | > 2,60 e ≤ 3,50 |
| G | > 3,50 |

**ALL Tabella 4 (§16.5) — qualità invernale del fabbricato** (EP_H,nd,limite = edificio di riferimento con i requisiti minimi di All. B §1)

| Condizione | Qualità |
|---|---|
| EP_H,nd ≤ 1 · EP_H,nd,limite | Alta |
| 1 · EP_H,nd,limite < EP_H,nd ≤ 1,7 · EP_H,nd,limite | Media |
| EP_H,nd > 1,7 · EP_H,nd,limite | Bassa |

**ALL Tabella 5 (§16.6) — qualità estiva del fabbricato**

| A_sol,est/A_sup utile | Y_IE [W/m²K] | Qualità |
|---|---|---|
| ≤ 0,03 | ≤ 0,14 | Alta |
| ≤ 0,03 | > 0,14 | Media |
| > 0,03 | ≤ 0,14 | Media |
| > 0,03 | > 0,14 | Bassa |

Y_IE è la media pesata sulle superfici, **escluse le verticali esposte a Nord**. Se tutte le superfici
verticali sono esposte a Nord si pone **Y_IE = 0,14** (§16.7).

---

## 3. Differenze rispetto al DM 26/06/2015

Riporto solo ciò che i testi rendono esplicito. Per tutto il resto (valori U, H'_T, fattori f_P,
rendimenti): **non indicato**, perché le tabelle dell'All. B e H non sono nei file.

| Aspetto | Cosa dicono i testi | Fonte |
|---|---|---|
| Parametri di riferimento per l'isolamento termico e requisiti tecnici degli impianti | «modifica» introdotta dal DM 28/10/2025 e recepita nell'All. B; **valori non indicati** | DEC premesse |
| Parametri per il calcolo delle prestazioni | «aggiornamento» (All. H); **dettaglio non indicato** | DEC premesse |
| BACS | nuovo obbligo per i non residenziali con impianti > 290 kW (classe B, ritorno < 6 anni) | DEC; ALL §5.10 |
| Ricarica dei veicoli elettrici | nuove tabelle degli obblighi (Tab. 1–3) | DEC; ALL §5.12–5.16 |
| FER per 2° livello e ristrutturazione dell'impianto termico | nuovo obbligo del 15% di (H + C) e P = 0,025·S (dal D.Lgs. 199/2021 e 5/2026) | DEC; DGR; ALL §7.2.b, §8.8 |
| Quote FER nazionali | 60% per le nuove (il testo non riporta i valori precedenti del DM 26/06/2015); 40% per il 1° livello | DGR All. A |
| Quote FER in Lombardia | 65% nuove dal 2027; 50% per il 1° livello (in vigore dalla DGR 2480/2019) | DGR |
| Deroga per impossibilità tecnica, economica o funzionale | introdotta (con verifica di EP_H,C,W,nren,limite) | DEC; ALL §6.16.v–vii |
| Regolazione per vano alla sostituzione del generatore (ritorno < 6 anni) | prescrizione presente (§5.11); non è detto se sia nuova rispetto al DM 2015 | ALL §5.11 |
| Tutto il resto | **non indicato** | — |

---

## 4. Relazione tecnica (modello CENED 2026, file RT)

Il modello è un **Allegato C provvisorio** («Versione 03/06/2026 – rif. Decreto 6437/2026»), in attesa del
format nazionale previsto dal DM 28/10/2025 (DEC punti 2–3). Contiene **tre schemi**, con numerazione
delle sezioni identica (1–9) ma contenuti diversi:

- **Schema A** (RT p.1–12): nuove costruzioni, ristrutturazioni importanti di 1° livello, ampliamenti, recuperi di volume, NZEB (applicazione integrale).
- **Schema B** (RT p.13–23): riqualificazione energetica e ristrutturazioni importanti di 2° livello, cioè interventi su involucro e impianti (applicazione parziale).
- **Schema C** (RT p.24–33): riqualificazione energetica dei soli impianti tecnici (applicazione parziale).

Deposito e varianti:
- la relazione si deposita in forma digitale con CILA, permesso di costruire o SCIA (ALL §4.8);
- negli enti soggetti alla L.10/91 art. 19 va integrata con l'attestazione del Responsabile per la conservazione e l'uso razionale dell'energia;
- può riferirsi a una o più unità dello stesso fabbricato (§4.9);
- in caso di varianti essenziali va aggiornata (§4.12);
- a fine lavori servono l'asseverazione del DL e l'APE, senza i quali la dichiarazione di fine lavori è inefficace (§4.11, §4.13).

### 4.1 Sezioni e dati richiesti

| Sez. | Contenuto | Schema A | Schema B | Schema C |
|---|---|---|---|---|
| **1. Informazioni generali** | Comune, Provincia; tipo di opere; edificio pubblico / a uso pubblico (sì/no); dati catastali (mappale, sezione, foglio, particella, subalterni); richiesta di permesso di costruire (n., data); titolo PdC/DIA/SCIA/CIL-CIA (n., data); variante (n., data); categoria di destinazione d'uso (All. A, più categorie se miste); n. di unità immobiliari; committente; progettisti e DL di impianti di climatizzazione, isolamento, ricambio d'aria e illuminazione; tecnico incaricato dell'APE | tutti + **edificio a uso temporaneo** (sì/no) e **data di scadenza** dell'opera + caselle per grande struttura di vendita / logistica ≤ 3 ha / logistica > 3 ha / datacenter (servono per il valore di K) | tutti, senza temporaneo né categorie K | come B |
| **2. Fattori tipologici** | rimando ai primi tre allegati obbligatori della sez. 8 | ✓ | ✓ | ✓ |
| **3. Parametri climatici** | GG (DPR 412/93); temperatura minima di progetto (UNI 5364, espressa in «°K»); temperatura massima estiva di progetto (in «°K») | ✓ | ✓ | ✓ |
| **4. Dati tecnici e costruttivi** | Inverno: V lordo climatizzato [m³], S disperdente [m²], S/V [1/m], superficie utile climatizzata [m²], θ_int e UR_int di progetto, contabilizzazione del calore (sì/no, diretta o indiretta). Estate: V, S, superficie utile, θ e UR di progetto, contabilizzazione del freddo | ✓ | ✓ | ✓ (sezione duplicata nel testo) |
| 4. Informazioni generali e prescrizioni | teleriscaldamento a < 1000 m (sì/no, opere o motivazione) | ✓ | – | – |
| | BACS (sì/no, classe con minimo B UNI EN 52120-1; se no, ragioni) | ✓ (ragioni se non residenziale > 290 kW) | ✓ (ragioni se non residenziale) | – |
| | cool roof (sì/no; riflettanza > 0,65 piane, > 0,30 a falda; se no, ragioni tecnico-economiche) e climatizzazione passiva delle coperture (sì/no, ragioni) | ✓ | ✓ | ✓ |
| | energy meter (sì/no, descrizione); contabilizzazione diretta di calore, freddo e ACS (sì/no, sistema alternativo e ragioni) | ✓ | – | – |
| | valvole termostatiche o termoregolazione per ambiente o unità (sì/no); compensazione climatica con impianti centralizzati (sì/no, ragioni) | – | ✓ | ✓ |
| | **FER termiche**: % ACS e % ACS + H + C; caselle per esenzione da teleriscaldamento efficiente, biomassa (DGR 4767/2025), impossibilità tecnica (§6.14.c) con **EP_H,C,W,nren < EP_H,C,W,nren,limite** | ✓ | % H + C «(minimo 15%)» + caselle teleriscaldamento e biomassa | come B |
| | **FER elettriche**: S [m²], P = K·S, descrizione e potenza degli impianti, compresi quelli su altro edificio (§6.17); motivazioni dell'eventuale impossibilità | ✓ | ✓ | ✓ |
| | regolazione automatica per locale o zona e compensazione climatica (sì/no, ragioni) | ✓ | (vedi sopra) | (vedi sopra) |
| | efficacia dei sistemi schermanti; **verifiche §6.22.b** (M_s > 230 kg/m²; Y_IE < 0,10 per le verticali non NO-N-NE; Y_IE < 0,18 «verticali ed orizzontali», vedi §6); verifiche §6.22.c | ✓ | – | – |
| | **ricarica veicoli**: parcheggio pubblico / privato, interno o adiacente, intervento sul parcheggio o sugli impianti elettrici, n. posti, n. punti (tipo A, tipo B, ultraveloce ≥ 150 kW, ≥ 350 kW), canalizzazioni (n., interna / interrata) | ✓ | ✓ | – |
| **5. Dati impianti — 5.1 Impianti termici** | a) descrizione (tipologia, generazione, termoregolazione, contabilizzazione, distribuzione, ventilazione forzata, accumulo, ACS); trattamento chimico dell'acqua (UNI 8065, D.Lgs. 18/2023); **filtro di sicurezza** (solo B e C). b) contatori di volume ACS e reintegro; caldaia o generatore d'aria calda: biomassa (sì/no, conformità alle DGR 5360/2021, 3649/2024, 4720/2025), combustibile, fluido termovettore, emissione, P utile nominale [kW], η utile al 100% Pn e al 30% Pn [%], combustibili multipli con percentuali; pompa di calore elettrica o a gas: tipo, lato esterno, fluido lato utenze, P termica, P elettrica, COP, EER; microcogenerazione: PES ≥ 0 (0,15 per la cogenerazione) e procedura; teleriscaldamento: efficiente (D.Lgs. 102/2014), certificazione dei f_P (protocollo, valori), potenza dello scambiatore [kW]; altre macchine. c) regolazione: conduzione invernale ed estiva, sistema di gestione, regolazione climatica in centrale, centralina (livelli nelle 24 h), regolatori di ambiente o zona (n., funzioni, livelli), motivazione della mancata installazione. d) contabilizzazione per unità (n., descrizione). e) terminali (n., tipo, P). f) canne fumarie (descrizione, norma di dimensionamento). g) trattamento dell'acqua. h) isolamento della rete (tipo, λ, spessore). i/j/k) schemi unifilari (terminali, generatori, distribuzione, controllo, sicurezza) | ✓ | ✓ | ✓ |
| 5.2–5.5 (A), 5.6–5.9 (B), 5.10–5.13 (C) | fotovoltaico, solare termico, illuminazione, altri impianti (descrizione e schemi); livello minimo di efficienza dei motori di ascensori e scale mobili | ✓ | ✓ | ✓ |
| **6. Principali risultati dei calcoli** | **A**: dichiarazione NZEB (§6.28); a) U dei divisori ≤ 0,8 W/m²K, verifica termoigrometrica (allegati), ricambi d'aria (n. medio nelle 24 h per zona), portata G con VMC [m³/h], portata e efficienza del recupero di calore; b) H'_T e H'_T,L (Tab. 10 e 11) con verifica; A_sol,est/A_sup,utile < limite (Tab. 11); EP_H,nd, EP_C,nd, EP_gl,tot con i limiti e le verifiche; η_H, η_W, η_C > limite; c) solare termico (tipo collettore, installazione, supporto, inclinazione e orientamento, accumulo, integrazione, potenza e % copertura); d) fotovoltaico (connessione, tipo moduli, installazione, supporto, inclinazione e orientamento, potenza e % copertura); e) consuntivo energia: E_del, EP_gl,ren, E_exp, rinnovabile in situ, EP_gl,tot; f) fattibilità dei sistemi ad alta efficienza (schede) | ✓ | – | – |
| | **B**: g) per ogni elemento: tipo (solaio, copertura, parete esterna, parete verso sottotetto, verso ambiente non riscaldato, verso terreno), isolante (cappotto esterno o interno, intercapedine; spessore in cm; tipo), U ante e post operam, Y_IE post operam; confronti con le tabelle All. B («13» verticali, «14 e 15» orizzontali, «16» trasparenti e opache apribili, «17» g_gl+sh), classe di permeabilità all'aria dei serramenti; U dei divisori ≤ 0,8; verifica termoigrometrica; ricambi d'aria, VMC, recupero di calore; h) η_H, η_W, η_C > limite; i) solare termico; j) fotovoltaico; k) consuntivo energia; l) fattibilità dei sistemi ad alta efficienza | – | ✓ | – |
| | **C**: caso §8.5 (≥ 100 kW) sì/no, diagnosi eseguita sì/no, motivazione della scelta; m) ricambi d'aria; n) η_H > η_H,limite, η_C > η_C,limite (All. B §1.2); ACS: apparecchi conformi alle direttive 2009/125/CE e 2010/30/UE (sì/no), η_W > η_W,limite; illuminazione e ventilazione conformi (sì/no); o) solare termico; p) fotovoltaico; q) consuntivo; r) fattibilità | – | – | ✓ |
| **7. Deroghe** | motivazione delle deroghe ammesse (testo libero) | ✓ | ✓ | ✓ |
| **8. Allegati obbligatori** (caselle) | **A**: piante con orientamento e uso; prospetti e sezioni con protezioni solari fisse; elaborati dei sistemi solari passivi; schemi degli impianti; tabelle dei componenti opachi (termiche, termoigrometriche, massa efficace, verifica di muffe e condensa); tabelle dei componenti finestrati (termiche, permeabilità); schede di fattibilità dei sistemi ad alta efficienza; documentazione per i generatori a biomassa. **B**: piante; tabelle opachi; tabelle finestrati; schemi impianti; biomassa. **C**: piante; schemi impianti; biomassa. Tutti: altri allegati facoltativi | ✓ | ✓ | ✓ |
| **9. Dichiarazione di rispondenza** | iscrizione all'albo (ordine, provincia, n.), consapevolezza delle sanzioni (art. 27 l.r. 24/2006); dichiara: a) conformità al decreto; b) **solo A**: rispetto degli obblighi FER; c) coerenza dei dati con gli elaborati. Data e firma | a, b, c | a, b (= c di A) | come B |

### 4.2 Contenuti che l'ALL chiede nella relazione tecnica (checklist per il generatore)

- **§4.16**: valutazione di fattibilità tecnica, funzionale, ambientale ed economica dei sistemi ad alta
  efficienza (FER, cogenerazione, teleriscaldamento, pompe di calore, monitoraggio), per nuove
  costruzioni e ristrutturazioni importanti.
- **§5.4**: esito della verifica costi-benefici su cool roof e climatizzazione passiva.
- **§5.8**: calcolo del PES annuo atteso, con le temperature medie mensili di ritorno.
- **§5.10 / §5.11**: motivazione della mancata installazione di BACS o regolazione per vano.
- **§6.2**: motivazione della soluzione scelta per il teleriscaldamento a < 1000 m.
- **§6.8**: documentazione se manca la compensazione climatica.
- **§6.16.v**: impossibilità di rispettare gli obblighi FER, con l'analisi di tutte le opzioni.
- **§6.17**: dati dell'impianto e dell'edificio ospitante.
- **§6.20**: dimostrazione degli obblighi FER al netto degli impianti «ospitati».
- **§8.2**: sostituzione dei serramenti con relazione parziale (permeabilità, U nuova ed esistente, g).
- **§8.5**: soluzione motivata dalla diagnosi energetica.
- **§12.11**: nomina del certificatore APE, entro l'inizio dei lavori.
- **§10.2.b**: riduzione ≥ 10% dovuta alla serra bioclimatica. Il testo rimanda ancora all'«Allegato C del decreto regionale n. 2456».

---

## 5. Modulo F del manuale CENED+2.0: sintesi operativa

**Attenzione**:
- il manuale è la **versione del 15.10.2019** e cita il DDUO 2456/2017, cioè numerazioni e tabelle
  **precedenti** al Decreto 6437/2026;
- la definizione NZEB è indicata come «punto 6.21», mentre nell'ALL 2026 è al §6.28;
- «Tabella 10» (H'_T) e «Tabella 11» (A_sol) sono le tabelle del decreto 2456/2017.

### 5.1 Calcolo dell'APE (F|1)

1. **Verifica › Calcola involucro** (dopo i moduli Ambiente, Porte e Dispersioni). Output intermedi
   per **zona termica** e per **subalterno**, annuali:
   - Q per raffrescamento e riscaldamento, in condizioni effettive e di riferimento [kWh];
   - entalpia nominale per deumidificazione e umidificazione [kWh];
   - grafici mensili.
2. **Verifica › Calcola edificio** (dopo il modulo impianti).
   - Output intermedi:
     - fabbisogni termici ed elettrici per sistema e servizio;
     - per UTA e centrali: fabbisogno termico e frigorifero in ingresso all'UTA, energia elettrica
       dell'UTA, energia consegnata per vettore e per servizio a ogni generatore, elettricità
       autoprodotta e autoconsumata, elettricità dalla rete, elettricità autoprodotta esportata;
     - **fattori di sottodimensionamento** mensili per servizio e per centrale;
     - grafici mensili e report grafico personalizzato.
   - Output finali:
     - scala e classe, EP_gl,nren, GG e zona climatica;
     - EP ren, nren e tot per servizio e totale [kWh/m²anno];
     - energia primaria [kWh];
     - CO₂ [kg CO₂eq] e indice [kg CO₂eq/m²anno];
     - efficienze globali medie annue per servizio;
     - fabbisogni per servizio;
     - dati geometrici invernali (V, S, S/V, superficie utile) ed estivi;
     - grafici di confronto fra edificio reale ed edifici di riferimento («APE e progetto»);
     - consuntivo.
3. **Impianti sottodimensionati** (#F.1). Si applica solo in certificazione, per ogni mese, servizio e
   centrale, in base al fattore di sottodimensionamento:

| Fattore di sottodimensionamento | Trattamento del fabbisogno residuo |
|---|---|
| ≤ 15% | trascurato |
| > 15% e ≤ 75% | il fabbisogno residuo è coperto da un generatore a gas (riscaldamento/ACS) o da una macchina frigorifera elettrica (raffrescamento) con l'«efficienza media prevista dalla normativa in caso di assenza di impianto» |
| > 75% | **l'intero** fabbisogno è calcolato con il generatore standard sopra descritto |

   Il ricalcolo è automatico e segnalato con messaggi e nella preview dell'APE.

4. **Verifica › Preview APE**:
   - genera il fac-simile in PDF;
   - l'APE definitivo nasce solo al deposito dell'XML firmato nel CEER (Verifica › Esporta file XML);
   - l'APE mostra EP_gl,nren e la classe da A4 a G;
   - la tabella «Dati di dettaglio degli impianti» a pag. 3 ha 2 campi per i generatori di
     riscaldamento, 2 per il raffrescamento e 1 per l'ACS; gli altri generatori vanno nelle note;
   - con l'opzione «Edificio senza impianto» compare «Impianto simulato in quanto assente».

### 5.2 Interventi migliorativi (F|2)

- **Obbligatori** nell'APE (ALL §12.14). In MF si possono omettere solo per le classi A3/A4, se non
  convenienti; l'ALL 2026 aggiunge «APE redatti per Nuova costruzione o Ristrutturazione importante».
  La dichiarazione va nelle note «Informazioni sul miglioramento».
- **Edificio senza impianto**: almeno le raccomandazioni sull'involucro, più l'indicazione di un impianto
  di riscaldamento e, nel residenziale, di ACS.
- **Definizione di intervento raccomandato**: migliora sia EP_gl,nren sia la classe raggiungibile,
  oppure migliora EP_gl,nren a parità di classe. Il costo-beneficio si valuta sul **tempo di ritorno
  semplice** (ALL §12.14).
- **Procedura**:
  1. File › Nuovo › Nuovo intervento migliorativo;
  2. scegliere il tipo: **REN 1** involucro opaco, **REN 2** involucro trasparente, **REN 3**
     climatizzazione invernale, **REN 4** climatizzazione estiva, **REN 5** altri impianti, **REN 6**
     fonti rinnovabili, **REN 7** interventi cumulativi;
  3. indicare il nome (compare come descrizione a pag. 2 dell'APE), la spunta «Ristrutturazione
     importante» e il tempo di ritorno;
  4. nel file figlio: inserire i dati, salvare e calcolare;
  5. nel file padre, sezione «Interventi migliorativi»: trascinare l'intervento dalla palette nella tabella.
- **Cumulativo**: File › Nuovo › Nuovo intervento migliorativo cumulativo; parte da un intervento singolo
  e si aggiungono gli altri, poi si calcola e si associa.
- **Stato dei figli**: icona verde se il file figlio esiste ed è calcolato, rossa altrimenti. Se un figlio
  viene modificato va scollegato e riassociato. Per spostare il progetto su un altro PC servono padre e figli.
- **Sull'APE**, per ogni intervento: tempo di ritorno, classe raggiungibile, EP_gl,nren. Ci sono anche il
  grafico di confronto e il «Confronto con edificio reale» per servizio.

### 5.3 Verifiche NZEB (F|3)

- **Modalità**: File › Nuovo › Nuovo edificio NZEB. È solo un **ausilio preliminare**: non sostituisce
  la relazione tecnica.
- **Output NZEB**, con esito per ciascun indicatore (superata / non superata / non eseguibile, per
  esempio η_C senza impianto di raffrescamento):
  - H'_T < limite (Tab. 10, decreto 2456/2017);
  - A_sol,est/A_sup,utile < limite (Tab. 11);
  - EP_H,nd, EP_C,nd, EP_gl,tot < limiti dell'edificio di riferimento;
  - η_H, η_W, η_C > limiti.
- **Altre sezioni**:
  - geometria invernale ed estiva (V lordo, S, S/V, superficie utile riscaldata e raffrescata);
  - quote FER per ACS e per H + ACS + C, con esito;
  - **valutazione dei sistemi schermanti**: per ogni serramento non esposto a NO/N/NE, verifica mensile
    che nei mesi estivi il fattore di ombreggiamento per ostruzioni e aggetti sia **inferiore al
    coefficiente massimo di schermatura, posto pari a 0,3**, più una verifica globale estate e inverno.
    **Questo criterio numerico è solo di CENED e non compare nell'ALL**, che chiede soltanto la
    «valutazione» (§6.22.a);
  - inerzia degli elementi opachi (M_s > 230 kg/m² o Y_IE < 0,10 per le verticali non NO/N/NE;
    Y_IE < 0,18 per orizzontali e inclinate);
  - consuntivo energia: E_del, EP_gl,ren, E_exp, rinnovabile in situ, EP_gl,tot.
- **Da NZEB ad APE**: File › Nuovo › Nuovo edificio APE da NZEB copia il file. Poi vanno completati:
  Dati generali (sopralluoghi), Dati certificazione, Dati APE, Subalterno › Dati APE, Subalterno › Terzo responsabile.
- Nella schermata «Dati APE» c'è la spunta «L'edificio oggetto dell'APE è un edificio a energia quasi zero».

### 5.4 Report (F|4)

- **Report sintetico**: file .xls con un foglio per zona, per sistema (riscaldamento, raffrescamento,
  ACS, ventilazione, trasporto), per centrale termica, frigorifera ed elettrica, più l'output finale.
- **Report di dettaglio**: da attivare in Configurazioni. Fogli: ARCHIVIO (dati climatici, strutture
  opache, serramenti, ponti), terreni, ambienti confinanti, zone, sistemi, UTA, centrali, OUTPUT,
  notifiche e messaggi, Verifiche NZEB, interventi migliorativi.
  - Il file .zip esportato permette di rigenerare il report senza ricalcolo.
  - Categorie dei messaggi: errori bloccanti, struttura del file, dati climatici, involucro (zone,
    ambienti confinanti, dispersioni, coerenza con l'epoca), impianto (terminali, sistemi, centrali, altro), output, altro.

---

## 6. Punti ambigui o illeggibili nel testo estratto

**Mancanze**

1. **Allegato B e Allegato H assenti.** Mancano tutte le tabelle numeriche di U, H'_T, A_sol, g_gl+sh,
   dell'edificio di riferimento, dei rendimenti e dei fattori f_P. Non sono ricostruibili dai file forniti.
2. **Allegato A (Definizioni) assente.** Mancano le definizioni formali di ristrutturazione importante
   di 1° e 2° livello e di riqualificazione, e le categorie E.x.
3. **Data di entrata in vigore del Decreto 6437** non indicata: solo la pubblicazione sul BURL. Il DM 28/10/2025 vale per i titoli richiesti dal 03/06/2026.

**Numerazione delle tabelle dell'Allegato B incoerente**

4. H'_T: ALL §6.14.b.i dice «Tabella 10 o 11»; §9.2–9.5 dicono Tab. 10.
5. A_sol,est: ALL §6.14.b.ii dice «Tabella 12»; §9.2–9.5, RT e MF dicono Tab. 11.
6. U delle pareti verticali: ALL §8.2.a dice «Tabella 12»; RT p.20 dice «tabella 13».
7. Coperture e pavimenti: ALL §8.2.b dice Tab. 13 e 14; RT dice «14 e 15».
8. Chiusure apribili: ALL §8.2.c dice Tab. 15; RT dice «16».
9. g_gl+sh: ALL §8.2.d dice «Tabella 16»; la coda di §8.2 dice «Tabella 17» e anche «Tabella 8 dell'Appendice B dell'Allegato 1» (formulazione del DM). RT dice «17».

**Rimandi interni errati o incoerenti**

10. U con i ponti termici (2° livello): ALL §5.1.b rimanda a «Allegato B, paragrafo 1, punto 2», §7.2.c a «paragrafo 3.1, punto 2».
11. ALL §5.12 rimanda alla «Tabella 4» per la ricarica pubblica, ma la tabella è intitolata **Tabella 1**.
12. Il nome «Tabella 4» è usato due volte (indici di §6.14 e qualità invernale di §16.5).
13. ALL Tabella 2 (tecnologie standard): per il trasporto rimanda al «punto 5.10», che ora tratta dei BACS. Gli ascensori sono al §5.9.
14. ALL §7.2.b cita «punto iii (potenza elettrica)», ma in §7.2.b la potenza è il punto ii; il punto iii è un rimando.
15. ALL §9.3.f cita il D.Lgs. 28/2011 («Allegato 3») invece del D.Lgs. 199/2021.
16. ALL §4.13 rimanda al «punto precedente 4.13» (probabilmente 4.12).
17. ALL §10.2.b rimanda all'«Allegato C del decreto regionale n. 2456 dell'8.3.2017».

**Contraddizioni fra ALL e DGR sugli obblighi FER**

18. **Teleriscaldamento efficiente e potenza elettrica.** Per la DGR (premesse, sul testo nazionale) l'obbligo di potenza **non si applica** con teleriscaldamento che copre tutto il fabbisogno. Per l'ALL §6.16.iii l'edificio **resta soggetto** al §6.14.c.iii.
19. **Edifici pubblici, obbligo di potenza.** DGR All. A e ALL §6.16.iv: «incrementati del 10%». DGR dispositivo punto 2 e DEC premesse: «ulteriori dieci punti percentuali» rispetto al punto 3, che però è un coefficiente K e non una percentuale.
20. **K dal 2027.** Nella DGR è «pari o maggiore a 0,06» (con il refuso «pari o maggiore a deve essere pari a»); nell'All. A è «pari a 0,06» per le 0,06 e «pari o maggiore a 0,08» per le 0,08. L'ALL §6.27 dice «pari a».
21. **Demolizione e ricostruzione totale.** La DGR All. A la include esplicitamente nella nuova costruzione (65%); l'ALL §6.14 non lo ripete.
22. **2° livello e ristrutturazione dell'impianto.** La DGR dice «mantenere, ove tecnicamente possibile» il 15%; l'ALL §7.2.b dice «ove tecnicamente, economicamente e funzionalmente fattibile».

**Tabelle della ricarica veicoli (§5.12–5.15)**

23. Simboli persi nell'estrazione (caratteri privati del font Symbol). Li ho interpretati come «≥» per P_n e diametri e come «÷» per le fasce di posti, per esempio «1120» = 11÷20.
24. Le celle unite rendono incerta l'attribuzione delle colonne tipo A e tipo B per le fasce oltre 250 (pubblico) o 500 (privato): non è chiaro se «2 ogni 50 posti» continui nelle fasce successive.
25. Nella Tab. 3 non è chiaro a quale caso si riferiscano i diametri 25 e 90 mm.

**Differenze fra modello di relazione tecnica e ALL**

26. **Cool roof.** ALL §5.4 dice «non inferiore a» 0,65 / 0,30 (≥); RT dice «> 0.65» / «> 0.30» (>).
27. **Y_IE < 0,18.** RT (p.5) scrive «Tutte le pareti opache verticali ed orizzontali»; ALL §6.22.b.ii dice «orizzontali e inclinate».
28. **PES.** RT aggiunge «(0,15 per impianti di cogenerazione)», valore assente nell'ALL (§5.8 dice solo PES ≥ 0).
29. **Unità di misura.** RT usa «°K» per le temperature di progetto e «W/m²°K».
30. **Numerazione e duplicazioni.** Nello Schema C la sezione 4 è duplicata e i sottoparagrafi di 5.1 saltano da «h» a «k». Negli Schemi B e C la sez. 6 è lettere g–r. Negli Schemi B e C l'impianto termico è 5.1 e gli altri impianti sono 5.6–5.9 e 5.10–5.13, ma la sez. 8 rimanda ancora a «5.1 lettera i, 5.2–5.5». Nel RT alcuni paragrafi sulle «macchine diverse» sono ripetuti due volte.
31. **Versione dell'Allegato C.** Il RT è intestato «Allegato C» e fa riferimento al «decreto attuativo della DGR 3868/2015», ma il DEC dice che l'Allegato C non è ancora aggiornato: è un modello provvisorio.
32. **Rimandi al DM.** Lo Schema B (sez. 6.h) rimanda al «comma 3.3 dell'Allegato 1 del decreto di cui all'art. 4 c.1 D.Lgs. 192/2005», cioè al DM, e non all'ALL.
33. **Fonti da verificare nello Schema C (sez. 6.n).** Cita le direttive 2009/125/CE e 2010/30/UE, mentre l'ALL §8.11–8.13 cita il Reg. (UE) 2017/1369.

**Altri punti dell'ALL**

34. **Termine BACS.** «Entro il 3 giugno 2026» (ALL §5.10) è una scadenza già passata alla data di adozione del modello: non è chiaro se sia un obbligo di adeguamento degli esistenti o un requisito progettuale.
35. **Tabella 5 (§16.6).** Nell'estrazione la parola «Media» è su due righe: la lettura adottata («Media» per entrambi i casi misti) è coerente ma dedotta dalla disposizione.
36. **§16.6** contiene un refuso: «è definito alla trasmittanza».
37. **Simbolo η perso.** Nell'ALL (Tabella 4 di §6.14 e §6.14.b.iv) e nel RT la lettera η appare come carattere privato o spazio: «H», «W», «C» stanno per η_H, η_W, η_C.

**Manuale CENED (Modulo F)**

38. **MF è del 2019.** Cita il DDUO 2456/2017, i punti 6.21 e 12.14 dell'epoca e le Tab. 10 e 11 del 2017. Il criterio «coefficiente di schermatura 0,3» non ha corrispondenza nell'ALL. Il frontespizio del MF è frammentato in sillabe (illeggibile ma senza contenuto tecnico).

---

## 7. Allegato B del Decreto 6437/2026 (aggiunto dopo aver ricevuto gli allegati)

Fonte: `Allegato-B.pdf` (12 pagine). Valori solo per le zone E ed F: in Lombardia i comuni sono in zona
E (1359) o F (204). Implementato in `cened/verifiche.py`.

| Tabella | Grandezza | E | F |
|---|---|---|---|
| 1 (rif.) | U opache verticali (esterno, ZNC, terreno) | 0,26 | 0,24 |
| 2 (rif.) | U coperture | 0,22 | 0,20 |
| 3 (rif.) | U pavimenti | 0,26 | 0,24 |
| 4 (rif.) | U chiusure trasparenti/opache e cassonetti | 1,40 | 1,10 |
| 5 | U divisori tra unità immobiliari (tutte le zone) | 0,8 | 0,8 |
| 6 / 17 | g_gl+sh finestre E→S→O (con schermatura mobile) | 0,35 | 0,35 |
| 13 | U max opache verticali (2° livello, riqualificazione) | 0,28 | 0,26 |
| 14 | U max coperture | 0,24 | 0,22 |
| 15 | U max pavimenti | 0,29 | 0,28 |
| 16 | U max chiusure trasparenti/opache e cassonetti | 1,40 | 1,10 |

H'_T limite, Tab. 10 (nuove costruzioni, ampliamenti, recuperi): S/V > 0,7 → 0,50 / 0,48;
0,4 < S/V ≤ 0,7 → 0,55 / 0,53; S/V ≤ 0,4 → 0,75 / 0,70 (E / F).

H'_T limite, Tab. 11 (1° livello), per quota vetrata ex ante ≤ 9, 14, 19, 24, 28, 33, 38, 43, 47, 52,
57, 62, 67, 71, 76, 81, 86, 90, 95, 100 %:
- E: 0,55 0,55 0,55 0,55 0,58 0,62 0,66 0,70 0,74 0,78 0,82 0,85 0,89 0,92 0,95 0,99 1,02 1,04 1,07 1,10
- F: 0,53 0,53 0,53 0,53 0,53 0,53 0,56 0,60 0,63 0,66 0,69 0,72 0,75 0,79 0,82 0,85 0,87 0,90 0,93 0,96

A_sol,est/A_sup,utile, Tab. 12: < 0,030 per E.1 (esclusi collegi, conventi, case di pena, caserme, E.1(3));
< 0,040 per gli altri edifici.

Regole: verso ZNC limite (e U di riferimento) diviso per b_tr (§1.1 p.2, §3.1 p.5); verso terreno si
confronta la U equivalente UNI EN ISO 13370 (§3.1 p.6); 2° livello: U comprensiva dei soli ponti termici
di Tab. 18 confrontata con la U limite + ψ_tab (§3.1 p.2); ponte tra strutture diverse attribuito a metà
a ciascuna (§3.1 p.10).

Impianti di riferimento: Tab. 7 (η_u: idronica 0,81/0,81/0,70 H/C/W, aeraulica 0,83, mista 0,82),
Tab. 8 (η_gn: gas 0,95 H / 0,85 W, liquido 0,82/0,80, PdC elettrica 3,0 H / 2,5 W, frigo 2,50, …),
Tab. 8 bis (efficienze per FER: 1,54 H, 1,28 C, 1,28 W), Tab. 9 (ventilazione, Wh/m³).
Caldaie in riqualificazione: η_gn,utile ≥ 90 + 2 log Pn (Pn ≤ 400 kW), §3.3.1.

L'**Allegato H** (586 pagine) è il metodo di calcolo completo usato dal motore CENED.
