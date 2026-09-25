# Allegato H (Decreto 6437/2026) - Specifica di implementazione, caso residenziale E.1(1)

Questo documento è la specifica per il motore di calcolo del pacchetto `cened/`. Lo scopo è eseguire il pre-calcolo,
la relazione Legge 10 e la simulazione degli interventi seguendo lo stesso metodo di CENED+2.0.
Il documento è ricavato dal testo estratto dal PDF (`risorse/normativa/allegati/Allegato-H.txt`, 586 pagine).
La classificazione (sez. 8) viene invece dal testo delle Disposizioni (`Disposizioni-per-efficienza-energetica-degli-edifici.txt`, §16)
e dall'Allegato B (`Allegato-B.txt`), perché l'Allegato H rinvia a quei testi.

## 0. Convenzioni del documento

- **Riferimenti di pagina.** "p. N" indica il numero di pagina stampato nell'Allegato H. Coincide con il blocco N-esimo
  del file `.txt` separato da `=====PAGINA=====`, contando da 1. Tra parentesi tonde ci sono i numeri di equazione
  originali, per esempio (3.11), e i numeri dei prospetti originali, per esempio "Prospetto 3.XXV".
- **Unità.** Energie in kWh. Potenze in W, salvo diversa indicazione. Δt è la durata del mese in **kh**:
  Δt = 24·N_k/1000 (3.13), dove N_k sono i giorni **effettivi** di calcolo del mese (anche frazioni di mese, §2.2).
  Con queste unità W × kh = kWh, e la divisione kWh / kh restituisce W.
- **Numeri.** I valori sono riportati come nel testo, con la virgola decimale. Nel codice si usa il punto.
- **Formule.** Le formule nel PDF sono estratte con i pedici "sparpagliati" (per esempio `RT,TT QΔtΔθHQ +=`).
  Le formule scritte qui sono la ricostruzione leggibile. Quando la ricostruzione non è univoca c'è il marcatore
  **[AMB-n]**, che rimanda all'elenco della sezione 10.
- **Ambito.** Solo residenziale E.1(1) (abitazioni civili), con E.1(2) quando è assimilato. Il documento si limita ai servizi H
  (riscaldamento), W (ACS), C (raffrescamento, in sintesi), V (ventilazione meccanica, in sintesi) e alla produzione FER
  (FV e solare termico). Illuminazione (cap. 6) e trasporto (cap. 12) non sono trattati in dettaglio: per il residenziale
  l'illuminazione non entra nell'EP (p. 32, p. 42).

---

## 1. Indice sintetico dell'Allegato H e mappa verso i moduli software

### 1.1 Indice (pagine dell'Allegato H)

| Cap. | Titolo | Pagine | Rilevanza E.1(1) |
|---|---|---|---|
| 1 | Prestazione energetica dell'edificio (compiti certificatore, riferimenti, generalità, **condizioni di riferimento**) | 8-15 | Alta (§1.4, p. 12-15) |
| 2 | Servizi e indicatori (EP, CO2, QER, vettori importati/esportati, schema sottosistemi, perdite recuperabili, efficienze) | 16-48 | Alta |
| 3 | Fabbisogno di energia termica **sensibile** (zone, Q_NH, Q_NC, trasmissione, ventilazione, apporti, fattori di utilizzazione) | 49-109 | Altissima |
| 4 | Fabbisogno di energia termica **latente** (umidificazione e deumidificazione) | 110-115 | Solo se c'è controllo dell'umidità |
| 5 | Fabbisogno ACS (volumi, a/b per superficie) | 116-119 | Alta |
| 6 | Illuminazione | 120-132 | No (solo non residenziale) |
| 7 | Sistema ACS (erogazione, distribuzione, ricircolo, accumulo, G-S, autoclave, recuperi) | 133-153 | Alta |
| 8 | Sistema riscaldamento/climatizzazione invernale (emissione, regolazione, distribuzione idronica/aeraulica, accumulo, G-S) | 154-206 | Altissima |
| 9 | Sistema raffrescamento/climatizzazione estiva | 207-240 | Media |
| 10 | Servizio ventilazione | 241-244 | Media (VMC) |
| 11 | Generazione (centrali, ripartizioni, caldaie, biomassa, Joule, aria calda, teleriscaldamento, **pompe di calore**, solare termico, frigo, cogenerazione, FV) | 245-432 | Altissima |
| 12 | Trasporto persone/cose (ascensori ecc.) | 433-445 | Bassa |
| App. A | Temperatura degli ambienti confinanti (non climatizzati, serre) | 446-456 | Alta |
| App. B | Trasmittanza equivalente del basamento (terreno) | 457-471 | Alta |
| App. C | Fattori di ombreggiatura | 472-476 | Alta |
| App. D | Capacità termica areica efficace (prospetto sintetico) | 477 | Alta |
| App. E | Efficienza del recupero termico VMC | 478-481 | Media |
| App. F | Irradiazione su superficie orientata | 482-489 | Alta |
| App. G | Procedura dettagliata per le schermature | 490-499 | Bassa |
| App. H | Caratteristiche dinamiche dei componenti (matrici di trasferimento, Y_IE, κ) | 500-508 | Media (Cm, Y_IE) |
| App. I | Rischio condensa | 509-518 | Verifiche (esiste già `igrotermia.py`) |
| App. J | Perdite di distribuzione (idroniche e aerauliche), temperature di rete | 519-565 | Alta |
| App. K | Temperatura del terreno (pompe di calore geotermiche) | 566-568 | Bassa |
| All. 1 | Dati climatici dei 12 capoluoghi (θe, Δθ, Hd/Hb, pv, vento, bin orari) | 569-583 | Altissima |
| All. 2 | Fattori di conversione in energia primaria, rendimenti di riferimento, fattori CO2 | 584-585 | Altissima |

### 1.2 Mappa capitolo → modulo software proposto

| Modulo (proposta) | Contenuto | Fonti Allegato H |
|---|---|---|
| `cened/clima.py` | Dati All. 1, correzione per altitudine, bin orari, stagione di calcolo (frazioni di mese) | §1.4, §3.3.5.1, All. 1, App. F |
| `cened/solare.py` | Irradiazione su piano orientato H_s,j; fattori d'ombra F_S | App. F, App. C, §3.3.8 |
| `cened/involucro.py` (esistente) | U componenti, finestre (Uw, Prospetti 3.V-3.XI), ponti termici | §3.3.5.2-3.3.5.3 |
| `cened/terreno.py` (esistente) | U_b equivalente del basamento | App. B |
| `cened/znc.py` (nuovo) | Temperatura θu dei locali non climatizzati e delle serre, H_V,ju | App. A |
| `cened/bilancio.py` (esistente, da riscrivere) | Q_T, ΔQ_T,R, Q_V, Q_V,adj, Q_I, Q_SI, Q_SE,O, η_H, η_C, Q_NH, Q_NC, stagione | Cap. 3, §1.4 |
| `cened/acs.py` | Q_NW, sottosistemi ACS, perdite recuperate Q_Z,rvd | Cap. 5, Cap. 7 |
| `cened/impianto_h.py` | Emissione, regolazione, distribuzione, accumulo, G-S, ausiliari | Cap. 8, App. J |
| `cened/generatori/` | `caldaia.py`, `biomassa.py`, `joule.py`, `teleriscaldamento.py`, `pdc.py`, `solare_termico.py`, `fv.py` | Cap. 11 |
| `cened/centrali.py` | Ripartizione della richiesta tra centrali e generatori (priorità, FC), centrale elettrica e autoconsumo FV | §11.1-11.5 |
| `cened/energia_primaria.py` | f_P per vettore, EP per servizio, QER, CO2 | Cap. 2, All. 2 |
| `cened/classe.py` | Edificio di riferimento, EP_gl,nren,rif,standard, classe A4…G, indicatori inverno/estate | Disposizioni §16, All. B |

**Ordine di calcolo obbligato** (p. 41, §2.6): **prima l'ACS** (perdite recuperate Q_Z,rvd), poi il fabbisogno netto
di riscaldamento Q*_NH,adj = Q_NH,adj − Q_Z,rvd (8.1), poi l'impianto H. Tutti gli altri fattori di recupero delle perdite
di impianto verso la zona sono **nulli**: sono ammessi solo quelli dei sottosistemi ACS. In questo modo si evitano le iterazioni.

---

## 2. Condizioni di riferimento e dati climatici

### 2.1 Condizioni d'uso convenzionali (§1.4, p. 12-13)

- Funzionamento **continuo 24 h**: θ_i costante, apporti interni, occupazione e ricambi d'aria costanti nelle 24 ore.
- **Riscaldamento**: θ_i = **20 °C** per tutte le categorie tranne E.6(1) (28 °C) e E.6(2)/E.8 (18 °C).
  Climatizzazione invernale: stesse temperature, UR = 50 % (90 % per E.6(1)).
- **Raffrescamento**: θ_i = **26 °C** (E.6(1) 28 °C, E.6(2) 24 °C). Climatizzazione estiva: UR = 50 %.
- Nel residenziale E.1(1)/E.1(2), un ambiente senza terminali di emissione si considera climatizzato quando è collegato
  in modo permanente ad ambienti climatizzati. Per tutte le categorie, lo si considera climatizzato anche quando la somma
  dei volumi dei locali privi di emissione è inferiore al 10 % del volume netto dell'unità (p. 12).

### 2.2 Periodo di calcolo e stagione (§1.4, p. 13-15)

Il calcolo è **mensile o su frazione di mese**. Il periodo di riscaldamento non può eccedere il **Prospetto I** (p. 13):

| Zona climatica | Periodo massimo di calcolo |
|---|---|
| E | 15 ottobre - 15 aprile |
| F | 5 ottobre - 22 aprile |

La stagione effettiva di ogni zona termica si determina con il rapporto apporti/perdite:

- Riscaldamento: il primo e l'ultimo giorno sono quelli in cui γ_H,day = γ_H,lim = (a_H + 1)/a_H (1.1),
  con a_H dalla (3.99)/(3.100).
- Raffrescamento: 1/γ_C,day = 1/γ_C,lim = (a_C + 1)/a_C (1.4). Se per tutti i mesi 1/γ_C < 1/γ_C,lim,
  la stagione di raffrescamento copre tutto l'anno. Il calcolo di Q_NC si estende comunque a tutti i mesi (p. 14).
- I valori giornalieri di γ si ottengono per **interpolazione lineare** tra i valori medi mensili, attribuiti al
  **giorno centrale** di ciascun mese.

Procedura in 6 passi (p. 15):

1. calcolare γ_H e γ_C mensili;
2. calcolare γ_H,lim e γ_C,lim;
3. individuare i mesi di transizione;
4. individuare i giorni di inizio e fine per interpolazione lineare;
5. troncare la stagione di riscaldamento al Prospetto I;
6. **ricalcolare i dati climatici** sulle frazioni dei mesi estremi.

Giorni per mese (1.3), (1.6): N = N_in,m nel mese di inizio, N = N_k nei mesi intermedi, N = N_fin,n nel mese di fine.
Un sistema unico che fa sia H sia C, quando entrambi i servizi risultano richiesti, esegue solo H dentro il periodo del
Prospetto I e solo C fuori da quel periodo (p. 15).

> Implementazione: la stagione dipende da a_H, che dipende da τ, che dipende da H_L (3.101)-(3.102). Conviene
> 1) calcolare γ_H e a_H su tutti i 12 mesi interi, 2) trovare i giorni di inizio e fine, 3) intersecarli con il Prospetto I,
> 4) ricalcolare i mesi estremi con N ridotto. Il metodo di interpolazione tra le temperature del mese e la frazione
> (quale θe si usa nella frazione di mese) non è specificato oltre il "ricalcolo dei dati climatici": **[AMB-1]**.

### 2.3 Dati climatici (§3.3.5.1 e Allegato 1, p. 54, p. 569-583)

**Correzione per altitudine** (3.14): θe = θe,r − δ·(z − z_r), con δ = **1/178 °C/m**. Si parte dal capoluogo
della provincia del Comune. La stessa regola vale anche per gli altri dati: la nota del Prospetto VI dice che "i dati relativi agli altri
comuni vanno ricavati con i criteri del §3.3.5.1". L'irradiazione e la pressione di vapore **non** vengono corrette:
si prendono quelle del capoluogo **[AMB-2]**.

**Allegato 1 - Prospetto I: θe,r [°C], medie mensili della temperatura media giornaliera** (fonte UNI 10349-1:2015).
L'ordine delle colonne è quello del PDF, che inizia da **ottobre**:

| Capoluogo | z [m] | Ott | Nov | Dic | Gen | Feb | Mar | Apr | Mag | Giu | Lug | Ago | Set |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Bergamo | 290 | 12,8 | 7,2 | 3,3 | 2,7 | 5,0 | 8,4 | 11,4 | 16,5 | 21,6 | 22,5 | 21,7 | 17,7 |
| Brescia | 93 | 13,0 | 7,7 | 3,5 | 3,0 | 3,5 | 8,6 | 12,1 | 17,8 | 21,1 | 22,2 | 22,0 | 18,4 |
| Como | 322 | 11,3 | 7,0 | 3,6 | -0,2 | 3,9 | 8,6 | 11,9 | 17,1 | 20,7 | 22,5 | 19,8 | 17,7 |
| Cremona | 96 | 12,9 | 6,0 | 3,2 | 1,8 | 3,1 | 7,6 | 12,3 | 17,4 | 21,8 | 22,6 | 21,6 | 17,6 |
| Lecco | 237 | 14,5 | 8,2 | 4,2 | 4,9 | 4,2 | 10,0 | 13,9 | 17,5 | 22,3 | 24,6 | 23,7 | 19,5 |
| Lodi | 60 | 14,3 | 6,6 | 1,7 | 1,6 | 4,7 | 9,6 | 12,8 | 18,6 | 22,6 | 24,3 | 22,8 | 18,0 |
| Mantova | 22 | 12,7 | 7,5 | 3,4 | 1,5 | 2,3 | 8,4 | 12,9 | 18,0 | 22,1 | 23,5 | 24,6 | 19,3 |
| Milano | 122 | 14,1 | 7,5 | 3,5 | 4,0 | 7,1 | 10,6 | 13,4 | 19,4 | 22,8 | 24,5 | 24,3 | 19,8 |
| Monza e Brianza | 142 | 13,8 | 9,3 | 2,8 | 2,9 | 4,8 | 8,0 | 13,1 | 18,0 | 22,9 | 24,9 | 23,9 | 19,1 |
| Pavia | 106 | 14,2 | 7,1 | 2,5 | 4,9 | 1,2 | 9,4 | 12,5 | 18,9 | 22,8 | 23,8 | 22,6 | 18,4 |
| Sondrio | 307 | 11,3 | 5,9 | 0,6 | -0,6 | 3,0 | 7,7 | 11,5 | 17,2 | 20,5 | 22,1 | 21,0 | 15,5 |
| Varese | 193 | 12,9 | 7,3 | 3,3 | 1,9 | 5,3 | 8,4 | 12,5 | 16,5 | 20,1 | 22,9 | 21,9 | 18,7 |

**Allegato 1 - Prospetto II: Δθ_er [K], escursione termica giornaliera media mensile** (colonne da gennaio; serve per il
raffrescamento/ventilazione notturna):

| Capoluogo | z [m] | Gen | Feb | Mar | Apr | Mag | Giu | Lug | Ago | Set | Ott | Nov | Dic |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Bergamo | 290 | 6,6 | 9,0 | 10,0 | 9,0 | 9,7 | 10,0 | 10,9 | 9,7 | 10,8 | 6,9 | 6,7 | 6,1 |
| Brescia | 93 | 6,1 | 10,5 | 11,4 | 11,4 | 12,4 | 14,2 | 13,3 | 14,6 | 13,1 | 11,2 | 9,3 | 7,0 |
| Como | 322 | 8,0 | 11,7 | 11,7 | 12,5 | 12,6 | 14,9 | 13,8 | 13,1 | 13,6 | 11,8 | 7,2 | 8,6 |
| Cremona | 96 | 7,3 | 10,9 | 11,4 | 12,8 | 11,6 | 14,5 | 12,8 | 12,7 | 11,3 | 9,0 | 7,7 | 7,9 |
| Lecco | 237 | 6,8 | 7,0 | 9,4 | 9,5 | 8,8 | 10,1 | 10,9 | 11,1 | 8,3 | 6,6 | 6,3 | 6,5 |
| Lodi | 60 | 8,4 | 11,3 | 12,7 | 11,0 | 12,5 | 13,5 | 13,1 | 11,8 | 13,5 | 10,9 | 9,6 | 7,4 |
| Mantova | 22 | 6,8 | 9,7 | 11,5 | 11,8 | 11,8 | 14,0 | 12,8 | 14,4 | 11,4 | 8,2 | 8,0 | 7,1 |
| Milano | 122 | 6,6 | 6,4 | 8,1 | 7,6 | 8,4 | 8,5 | 8,6 | 8,5 | 8,3 | 5,8 | 3,7 | 4,8 |
| Monza e Brianza | 142 | 7,9 | 8,1 | 8,6 | 10,7 | 9,7 | 10,2 | 14,7 | 13,1 | 12,1 | 9,9 | 8,3 | 5,9 |
| Pavia | 106 | 7,5 | 12,5 | 13,1 | 10,6 | 11,6 | 13,9 | 12,0 | 12,8 | 13,8 | 11,1 | 9,8 | 8,7 |
| Sondrio | 307 | 9,8 | 13,3 | 13,0 | 12,6 | 14,5 | 13,3 | 15,0 | 14,5 | 12,5 | 12,3 | 11,2 | 9,5 |
| Varese | 193 | 6,0 | 9,1 | 8,7 | 9,9 | 10,3 | 9,1 | 10,5 | 9,7 | 8,5 | 8,2 | 5,9 | 5,6 |

**Allegato 1 - Prospetto III: irradiazione giornaliera media mensile diffusa Hd e diretta Hb sul piano orizzontale
[MJ/m²]** (fonte UNI 10349-1:2015). Nel testo estratto **le righe non riportano il nome del capoluogo**. L'ordine assunto
qui (Bergamo…Varese) è quello di tutte le altre tabelle ed è **da verificare** sul PDF **[AMB-3]**. Per convertire
MJ/m² in kWh/m² si divide per 3,6.

| Riga | Gen Hd | Gen Hb | Feb Hd | Feb Hb | Mar Hd | Mar Hb | Apr Hd | Apr Hb | Mag Hd | Mag Hb | Giu Hd | Giu Hb | Lug Hd | Lug Hb | Ago Hd | Ago Hb | Set Hd | Set Hb | Ott Hd | Ott Hb | Nov Hd | Nov Hb | Dic Hd | Dic Hb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 (Bergamo?) | 2,2 | 2,7 | 2,9 | 5,4 | 4,4 | 7,8 | 6,3 | 8,4 | 9,3 | 8,6 | 10,2 | 10,3 | 9,2 | 12,4 | 7,7 | 11,2 | 5,4 | 9,3 | 3,4 | 4,4 | 2,4 | 2,3 | 1,6 | 2,0 |
| 2 (Brescia?) | 2,0 | 1,4 | 3,3 | 4,4 | 5,1 | 6,9 | 6,5 | 8,8 | 8,2 | 12,2 | 9,2 | 15,4 | 9,1 | 14,7 | 7,7 | 13,6 | 5,7 | 9,0 | 4,2 | 4,2 | 2,6 | 2,6 | 1,8 | 1,6 |
| 3 (Como?) | 2,2 | 1,9 | 3,1 | 5,5 | 4,9 | 7,1 | 5,9 | 10,1 | 7,6 | 11,6 | 9,5 | 13,2 | 8,8 | 13,7 | 7,1 | 10,8 | 5,6 | 8,6 | 3,7 | 7,0 | 2,1 | 1,8 | 1,9 | 1,5 |
| 4 (Cremona?) | 2,1 | 2,1 | 2,9 | 4,6 | 4,3 | 8,2 | 5,9 | 8,8 | 7,8 | 10,4 | 7,8 | 14,6 | 8,4 | 12,7 | 7,5 | 10,4 | 5,7 | 7,7 | 3,4 | 3,2 | 2,1 | 2,2 | 1,4 | 2,0 |
| 5 (Lecco?) | 2,0 | 2,4 | 2,8 | 3,9 | 3,7 | 8,8 | 5,9 | 8,8 | 8,6 | 9,0 | 8,9 | 12,3 | 8,0 | 15,4 | 7,2 | 13,3 | 4,7 | 9,1 | 3,6 | 4,7 | 2,1 | 2,5 | 1,5 | 1,9 |
| 6 (Lodi?) | 2,1 | 2,9 | 3,2 | 4,6 | 4,7 | 8,6 | 6,6 | 9,5 | 9,5 | 11,1 | 9,6 | 14,1 | 9,0 | 15,1 | 7,5 | 12,2 | 5,7 | 9,8 | 4,1 | 3,8 | 2,5 | 3,5 | 1,9 | 1,9 |
| 7 (Mantova?) | 2,1 | 2,5 | 3,5 | 4,4 | 4,8 | 7,4 | 6,8 | 9,5 | 8,6 | 11,0 | 9,5 | 14,6 | 9,2 | 13,5 | 7,9 | 13,1 | 6,1 | 8,9 | 3,8 | 3,9 | 2,9 | 2,3 | 1,7 | 2,4 |
| 8 (Milano?) | 2,2 | 2,7 | 3,2 | 4,2 | 5,0 | 6,8 | 6,5 | 9,5 | 8,3 | 10,7 | 9,8 | 13,1 | 8,8 | 14,5 | 7,5 | 11,6 | 5,8 | 9,4 | 3,6 | 4,4 | 2,1 | 2,2 | 1,9 | 1,7 |
| 9 (Monza e Brianza?) | 2,0 | 1,9 | 3,1 | 3,6 | 5,1 | 5,8 | 7,1 | 8,3 | 8,2 | 11,5 | 9,9 | 10,1 | 8,5 | 15,5 | 7,9 | 13,0 | 5,5 | 8,3 | 3,9 | 3,8 | 2,4 | 2,4 | 1,8 | 1,1 |
| 10 (Pavia?) | 2,1 | 1,6 | 3,4 | 4,6 | 5,0 | 8,3 | 6,4 | 8,1 | 8,8 | 11,9 | 10,2 | 13,5 | 9,5 | 13,8 | 8,2 | 11,3 | 6,3 | 7,8 | 4,0 | 4,1 | 2,7 | 2,3 | 1,8 | 1,7 |
| 11 (Sondrio?) | 2,0 | 2,7 | 3,0 | 5,7 | 4,6 | 7,9 | 6,3 | 9,1 | 8,6 | 9,2 | 9,3 | 11,6 | 8,9 | 11,1 | 7,3 | 10,0 | 5,6 | 7,4 | 3,7 | 4,9 | 2,2 | 3,1 | 1,3 | 2,3 |
| 12 (Varese?) | 1,9 | 2,7 | 2,9 | 5,0 | 4,3 | 7,5 | 5,8 | 11,0 | 7,5 | 13,0 | 8,5 | 12,8 | 8,4 | 16,2 | 7,5 | 12,3 | 5,3 | 9,5 | 3,7 | 6,1 | 2,3 | 3,0 | 1,6 | 2,1 |

Dati geografici (tabella senza numero, p. 570; "Insolazione annuale" riportata come nel testo, con lo spazio come separatore
delle migliaia):

| Località | z [m] | Latitudine | Longitudine | Insolazione annua [MJ/m²] (testo) | Media giornaliera [MJ/m²] (testo) |
|---|---|---|---|---|---|
| Bergamo | 290 | 45° 43' | 9° 41' | 4 564 | 12.5 |
| Brescia | 93 | 45° 26' | 10° 02' | 4 883 | 13.4 |
| Como | 322 | 45° 43' | 9° 5' | 4 729 | 13.0 |
| Cremona | 96 | 45° 27' | 9° 39' | 4 455 | 12.2 |
| Lecco | 237 | 45° 50' | 9° 21' | 4 610 | 12.6 |
| Lodi | 60 | 45° 14' | 9° 24' | 4 984 | 13.7 |
| Mantova | 22 | 44° 58' | 10° 46' | 4 888 | 13.4 |
| Milano | 122 | 45° 28' | 9° 13' | 4 740 | 13.0 |
| Monza-B. | 142 | 45° 33' | 9° 12' | 4 598 | 12.6 |
| Pavia | 106 | 45° 14' | 8° 41' | 4 798 | 13.1 |
| Sondrio | 307 | 46° 10' | 9° 52' | 4 501 | 12.3 |
| Varese | 193 | 45° 49' | 8° 37' | 4 906 | 13.4 |

**Allegato 1 - Prospetto IV: pressione parziale del vapore pv [Pa]** (colonne da ottobre; serve per T_sky nella (3.36)):

| Capoluogo | Ott | Nov | Dic | Gen | Feb | Mar | Apr | Mag | Giu | Lug | Ago | Set |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Bergamo | 1374 | 959 | 644 | 666 | 689 | 862 | 1054 | 1376 | 2042 | 2208 | 2180 | 1438 |
| Brescia | 1203 | 971 | 769 | 708 | 675 | 833 | 1018 | 1357 | 1457 | 1902 | 1868 | 1646 |
| Como | 1112 | 962 | 719 | 536 | 535 | 718 | 940 | 1264 | 1737 | 1748 | 1677 | 1574 |
| Cremona | 1364 | 880 | 450 | 657 | 628 | 704 | 985 | 1548 | 1497 | 2003 | 1994 | 1611 |
| Lecco | 1335 | 922 | 687 | 645 | 624 | 636 | 1072 | 1134 | 1511 | 1701 | 1710 | 1477 |
| Lodi | 1372 | 817 | 650 | 568 | 756 | 818 | 1075 | 1228 | 1669 | 1997 | 2222 | 1398 |
| Mantova | 1351 | 1014 | 723 | 675 | 667 | 793 | 1096 | 1692 | 1697 | 2121 | 2307 | 1670 |
| Milano | 1323 | 822 | 633 | 682 | 766 | 810 | 1048 | 1523 | 1548 | 1775 | 1864 | 1265 |
| Monza e Brianza | 1411 | 1064 | 649 | 686 | 632 | 746 | 1001 | 1407 | 1904 | 1906 | 1640 | 1652 |
| Pavia | 1440 | 963 | 720 | 796 | 510 | 717 | 946 | 1649 | 1636 | 2125 | 2370 | 1812 |
| Sondrio | 1124 | 695 | 582 | 437 | 536 | 509 | 827 | 1066 | 1708 | 1559 | 1486 | 1361 |
| Varese | 1144 | 894 | 657 | 592 | 692 | 817 | 908 | 1249 | 1615 | 1459 | 1750 | 1597 |

**Allegato 1 - Prospetto V: velocità del vento [m/s]** (serve per U_x dei vespai, App. B (B.14)):

| Località | z | Gen | Feb | Mar | Apr | Mag | Giu | Lug | Ago | Set | Ott | Nov | Dic | Media annua | Zona vento | Dir. prevalente |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Bergamo | 290 | 0,6 | 0,7 | 1,1 | 1,1 | 1,1 | 1,0 | 0,9 | 0,9 | 0,9 | 0,8 | 0,7 | 0,9 | 0,9 | 1 | NE |
| Brescia | 93 | 1,2 | 1,1 | 1,6 | 1,6 | 1,5 | 1,5 | 1,2 | 1,0 | 1,2 | 1,1 | 1,1 | 1,2 | 1,3 | 1 | E |
| Como | 322 | 0,6 | 1,1 | 1,4 | 1,3 | 1,4 | 1,3 | 1,0 | 1,0 | 1,0 | 0,8 | 0,8 | 0,8 | 1,0 | 1 | S |
| Cremona | 96 | 0,7 | 0,8 | 1,3 | 1,0 | 0,9 | 0,8 | 0,7 | 0,6 | 0,5 | 0,4 | 0,8 | 1,1 | 0,8 | 1 | E |
| Lecco | 237 | 1,7 | 1,3 | 2,2 | 1,5 | 1,3 | 1,9 | 1,7 | 1,8 | 1,8 | 1,4 | 1,2 | 1,2 | 1,6 | 1 | S |
| Lodi | 60 | 0,6 | 0,5 | 0,9 | 0,9 | 1,0 | 1,0 | 0,8 | 0,5 | 0,7 | 0,4 | 0,5 | 0,5 | 0,7 | 1 | SW |
| Mantova | 22 | 1,2 | 1,0 | 1,6 | 1,2 | 1,3 | 1,0 | 1,1 | 0,8 | 0,8 | 0,8 | 0,9 | 1,2 | 1,1 | 1 | E |
| Milano | 122 | 1,5 | 1,6 | 2,2 | 1,9 | 1,8 | 2,0 | 1,9 | 1,5 | 1,6 | 1,4 | 1,2 | 1,5 | 1,7 | 1 | SW |
| Monza-B. | 142 | 1,2 | 1,7 | 1,7 | 1,8 | 1,5 | 1,7 | 1,7 | 1,5 | 1,4 | 1,2 | 1,1 | 1,4 | 1,5 | 1 | ND |
| Pavia | 106 | 1,5 | 2,2 | 2,3 | 2,4 | 2,1 | 2,1 | 1,6 | 1,6 | 1,7 | 1,2 | 1,7 | 1,2 | 1,8 | 1 | S |
| Sondrio | 307 | 0,6 | 0,9 | 1,3 | 1,4 | 1,6 | 1,5 | 1,5 | 1,4 | 1,0 | 0,7 | 0,6 | 0,3 | 1,1 | 1 | E |
| Varese | 193 | 0,9 | 0,7 | 1,2 | 1,0 | 1,2 | 0,8 | 0,8 | 0,8 | 0,7 | 0,7 | 0,8 | 1,0 | 0,9 | 1 | E |

**Allegato 1 - Prospetto VI: temperatura di progetto e temperatura media annua** (θe,av serve per θ_0 dell'acqua di
rete nell'ACS, per θ_cw del solare termico e per gli edifici confinanti senza impianto):

| Località | z [m] | θe progetto [°C] | θe,av media annua [°C] |
|---|---|---|---|
| Bergamo | 290 | -5 | 12,6 |
| Brescia | 93 | -7 | 12,8 |
| Como | 322 | -5 | 12,0 |
| Cremona | 96 | -5 | 12,4 |
| Lecco | 237 | -5 | 14,0 |
| Lodi | 60 | -5 | 13,2 |
| Mantova | 22 | -5 | 13,1 |
| Milano | 122 | -5 | 14,3 |
| Monza-B. | 142 | -5 | 13,7 |
| Pavia | 106 | -5 | 13,3 |
| Sondrio | 307 | -10 | 11,4 |
| Varese | 193 | -5 | 12,7 |

**Allegato 1 - Prospetti VII-XVIII: bin orari** della temperatura esterna, cioè ore/mese per classi di 1 K, da −15 a
+40 °C. Una tabella per capoluogo, nell'ordine: VII Bergamo (p. 572), VIII Brescia, IX Como, X Cremona, XI Lecco, XII Lodi,
XIII Mantova, XIV Milano (p. 579), XV Monza-Brianza, XVI Pavia, XVII Sondrio, XVIII Varese (p. 583). Le righe hanno il formato
`θ Gen … Dic TOTALE`. Le righe vuote (θ senza ore) sono prive di numeri. Le tabelle servono **solo** per le pompe di
calore aria (bin mensili, §11.8.8.2) e si possono importare in automatico dal `.txt` (pagine 572-583, una per capoluogo).
Il testo non indica come correggere i bin per l'altitudine del Comune **[AMB-4]**.

### 2.4 Apporti interni residenziali (§3.3.7, p. 87)

Q_I = Φ_a · Δt (3.59), con Φ_a dal **Prospetto 3.XXV** (fonte UNI/TS 11300-1:2014):

| Categoria | Condizione | Φ_a [W] |
|---|---|---|
| E.1(1); E.1(2) | A ≤ 120 m² | 7,987·A − 0,0353·A² |
| E.1(1); E.1(2) | A > 120 m² | 450 |

A è la superficie utile. Per collegi, caserme, case di pena e conventi (E.1(1) non abitativi) si usa invece la (3.60):
Q_I = q_a·A·Δt con q_a = 6 W/m² (Prospetto 3.XXVI). Il valore si riferisce all'unità immobiliare e **non si riduce** con il
profilo d'uso (occupazione 24/24, Prospetto 4.I).

### 2.5 Ricambi d'aria residenziali (§3.3.6.2-3.3.6.3, p. 71-80)

- Per E.1(1)/E.1(2) (ed E.8) la portata minima di progetto è (3.45): **V_a,p,min = V·n/3600** [m³/s],
  con V = **volume netto** e **n = 0,5 h⁻¹**, infiltrazioni comprese (p. 73).
- Portata media giornaliera di riferimento (aerazione o ventilazione naturale) (3.46):
  **V_a,k = V_a,p,min · f_v,t,k**, con **f_v,t = 0,60** per E.1.1 abitazioni civili e per E.1.2
  (Prospetto 3.XIX, p. 78; nota "(*) compresa estrazione d'aria dai servizi").
  Il risultato è **0,5 × 0,6 = 0,30 vol/h** di volume netto.
- H_V = ρ_a·c_a · Σ_k (V_a,k · c_v,k) (3.40), con **ρ_a·c_a = 1.210 J/(m³K)**. Qui c_v,k = 1, salvo aria prelevata da serre o
  locali non climatizzati: c_v,k = (θ_i − θ_im,k)/(θ_i − θe) (3.41).
  Solo per la certificazione, e senza dati di progetto (serre escluse), si può sostituire c_v,k con F_T del Prospetto 3.I.
- La ventilazione naturale "vera" (V_a,0 = V·n_vn/3600, Prospetti 3.XX e 3.XXI) e il vento (V_a,x = V·n50·e/3600,
  Prospetti 3.XXII e 3.XXIII) entrano **solo** nella condizione corretta con VMC o ventilazione ibrida (§3.3.6.3 c-f).
  Nella condizione di riferimento residenziale conta solo la (3.46).


---

## 3. Fabbisogno di energia termica utile (sensibile) invernale ed estivo (Cap. 3, p. 49-109)

### 3.1 Struttura generale: calcolo di riferimento e calcolo corretto (§3.2, p. 49)

Il fabbisogno di ogni zona si calcola **due volte**, mese per mese:

1. **Riferimento** (Q_NH, Q_NC): con **ventilazione naturale o sola aerazione** (H_V dalla (3.46)). Da qui si ottengono
   Q_BH,yr = Σ_m Σ_zone Q_NH e Q_BC,yr (3.1)-(3.2). Il valore **caratterizza l'involucro** e alimenta EP_H,nd
   (indicatore invernale, sez. 8.3) **[AMB-5]**.
2. **Corretto** (Q_NH,adj, Q_NC,adj): con il **modo di ventilare effettivo** (VMC, ibrida, notturna, tutt'aria).
   Il valore è la richiesta all'impianto (Q_BH,adj,yr). Senza VMC vale H_V,adj = H_V e i due calcoli coincidono.

### 3.2 Bilancio mensile della zona (§3.3.1-3.3.4)

Riscaldamento (3.3)-(3.5), da scrivere identico per "adj":

```
Q_L      = Q_T + Q_V                                  (3.9)   [Q_L,adj = Q_T + Q_V,adj]
Q_L,H,net = Q_L − Q_SE,O − Q_SE,S                     (3.5)
Q_G      = Q_I + Q_SI + Q_SI,S                        (3.10)
Q_NH     = max(0 ; Q_L,H,net − η_G,H · Q_G)           (3.3)
se Q_NH = 0  → η_G,H := 1  (condizione (3.4), così come scritta nel testo)
```

Raffrescamento (3.6)-(3.8):

```
Q_L,C,net = Q_L − Q_SE,O − Q_SE,S                     (3.8)
Q_NC      = max(0 ; Q_G − η_L,C · Q_L,C,net)          (3.6)
se Q_NC = 0 → η_L,C := 1                              (3.7)
```

**Differenza chiave rispetto alla UNI/TS 11300-1.** Gli apporti solari sulle **superfici opache** (Q_SE,O) e le quote
indirette da serra (Q_SE,S) **non** sono sommati agli apporti. Si **sottraggono dalle perdite** e quindi **non** sono
moltiplicati per η. Negli apporti Q_G ci sono solo Q_I e i solari attraverso i trasparenti. Anche il γ usa Q_L,net (3.98).

> La (3.4) chiede "se Q_NH = 0 si pone η = 1". Serve solo come convenzione per il report. Nel calcolo del
> fabbisogno (che resta 0) non ha effetto **[AMB-6]**.

### 3.3 Trasmissione (§3.3.5, p. 53-68)

```
Q_T = H_T · Δθ · Δt + ΔQ_T,R          (3.11)     Δθ = θ_i − θ_e (3.12)
H_T = Σ_k A_L,k · U_k · (θ_i − θ_a,k)/(θ_i − θ_e)    (3.15)
```

- A_L,k è l'**area lorda** (dimensioni esterne). θ_a,k è la temperatura dell'ambiente oltre la struttura: θ_e verso
  l'esterno. Per i locali non climatizzati e le serre si calcola con l'**Appendice A** (sez. 3.9).
  Per gli ambienti di altri edifici si usa §A.2: se riscaldati, θ_i di progetto della loro destinazione; se non riscaldati,
  la **temperatura media annua esterna** (p. 456).
- **Metodo semplificato solo per la certificazione**, "in assenza di dati di progetto attendibili" (serre escluse) (3.16):
  **H_T = Σ A_L,k · U_C,k · F_T,k**, con F_T,k dal **Prospetto 3.I** (p. 56):

| Ambiente circostante | F_T,k |
|---|---|
| Ambienti con temperatura pari alla temperatura esterna | 1,00 |
| Non climatizzato con una parete esterna | 0,40 |
| Non climatizzato senza serramenti esterni e con almeno due pareti esterne | 0,50 |
| Non climatizzato con serramenti esterni e con almeno due pareti esterne (es. autorimesse) | 0,60 |
| Non climatizzato con tre pareti esterne (es. vani scala esterni) | 0,80 |
| Piano interrato o seminterrato non climatizzato senza finestre o serramenti esterni | 0,50 |
| Piano interrato o seminterrato non climatizzato con finestre o serramenti esterni | 0,80 |
| Sottotetto con tasso di ventilazione elevato (tetti a tegole o copertura discontinua) senza feltro o assito | 1,00 |
| Sottotetto con altro tetto non isolato | 0,90 |
| Sottotetto con tetto isolato | 0,70 |
| Aree interne di circolazione non climatizzate senza muri esterni e con ricambio < 0,5 h⁻¹ | 0,00 |
| Aree interne di circolazione non climatizzate liberamente ventilate (aperture/volume > 0,005 m²/m³) | 1,00 |
| Terreno (*) | 0,45 |
| Vespaio (aerato e non) | 0,80 |

(Fonte UNI/TS 11300-1:2014; (*) elaborazione Finlombarda.)

**Ponti termici** (3.17): U_k = (Σ_j A_L,j·U_j + Σ_i ψ_e,i·L_e,i)/Σ_j A_L,j. I ponti termici vengono cioè **spalmati sulla
struttura k** a cui sono attribuiti, con ψ riferito alle dimensioni esterne. Si usa la UNI EN ISO 14683 con calcolo
numerico (ISO 10211), con un atlante o con metodi manuali. È **escluso** l'uso dei valori di progetto ψ dell'Allegato A
della ISO 14683 (p. 57).

**Trasmittanza delle pareti** (3.18): 1/U = R_se + Σ d_i/λ_i + Σ R_i (intercapedini) + R_si.

*Prospetto 3.II - intercapedini d'aria ad alta emissività, R [m²K/W]:*

| Spessore [mm] | Ascendente | Orizzontale | Discendente |
|---|---|---|---|
| 0 | 0,00 | 0,00 | 0,00 |
| 5 | 0,11 | 0,11 | 0,11 |
| 7 | 0,13 | 0,13 | 0,13 |
| 10 | 0,15 | 0,15 | 0,15 |
| 15 | 0,16 | 0,17 | 0,17 |
| 25 | 0,16 | 0,18 | 0,19 |
| 50 | 0,16 | 0,18 | 0,21 |
| 100 | 0,16 | 0,18 | 0,22 |
| 300 | 0,16 | 0,18 | 0,23 |

Per i valori intermedi si interpola.

*Prospetto 3.III - resistenze superficiali [m²K/W]:*

| | Ascendente | Orizzontale | Discendente |
|---|---|---|---|
| R_si | 0,10 | 0,13 | 0,17 |
| R_se | 0,04 | 0,04 | 0,04 |

*Prospetto 3.IV - cassonetti:* non isolato **6** W/m²K; isolato (isolante ≥ 2 cm) **1** W/m²K.

**Serramenti** (3.19): U_W = (A_g·U_g + A_t·U_t + L_g·ψ_g)/(A_g + A_t). I dati vengono dai Prospetti 3.V (U_g),
3.VI (U_t), 3.VII e 3.VIII (ψ_g), oppure dalla tabella precalcolata 3.IX, valida per un serramento 1,20 × 1,50 m (±10 %)
con telaio al 20 %.

*Prospetto 3.V - U_g [W/m²K] di vetrate verticali (gas con concentrazione ≥ 90 %):*

| Tipo | Dimensioni [mm] | Aria | Argon | Krypton | SF6 | Xenon |
|---|---|---|---|---|---|---|
| vetro normale ε=0,89 | 4-6-4 | 3,3 | 3,0 | 2,8 | 3,0 | 2,6 |
| vetro normale ε=0,89 | 4-8-4 | 3,1 | 2,9 | 2,7 | 3,1 | 2,6 |
| vetro normale ε=0,89 | 4-12-4 | 2,8 | 2,7 | 2,6 | 3,1 | 2,6 |
| vetro normale ε=0,89 | 4-16-4 | 2,7 | 2,6 | 2,6 | 3,1 | 2,6 |
| vetro normale ε=0,89 | 4-20-4 | 2,7 | 2,6 | 2,6 | 3,1 | 2,6 |
| lastra/e trattata/e ε=0,20 | 4-6-4 | 2,7 | 2,3 | 1,9 | 2,3 | 1,6 |
| lastra/e trattata/e ε=0,20 | 4-8-4 | 2,4 | 2,1 | 1,7 | 2,4 | 1,6 |
| lastra/e trattata/e ε=0,20 | 4-12-4 | 2,0 | 1,8 | 1,6 | 2,4 | 1,6 |
| lastra/e trattata/e ε=0,20 | 4-16-4 | 1,8 | 1,6 | 1,6 | 2,5 | 1,6 |
| lastra/e trattata/e ε=0,20 | 4-20-4 | 1,8 | 1,7 | 1,6 | 2,5 | 1,7 |
| lastra/e trattata/e ε=0,15 | 4-6-4 | 2,6 | 2,3 | 1,8 | 2,2 | 1,5 |
| lastra/e trattata/e ε=0,15 | 4-8-4 | 2,3 | 2,0 | 1,6 | 2,3 | 1,4 |
| lastra/e trattata/e ε=0,15 | 4-12-4 | 1,9 | 1,6 | 1,5 | 2,3 | 1,5 |
| lastra/e trattata/e ε=0,15 | 4-16-4 | 1,7 | 1,5 | 1,5 | 2,4 | 1,5 |
| lastra/e trattata/e ε=0,15 | 4-20-4 | 1,7 | 1,5 | 1,5 | 2,4 | 1,5 |
| lastra/e trattata/e ε=0,10 | 4-6-4 | 2,6 | 2,2 | 1,7 | 2,1 | 1,4 |
| lastra/e trattata/e ε=0,10 | 4-8-4 | 2,2 | 1,9 | 1,4 | 2,2 | 1,3 |
| lastra/e trattata/e ε=0,10 | 4-12-4 | 1,8 | 1,5 | 1,3 | 2,3 | 1,3 |
| lastra/e trattata/e ε=0,10 | 4-16-4 | 1,6 | 1,4 | 1,3 | 2,3 | 1,4 |
| lastra/e trattata/e ε=0,10 | 4-20-4 | 1,6 | 1,4 | 1,4 | 2,3 | 1,4 |
| lastra/e trattata/e ε=0,05 | 4-6-4 | 2,5 | 2,1 | 1,5 | 2,0 | 1,2 |
| lastra/e trattata/e ε=0,05 | 4-8-4 | 2,1 | 1,7 | 1,3 | 2,1 | 1,1 |
| lastra/e trattata/e ε=0,05 | 4-12-4 | 1,7 | 1,3 | 1,1 | 2,1 | 1,2 |
| lastra/e trattata/e ε=0,05 | 4-16-4 | 1,4 | 1,2 | 1,2 | 2,2 | 1,2 |
| lastra/e trattata/e ε=0,05 | 4-20-4 | 1,5 | 1,2 | 1,2 | 2,2 | 1,2 |
| vetro normale ε=0,89 | 4-6-4-6-4 | 2,3 | 2,1 | 1,8 | 1,9 | 1,7 |
| vetro normale ε=0,89 | 4-8-4-8-4 | 2,1 | 1,9 | 1,7 | 1,9 | 1,6 |
| vetro normale ε=0,89 | 4-12-4-12-4 | 1,9 | 1,8 | 1,6 | 2,0 | 1,6 |
| lastra/e trattata/e ε=0,20 | 4-6-4-6-4 | 1,8 | 1,5 | 1,1 | 1,3 | 0,9 |
| lastra/e trattata/e ε=0,20 | 4-8-4-8-4 | 1,5 | 1,3 | 1,0 | 1,3 | 0,8 |
| lastra/e trattata/e ε=0,20 | 4-12-4-12-4 | 1,2 | 1,0 | 0,8 | 1,3 | 0,8 |
| lastra/e trattata/e ε=0,15 | 4-6-4-6-4 | 1,7 | 1,4 | 1,1 | 1,2 | 0,9 |
| lastra/e trattata/e ε=0,15 | 4-8-4-8-4 | 1,5 | 1,2 | 0,9 | 1,2 | 0,8 |
| lastra/e trattata/e ε=0,15 | 4-12-4-12-4 | 1,2 | 1,0 | 0,7 | 1,3 | 0,7 |
| lastra/e trattata/e ε=0,10 | 4-6-4-6-4 | 1,7 | 1,3 | 1,0 | 1,1 | 0,8 |
| lastra/e trattata/e ε=0,10 | 4-8-4-8-4 | 1,4 | 1,1 | 0,8 | 1,1 | 0,7 |
| lastra/e trattata/e ε=0,10 | 4-12-4-12-4 | 1,1 | 0,9 | 0,6 | 1,2 | 0,6 |
| lastra/e trattata/e ε=0,05 | 4-6-4-6-4 | 1,6 | 1,2 | 0,9 | 1,1 | 0,7 |
| lastra/e trattata/e ε=0,05 | 4-8-4-8-4 | 1,3 | 1,0 | 0,7 | 1,1 | 0,5 |
| lastra/e trattata/e ε=0,05 | 4-12-4-12-4 | 1,0 | 0,8 | 0,5 | 1,1 | 0,5 |

*Prospetto 3.VI - U_t del telaio [W/m²K]:*

| Materiale | Tipo | U_t |
|---|---|---|
| Poliuretano | con anima di metallo e spessore PUR ≥ 5 | 2,8 |
| PVC profilo vuoto | due camere cave | 2,2 |
| PVC profilo vuoto | tre camere cave | 2,0 |
| PVC profilo vuoto | cinque camere cave | 1,2 |
| PVC profilo vuoto | sei camere cave | 1,0 |
| Legno duro (rovere, mogano, iroko) | spessore 50 / 60 / 70 / 90 mm | 2,2 / 2,0 / 1,9 / 1,6 |
| Legno tenero (pino, abete, larice, douglas, hemlock) | spessore 50 / 60 / 70 / 90 mm | 2,0 / 1,8 / 1,6 / 1,3 |
| Metallo | senza taglio termico | 7,0 |
| Metallo con taglio termico | sezione 45-55 mm, barrette 14-16 mm | 2,8 |
| Metallo con taglio termico | sezione 60-70 mm, barrette 22-28 mm | 2,5 |
| Metallo con taglio termico | sezione 70-75 mm, barrette 30-36 mm | 2,2 |
| Metallo con taglio termico | sezione 70-75 mm, barrette 36-42 mm, cavità riempita di schiuma | 1,6 |
| Metallo con taglio termico | sezione 90 mm, barrette 52-58 mm, cavità riempita di schiuma | 1,1 |

*Prospetti 3.VII (distanziatori metallici) e 3.VIII (distanziatori in PVC) - ψ_g [W/mK]:*

| Telaio | 3.VII non rivestita | 3.VII bassoemissiva | 3.VIII non rivestita | 3.VIII bassoemissiva |
|---|---|---|---|---|
| Legno, PVC o poliuretano | 0,06 | 0,08 | 0,05 | 0,06 |
| Alluminio con taglio termico | 0,08 | 0,11 | 0,06 | 0,08 |
| Metallo senza taglio termico | 0,02 | 0,05 | 0,01 | 0,04 |

*Prospetto 3.IX - U_W di finestre con telaio al 20 % dell'area [W/m²K]* (righe U_g, colonne U_t):

| Tipo vetrata e Ug [W/m²K] | Ut=0,8 | 1,0 | 1,2 | 1,4 | 1,6 | 1,8 | 2,0 | 2,2 | 2,6 | 3,0 | 3,4 | 3,8 | 7,0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Singola 5,7 | 4,7 | 4,8 | 4,8 | 4,8 | 4,9 | 4,9 | 5,0 | 5,0 | 5,1 | 5,2 | 5,2 | 5,3 | 6,0 |
| Doppia/tripla 3,3 | 3,0 | 3,0 | 3,0 | 3,1 | 3,1 | 3,2 | 3,2 | 3,3 | 3,4 | 3,5 | 3,5 | 3,6 | 4,1 |
| Doppia/tripla 3,2 | 2,9 | 2,9 | 3,0 | 3,0 | 3,0 | 3,1 | 3,1 | 3,2 | 3,3 | 3,4 | 3,5 | 3,5 | 4,0 |
| Doppia/tripla 3,1 | 2,8 | 2,8 | 2,9 | 2,9 | 3,0 | 3,0 | 3,0 | 3,1 | 3,2 | 3,3 | 3,4 | 3,5 | 3,9 |
| Doppia/tripla 3,0 | 2,7 | 2,8 | 2,8 | 2,8 | 2,9 | 2,9 | 3,0 | 3,1 | 3,1 | 3,2 | 3,3 | 3,4 | 3,9 |
| Doppia/tripla 2,9 | 2,6 | 2,7 | 2,7 | 2,8 | 2,8 | 2,8 | 2,9 | 3,0 | 3,1 | 3,1 | 3,2 | 3,3 | 3,8 |
| Doppia/tripla 2,8 | 2,6 | 2,6 | 2,6 | 2,7 | 2,7 | 2,8 | 2,8 | 2,9 | 3,0 | 3,1 | 3,1 | 3,1 | 3,7 |
| Doppia/tripla 2,7 | 2,5 | 2,5 | 2,6 | 2,6 | 2,6 | 2,7 | 2,7 | 2,8 | 2,9 | 3,0 | 3,1 | 3,1 | 3,6 |
| Doppia/tripla 2,6 | 2,4 | 2,4 | 2,5 | 2,5 | 2,6 | 2,6 | 2,6 | 2,7 | 2,8 | 2,9 | 3,0 | 3,1 | 3,5 |
| Doppia/tripla 2,5 | 2,3 | 2,4 | 2,4 | 2,4 | 2,5 | 2,5 | 2,6 | 2,7 | 2,7 | 2,8 | 2,9 | 3,0 | 3,5 |
| Doppia/tripla 2,4 | 2,2 | 2,3 | 2,3 | 2,4 | 2,4 | 2,4 | 2,5 | 2,6 | 2,6 | 2,7 | 2,8 | 2,9 | 3,4 |
| Doppia/tripla 2,3 | 2,2 | 2,2 | 2,2 | 2,3 | 2,3 | 2,4 | 2,4 | 2,5 | 2,6 | 2,7 | 2,7 | 2,8 | 3,3 |
| Doppia/tripla 2,2 | 2,1 | 2,1 | 2,2 | 2,2 | 2,2 | 2,3 | 2,3 | 2,4 | 2,5 | 2,6 | 2,7 | 2,7 | 3,2 |
| Doppia/tripla 2,1 | 2,0 | 2,0 | 2,1 | 2,1 | 2,2 | 2,2 | 2,2 | 2,3 | 2,4 | 2,5 | 2,6 | 2,7 | 3,1 |
| Doppia/tripla 2,0 | 2,0 | 2,0 | 2,1 | 2,1 | 2,1 | 2,2 | 2,2 | 2,3 | 2,4 | 2,5 | 2,6 | 2,7 | 3,1 |
| Doppia/tripla 1,9 | 1,9 | 1,9 | 2,0 | 2,0 | 2,1 | 2,1 | 2,1 | 2,3 | 2,3 | 2,4 | 2,5 | 2,6 | 3,1 |
| Doppia/tripla 1,8 | 1,8 | 1,9 | 1,9 | 1,9 | 2,0 | 2,0 | 2,1 | 2,2 | 2,3 | 2,3 | 2,4 | 2,5 | 3,0 |
| Doppia/tripla 1,7 | 1,7 | 1,8 | 1,8 | 1,9 | 1,9 | 1,9 | 2,0 | 2,1 | 2,2 | 2,3 | 2,3 | 2,4 | 2,9 |
| Doppia/tripla 1,6 | 1,7 | 1,7 | 1,7 | 1,8 | 1,8 | 1,9 | 1,9 | 2,0 | 2,1 | 2,2 | 2,3 | 2,3 | 2,8 |
| Doppia/tripla 1,5 | 1,6 | 1,6 | 1,7 | 1,7 | 1,7 | 1,8 | 1,8 | 1,9 | 2,0 | 2,1 | 2,2 | 2,3 | 2,7 |
| Doppia/tripla 1,4 | 1,5 | 1,5 | 1,6 | 1,6 | 1,7 | 1,7 | 1,7 | 1,9 | 1,9 | 2,0 | 2,1 | 2,2 | 2,7 |
| Doppia/tripla 1,3 | 1,4 | 1,5 | 1,5 | 1,5 | 1,6 | 1,6 | 1,7 | 1,8 | 1,9 | 1,9 | 2,0 | 2,1 | 2,6 |
| Doppia/tripla 1,2 | 1,3 | 1,4 | 1,4 | 1,5 | 1,5 | 1,5 | 1,6 | 1,7 | 1,8 | 1,9 | 1,9 | 2,0 | 2,5 |
| Doppia/tripla 1,1 | 1,3 | 1,3 | 1,3 | 1,4 | 1,4 | 1,5 | 1,5 | 1,6 | 1,7 | 1,8 | 1,9 | 1,9 | 2,4 |
| Doppia/tripla 1,0 | 1,2 | 1,2 | 1,3 | 1,3 | 1,3 | 1,4 | 1,4 | 1,5 | 1,6 | 1,7 | 1,8 | 1,9 | 2,3 |
| Doppia/tripla 0,9 | 1,1 | 1,1 | 1,2 | 1,2 | 1,3 | 1,3 | 1,3 | 1,5 | 1,5 | 1,6 | 1,7 | 1,8 | 2,3 |
| Doppia/tripla 0,8 | 1,0 | 1,1 | 1,1 | 1,1 | 1,2 | 1,2 | 1,3 | 1,4 | 1,5 | 1,5 | 1,6 | 1,7 | 2,2 |
| Doppia/tripla 0,7 | 0,9 | 1,0 | 1,0 | 1,1 | 1,1 | 1,1 | 1,2 | 1,3 | 1,4 | 1,5 | 1,5 | 1,6 | 2,1 |
| Doppia/tripla 0,6 | 0,9 | 0,9 | 0,9 | 1,0 | 1,0 | 1,1 | 1,1 | 1,2 | 1,3 | 1,4 | 1,5 | 1,5 | 2,0 |
| Doppia/tripla 0,5 | 0,8 | 0,8 | 0,9 | 0,9 | 0,9 | 1,0 | 1,0 | 1,2 | 1,2 | 1,3 | 1,4 | 1,5 | 1,9 |

**Doppio serramento** (3.20): U_W = [1/U_w1 − R_si + R_s − R_se + 1/U_w2]⁻¹, con R_si = 0,13 e R_se = 0,04.
R_s dell'intercapedine viene dal Prospetto 3.X (p. 62):

| Spessore [mm] | ε = 0,1 | 0,2 | 0,4 | 0,8 | Entrambe non trattate |
|---|---|---|---|---|---|
| 6 | 0,211 | 0,191 | 0,163 | 0,132 | 0,127 |
| 9 | 0,299 | 0,259 | 0,211 | 0,162 | 0,154 |
| 12 | 0,377 | 0,316 | 0,247 | 0,182 | 0,173 |
| 15 | 0,447 | 0,364 | 0,276 | 0,197 | 0,186 |
| 50 … 300 | 0,406 | 0,336 | 0,26 | 0,189 | 0,179 |

(Nel testo le righe 50, 100, 150, 200, 250 e 300 hanno valori identici.)

**Chiusure oscuranti** (3.21)-(3.22): U_w,ave = U_w+shut·f_shut + U_w·(1 − f_shut), con **f_shut = 0,6 sempre**
(convenzionale) e U_w+shut = 1/(1/U_w + ΔR). ΔR dal Prospetto 3.XI (p. 63):

| Tipo di chiusura | R_sh | ΔR alta permeabilità | ΔR media | ΔR bassa |
|---|---|---|---|---|
| Avvolgibili in alluminio | 0,01 | 0,09 | 0,12 | 0,15 |
| Avvolgibili in legno o plastica senza schiuma | 0,10 | 0,12 | 0,16 | 0,22 |
| Avvolgibili in plastica con schiuma | 0,15 | 0,13 | 0,19 | 0,26 |
| Chiusure in legno 25-30 mm | 0,20 | 0,14 | 0,22 | 0,30 |

> Nel testo non è detto se U_w,ave si usi solo in inverno o tutto l'anno. Il testo dice "ai fini del presente dispositivo
> viene sempre convenzionalmente assunta pari a 0,6", quindi va usata in tutti i mesi **[AMB-7]**.

Facciate continue: U_cw secondo la UNI EN ISO 12631. Muri Trombe e pareti ventilate: (3.23)-(3.31), p. 63-66, non necessari
nel caso base.

### 3.4 Extra flusso radiativo verso la volta celeste (§3.3.5.4, p. 67-68)

Il termine è **sommato alle perdite** (compare nella Q_T):

```
ΔQ_T,R = ( Σ_k F_r,k · Φ_r,k ) · Δt                         (3.32)   [solo componenti verso l'esterno]
F_r    = F_s,d · (1 + cos β)/2                                (3.33)   F_s,d = ombra sul diffuso (Prosp. C.7-C.9), 1 se assente
Φ_r,k  = (U_k / h_e) · A_k · ε_k · h_r · Δθ_er               (3.34)   h_e = 25 W/m²K
h_r    = σ (T_sky⁴ − T_e⁴)/(T_sky − T_e)                      (3.35)   σ = 5,67·10⁻⁸
T_sky  = 291 − 51,6 · exp(−p_v/1000)        [K]              (3.36)   p_v da All.1 Prosp. IV  [AMB-8]
Δθ_er  = θ_e + 273,15 − T_sky                                 (3.37)
```

ε = 0,9 per superfici intonacate o ruvide non metalliche; ε = 0,837 per vetri senza depositi di ossidi metallici.
**Differenza rispetto alla UNI/TS 11300-1.** La TS usa h_r = 5·ε e Δθ_er = 11 K fissi (come fa oggi `bilancio.py`).
L'Allegato H calcola invece T_sky dalla pressione di vapore mensile, quindi h_r e Δθ_er variano mese per mese.
F_r è il fattore di vista sul cielo (1 per i tetti orizzontali, 0,5 per le pareti verticali).

### 3.5 Ventilazione (§3.3.6, p. 68-87)

```
Q_V     = H_V · Δθ · Δt              (3.38)
Q_V,adj = H_V,adj · Δθ · Δt          (3.39)
H_V     = ρ_a c_a · Σ_k V_a,k · c_v,k      (3.40)     ρ_a c_a = 1.210 J/(m³K) (1210 W·s/(m³K))
H_V,adj = ρ_a c_a · Σ_k V_a,k,adj          (3.42)
```

Portate:

- **Riferimento** (e condizione effettiva con sola ventilazione naturale): V_a,k = V_a,p,min · f_v,t,k (3.46), vedi sez. 2.5.
- **VMC** (3.47): V_a,k = V_a,x·(1 − β_k) + (V_f,a · b_v · FC_v + V'_a,x)·β_k.
- **Ibrida** (3.48): V_a,k = V_a,0 + V_a,x·(1 − β_k) + (V_f,a·b_v·FC_v + V'_a,x)·β_k.
- **Ventilazione notturna** (3.52): β^g = 0,67 di giorno e β^n = 0,33 di notte; b_v,n = 1,5·b_v se θ_i > θe (p. 81).
- β_k = f_G,per (3.58). Per il residenziale f_G,per = **24/24** (Prospetto 4.I), quindi nel residenziale **β = 1**.
- V_f,a = max(V_a,des ; V_a,p,min) (3.55). V_a,des è la portata di estrazione, di immissione, oppure max(imm., estr.)
  per il bilanciato (3.56).
- V_a,x = V·n50·e/3600 (3.54). V'_a,x = V_a,x / [1 + (f/e)·((V_sup − V_ext)/(V·n50/3600))²] (3.57) **[AMB-9]**.
- **Prospetto 3.XXII - n50 [h⁻¹]**. Senza informazioni sui serramenti si usa la permeabilità **media**.

| Permeabilità | Multifamiliare / altro | Monofamiliare |
|---|---|---|
| Bassa | 1 | 2 |
| Media | 4 | 7 |
| Alta | 8 | 14 |

- **Prospetto 3.XXIII - coefficienti e, f**:

| Schermatura | e (più facciate esposte) | e (una facciata) |
|---|---|---|
| Nessuna (aperta campagna, grattacieli in centro) | 0,10 | 0,03 |
| Media (campagna con alberi o edifici vicini, periferie) | 0,07 | 0,02 |
| Forte (edifici di media altezza in centro, in mezzo a foreste) | 0,04 | 0,01 |
| f (tutte le classi) | 15 | 20 |

- **Prospetti 3.XX (multifamiliare e altri) e 3.XXI (monofamiliare) - n_vn [h⁻¹]** (per V_a,0 = V·n_vn/3600, (3.53)):

| Schermatura | 3.XX più facciate B/M/A | 3.XX una facciata B/M/A | 3.XXI B/M/A |
|---|---|---|---|
| Nessuna | 0,5 / 0,7 / 1,2 | 0,5 / 0,6 / 1,0 | 0,5 / 0,7 / 1,2 |
| Media | 0,5 / 0,6 / 0,9 | 0,5 / 0,5 / 0,7 | 0,5 / 0,6 / 0,9 |
| Forte | 0,5 / 0,5 / 0,6 | 0,5 / 0,5 / 0,5 | 0,5 / 0,5 / 0,6 |

- **FC_v - Prospetto 3.XXIV**, riga E.1 Residenze. Colonne: presenza; movimento; CO2 (modulo di regolazione / ventilatore
  a velocità variabile); umidità relativa (modulo / ventilatore); bocchetta con rilevatore di presenza (modulo / ventilatore).
  Valori nell'ordine del testo: **0,80 0,80 0,80 0,70 0,70 0,70 0,70 0,60**. La corrispondenza tra valori e colonne
  si ricostruisce con difficoltà dall'estrazione **[AMB-10]**. A portata costante (senza regolazione) FC_v = 1.
- **b_v** (§3.3.6.10, p. 86-87):
  - semplice flusso (immissione diretta o estrazione): b_v = 1;
  - con prelievo da locale non climatizzato o serra: b_v = (θ_i − θ_im,k)/(θ_i − θe).
    In certificazione, se H_V è stato stimato con F_T, si pone b_v = F_T;
  - doppio flusso senza recupero: 1;
  - doppio flusso **con recupero**: b_v = (θ_i − θ_im)/(θ_i − θe), con θ_im dall'Appendice E:
    θ_out,re = θ_in,re + η_R,eff·(θ_in,ex − θ_in,re) (E.2). Se la portata è diversa dalla nominale e mancano dati,
    η_R,eff = η nominale **meno 10 punti percentuali** (p. 479). Per sistemi a doppio condotto al servizio di una singola
    unità immobiliare le Δθ dei condotti si pongono = 0 (p. 479);
  - impianto a tutt'aria nelle ore di climatizzazione: b_v = 0.
- Portata minima per le altre destinazioni (3.43)-(3.44), Prospetti 3.XIII-3.XVIII: non necessaria per E.1(1).

### 3.6 Apporti solari attraverso i trasparenti (§3.3.8, p. 88-100)

```
Q_SI = N · Σ_j H_s,j · Σ_i [ A_L,i · (1 − F_F,i) · F_S,i,j · F_(sh+gl),i,j · g⊥,i ]      (3.61)
```

- N = giorni del mese. H_s,j = irradiazione **globale giornaliera media mensile** sul piano del serramento [kWh/m²/giorno]
  (Appendice F, sez. 3.10). A_L,i = area lorda del serramento, cioè il foro nella parete.
- (1 − F_F) = frazione vetrata. Senza dati si usa **0,80** (p. 89).
- g⊥ dal **Prospetto 3.XXVII** (solo senza dati del costruttore):

| Tipo di vetro | g⊥ |
|---|---|
| Vetro singolo | 0,85 |
| Vetro singolo selettivo | 0,66 |
| Doppio vetro normale | 0,75 |
| Doppio vetro con rivestimento basso emissivo | 0,67 |
| Triplo vetro normale | 0,70 |
| Triplo vetro con doppio rivestimento basso emissivo | 0,5 |
| Doppia finestra con vetri singoli | 0,75 |

- **Ombreggiamento** (3.64): **F_S,i,j = min(F_h ; F_o ; F_f)**. Nella UNI/TS 11300-1 si usa il *prodotto*
  F_hor·F_ov·F_fin: qui si prende il **minimo**. Per i serramenti nei tetti con pendenza ≤ 45° e nei tetti piani, F_S = 1.
- **Schermature mobili e correzione angolare** (3.65)-(3.66):

```
F_(sh+gl),i,j = f_shd,j · F_sh,i,j + (1 − f_shd,j) · F_gl,i                          (3.65)
F_sh,i,j      = [ f_b,j · g_(sh+gl),b,i + (1 − f_b,j) · g_(sh+gl),d,i ] / g⊥,i          (3.66)
```

Senza schermature mobili f_shd = 0, quindi F_(sh+gl) = F_gl. Il fattore F_gl sostituisce il **F_w = 0,9** della
UNI/TS 11300-1 (in `bilancio.py` oggi c'è F_W = 0,9). Le schermature considerate sono solo quelle parallele al vetro.
Per le tende (tendaggi) si usa invece F_sh dal Prospetto 3.XXXII.

*Prospetto 3.XXVIII - f_shd* (per orientamenti intermedi si interpola linearmente):

| Mese | Nord | Est | Sud | Ovest |
|---|---|---|---|---|
| Gennaio | 0,00 | 0,52 | 0,81 | 0,39 |
| Febbraio | 0,00 | 0,48 | 0,82 | 0,55 |
| Marzo | 0,00 | 0,66 | 0,81 | 0,63 |
| Aprile | 0,00 | 0,71 | 0,74 | 0,62 |
| Maggio | 0,00 | 0,71 | 0,62 | 0,64 |
| Giugno | 0,00 | 0,75 | 0,56 | 0,68 |
| Luglio | 0,00 | 0,74 | 0,62 | 0,73 |
| Agosto | 0,00 | 0,75 | 0,76 | 0,72 |
| Settembre | 0,00 | 0,73 | 0,82 | 0,67 |
| Ottobre | 0,00 | 0,72 | 0,86 | 0,60 |
| Novembre | 0,00 | 0,62 | 0,84 | 0,30 |
| Dicembre | 0,00 | 0,50 | 0,86 | 0,42 |

*Prospetto 3.XXIX - F_gl* (correzione angolare, vetro non schermato):

| Mese | Singolo S | Singolo E/O | Singolo N | Singolo Orizz. | Doppio S | Doppio E/O | Doppio N | Doppio Orizz. | Triplo S | Triplo E/O | Triplo N | Triplo Orizz. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gen | 0,984 | 0,902 | 0,932 | 0,876 | 0,978 | 0,861 | 0,901 | 0,812 | 0,972 | 0,833 | 0,880 | 0,770 |
| Feb | 0,967 | 0,923 | 0,932 | 0,902 | 0,950 | 0,890 | 0,901 | 0,851 | 0,937 | 0,868 | 0,880 | 0,817 |
| Mar | 0,933 | 0,932 | 0,931 | 0,931 | 0,897 | 0,904 | 0,901 | 0,895 | 0,872 | 0,884 | 0,879 | 0,871 |
| Apr | 0,888 | 0,938 | 0,921 | 0,949 | 0,833 | 0,912 | 0,890 | 0,923 | 0,796 | 0,894 | 0,868 | 0,906 |
| Mag | 0,852 | 0,941 | 0,895 | 0,955 | 0,787 | 0,916 | 0,854 | 0,933 | 0,747 | 0,898 | 0,828 | 0,918 |
| Giu | 0,838 | 0,941 | 0,877 | 0,955 | 0,770 | 0,915 | 0,831 | 0,934 | 0,731 | 0,898 | 0,802 | 0,920 |
| Lug | 0,835 | 0,941 | 0,877 | 0,956 | 0,766 | 0,915 | 0,831 | 0,935 | 0,724 | 0,898 | 0,801 | 0,921 |
| Ago | 0,861 | 0,940 | 0,905 | 0,952 | 0,797 | 0,915 | 0,870 | 0,928 | 0,756 | 0,898 | 0,846 | 0,912 |
| Set | 0,911 | 0,935 | 0,930 | 0,940 | 0,865 | 0,907 | 0,899 | 0,909 | 0,833 | 0,888 | 0,877 | 0,887 |
| Ott | 0,957 | 0,925 | 0,931 | 0,912 | 0,933 | 0,894 | 0,900 | 0,865 | 0,915 | 0,872 | 0,878 | 0,833 |
| Nov | 0,981 | 0,912 | 0,931 | 0,880 | 0,971 | 0,876 | 0,901 | 0,818 | 0,964 | 0,851 | 0,879 | 0,776 |
| Dic | 0,987 | 0,903 | 0,932 | 0,858 | 0,982 | 0,862 | 0,901 | 0,789 | 0,977 | 0,834 | 0,880 | 0,744 |

*Prospetto 3.XXX - f_b* (quota diretta sulla globale, Lombardia):

| Mese | Sud | Est/Ovest | Nord | Orizzontale |
|---|---|---|---|---|
| Gennaio | 0,75 | 0,50 | 0 | 0,40 |
| Febbraio | 0,70 | 0,50 | 0 | 0,50 |
| Marzo | 0,65 | 0,55 | 0 | 0,55 |
| Aprile | 0,55 | 0,55 | 0,10 | 0,60 |
| Maggio | 0,40 | 0,55 | 0,25 | 0,60 |
| Giugno | 0,35 | 0,55 | 0,30 | 0,65 |
| Luglio | 0,45 | 0,60 | 0,35 | 0,70 |
| Agosto | 0,50 | 0,60 | 0,15 | 0,65 |
| Settembre | 0,65 | 0,60 | 0 | 0,60 |
| Ottobre | 0,75 | 0,55 | 0 | 0,55 |
| Novembre | 0,75 | 0,50 | 0 | 0,45 |
| Dicembre | 0,75 | 0,50 | 0 | 0,40 |

**Trasmittanza solare con schermo, g_(sh+gl),b/d** (§3.3.8.1-3.3.8.2, p. 93-99, semplificazione UNI EN 13363-1):

- Schermo **esterno** (3.67)-(3.69):
  g_(sh+gl) = τ_e·g⊥ + α_e·(G/G_2) + τ_e·(1 − g⊥)·(G/G_1),
  con G_1 = 5, G_2 = 10 W/m²K e G = (1/U_g + 1/G_1 + 1/G_2)⁻¹.
- Schermo **interno** (3.72)-(3.74): g_(sh+gl) = g⊥·(1 − g⊥·ρ_e − α_e·G/G_2), con G_2 = 30 e G = (1/U_g + 1/G_2)⁻¹.
- Schermo **integrato** in intercapedine non ventilata (3.75)-(3.77):
  g = g⊥·τ_e + g⊥·[α_e + (1 − g⊥)·ρ_e]·G/G_3, con G_3 = 3 e G = (1/U_g + 1/G_3)⁻¹ **[AMB-11]**.
- α_e = 1 − τ_e − ρ_e (3.70)-(3.71). Per le tende a rullo le componenti diretta e diffusa coincidono.
- Sistemi a lamelle (veneziane, persiane e, per estensione, tapparelle e frangisole), a 45° (3.78)-(3.81), ricostruzione
  **[AMB-12]**: τ_e,b(45) = 0,65·τ_B⊥ + 0,15·ρ_B⊥; ρ_e,b(45) = ρ_B⊥·(0,75 + 0,70·τ_B⊥) (?);
  τ_e,d(45) = 0,30 + 0,70·τ_e,b(45) (?); ρ_e,d(45) = 0,70·ρ_e,b(45).

*Prospetto 3.XXXI - τ_e,B⊥, ρ_e,B⊥, α_e,B⊥ convenzionali* (UNI EN 13363-1):

| Trasparenza | τ | ρ bianco | ρ pastello | ρ scuro | ρ nero | α bianco | α pastello | α scuro | α nero |
|---|---|---|---|---|---|---|---|---|---|
| Opaca | 0,0 | 0,7 | 0,5 | 0,3 | 0,1 | 0,3 | 0,5 | 0,7 | 0,9 |
| Mediamente traslucida o perforata | 0,2 | 0,6 | 0,4 | 0,2 | 0,1 | 0,2 | 0,4 | 0,6 | 0,7 |
| Altamente traslucida o perforata | 0,4 | 0,4 | 0,3 | 0,2 | 0,1 | 0,2 | 0,3 | 0,4 | 0,5 |

*Prospetto 3.XXXII - F_sh per tende* (assorbimento / trasmissione → F_sh con tenda interna / esterna):

| Tipo di tenda | α | τ | F_sh interna | F_sh esterna |
|---|---|---|---|---|
| Tendaggi bianchi | 0,1 | 0,5 | 0,65 | 0,55 |
| Tendaggi bianchi | 0,1 | 0,7 | 0,80 | 0,75 |
| Tendaggi bianchi | 0,1 | 0,9 | 0,95 | 0,95 |
| Tessuti colorati | 0,3 | 0,1 | 0,42 | 0,17 |
| Tessuti colorati | 0,3 | 0,3 | 0,57 | 0,37 |
| Tessuti colorati | 0,3 | 0,5 | 0,77 | 0,57 |
| Tessuti con lamina di alluminio | 0,2 | 0,05 | 0,20 | 0,08 |

(Nell'estrazione la tabella è disposta in colonne. L'accoppiamento tra righe e colonne qui sopra è la lettura più
plausibile **[AMB-13]**.)

**Serre** (3.62)-(3.63): Q_SI,S = N · [(1−F_F)·F_S·F_(sh+gl)·g⊥]_we · Σ_k A_L,wi·(1−F_F)_wi·F_S,wi·F_(sh+gl),wi·g⊥,wi·H_s,pi,k.
Il termine [·]_we è la media pesata per area dei vetri della serra verso l'esterno.

### 3.7 Apporti solari sulle superfici opache (§3.3.9, p. 100-105)

```
Q_SE,O = N · Σ_j H_s,j · Σ_i A_L,i · F_S,i · S_f,i                  (3.82)
S_f,i  = α_i · U_i / h_e ,   h_e = 25 W/m²K                           (3.83)
```

F_S come nella (3.64). Per tetti con pendenza ≤ 45° o piani F_S = 1. α dal **Prospetto 3.XXXIII**: chiaro **0,3**,
medio **0,6**, scuro **0,9**. La (3.82) si applica ai componenti opachi verso l'esterno.
Isolamento trasparente (3.84)-(3.89) e c_j dal Prospetto 3.XXXIV (p. 101-102); pareti solari ventilate (3.90)-(3.92)
ed elementi ventilati (3.93)-(3.94): casi speciali, non necessari nel caso base.
Contributo indiretto della serra (3.95): Q_SE,S = N·[(1−F_F)F_S F_(sh+gl) g⊥]_we · Σ_k A_L,pi·α_pi·(U_pi/h_i)·H_s,pi,
con **h_i = 7,7 W/m²K**.

### 3.8 Fattori di utilizzazione, costante di tempo, capacità termica (§3.3.10-3.3.11, p. 105-109)

Riscaldamento (identico per "adj"):

```
γ_H = Q_G,H / Q_L,H,net                                  (3.98)
a_H = a_0,H + τ_H/τ_0,H = 1 + τ_H/15                     (3.99)/(3.100)   a_0,H = 1 ; τ_0,H = 15 h
τ_H = C_m · A_tot / (3,6 · H_L,H)                        (3.101)  [C_m in kJ/(m²K), A_tot in m², H in W/K → h]
H_L,H = (Q_T,H + Q_V,H) / (Δt · Δθ)                       (3.102)  [adj: Q_V,H,adj]
η_G,H = (1 − γ^a)/(1 − γ^(a+1))    se γ > 0 e γ ≠ 1       (3.96)
η_G,H = a/(a+1)                    se γ = 1                (3.97)
```

Raffrescamento:

```
γ_C = Q_G,C / Q_L,C,net                                  (3.106)
a_C = 1 + τ_C/15                                         (3.107)/(3.108)   a_0,C = 1 ; τ_0,C = 15 h
τ_C = C_m · A_tot/(3,6 · H_L,C) ;  H_L,C = (Q_T,C + Q_V,C)/(Δt·Δθ)    (3.109)/(3.110)
η_L,C = (1 − γ_C^(−a_C)) / (1 − γ_C^(−(a_C+1)))  se γ_C > 0 e γ_C ≠ 1    (3.103)
η_L,C = a_C/(a_C + 1)       se γ_C = 1                  (3.104)
η_L,C = 1                   se γ_C ≤ 0 (perdite nette negative)   (3.105) [AMB-14]
```

- **C_m** [kJ/(m²K)] = capacità termica efficace **per unità di superficie interna**. A_tot = somma delle superfici
  **nette** dei componenti opachi che delimitano la zona (p. 107). Il calcolo analitico segue l'Appendice H (H.37):
  C = Σ κ_I·A/1000 [kJ/K], quindi C_m·A_tot = C. Solo per la certificazione, senza dati di progetto, si usa il
  **Prospetto D.I** (p. 477). Lì la superficie di riferimento è "somma dell'area delle superfici verticali più due volte
  l'area in pianta per il numero di piani della zona".

*Prospetto D.I - C_m [kJ/(m²K)]* (colonne: numero di piani 1 / 2 / ≥3):

| Intonaco | Isolamento | Pareti esterne | Pavimenti | 1 | 2 | ≥3 |
|---|---|---|---|---|---|---|
| gesso | interno | qualsiasi | tessile | 75 | 75 | 85 |
| gesso | interno | qualsiasi | legno | 85 | 95 | 105 |
| gesso | interno | qualsiasi | piastrelle | 95 | 105 | 115 |
| gesso | assente/esterno | leggere/blocchi | tessile | 95 | 95 | 95 |
| gesso | assente/esterno | medie/pesanti | tessile | 105 | 95 | 95 |
| gesso | assente/esterno | leggere/blocchi | legno | 115 | 115 | 115 |
| gesso | assente/esterno | medie/pesanti | legno | 115 | 125 | 125 |
| gesso | assente/esterno | leggere/blocchi | piastrelle | 115 | 125 | 135 |
| gesso | assente/esterno | medie/pesanti | piastrelle | 125 | 135 | 135 |
| malta | interno | qualsiasi | tessile | 105 | 105 | 105 |
| malta | interno | qualsiasi | legno | 115 | 125 | 135 |
| malta | interno | qualsiasi | piastrelle | 125 | 135 | 135 |
| malta | assente/esterno | leggere/blocchi | tessile | 125 | 125 | 115 |
| malta | assente/esterno | medie | tessile | 135 | 135 | 125 |
| malta | assente/esterno | pesanti | tessile | 145 | 135 | 125 |
| malta | assente/esterno | leggere/blocchi | legno | 145 | 145 | 145 |
| malta | assente/esterno | medie | legno | 155 | 155 | 155 |
| malta | assente/esterno | pesanti | legno | 165 | 165 | 165 |
| malta | assente/esterno | leggere/blocchi | piastrelle | 145 | 155 | 155 |
| malta | assente/esterno | medie | piastrelle | 155 | 165 | 165 |
| malta | assente/esterno | pesanti | piastrelle | 165 | 165 | 165 |

> La superficie A_tot da usare con il Prospetto D.I (involucro + 2·pianta·piani) è diversa da quella usata con il
> metodo analitico (superfici nette opache che delimitano la zona) **[AMB-15]**.

### 3.9 Zone non climatizzate: metodo analitico, non b_tr fisso (Appendice A, p. 446-456)

La temperatura mensile θ_u del locale non climatizzato si ottiene da un **bilancio stazionario** (capacità trascurate) (A.1):

```
θ_u = [ (Q_SI + Q_SE + Q_I − ΔQ_T,R)/Δt + Σ_j H_T,ju·θ_j + Σ_j H_V,ju·θ_j ] / ( Σ_j H_T,ju + Σ_j H_V,ju )
```

- La somma su j comprende le zone climatizzate adiacenti (θ_j = θ_i) e l'**esterno** (θ_e).
- Q_SI (3.61) e Q_SE (3.82) sono calcolati per il locale u. Q_I si include solo se non trascurabile.
- H_V,ju dipende dallo schema dei flussi (A.2)-(A.12). Caso a), circolazioni separate:
  H_V,uZ = ρc·Σ V_a,k (portate delle stanze della zona che danno sul locale, con b_v = 1);
  H_V,ue = ρc·V_u·n_u/3600 con **n_u = 0,5 vol/h**.
  Caso b), zona che espelle attraverso u: H_V,ue = 0. Caso c), zona che prende aria attraverso u: H_V,uZ = 0 e
  V_ue = Σ V_a,k.
- **Serra** (A.21): come la (A.1), ma con α·(Q_SI + …) − Q_SPI al numeratore. α = assorbimento medio delle superfici
  opache della serra (A.22) e Q_SPI = Σ Q_SE,S,j (A.23). Senza ventilazione con le zone, V_s = V_s·n/3600 con
  n = 0,5 nel periodo di riscaldamento e 1,0 negli altri periodi (A.24).
- Poi H_T della zona usa (θ_i − θ_u)/(θ_i − θ_e) (3.15) e la ventilazione attraverso u usa c_v o b_v con θ_u.

**Differenza rispetto alla UNI/TS 11300-1.** Nella TS si usa b_tr,x tabellato o calcolato (b = H_ue/(H_iu + H_ue)).
Qui si calcola θ_u **mese per mese**, includendo gli apporti solari del locale e l'extra flusso radiativo. Il b_tr
fisso (Prospetto 3.I, F_T) è ammesso solo "ai soli fini della certificazione energetica, in assenza di dati di progetto
attendibili" (3.16).

### 3.10 Irradiazione su superficie orientata (Appendice F, p. 482-489)

Metodo mensile (F.25)-(F.27), con giorno tipo n del Prospetto F.III:

```
H_T,y = H_bh · R_b,y + H_dh·(1 + cos β)/2 + ρ·(H_bh + H_dh)·(1 − cos β)/2           (F.25)
```

- H_bh e H_dh da Allegato 1, Prospetto III (diretta e diffusa orizzontale), in MJ/m² → /3,6 per avere kWh/m².
- ρ = albedo, convenzionale **0,2** (Prospetto F.II). In certificazione si possono usare due soli valori globali,
  uno invernale e uno estivo (p. 485).
- R_b,y (F.26) = [T·(ω_t − ω_a)·π/180 + U·(sin ω_t − sin ω_a) − V·(cos ω_t − cos ω_a)] /
  [2·(T_h·ω_ss·π/180 + U_h·sin ω_ss)] **[AMB-16]**, con:
  - T = sin δ·(sin φ cos β − cos φ sin β cos γ);
  - U = cos δ·(cos φ cos β + sin φ sin β cos γ);
  - V = cos δ·sin β·sin γ   (F.11);
  - T_h e U_h calcolati con β = 0;
  - ω_ss = cos⁻¹(−tan δ tan φ) (F.16);
  - ω_a,y e ω_t,y (alba e tramonto sulla superficie) da (F.17)-(F.23), con il caso dei due archi di visibilità
    (nord in estate, (F.27)).
- γ: 0° sud, −90° est, +90° ovest, ±180° nord. β: 0° orizzontale, 90° verticale.
- **Prospetto F.III - giorno tipo e declinazione**:

| Mese | n | δ [°] |
|---|---|---|
| Gen | 17 | −20,9 |
| Feb | 47 | −13,0 |
| Mar | 75 | −2,4 |
| Apr | 105 | 9,4 |
| Mag | 135 | 18,8 |
| Giu | 162 | 23,1 |
| Lug | 198 | 21,2 |
| Ago | 228 | 13,5 |
| Set | 258 | 2,2 |
| Ott | 288 | −9,6 |
| Nov | 318 | −18,9 |
| Dic | 344 | −23,1 |

- La latitudine φ è quella del capoluogo (tabella sez. 2.3).
- Il modello orario a cielo sereno (F.1)-(F.13) serve all'Appendice G e **non** al calcolo mensile standard.

### 3.11 Fattori d'ombra (Appendice C, p. 472-476)

Angoli (Figure C.1-C.3), misurati dal **baricentro** della superficie, telaio compreso:

- ostruzione esterna: α è l'angolo sull'orizzonte dell'ostruzione visto dal baricentro (Figura C.1). La formula della
  figura è illeggibile nell'estrazione (compaiono a, b, c, d e "se d = 0") **[AMB-17]**;
- aggetto orizzontale (Figure C.2A e C.3A): α = tan⁻¹(b/a);
- aggetto verticale (Figure C.2B e C.3B): β = tan⁻¹(d/c).

Ci sono tabelle a 44° e a 46° di latitudine; per latitudini intermedie e per gli angoli intermedi si interpola
linearmente. Per l'aggetto verticale le tabelle considerano un solo aggetto. Con doppio aggetto a sud (±15°) si usa la
(C.1): F_s,f = F_s,f,O + F_s,f,E − 1.

*Prospetto C.1 - F_h (ostruzioni esterne), 44° N:*

| Angolo | Gen S | Gen E/O | Gen N | Feb S | Feb E/O | Feb N | Mar S | Mar E/O | Mar N | Apr S | Apr E/O | Apr N | Mag S | Mag E/O | Mag N | Giu S | Giu E/O | Giu N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 10° | 0,91 | 0,80 | 0,83 | 0,90 | 0,78 | 0,83 | 0,96 | 0,86 | 0,83 | 0,93 | 0,86 | 0,84 | 0,90 | 0,84 | 0,79 | 0,89 | 0,87 | 0,84 |
| 20° | 0,59 | 0,58 | 0,67 | 0,80 | 0,59 | 0,67 | 0,91 | 0,67 | 0,67 | 0,87 | 0,69 | 0,68 | 0,81 | 0,68 | 0,63 | 0,79 | 0,72 | 0,65 |
| 30° | 0,09 | 0,44 | 0,52 | 0,47 | 0,43 | 0,52 | 0,87 | 0,50 | 0,52 | 0,80 | 0,52 | 0,54 | 0,73 | 0,53 | 0,51 | 0,69 | 0,56 | 0,52 |
| 40° | 0,05 | 0,23 | 0,38 | 0,14 | 0,31 | 0,38 | 0,64 | 0,33 | 0,38 | 0,75 | 0,37 | 0,40 | 0,65 | 0,37 | 0,39 | 0,61 | 0,39 | 0,41 |

| Angolo | Lug S | Lug E/O | Lug N | Ago S | Ago E/O | Ago N | Set S | Set E/O | Set N | Ott S | Ott E/O | Ott N | Nov S | Nov E/O | Nov N | Dic S | Dic E/O | Dic N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 10° | 0,91 | 0,86 | 0,82 | 0,93 | 0,88 | 0,84 | 0,95 | 0,79 | 0,83 | 0,96 | 0,82 | 0,83 | 0,94 | 0,82 | 0,83 | 0,87 | 0,76 | 0,83 |
| 20° | 0,82 | 0,71 | 0,63 | 0,86 | 0,71 | 0,69 | 0,91 | 0,64 | 0,67 | 0,91 | 0,64 | 0,67 | 0,72 | 0,61 | 0,67 | 0,46 | 0,55 | 0,67 |
| 30° | 0,74 | 0,55 | 0,52 | 0,80 | 0,54 | 0,55 | 0,87 | 0,48 | 0,51 | 0,76 | 0,46 | 0,52 | 0,17 | 0,44 | 0,52 | 0,05 | 0,40 | 0,52 |
| 40° | 0,66 | 0,38 | 0,41 | 0,74 | 0,40 | 0,42 | 0,83 | 0,32 | 0,37 | 0,11 | 0,34 | 0,38 | 0,05 | 0,27 | 0,38 | 0,04 | 0,22 | 0,38 |

*Prospetto C.2 - F_h, 46° N:*

| Angolo | Gen S | Gen E/O | Gen N | Feb S | Feb E/O | Feb N | Mar S | Mar E/O | Mar N | Apr S | Apr E/O | Apr N | Mag S | Mag E/O | Mag N | Giu S | Giu E/O | Giu N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 10° | 0,88 | 0,76 | 0,83 | 0,93 | 0,83 | 0,83 | 0,96 | 0,85 | 0,83 | 0,93 | 0,86 | 0,84 | 0,90 | 0,84 | 0,81 | 0,89 | 0,87 | 0,85 |
| 20° | 0,47 | 0,54 | 0,67 | 0,80 | 0,63 | 0,67 | 0,92 | 0,66 | 0,67 | 0,87 | 0,69 | 0,68 | 0,81 | 0,69 | 0,64 | 0,79 | 0,72 | 0,66 |
| 30° | 0,05 | 0,39 | 0,52 | 0,40 | 0,45 | 0,52 | 0,87 | 0,49 | 0,52 | 0,81 | 0,52 | 0,54 | 0,73 | 0,53 | 0,51 | 0,69 | 0,56 | 0,52 |
| 40° | 0,04 | 0,21 | 0,38 | 0,14 | 0,32 | 0,38 | 0,49 | 0,33 | 0,38 | 0,75 | 0,37 | 0,40 | 0,65 | 0,38 | 0,39 | 0,60 | 0,39 | 0,41 |

| Angolo | Lug S | Lug E/O | Lug N | Ago S | Ago E/O | Ago N | Set S | Set E/O | Set N | Ott S | Ott E/O | Ott N | Nov S | Nov E/O | Nov N | Dic S | Dic E/O | Dic N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 10° | 0,91 | 0,87 | 0,83 | 0,93 | 0,88 | 0,84 | 0,95 | 0,81 | 0,83 | 0,96 | 0,81 | 0,83 | 0,93 | 0,81 | 0,83 | 0,84 | 0,71 | 0,83 |
| 20° | 0,82 | 0,71 | 0,64 | 0,86 | 0,71 | 0,69 | 0,91 | 0,64 | 0,67 | 0,90 | 0,63 | 0,67 | 0,61 | 0,58 | 0,67 | 0,35 | 0,51 | 0,67 |
| 30° | 0,73 | 0,55 | 0,52 | 0,79 | 0,54 | 0,55 | 0,87 | 0,48 | 0,51 | 0,64 | 0,44 | 0,52 | 0,09 | 0,43 | 0,52 | 0,04 | 0,35 | 0,52 |
| 40° | 0,65 | 0,38 | 0,41 | 0,73 | 0,39 | 0,42 | 0,83 | 0,32 | 0,37 | 0,06 | 0,33 | 0,38 | 0,04 | 0,23 | 0,38 | 0,03 | 0,21 | 0,38 |

*Prospetto C.3 - F_o (aggetti orizzontali), 44° N:*

| Angolo | Gen S | Gen E/O | Gen N | Feb S | Feb E/O | Feb N | Mar S | Mar E/O | Mar N | Apr S | Apr E/O | Apr N | Mag S | Mag E/O | Mag N | Giu S | Giu E/O | Giu N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 30° | 0,89 | 0,87 | 0,80 | 0,84 | 0,84 | 0,80 | 0,79 | 0,82 | 0,80 | 0,71 | 0,80 | 0,81 | 0,67 | 0,79 | 0,82 | 0,64 | 0,78 | 0,82 |
| 45° | 0,82 | 0,83 | 0,72 | 0,77 | 0,78 | 0,72 | 0,68 | 0,76 | 0,72 | 0,58 | 0,71 | 0,73 | 0,54 | 0,69 | 0,76 | 0,55 | 0,67 | 0,76 |
| 60° | 0,74 | 0,81 | 0,65 | 0,68 | 0,73 | 0,65 | 0,56 | 0,70 | 0,65 | 0,49 | 0,63 | 0,66 | 0,50 | 0,59 | 0,70 | 0,51 | 0,56 | 0,70 |

| Angolo | Lug S | Lug E/O | Lug N | Ago S | Ago E/O | Ago N | Set S | Set E/O | Set N | Ott S | Ott E/O | Ott N | Nov S | Nov E/O | Nov N | Dic S | Dic E/O | Dic N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 30° | 0,63 | 0,78 | 0,83 | 0,68 | 0,79 | 0,81 | 0,75 | 0,82 | 0,80 | 0,83 | 0,85 | 0,80 | 0,88 | 0,86 | 0,80 | 0,90 | 0,88 | 0,80 |
| 45° | 0,52 | 0,68 | 0,77 | 0,53 | 0,69 | 0,73 | 0,64 | 0,75 | 0,72 | 0,74 | 0,79 | 0,72 | 0,81 | 0,82 | 0,72 | 0,84 | 0,85 | 0,72 |
| 60° | 0,48 | 0,56 | 0,71 | 0,47 | 0,59 | 0,67 | 0,50 | 0,69 | 0,65 | 0,63 | 0,75 | 0,65 | 0,72 | 0,79 | 0,65 | 0,77 | 0,82 | 0,65 |

*Prospetto C.4 - F_o, 46° N:*

| Angolo | Gen S | Gen E/O | Gen N | Feb S | Feb E/O | Feb N | Mar S | Mar E/O | Mar N | Apr S | Apr E/O | Apr N | Mag S | Mag E/O | Mag N | Giu S | Giu E/O | Giu N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 30° | 0,90 | 0,88 | 0,80 | 0,84 | 0,83 | 0,80 | 0,80 | 0,83 | 0,80 | 0,72 | 0,80 | 0,80 | 0,68 | 0,79 | 0,82 | 0,66 | 0,78 | 0,82 |
| 45° | 0,84 | 0,85 | 0,72 | 0,77 | 0,77 | 0,72 | 0,70 | 0,76 | 0,72 | 0,60 | 0,72 | 0,73 | 0,55 | 0,70 | 0,75 | 0,56 | 0,68 | 0,75 |
| 60° | 0,77 | 0,83 | 0,65 | 0,68 | 0,72 | 0,65 | 0,58 | 0,71 | 0,65 | 0,49 | 0,63 | 0,66 | 0,50 | 0,60 | 0,69 | 0,51 | 0,57 | 0,69 |

| Angolo | Lug S | Lug E/O | Lug N | Ago S | Ago E/O | Ago N | Set S | Set E/O | Set N | Ott S | Ott E/O | Ott N | Nov S | Nov E/O | Nov N | Dic S | Dic E/O | Dic N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 30° | 0,65 | 0,78 | 0,82 | 0,69 | 0,79 | 0,81 | 0,77 | 0,83 | 0,80 | 0,84 | 0,85 | 0,80 | 0,89 | 0,87 | 0,80 | 0,91 | 0,90 | 0,80 |
| 45° | 0,53 | 0,68 | 0,76 | 0,56 | 0,70 | 0,73 | 0,65 | 0,76 | 0,72 | 0,75 | 0,80 | 0,72 | 0,82 | 0,83 | 0,72 | 0,86 | 0,87 | 0,72 |
| 60° | 0,49 | 0,57 | 0,70 | 0,48 | 0,60 | 0,66 | 0,52 | 0,69 | 0,65 | 0,65 | 0,76 | 0,65 | 0,74 | 0,81 | 0,65 | 0,79 | 0,85 | 0,65 |

*Prospetto C.5 - F_f (aggetti verticali, angolo β), 44° N:*

| Angolo | Gen S | Gen E/O | Gen N | Feb S | Feb E/O | Feb N | Mar S | Mar E/O | Mar N | Apr S | Apr E/O | Apr N | Mag S | Mag E/O | Mag N | Giu S | Giu E/O | Giu N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 30° | 0,92 | 0,70 | 0,89 | 0,89 | 0,83 | 0,89 | 0,88 | 0,83 | 0,89 | 0,88 | 0,89 | 0,88 | 0,88 | 0,92 | 0,84 | 0,89 | 0,92 | 0,84 |
| 45° | 0,87 | 0,56 | 0,85 | 0,83 | 0,74 | 0,85 | 0,83 | 0,75 | 0,85 | 0,83 | 0,84 | 0,83 | 0,85 | 0,88 | 0,79 | 0,85 | 0,89 | 0,78 |
| 60° | 0,80 | 0,42 | 0,80 | 0,77 | 0,64 | 0,80 | 0,78 | 0,66 | 0,80 | 0,80 | 0,79 | 0,79 | 0,82 | 0,85 | 0,75 | 0,82 | 0,86 | 0,74 |

| Angolo | Lug S | Lug E/O | Lug N | Ago S | Ago E/O | Ago N | Set S | Set E/O | Set N | Ott S | Ott E/O | Ott N | Nov S | Nov E/O | Nov N | Dic S | Dic E/O | Dic N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 30° | 0,88 | 0,92 | 0,83 | 0,88 | 0,90 | 0,87 | 0,88 | 0,86 | 0,89 | 0,89 | 0,79 | 0,89 | 0,92 | 0,71 | 0,89 | 0,92 | 0,68 | 0,89 |
| 45° | 0,85 | 0,89 | 0,77 | 0,84 | 0,86 | 0,82 | 0,83 | 0,80 | 0,84 | 0,83 | 0,69 | 0,85 | 0,86 | 0,58 | 0,85 | 0,87 | 0,53 | 0,85 |
| 60° | 0,82 | 0,87 | 0,73 | 0,81 | 0,82 | 0,78 | 0,79 | 0,73 | 0,79 | 0,78 | 0,57 | 0,80 | 0,80 | 0,44 | 0,80 | 0,80 | 0,38 | 0,80 |

*Prospetto C.6 - F_f, 46° N:*

| Angolo | Gen S | Gen E/O | Gen N | Feb S | Feb E/O | Feb N | Mar S | Mar E/O | Mar N | Apr S | Apr E/O | Apr N | Mag S | Mag E/O | Mag N | Giu S | Giu E/O | Giu N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 30° | 0,92 | 0,68 | 0,89 | 0,90 | 0,82 | 0,89 | 0,88 | 0,83 | 0,89 | 0,88 | 0,88 | 0,88 | 0,88 | 0,91 | 0,85 | 0,89 | 0,92 | 0,85 |
| 45° | 0,87 | 0,54 | 0,85 | 0,84 | 0,73 | 0,85 | 0,83 | 0,74 | 0,85 | 0,83 | 0,83 | 0,83 | 0,85 | 0,87 | 0,80 | 0,85 | 0,89 | 0,79 |
| 60° | 0,80 | 0,38 | 0,80 | 0,78 | 0,63 | 0,80 | 0,78 | 0,65 | 0,80 | 0,80 | 0,78 | 0,79 | 0,82 | 0,84 | 0,75 | 0,82 | 0,85 | 0,75 |

| Angolo | Lug S | Lug E/O | Lug N | Ago S | Ago E/O | Ago N | Set S | Set E/O | Set N | Ott S | Ott E/O | Ott N | Nov S | Nov E/O | Nov N | Dic S | Dic E/O | Dic N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0° | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| 30° | 0,88 | 0,92 | 0,84 | 0,88 | 0,90 | 0,87 | 0,88 | 0,86 | 0,89 | 0,89 | 0,78 | 0,89 | 0,92 | 0,70 | 0,89 | 0,92 | 0,66 | 0,89 |
| 45° | 0,85 | 0,88 | 0,78 | 0,84 | 0,85 | 0,83 | 0,83 | 0,79 | 0,84 | 0,84 | 0,68 | 0,85 | 0,87 | 0,56 | 0,85 | 0,87 | 0,50 | 0,85 |
| 60° | 0,82 | 0,85 | 0,74 | 0,81 | 0,81 | 0,78 | 0,79 | 0,72 | 0,79 | 0,78 | 0,56 | 0,80 | 0,80 | 0,42 | 0,80 | 0,80 | 0,34 | 0,80 |

*Prospetti C.7, C.8, C.9 - fattori d'ombra sulla sola radiazione diffusa* (servono per F_s,d nella (3.33)):

| Angolo | F_h,d (ostruzioni) | Angolo | F_o,d (aggetti orizzontali) | F_f,d (aggetti verticali) |
|---|---|---|---|---|
| 0° | 1,00 | 0° | 1,00 | 1,00 |
| 10° | 0,83 | 30° | 0,80 | 0,89 |
| 20° | 0,67 | 45° | 0,72 | 0,85 |
| 30° | 0,52 | 60° | 0,65 | 0,80 |
| 40° | 0,38 | | | |

### 3.12 Terreno (Appendice B, p. 457-471): U_b equivalente in regime stazionario

L'Allegato H usa una **trasmittanza equivalente stazionaria del basamento** U_b, moltiplicata per il Δθ mensile
θ_i − θ_e nella (3.15). **Non** usa il metodo con le componenti periodiche della UNI EN ISO 13370 (H_pi, H_pe,
sfasamenti). `cened/terreno.py` va quindi allineato alle formule seguenti, oppure usato solo con il termine stazionario.

- B' = A/(0,5·P) (B.2). Il testo mostra "B' = A/(½P)"; la forma estratta "2B P A=" viene letta così.
- d_t = w + λ·(R_si + R_f + R_se) (B.6). Il simbolo λ è perso nell'estrazione, ma è la forma standard **[AMB-18]**.
- **Pavimento controterra** (B.3)-(B.5):
  - U_b = U_0 + 2·Ψ/B' (Prospetto B.I). Nella (B.3) si legge "Ub = U0 + Ψ(P/A)". Poiché P/A = 2/B', le due scritture
    sono equivalenti;
  - se d_t < B': U_0 = 2λ/(π·B' + d_t) · ln(π·B'/d_t + 1);
  - se d_t ≥ B': U_0 = λ/(0,457·B' + d_t).
- **Isolamento perimetrale** (B.7)-(B.9): d' = R' · λ = (R_n − d_n/λ)·λ.
  - Orizzontale: Ψ = −(λ/π)·[ln(D/d_t + 1) − ln(D/(d_t + d') + 1)].
  - Verticale: come l'orizzontale con 2D al posto di D.
- **Vespaio / spazio aerato** (B.10)-(B.14): U_b = 1/(1/U_f + 1/(U_g + U_x)).
  - U_g = 2λ/(π·B' + d_g) · ln(π·B'/d_g + 1), con d_g = w + λ·(R_si + R_g + R_se).
  - U_x = 2·h·U_w/B' + 1450·ε·v·f_w/B'. Qui ε = area delle aperture per unità di perimetro, v = vento medio annuo
    (Allegato 1, Prospetto V), f_w dal Prospetto B.III: protetta 0,02, media 0,05, esposta 0,10.
  - Se il vespaio scende più di 0,5 m sotto terra: U_g = U_bf + z·P·U_bw/A (B.13).
- **Interrato riscaldato** (B.15)-(B.19): U_b = U_bf + z·P·U_bw/A + Ψ·P/A.
  - U_bf: se (d_t + z/2) < B', U_bf = 2λ/(π·B' + d_t + z/2) · ln(π·B'/(d_t + z/2) + 1);
    altrimenti U_bf = λ/(0,457·B' + d_t + z/2).
  - U_bw = (2λ/(π·z))·(1 + 0,5·d_t/(d_t + z))·ln(z/d_w + 1), con d_w = λ·(R_si + R_w + R_se). Se d_w < d_t si usa d_t.
- **Interrato non riscaldato** (B.20): 1/U_b = 1/U_f + A/(A·U_bf + z·P·U_bw + h·P·U_w + 0,33·n·V), con **n = 0,3 h⁻¹**.
- **Interrato parzialmente riscaldato**: (B.21)-(B.22) per il solaio sotto il piano di campagna. Per locali affiancati
  si pesa sulle aree (§B.8.2).
- Proprietà del terreno (Prospetto B.II): argilla o limo λ = 1,5; sabbia o ghiaia λ = 2,0 (**default** se ignoto);
  roccia λ = 3,5 W/mK.
- I ponti termici parete/pavimento sono esclusi da U_b e vanno messi come ψ sulle pareti (§B.2).
- In certificazione, senza dati, resta sempre ammesso il metodo semplificato **F_T = 0,45** (terreno) e **0,80**
  (vespaio) sulla U del solaio (Prospetto 3.I).

### 3.13 Riepilogo delle DIFFERENZE rispetto alla UNI/TS 11300-1 classica

| Aspetto | UNI/TS 11300-1:2014 | Allegato H (Lombardia) | Rif. |
|---|---|---|---|
| Passo | Mensile | Mensile **con frazioni di mese** nei mesi estremi e stagione **calcolata** con γ_lim (interpolazione giornaliera), troncata al Prospetto I | §1.4 |
| Doppio calcolo | Unico (con ventilazione effettiva) | **Riferimento** (ventilazione naturale) + **corretto** (ventilazione reale) | §3.2 |
| Apporti solari sugli opachi | Negli apporti Q_sol, utilizzati con η | **Sottratti alle perdite** (Q_L,net), non moltiplicati per η | (3.5) |
| Extra flusso verso il cielo | h_r = 5ε e Δθ_er = 11 K fissi; sottratto agli apporti | h_r e Δθ_er da **T_sky(p_v)** mensile; **sommato a Q_T** | (3.32)-(3.37) |
| Locali non climatizzati | b_tr tabellato o calcolato | **θ_u con bilancio mensile** (Appendice A) con apporti solari; F_T tabellato solo in certificazione | (3.15), App. A |
| Terreno | ISO 13370 con componenti periodiche (o b_tr) | U_b **stazionaria** (App. B) × (θ_i − θ_e) mensile; F_T = 0,45 in semplificato | App. B |
| Ombre | F_sh,ob = F_hor·F_ov·F_fin (prodotto) | **min(F_h, F_o, F_f)** | (3.64) |
| Correzione angolare del vetro | F_w = 0,9 | **F_gl mensile per orientamento** (Prospetto 3.XXIX) | (3.65) |
| Schermature mobili | f_sh,with (Prosp. 20 TS) | f_shd (Prospetto 3.XXVIII) e g_(sh+gl) con diretta/diffusa (f_b, Prospetto 3.XXX), metodo EN 13363-1 | (3.65)-(3.81) |
| Chiusure oscuranti | f_shut in funzione del periodo | f_shut = **0,6** fisso | (3.21) |
| ρ·c aria | 1200 J/(m³K) | **1210** J/(m³K) | (3.40) |
| a_0, τ_0 raffrescamento | a_C,0 e τ_C,0 propri (EN 13790) | **a_0,C = 1, τ_0,C = 15 h** (come il riscaldamento) | (3.107) |
| η_C | Rapporto γ = apporti/perdite con formula TS | η_L,C = (1 − γ^−a)/(1 − γ^−(a+1)) con γ = Q_G/Q_L,net | (3.103) |
| τ | C_m/(H_tr + H_ve) | C_m·A_tot/(3,6·H_L), con **H_L = (Q_T + Q_V)/(Δt·Δθ)**, che include ΔQ_T,R e le correzioni θ_a | (3.101)-(3.102) |
| Ventilazione residenziale | n = 0,5 · f_ve,t = 0,6 | uguale (0,5 × 0,6) su **volume netto**, ρc = 1210 | (3.45)-(3.46) |
| Apporti interni residenziali | 7,987A − 0,0353A² (A ≤ 120), 450 W | uguale | Prosp. 3.XXV |

> Nota: la colonna "UNI/TS 11300-1" riassume la norma nazionale come la usa oggi `bilancio.py`. È una conoscenza di
> contesto e **non** viene dal testo dell'Allegato H, quindi va verificata sulla norma prima di citarla in una relazione.
> La colonna "Allegato H" è invece tratta dal testo, con i riferimenti indicati.

### 3.14 Latente (Cap. 4) e raffrescamento: note

Il fabbisogno latente (4.1)-(4.9) si calcola **solo** in presenza di impianti che controllano l'umidità (p. 110):
nel residenziale di solito non serve. Il fabbisogno estivo sensibile Q_NC si calcola su tutti i mesi; la stagione
effettiva viene da γ_C,lim (sez. 2.2).

---

## 4. Acqua calda sanitaria (Cap. 5, Cap. 7, §11.8.1)

### 4.1 Fabbisogno utile (§5.1-5.2.1, p. 116-118)

```
Q_NW,m = Σ_i ρ_w · c_w · V_w,i · (θ_er,i − θ_0) · N_m · (1 − C_r)          (5.2)
Q_NW,yr = Σ_m Q_NW,m   (12 mesi, 24 h/giorno tutto l'anno)                   (5.1)
```

- ρ_w = 1000 kg/m³; c_w = 1,162·10⁻³ kWh/(kg K); θ_er = **40 °C**.
- θ_0 = **temperatura media annuale dell'aria esterna** (Allegato 1). Il testo rinvia al "Prospetto I", ma la media annua
  θe,av è tabulata nel **Prospetto VI** **[AMB-19]**. Per i Comuni si applica la correzione per altitudine?
  Il testo non lo precisa **[AMB-2]**.
- Nel residenziale V_w,i si calcola **per unità immobiliare** (5.3): V_w,i = (a·S_u,i + b)·10⁻³ [m³/giorno].
  S_u è la superficie utile dell'abitazione. **Prospetto 5.V** (fonte UNI/TS 11300-2:2014):

| S_u [m²] | ≤ 35 | 35 < S_u ≤ 50 | 50 < S_u ≤ 200 | > 200 |
|---|---|---|---|---|
| a [l/(m²·giorno)] | 0 | 2,667 | 1,067 | 0 |
| b [l/giorno] | 50 | −43,33 | 36,67 | 250 |

- Edificio: V_W = Σ_i V_w,i sulle unità immobiliari (5.4).
- **Recupero di calore dalle docce** (p. 116-117): C_r = ε·C_s·C_c, con ε = 0,3 in assenza di dati, C_s = 0,85 e
  C_c = 0,4·n_d,rec/(0,4·n_d + n_v). Non ha effetto sulle vasche.

### 4.2 Schema del sistema ACS e richiesta al generatore (§7.1, p. 135-137)

Per un sistema dedicato a un'unica utenza (7.4):

```
Q_W,g,out = Q_NW + (Q_W,e,ls − k_W,e·W_W,e) + (Q_W,d,ls − k_W,d·W_W,d)
          + (Q_W,s,ls − k_W,s·W_W,s) + Σ_j (Q_W,g-s,ls − k_W,g-s·W_W,g-s)_j
```

Ausiliari (7.8): W_W,ds = W_W,e + W_W,d + W_W,s + W_W,G-S + W_W,a. Il generatore è escluso.

### 4.3 Erogazione (§7.3, p. 138-139)

- η_e,W = **1** sempre (p. 139), quindi Q_W,e,ls = 0 (7.9).
- W_W,e = Q_NW/η_eW,el con η_eW,el = 1: vale **solo** per erogatori o riscaldatori istantanei elettrici (7.10).
  In quel caso k_W,e = 1, altrimenti 0.
- Le perdite di erogazione **non sono recuperabili**: f_R,W,e = 0 (7.12).

### 4.4 Distribuzione (§7.4, p. 140-145)

- Q_W,d,out = Q_NW + Q_W,e,ls − k_W,e·W_W,e (7.13).
- **Metodo forfettario** (solo per la certificazione di singole unità immobiliari con generatore dedicato, senza
  ricircolo e senza circuito G-S) (7.18)-(7.19): Q_W,d,ls = Q_W,d,out · f_l,W,d; Q_Z,rvd,d = f_R,W,d · Q_W,d,L.
  **Prospetto 7.I** (fonte UNI/TS 11300-2:2014):

| Tipologia del sistema | f_l,W,d | f_R,W,d |
|---|---|---|
| Installato prima della L. 373/76 | 0,12 | 0,5 |
| Dopo la L. 373/76, rete solo parzialmente in ambiente climatizzato | 0,08 | 0,5 |
| Dopo la L. 373/76, rete totalmente in ambiente climatizzato | 0,08 | 0,9 |

- **Metodo analitico** della rete alle utenze (7.20)-(7.21), con perdita "a svuotamento" del contenuto dei tubi:
  Q_W,du,ls,i = L_i · (π·d_int,i²/4) · ρ_w c_w · (θ_w,avg − θ_a,i) · n_w,du · N.
  - ρ_w c_w = 4 168 600 J/(m³K);
  - n_w,du = **3** cicli al giorno;
  - θ_w,avg dal **Prospetto 7.II**: rete alle utenze **48 °C**, ricircolo **48 °C**, rete accumulo-generatore **70 °C**
    (per un'erogazione a 40 °C);
  - θ_a dal Prospetto J.I (sez. 5.5).
  - Unità di misura: la (7.21) dà J se ρc è in J/(m³K). Serve la divisione per 3,6·10⁶ per ottenere kWh, che il testo
    non esplicita **[AMB-20]**.
- **Ricircolo** (7.23)-(7.26). Di norma si calcola in dettaglio (App. J). In certificazione: Q_W,dr,ls = (L_V + L_S)·φ_r·Δt,
  con **φ_r = 40 W/m**. Le lunghezze convenzionali vengono dal Prospetto 7.III (EN 15316-3-2; area media di 80 m², tratto
  medio di 6 m), letto come: L_V = 2·L_B + 0,0125·L_B·B_B; L_S = 0,075·L_B·B_B·n_f·h_f; L_SL = 0,075·L_B·B_B·n_f
  **[AMB-21]**.
  - W_W,dr = Σ W_i · F_C · Δt, con F_C = 0,5 con timer, 0,8 con controllo in temperatura, 1 senza controllo (7.25).
  - k_W,dr = 0,85.
  - Recupero: Q_Z,rvd,dr = Q_d,ls,rvd dalla (J.3).

### 4.5 Accumulo non integrato nel generatore (§7.5, p. 145-148)

```
Q_W,s,ls = K_boll · (θ_s − θ_a) · Δt        θ_s = 60 °C                     (7.31)
K_boll   = Q_test / (0,024 · (θ_test,s − θ_test,a))   se il costruttore fornisce Q_test [kWh/giorno]   (7.32)
Q_W,s,ls = (λ_s/d_s) · S_s · (θ_s − θ_a) · Δt   (certificazione senza dati)    (7.33)
Q_Z,rvd,s = f_R,W,s · Q_W,s,L   con f_R,W,s = 1 se in ambiente climatizzato, altrimenti 0     (7.30)
```

- k_W,s = 1. Le resistenze di backup, se presenti: W_W,s = f_W,el · Q_W,s,in, con f_W,el = 1 se la resistenza è l'unica
  fonte, 0 se il generatore è condiviso con il riscaldamento (7.35)-(7.37).
- **Prospetto 7.IV - θ_a del locale dell'accumulo**:

| Tipo di ambiente | θ_a |
|---|---|
| Ambiente climatizzato | θ dell'ambiente climatizzato |
| Ambiente non climatizzato | Calcolata con l'Appendice A |
| Centrale termica (non adiacente a locali non climatizzati) | θ_e media mensile + 5 °C |
| Esterno | θ_e media mensile |

### 4.6 Circuito accumulo-generatore G-S (§7.6, p. 148-151)

- Q_W,g-s,out = Q_W,s,in (7.38). Con solare: f_RP,sol = FS e f_RP,alt = 1 − FS (7.40).
- Perdite:
  - distanza ≤ 5 m con tubi isolati: 0;
  - distanza ≤ 5 m con tubi non isolati: calcolo con l'App. J (θ = 70 °C);
  - distanza > 5 m: App. J.
- W_W,g-s = Σ W_j · Δt · FC_gw, con FC_gw dalla (7.47). In forma chiusa (7.48).

### 4.7 Recuperi ACS verso la zona (§7.8, p. 152-153, e §2.6)

Q_Z,rvd = Q_Z,rvd,d + Q_Z,rvd,s + Q_Z,rvd,g-s + Q_Z,rvd,g (7.50). Si sottrae al fabbisogno di riscaldamento:
Q*_NH,adj = Q_NH,adj − Q_Z,rvd (8.1). Si somma a quello di raffrescamento (2.60). Il valore è **sempre ≥ 0**, anche
in estate (p. 41).

### 4.8 Generatori per sola ACS (§11.8.1, p. 284-285)

Scaldacqua autonomi per una singola unità immobiliare (11.89): Q_W,g,L = (1/ε_gW − 1)·Q_W,g,out, con ε_gW costante
tutto l'anno. **Prospetto 11.V** (usare solo in mancanza di dati del costruttore):

| Apparecchio | Versione | η_N | ε_gW |
|---|---|---|---|
| Gas istantaneo per sola ACS | Tipo B con pilota permanente | 0,75 | 0,45 |
| Gas istantaneo per sola ACS | Tipo B senza pilota | 0,85 | 0,77 |
| Gas istantaneo per sola ACS | Tipo C senza pilota | 0,88 | 0,80 |
| Gas ad accumulo per sola ACS | Tipo B con pilota permanente | 0,75 | 0,40 |
| Gas ad accumulo per sola ACS | Tipo B senza pilota | 0,85 | 0,72 |
| Gas ad accumulo per sola ACS | Tipo C senza pilota | 0,88 | 0,75 |
| Bollitore elettrico ad accumulo | - | 0,95 | 0,75 |
| Bollitore ad accumulo a fuoco diretto | A camera aperta | 0,84 | 0,70 |
| Bollitore ad accumulo a fuoco diretto | A condensazione | 0.98 | 0,90 |

Questi ε_gW **includono già la perdita di accumulo** (circa 10 %): in questo caso Q_W,s,ls non va sommata nella (7.4).
Il bollitore elettrico va contato come fabbisogno **elettrico**. Recupero verso la zona (11.87):
Q_Z,RL,g = f_R,W,g · (Q_W,g,L · f_pr).

- **Prospetto 11.III - f_R,W,g**: all'aperto 0; in locale non riscaldato 0,7; entro lo spazio riscaldato 1.
- **Prospetto 11.IV - f_pr**: combustibile con bruciatore atmosferico 0,50; bruciatore ad aria soffiata 0,75;
  energia elettrica 1.

Generatori combinati riscaldamento + ACS (§11.5.3, p. 279-280):

- **produzione istantanea**: si dà priorità all'ACS. FC_W = Q_W,gn,out/(Φ_W,N·Δt) (11.75);
  Δt_gn,W = FC_W·Δt (11.76); Δt_gn,H = Δt − Δt_gn,W (11.77); FC_H = Q_H,gn,out/(Φ_H,N·Δt_gn,H) (11.78).
  Le perdite si calcolano separatamente sui due intervalli (11.79)-(11.81);
- **con accumulo**: nei mesi con riscaldamento si somma la richiesta H + W; negli altri mesi si calcola solo la W.

---

## 5. Impianto di riscaldamento (Cap. 8, §11.1-11.8, App. J)

### 5.1 Schema generale e bilancio del sottosistema (§2.5, §8.1-8.2)

Ogni sottosistema Y del servizio X (servizio "caldo", caso a) (2.39)-(2.49):

```
Q_X,Y,in = Q_X,Y,out + Q_X,Y,ls − Q_X,Y,aux,rvd        Q_X,Y,aux,rvd = k_X,Y · W_X,Y
con rendimento precalcolato:  Q_X,Y,ls,net = (1/η_X,Y − 1) · Q_X,Y,out      (2.48)
```

Per il raffrescamento (caso b) le perdite diventano guadagni (Q_thg) e la quota recuperata degli ausiliari **si somma**
alla richiesta (2.40), (2.44).

Richiesta al generatore per un'unità con solo riscaldamento idronico (8.16):

```
Q_H,g,out = Q*_NH,adj + (Q_H,e,ls − k_H,e·W_H,e) + (Q_H,d,ls − k_H,d·W_H,d)
          + (Q_H,s,ls − k_H,s·W_H,s) + (Q_H,g-s,ls − k_H,g-s·W_H,g-s)
Q*_NH,adj = Q_NH,adj − Q_Z,rvd                                         (8.1)
W_H,ds    = W_H,e + W_H,d + W_H,s + W_H,g-s   (generazione esclusa)    (8.25)
```

Con più impianti nella stessa zona:

- in parallelo: f_i,j = Φ_N,i,j,Tot / Σ_j Φ_N,i,j,Tot (8.2), cioè le potenze di progetto dei terminali;
- in sequenza: (8.3);
- misto aria primaria + idronico: (8.4)-(8.5).

Fattore di carico dell'emissione (8.7)-(8.8): FC_e,i,j = Φ_av/Φ_N,Tot, con Φ_av = Q*_NH,adj,i,j/Δt.

**Emettitori elettrici** (§8.4.6): Q_H,e,in = 0 e W_H,e = Q*_NH,adj + Q_H,e,ls (8.37). Con un generatore d'aria calda
a effetto Joule, l'energia si somma all'ausiliario (p. 175, nota 2).

**Split e sistemi autonomi d'ambiente** (p. 156): esistono solo emissione e generazione. In certificazione gli ambienti
serviti si trattano come un'unica zona, servita da un'unica macchina. La macchina ha come potenza nominale la somma
delle potenze e come prestazione quella della **macchina peggiore**. Gli ambienti senza split si considerano non
climatizzati (per il servizio C).

### 5.2 Emissione e regolazione (§8.4, p. 168-177)

```
Q_H,e,ls = (1/η_eH − 1) · Q*_NH,adj                  (8.27)
η_eH     = 1 / ( 1/η_ee + 1/η_c − 1 )                (8.29)
φ_t      = Q*_NH,adj / (V_L · Δt)   [W/m³]            (8.30)   V_L = volume LORDO riscaldato della zona
```

**Differenza rispetto alla UNI/TS 11300-2.** Emissione e regolazione non sono due rendimenti in cascata: si combinano
**in un unico rendimento con la (8.29)** e si applicano alla stessa base. Il testo della (8.30) chiama Q "annuo" ma usa
Δt mensile, e la nota a) del Prospetto 8.I parla di "medio stagionale" **[AMB-22]**.

**Prospetto 8.I - η_ee, locali con altezza < 4 m** (UNI/TS 11300-2:2014):

| Terminale | φ_t < 4 W/m³ | 4-10 | > 10 |
|---|---|---|---|
| Radiatori su parete esterna isolata (*) | 0,98 | 0,97 | 0,95 |
| Radiatori su parete interna | 0,96 | 0,95 | 0,92 |
| Ventilconvettori (**) (acqua media a 45 °C) | 0,96 | 0,95 | 0,94 |
| Termoconvettori | 0,94 | 0,93 | 0,92 |
| Bocchette in sistemi ad aria calda (***) | 0,94 | 0,92 | 0,90 |
| Riscaldatori ad infrarossi | 0,99 | 0,98 | 0,97 |
| Pannelli annegati a pavimento | 0,99 | 0,98 | 0,97 |
| Pannelli annegati a soffitto | 0,97 | 0,95 | 0,93 |
| Pannelli a parete | 0,97 | 0,95 | 0,93 |

(*) Valori per mandata ≤ 55 °C. A 85 °C il rendimento scende di 0,02; tra 55 e 85 °C si interpola. Con parete
riflettente +0,01. Con parete esterna non isolata (U > 0,8 W/m²K) −0,04.
(**) I consumi elettrici non sono compresi e si calcolano a parte. Il rendimento tiene già conto del recupero
dell'energia elettrica.
(***) Per l'aria calda valgono le condizioni: griglie di ripresa a non più di 2,00 m dal pavimento, diffusori
dimensionati correttamente, generatore adeguato, buona tenuta dell'involucro.

**Prospetto 8.II - η_ee, locali con altezza > 4 m.** Colonne: φ_t < 4, 4-10, > 10; ciascuna per altezza 6 / 10 / 14 m.

| Terminale | <4: 6 | 10 | 14 | 4-10: 6 | 10 | 14 | >10: 6 | 10 | 14 |
|---|---|---|---|---|---|---|---|---|---|
| Radiatori su parete esterna isolata | 0,96 | 0,94 | 0,92 | 0,95 | 0,93 | 0,91 | 0,93 | 0,91 | 0,89 |
| Radiatori su parete interna | 0,94 | 0,92 | 0,90 | 0,93 | 0,91 | 0,89 | 0,90 | 0,88 | 0,86 |
| Ventilconvettori (acqua a 45 °C) | 0,94 | 0,92 | 0,90 | 0,93 | 0,91 | 0,89 | 0,92 | 0,90 | 0,88 |
| Generatore d'aria calda singolo a basamento o pensile | 0,97 | 0,96 | 0,95 | 0,95 | 0,94 | 0,93 | 0,93 | 0,92 | 0,91 |
| Aerotermi ad acqua | 0,96 | 0,95 | 0,94 | 0,94 | 0,93 | 0,92 | 0,92 | 0,91 | 0,90 |
| Generatore d'aria calda pensile a condensazione | 0,98 | 0,97 | 0,96 | 0,96 | 0,95 | 0,94 | 0,94 | 0,93 | 0,92 |
| Bocchette in sistemi ad aria calda | 0,97 | 0,96 | 0,95 | 0,95 | 0,94 | 0,93 | 0,93 | 0,92 | 0,91 |
| Strisce radianti ad acqua, a vapore, a fuoco diretto | 0,99 | 0,98 | 0,97 | 0,97 | 0,97 | 0,96 | 0,96 | 0,96 | 0,95 |
| Riscaldatori ad infrarossi | 0,98 | 0,97 | 0,96 | 0,96 | 0,96 | 0,95 | 0,95 | 0,95 | 0,94 |
| Pannelli a pavimento annegati | 0,98 | 0,97 | 0,96 | 0,96 | 0,96 | 0,95 | 0,95 | 0,95 | 0,95 |
| Pannelli a pavimento (isolati) | 0,99 | 0,98 | 0,97 | 0,97 | 0,97 | 0,96 | 0,96 | 0,96 | 0,95 |

Se le condizioni del Prospetto 8.III (corretta installazione per locali > 4 m) non sono rispettate, si sottrae **0,1**
oppure si segue il calcolo analitico del §8.4.3.

**Pannelli annegati in strutture disperdenti** (8.31)-(8.33): η_eeH,cor = η_eeH·f_emb, con
f_emb = Σ(f_j·Φ_j)/ΣΦ_j e f_j = U_int/(U_int + U_est).

**Prospetto 8.IV - η_c regolazione, riscaldamento** (UNI/TS 11300-2:2014). Colonne:

- A = bassa inerzia (radiatori, convettori, ventilconvettori, strisce radianti, aria calda);
- B = pannelli integrati nelle strutture e disaccoppiati termicamente;
- C = pannelli annegati nelle strutture e non disaccoppiati.

| Regolazione | Caratteristiche | A | B | C |
|---|---|---|---|---|
| Sola climatica (sonda esterna) | - | 1 − (0,6·η_GH,adj·γ_H,adj) | 0,98 − (0,6·η_GH,adj·γ_H,adj) | 0,94 − (0,6·η_GH,adj·γ_H,adj) |
| Solo di zona | On-off | 0,93 | 0,91 | 0,87 |
| Solo di zona | P banda 2 °C | 0,94 | 0,92 | 0,88 |
| Solo di zona | P banda 1 °C | 0,97 | 0,95 | 0,91 |
| Solo di zona | P banda 0,5 °C | 0,98 | 0,96 | 0,92 |
| Solo di zona | PI o PID | 0,99 | 0,97 | 0,93 |
| Solo per singolo ambiente | On-off | 0,94 | 0,92 | 0,88 |
| Solo per singolo ambiente | P banda 2 °C | 0,95 | 0,93 | 0,89 |
| Solo per singolo ambiente | P banda 1 °C | 0,98 | 0,97 | 0,95 |
| Solo per singolo ambiente | P banda 0,5 °C | 0,99 | 0,98 | 0,96 |
| Solo per singolo ambiente | PI o PID | 0,995 | 0,99 | 0,97 |
| Zona + climatica | On-off | 0,96 | 0,94 | 0,92 |
| Zona + climatica | P banda 2 °C | 0,96 | 0,95 | 0,93 |
| Zona + climatica | P banda 1 °C | 0,97 | 0,96 | 0,94 |
| Zona + climatica | P banda 0,5 °C | 0,98 | 0,97 | 0,95 |
| Zona + climatica | PI o PID | 0,995 | 0,98 | 0,96 |
| Singolo ambiente + climatica | On-off | 0,97 | 0,95 | 0,93 |
| Singolo ambiente + climatica | P banda 2 °C | 0,97 | 0,96 | 0,94 |
| Singolo ambiente + climatica | P banda 1 °C | 0,98 | 0,97 | 0,95 |
| Singolo ambiente + climatica | P banda 0,5 °C | 0,99 | 0,98 | 0,96 |
| Singolo ambiente + climatica | PI o PID | 0,995 | 0,99 | 0,97 |

Senza regolazione ambiente (solo termostato di caldaia) si usa "sola climatica" **meno 0,05**. Il testo precisa: "ai soli
fini di valutazione dei miglioramenti dell'efficienza energetica" **[AMB-23]**. Le valvole termostatiche corrispondono
a "singolo ambiente, P banda 2 °C" o "P banda 1 °C" secondo la UNI EN 215. Nella formula della climatica si usano
η_GH,adj e γ_H,adj **del mese**.

**Ausiliari dell'emissione** (8.34)-(8.35):

- ventilatore sempre acceso: W_H,e = Σ W_k·Δt;
- ventilatore che si arresta al raggiungimento della temperatura (ventilconvettori): W_H,e = Σ W_k·FC_e·Δt.

La quota di energia elettrica non recuperata non è recuperabile (nota 1). Nella distribuzione terziaria (8.38) k_H,e = 1.

**Prospetto 8.V - potenza elettrica dei terminali:**

- radiatori, convettori, strisce radianti, pannelli: nulla;
- bocchette e diffusori: compresi nella distribuzione dell'aria;
- ventilconvettori e convettori ventilati:

| Portata d'aria | Potenza [W] |
|---|---|
| fino a 200 m³/h | 40 |
| da 200 a 400 m³/h | 50 |
| da 400 a 600 m³/h | 60 |

- generatori d'aria calda non canalizzati (pensili, a basamento, roof top):

| Portata d'aria [m³/h] | Potenza [W] |
|---|---|
| 1500 | 90 |
| 2500 | 170 |
| 3000 | 250 |
| 4000 | 350 |
| 6000 | 700 |
| 8000 | 900 |

### 5.3 Distribuzione idronica (§8.5, p. 177-188)

Livelli: terziaria (d3, nella zona), secondaria (d2, verso la zona), primaria (d1).

- Si procede a ritroso: Q_d3,out = Q*_NH,adj + Q_e,ls − k_e·W_e (8.38); Q_d2,out = Q_d3,out + Q_d3,ls,net (8.40);
  Q_d1,out = Σ(Q_d2,out + Q_d2,ls,net) (8.43).
- **Metodo analitico** (App. J): Q_dx,ls,net = Q_d,ls − Q_d,ls,rvd − k·W, con k = 0,85 (8.39), (8.42), (8.44).
- **Metodo con rendimenti precalcolati** (8.45): Q_dx,ls,net = (1/η_dH − 1)·Q_dx,out, con **k = 0**. Vale solo per le
  tipologie residenziali dei prospetti. I rendimenti includono già i recuperi.
- Livelli di isolamento:
  - A: conforme al DPR 412/93;
  - B: discreto, protetto da uno strato di gesso, plastica o alluminio;
  - C: medio, con materiali non fissati stabilmente;
  - D: insufficiente, deteriorato o assente;
  - E: scadente o assente in impianti anteriori al DPR 412/93.

**Prospetto 8.VI - η_dH, impianti autonomi:**

| Caso | A | B | C | D | E |
|---|---|---|---|---|---|
| 1.1 Autonomo a piano intermedio (edificio condominiale, tubi interamente nella zona) | 0,99 | - | - | - | 0,99 |
| 1.2 Autonomo a piano terreno su locali non riscaldati o terreno, monotubo | 0,96 | - | - | - | 0,95 |
| 1.3 Autonomo a piano terreno su locali non riscaldati o terreno, collettori | 0,94 | - | - | - | 0,93 |
| 2.1 Edificio singolo (1 piano), tubazioni in vista nel cantinato | 0,964 | 0,95 | 0,92 | 0,873 | - |
| 2.2 Edificio singolo, incassate a pavimento, monotubo | 0,975 | 0,965 | 0,955 | 0,935 | - |
| 2.3 Edificio singolo, incassate a pavimento, collettori | 0,97 | 0,96 | 0,94 | 0,92 | - |

Per i casi 1.x sono esclusi l'appartamento su esterno o su pilotis, per i quali si usa il metodo analitico.

**Prospetto 8.VII - η_dH, impianti a zone alimentati da montanti** (la parte interna all'appartamento; le dispersioni del
montante si calcolano analiticamente e si ripartiscono sulle zone):

| Caso | A | E |
|---|---|---|
| 3.1 Piano intermedio | 0,99 | 0,99 |
| 3.2 Piano terreno su locali non riscaldati o terreno, monotubo | 0,96 | 0,95 |
| 3.3 Piano terreno su locali non riscaldati o terreno, collettori | 0,94 | 0,93 |

**Prospetto 8.VIII - η_dH, centralizzati a montanti con distribuzione orizzontale nel cantinato** (A/B/C/D =
isolamento della distribuzione orizzontale):

| Montanti | Piani | A | B | C | D |
|---|---|---|---|---|---|
| 4.1 Non isolati, nell'intercapedine dei muri esterni | 1 | 0,964 | 0,950 | 0,920 | 0,873 |
| | 2 | 0,933 | 0,924 | 0,901 | 0,866 |
| | 3 | 0,929 | 0,923 | 0,906 | 0,879 |
| | ≥4 | 0,928 | 0,923 | 0,910 | 0,890 |
| 4.2 Non isolati, in traccia nel lato interno delle pareti esterne | 1 | 0,966 | 0,952 | 0,922 | 0,875 |
| | 2 | 0,938 | 0,929 | 0,906 | 0,871 |
| | 3 | 0,937 | 0,931 | 0,914 | 0,887 |
| | ≥4 | 0,938 | 0,933 | 0,920 | 0,900 |
| 4.3 Non isolati, in traccia nelle pareti interne (vale anche con cappotto) | 1 | 0,970 | 0,958 | 0,932 | 0,889 |
| | 2 | 0,985 | 0,979 | 0,966 | 0,944 |
| | 3 | 0,990 | 0,986 | 0,977 | 0,963 |
| | ≥4 | 0,990 | 0,990 | 0,983 | 0,972 |

I prospetti valgono per 80/60 °C a temperatura variabile. Per altre temperature di progetto (8.46):
**η_dH,c = 1 − (1 − η_dH)·C**, con C dal Prospetto 8.IX. C si basa su tubi in ambiente a 12,5 °C medi stagionali;
tra i valori si interpola.

**Prospetto 8.IX - fattore di correzione C:**

| Mandata/ritorno di progetto [°C] | Δt di progetto [°C] | θ media stagionale [°C] | C | Tipologia indicativa |
|---|---|---|---|---|
| 80-60 | 50 | 37,3 | 1,00 | Radiatori |
| - | 45 | 36,0 | 0,94 | Radiatori |
| 70-55 | 42,5 | 35,3 | 0,92 | Radiatori |
| - | 40 | 34,7 | 0,89 | Radiatori |
| - | 35 | 33,0 | 0,82 | Radiatori |
| 55-45 | 30 | 31,4 | 0,77 | Ventilconvettori |
| - | 25 | 29,8 | 0,69 | Ventilconvettori |
| - | 20 | 27,9 | 0,62 | Pannelli radianti |
| - | 15 | 26,1 | 0,55 | Pannelli radianti |
| 35-30 | 12,5 | 25,1 | 0,51 | Pannelli radianti |
| - | 10 | 24,2 | 0,47 | Pannelli radianti |

(La colonna "Δt di progetto" è la differenza tra la temperatura media dell'acqua e l'ambiente; l'attribuzione delle
tipologie alle righe è indicativa, come nel testo.)

**Pompe** (8.47)-(8.49):

- W = ΣW_k·FC_e·Δt se la pompa è comandata dalla richiesta dell'utenza;
- W = ΣW_k·FC_g·Δt se è comandata dal generatore;
- W = ΣW_k·Δt se è sempre accesa durante il servizio.

Senza dato di targa (8.50)-(8.51): W_po = Φ_idr/η_po, con Φ_idr = ρ·V·H/367,2 [W] (V in dm³/h, H in m). Per η_po si usa il
**Prospetto 8.X**, ricostruito come η = Φ_idr^0,50/25,46 (Φ < 50 W), Φ_idr^0,26/10,52 (50 ≤ Φ < 250 W),
Φ_idr^0,40/26,23 (250 ≤ Φ < 1000 W) **[AMB-24]**. Da 1000 W in su η = 0,6.

### 5.4 Accumulo del riscaldamento e circuito G-S (§8.7-8.8, p. 199-206)

- Q_X,s,ls,k = K_acc·(θ_s − θ_a)·Δt (8.90). K_acc = Q_test/(0,024·(θ_test,s − θ_test,a)) (8.91). Senza dati:
  (λ_s/d_s)·S_s·(θ_s − θ_a)·Δt (8.92).
- θ_a dal Prospetto 7.IV. θ_s, temperatura media dell'accumulo del riscaldamento, **non è fissata** nel §8.7 **[AMB-25]**.
- Q_X,s,in = Q_X,s,out + Q_X,s,ls (8.93). Pompa del secondario verso uno scambiatore esterno (8.95)-(8.99): k = 0,85.
- Circuito G-S: stesse regole della sez. 4.6. Con solare f_R,sol = FS_X (8.101). Ausiliari (8.107)-(8.109): FC_gh dalla
  (8.108) e k = 0,85.

### 5.5 Temperature di rete e perdite analitiche (Appendice J, p. 519-552)

- Perdita di un tratto (J.1): Q_d,ls = Σ_i L_i·Ψ_i·(θ_w,avg − θ_a,i)·Δt, con θ_w,avg = (θ_f + θ_r)/2 (J.13).
- Recuperabile (J.2): Q_rbl = Σ Q_i·k_rbl,i. Recuperata (J.3): Q_rvd = Σ Q_i·k_rbl,i·k_r,i, con **k_r = 0,95** se c'è
  regolazione di zona o per singolo ambiente, **0,8** con la sola climatica e negli altri casi.

*Prospetto J.I - θ_a delle tubazioni:*

| Posizione della tubazione | θ_a |
|---|---|
| In ambienti climatizzati | θ dell'ambiente climatizzato |
| Incassata in struttura isolata dell'involucro, all'interno dello strato isolante principale | θ dell'ambiente climatizzato |
| Incassata in struttura isolata dell'involucro, all'esterno dello strato isolante principale | θ_e media mensile |
| Incassata in struttura non isolata dell'involucro | θ_e media mensile |
| Incassata in struttura interna all'involucro | θ dell'ambiente climatizzato |
| All'esterno | θ_e media mensile |
| In ambiente non climatizzato adiacente a climatizzati | θ_u (App. A) |
| In altri ambienti non climatizzati | θ_u (App. A) |
| Interrata (profondità < 1 m) | θ_e media mensile |
| In centrale termica (non adiacente a locali non climatizzati) | θ_e media mensile + 5 °C |

*Prospetto J.II - k_rbl:*

| Posizione | k_rbl |
|---|---|
| In ambiente climatizzato | 1 |
| Incassata in struttura interna all'involucro | 0,95 |
| Incassata in struttura isolata dell'involucro, all'interno dello strato isolante principale | 0,95 |
| Incassata in struttura isolata dell'involucro, all'esterno dello strato isolante principale | 0,05 |
| Incassata in struttura non isolata dell'involucro | U_i/(U_e + U_i) |
| All'esterno dell'ambiente climatizzato | 0 |

- Ψ precalcolati (J.10)-(J.12), con d in mm:
  - tubi in aria isolati secondo il DPR 412: Ψ = 0,143 + 0,0018·d;
  - montanti in intercapedine con isolante al 50 %: Ψ = 0,19 + 0,0034·d;
  - tubi in strutture interne con isolante al 30 %: Ψ = 0,225 + 0,00532·d.
  - Tubi non isolati all'esterno: Ψ = 16,5·π·d (J.4).
  - Staffaggi: +10 % della lunghezza.
  - Singolarità in centrale (Prospetto J.IV), come lunghezza equivalente non isolata: pompa 0,3 m, valvola miscelatrice
    0,6 m, flangia o bocchettone 0,1 m.
- **Temperatura media dei terminali** (J.47): θ_em,av = θ_a + (Φ_em,av/Φ_em,nom)^(1/n) · Δθ_nom,
  con Φ_em,av = Q*_NH,adj/(η_eH·Δt_em) (J.43) e Δt_em = Δt.
  - Esponente n (Prospetto J.V): radiatori 1,30; termoconvettori 1,40; pannelli radianti 1,10; aerotermi e
    ventilconvettori 1,00; batterie alettate 1,00.
  - Mandata e ritorno dipendono dalla regolazione (J.48)-(J.55). Con portata costante e mandata variabile:
    θ_f = θ_em,av + Φ/(2ṁc) e θ_r = θ_em,av − Φ/(2ṁc).
  - Con climatica senza profilo noto (J.52): θ_f = max(θ_em,av + Δθ_fr/2 ; …), con Δθ_em,fr = **20 K** con valvole
    termostatiche e **10 K** negli altri casi (J.55).
  - Primaria (J.23)-(J.24): mandata = max delle secondarie + **5 °C**.
  - Queste temperature alimentano sia le perdite di rete sia θ_gn della caldaia e θ_h della pompa di calore.

### 5.6 Ripartizione tra centrali e generatori (§11.1-11.5)

- Centrale termica integrata: Q_HS,out = Q_H + Q_HA + Q_W + Q_HCA + Q_CS (11.3). I fattori di ripartizione
  f_HS,S = Q_HS,S,out/Q_HS,out (11.8) si applicano ai vettori in ingresso (11.31).
- Generatore unico (11.50)-(11.52): Q_gn,out = Q_g,out − k_pf·W_pf, con **k_pf = 0,8**; Φ_gn,out,av = Q_gn,out/Δt_gn;
  **FC = Φ_gn,out,av/Φ_gn,out,N**.
- Più generatori di soli combustibili fossili (11.55)-(11.56):
  - in parallelo puro: FC uguale per tutti = Q_net/(ΣΦ_N·Δt);
  - in cascata: si riempiono in ordine.
- **Generatori misti (priorità, Prospetto 11.II)** (p. 274), in mancanza di una priorità di progetto e solo per la
  certificazione:

| Priorità | Generatore | Produzione |
|---|---|---|
| 1 | Solare termico | Termica |
| 2 | Cogeneratore (b) | Elettrica e termica cogenerata |
| 3 | Caldaia a biomassa | Termica |
| 4 | Pompa di calore | Termica |
| 5 | Generatori di calore a combustibili fossili | Termica |

(a) Con teleriscaldamento e solare, il solare ha priorità 1. (b) Solo cogeneratori a inseguimento termico.

Procedura (11.61)-(11.74):

1. si calcola la frazione solare SF per servizio;
2. si calcola la richiesta residua Q_net·(1 − SF);
3. per k crescente si assegna FC_k = (Φ_tot,av − Σ_{j<k} Φ_N,j)/Φ_N,k (11.72), limitato tra 0 e 1 e con le condizioni
   di operabilità OP e di limite FC_LIM (biomassa, pompa di calore sotto θ di cut-off);
4. se il generatore non è operabile, la sua quota passa al successivo (funzionamento "alternato").

- Perdite della centrale (11.82)-(11.84): Q_g,L = Σ Q_gn,ls + (1 − k)·W_pf, con k = 0,8. Le perdite di generazione sono
  recuperabili dalla zona **solo per le centrali ACS** (11.87).
- Ausiliari di generazione (11.88).

### 5.7 Caldaie a combustibili fossili (§11.8.2, p. 285-296)

Due strade:

- **(1) rendimenti precalcolati**, ammessi **solo per la certificazione energetica** (p. 286);
- **(2) metodo di calcolo** (§11.8.2.2-11.8.2.9) oppure modello dettagliato (§11.8.3, p. 297-311). Per la Legge 10 serve
  il calcolo.

**(1) Precalcolati** (11.90)-(11.92): η_gH = η_base + F1 + … + F7 [%]. Q_gn,ls = (1/η_gH − 1)·Q_gn,out e
Q_gn,in = Q_gn,out/η_gH. Significato dei fattori:

- F1 = rapporto tra la potenza installata e la potenza di progetto UNI EN 12831 (per i modulanti si usa la potenza
  minima regolata; oltre il massimo tabulato si prende l'ultimo valore; tra i valori si interpola);
- F2 = installazione all'esterno;
- F3 = camino più alto di 10 m;
- F4 = temperatura media di caldaia > 65 °C in condizioni di progetto;
- F5 = generatore monostadio;
- F6 = camino > 10 m senza chiusura dell'aria comburente all'arresto;
- F7 = temperatura di ritorno nel mese più freddo.

L'intestazione delle colonne nel testo estratto è parzialmente persa. Le tabelle seguenti sono la lettura più
plausibile **[AMB-26]**:

| Prospetto | Tipo | η_base | F1 (rapporto → valore) | F2 | F3 | F4 | F5 | F6 | F7 |
|---|---|---|---|---|---|---|---|---|---|
| 11.VI | Atmosferico tipo B, ** (2 stelle) | 90 (84 se ante 1996; 88 se *) | 1 → 0; 2 → −2; 4 → −6 | −9 | −2 | −2 | - | - | - |
| 11.VII | Camera stagna tipo C per autonomi, *** | 93 | 1 → 0; 2 → −2; 4 → −5 | −4 | - | −1 | - | - | - |
| 11.VIII | Gas/gasolio ad aria soffiata o premiscelato, modulante, ** | 90 (86 ante 1996; 88 se *) | 1 → 0; 1,25 → −1; 1,5 → −2 | −1 | - | −1 | −1 | −2 | - |
| 11.IX | Condensazione ****, ΔT fumi-ritorno < 12 °C | 104 | 1 → 0; 1,25 → 0; 1,5 → 0 | −1 | - | - | −3 | - | 40 → 0; 50 → −4; 60 → −6; >60 → −7 |
| 11.IX | Condensazione ****, ΔT da 12 a 24 °C | 101 | 0; 0; 0 | −1 | - | - | −3 | - | 0; −2; −3; −4 |
| 11.IX | Condensazione ****, ΔT > 24 °C (nel testo "24 °C") | 99 | 0; 0; 0 | −1 | - | - | −2 | - | 0; −1; −2; −3 |

Note:

- 11.VI: base riferita a una caldaia **, sovradimensionamento 1 rispetto al minimo di modulazione, installazione
  interna, camino < 10 m, mandata di progetto < 65 °C.
- 11.VIII: sovradimensionamento riferito alla potenza nominale, installazione in centrale termica, con chiusura dell'aria
  all'arresto.
- 11.IX: caldaia a condensazione con accumulo installata all'esterno: F2 = −3.

**(2) Metodo di calcolo** (EN 15316-4-1 adattata):

```
η_gn,N,cor = η_gn,N + f_cor,N·(θ_gn,test,N − θ_gn,N)                 (11.93)   [%]
η_gn,N     = A + B·log10(Φ_gn,out,N/1000)   (Φ max 400.000 W)        (11.94)
f_cor,N    = [η(θ_test,N) − η(θ_test,N,add)]/(θ_test,N,add − θ_test,N)   (11.95)
Φ_ls,N,cor = (100 − η_gn,N,cor)/η_gn,N,cor · Φ_gn,out,N               (11.96)
η_gn,I,cor = η_gn,I + f_cor,I·(θ_gn,test,I − θ_gn,I)                  (11.97)
η_gn,I     = C + D·log10(Φ_gn,out,N/1000)                             (11.98)  (f_f = 1,05 per condensazione a gasolio, 1 altrimenti; posizione di f_f nella formula illeggibile [AMB-27])
Φ_gn,out,I = 0,3·Φ_gn,out,N  (combustibili liquidi e gassosi)
Φ_ls,I,cor = (100 − η_gn,I,cor)/η_gn,I,cor · Φ_gn,out,I               (11.100)
Φ_ls,S     = Φ_gn,out,N · (E/100) · (Φ_gn,out,N/1000)^F               (11.101)
Φ_ls,S,cor = Φ_ls,S · ((θ_gn,av − θ_a,gn)/(θ_gn,test − θ_a,test))^1,25   (11.102)  θ_a,test = 20 °C
se 0 ≤ Φ_av ≤ Φ_I:     Φ_ls,av = Φ_ls,S,cor + (Φ_ls,I,cor − Φ_ls,S,cor)·Φ_av/Φ_I                    (11.103)
se Φ_I < Φ_av ≤ Φ_N:   Φ_ls,av = Φ_ls,I,cor + (Φ_ls,N,cor − Φ_ls,I,cor)·(Φ_av − Φ_I)/(Φ_N − Φ_I)   (11.104)
Q_gn,ls = Φ_ls,av · Δt                                                (11.105)
W_aux,x = G + H·(Φ_gn,out,N/1000)^n     (x = N, I, S; Prosp. 11.XV)    (11.109)
W_gn    = W_aux,av·Δt, W_aux,av interpolata come le perdite            (11.106)-(11.108)
Q_aux,ls,rbl = 0,25·W_gn·(1 − b_gn)                                   (11.110)
Q_env,ls,rbl = (1 − b_gn)·p_gn,env·Φ_ls,S,cor·Δt                       (11.111)  p_gn,env: atmosferico 0,50; aria soffiata 0,75
Q_gn,in = Q_gn,out + Q_gn,ls − Q_gn,ls,rh      (Q_gn,ls,rh = Q_aux,rbl + Q_env,rbl)   (11.112)-(11.114)
```

θ_gn,N e θ_gn,I: temperatura media dell'acqua nel generatore nelle condizioni effettive (per la condensazione, la
temperatura di **ritorno**). Si ricavano dalle temperature di rete (App. J, §J.1.3.2, circuito G-S).

**Prospetto 11.X - parametri A, B, C, D [%] e θ_gn,w,min** (adattato da UNI EN 15316-4-1:2008):

| Tipo | Anno | A | B | C | D | θ_w,min |
|---|---|---|---|---|---|---|
| Combustibile fossile solido | prima 1978 | 78,0 | 2,0 | 72,0 | 3,0 | 50 °C |
| | 1978-1994 | 80,0 | 2,0 | 75,0 | 3,0 | 50 °C |
| | dopo 1994 | 81,0 | 2,0 | 77,0 | 3,0 | 50 °C |
| Convenzionali: atmosferici a gas | prima 1978 | 79,5 | 2,0 | 76,0 | 3,0 | 50 °C |
| | 1978-1994 | 82,5 | 2,0 | 78,0 | 3,0 | 50 °C |
| | dopo 1994 | 85,0 | 2,0 | 81,5 | 3,0 | 50 °C |
| Convenzionali: bruciatore a tiraggio forzato | prima 1978 | 80,0 | 2,0 | 75,0 | 3,0 | 50 °C |
| | 1978-1986 | 82,0 | 2,0 | 77,5 | 3,0 | 50 °C |
| | 1987-1994 | 84,0 | 2,0 | 80,0 | 3,0 | 50 °C |
| | dopo 1994 | 85,0 | 2,0 | 81,5 | 3,0 | 50 °C |
| Bassa temperatura: atmosferici a gas | 1978-1994 | 85,5 | 1,5 | 86,0 | 1,5 | 35 °C |
| | dopo 1994 | 88,5 | 1,5 | 89,0 | 1,5 | 35 °C |
| Bassa temperatura: tiraggio forzato | prima 1987 | 84,0 | 1,5 | 82,0 | 1,5 | 35 °C |
| | 1987-1994 | 86,0 | 1,5 | 86,0 | 1,5 | 35 °C |
| | dopo 1994 | 88,5 | 1,5 | 89,0 | 1,5 | 35 °C |
| Condensazione | prima 1987 | 89,0 | 1,0 | 95,0 | 1,0 | 20 °C |
| | 1987-1994 | 91,0 | 1,0 | 97,5 | 1,0 | 20 °C |
| | dopo 1994 | 92,0 | 1,0 | 98,0 | 1,0 | 20 °C |
| Condensazione ad alta prestazione (1) | dopo 1999 | 94,0 | 1,0 | 103 | 1,0 | 20 °C |

(1) Se si usano i valori dichiarati, il rendimento dichiarato deve essere non minore di quello calcolabile con questi
parametri.

**Prospetto 11.XI - pieno carico** (θ_test,N; f_cor,N [%/°C]): standard 70 °C, 0,04; bassa temperatura 70 °C, 0,04;
condensazione a gas 70 °C, 0,20; condensazione a gasolio 70 °C, 0,10.

**Prospetto 11.XII - carico intermedio** (θ_test,I; f_cor,I): standard 50 °C, 0,05; bassa temperatura 40 °C, 0,05;
condensazione (*) 30 °C, 0,20; condensazione a gasolio (*) 30 °C, 0,10. (*) Per la condensazione la prova usa il ritorno
a 30 °C, applicabile a una temperatura media di 35 °C.

**Prospetto 11.XIII - perdite a carico nullo, E [%] e F** (θ_gn,test = 70 °C):

| Tipo | Anno | E | F |
|---|---|---|---|
| Solido | prima 1978 | 12,5 | −0,28 |
| | 1978-1994 | 10,5 | −0,28 |
| | dopo 1994 | 8,0 | −0,28 |
| Convenzionali: atmosferici a gas | prima 1978 | 8,0 | −0,27 |
| | 1978-1994 | 7,0 | −0,3 |
| | dopo 1994 | 8,5 | −0,4 |
| Convenzionali: tiraggio forzato (olio/gas) | prima 1978 | 9,0 | −0,28 |
| | 1978-1994 | 7,5 | −0,31 |
| | dopo 1994 | 8,5 | −0,4 |
| Bassa temperatura: atmosferici a gas | fino al 1994 | 7,5 | −0,30 |
| | dopo 1994 | 6,5 | −0,35 |
| Bassa temperatura: combinati KSp (a) | dopo 1994 | 3,0 | 0,0 |
| Bassa temperatura: combinati DL (b) | dopo 1994 | 2,4 | 0,0 |
| Bassa temperatura: tiraggio forzato (olio/gas) | dopo 1994 | 8,0 | −0,33 |
| | dopo 1994 (seconda riga, stessa descrizione nel testo) | 5,0 | −0,35 |
| Condensazione (olio/gas) | fino al 1994 | 8,0 | −0,33 |
| | dopo 1994 | 4,8 | −0,35 |
| Condensazione: combinati KSp (a) | dopo 1994 | 3,0 | 0,0 |
| Condensazione: combinati DL (b) | dopo 1994 | 2,4 | 0,0 |

(a) KSp: combinati con produzione istantanea di ACS tramite un piccolo accumulo (2 < V < 10 l).
(b) DL: combinati con scambiatore (V < 2 l).
Nella riga "tiraggio forzato bassa temperatura" compaiono due righe "dopo 1994" con valori diversi **[AMB-28]**.

**Prospetto 11.XIV - b_gn e θ_a,gn:**

| Ubicazione | b_gn | θ_a,gn |
|---|---|---|
| All'aperto | 1 | θ_e media del mese |
| Centrale termica adiacente ad ambienti climatizzati | 0,3 | θ del locale non climatizzato (via b_tr,x) |
| Centrale termica non adiacente ad ambienti climatizzati | 0,3 | θ_e media mensile + 5 °C |
| Entro lo spazio riscaldato | 0 | 20 |

**Prospetto 11.XV - ausiliari: G, H, n**

| Tipologia | Potenza | G | H | n |
|---|---|---|---|---|
| Atmosferici a gas (standard e bassa temperatura) | N | 40 | 0,148 | 1 |
| | I | 40 | 0,148 | 1 |
| | S | 15 | 0 | 0 |
| Aria soffiata, combustibili liquidi e gassosi (standard, bassa temperatura, condensazione) | N | 0 | 45 | 0,48 |
| | I | 0 | 15 | 0,48 |
| | S | 15 | 0 | 0 |

### 5.8 Biomassa (§11.8.4, p. 311-320)

- Biocombustibili liquidi e gassosi: come le caldaie fossili, con vettore rinnovabile.
- Biomassa solida: precalcolati (11.164): η_gn = η_gn,base + F1…F7, con Q_gn,ls = (1/η_gn − 1)·Q_gn,out (11.160) e
  **k_aux·W_aux = 0**, perché gli ausiliari sono già inclusi (11.161). Q_gn,in = Q_gn,out/η_gn + Q_s,gn,ls,rvd (11.162).
  - η_gn,base = valore dichiarato, oppure il default:
    - 11.XXXII termocamini, termostufe e termocucine a caricamento manuale: **50 %**;
    - 11.XXXIII manuali aspirati o con ventilatore: **47 % + 6 % Log Pn**;
    - 11.XXXIV, 11.XXXV e 11.XXXVII a caricamento automatico: **75 %**;
    - 11.XXXVI caminetti, inserti e stufe manuali ad aria: **50 %**.
  - Fattori (con un serbatoio inerziale conforme alla EN 303-5 si pone F1 = 1):

| Prospetto | F1 | F2 | F3 | F4 | F5 | F6 | F7 |
|---|---|---|---|---|---|---|---|
| 11.XXXII (acqua, manuale) | 1 → 0; 2 → −2; 4 → −6 | - | −4 | - | - | - | - |
| 11.XXXIII (acqua, manuale con ventilatore) | 1 → 0; 2 → −2; 4 → −6 | −9 | −2 | −2 | - | - | - |
| 11.XXXIV (acqua, automatico) | 1 → 0; 1,5 → −1; 2 → −2 | −2 | - | −1 | −1 | −2 | - |
| 11.XXXV (acqua, automatico a condensazione) | 1 → 0; 1,5 → −1; 2 → −2 | −1 | - | - | −2 | −2 | 40 → 0; 50 → −3; 60 → −5; >60 → −6 |
| 11.XXXVI (aria, manuale) | 1 → 0; 2 → −2; 4 → −6 | - | −4 | - | - | - | - |
| 11.XXXVII (aria, automatico) | 1 → 0; 1,5 → −1; 2 → −2 | - | - | - | - | - | - |

  (Attribuzione delle colonne secondo le intestazioni estratte **[AMB-26]**.)

- **Quote massime da biomassa** (FC_gn ≤ FC_LIM, (11.158)):

| Prospetto | Tipo | Con accumulo | Senza accumulo |
|---|---|---|---|
| 11.XXIX (H + ACS, acqua) | Manuale, aria comburente a controllo manuale | 55 % | 40 % |
| | Manuale, aria comburente a controllo automatico | 75 % | 65 % |
| | Automatico, aria comburente a controllo automatico | 90 % | 90 % |
| 11.XXX (solo ACS, acqua) | Installato in ambiente | - | - |
| | In centrale termica, manuale | 50 % | - |
| | In centrale termica, automatico | 90 % | - |
| | Automatico con ventilatore a condensazione | 90 % | 0 |
| 11.XXXI (riscaldamento ad aria, affiancato a un impianto fossile con regolazione ambiente) | Manuale, aria a controllo manuale | - | 30 % |
| | Automatico, aria a controllo automatico | - | 50 % |

Senza regolazione individuale sui terminali dell'impianto fossile, la quota da biomassa (Prospetto 11.XXXI) è **0**.
Se l'edificio è servito solo dal generatore a biomassa ad aria, la quota è 100 %.

- Perdite dell'accumulo recuperate (11.165): Q = (1 − b_gs)·k_gs·Q_s,ls, con b_gs = 0 in ambiente climatizzato e 1
  fuori; k_gs = 1 per l'ACS e 0,8 per il riscaldamento. Valgono solo nella stagione di riscaldamento.
- Ausiliari (11.166)-(11.171): W = A + B·(Φ_N/1000)^n, con A, B, n dal Prospetto 11.XXXVIII (acqua) o 11.XXXIX (aria).
  Atmosferici ad acqua: N: 40 / 0,35 / 1; int: 20 / 0,1 / 1; off: 15 / 0 / 0. Con ventilatore: N: 0 / 45 / 0,48;
  int: 0 / 15 / 0,48; off: 15 / 0 / 0. Per l'aria gli atmosferici hanno tutti i parametri a 0.
  Se Φ_min è ignota: 0,7·Φ_N per il caricamento manuale, 0,2·Φ_N per l'automatico.
- Volume dell'accumulo se ignoto (11.172)-(11.173): automatico V = 0,025 l/W · Φ_des; manuale
  V = 0,015·Δt_gn·Φ_N·(1 − 0,3·Φ_des/Φ_min) **[AMB-29]**.

### 5.9 Effetto Joule, aria calda, teleriscaldamento (§11.8.5-11.8.7, p. 320-326)

- **Joule** (11.174): Q_gn,ls = Φ_N·P'_env·(θ_gn,av − θ_gn,int)/Δθ_test·(1 − k_gn,rh)·Δt_gn, con Δθ_test = 50 K se non
  dichiarato. Default del fattore di perdita (11.175): P'_env = 1,5 − 0,44·log10(Φ_N/1000) [%].
- **Aria calda a fuoco diretto** (11.176)-(11.178), Prospetto 11.XL (η_gH base; riduzione se installato all'esterno):

| Tipo | η_gH | Riduzione all'esterno |
|---|---|---|
| Gas o gasolio, aria soffiata o premiscelato, on-off | 90 | 3 |
| Gas a camera stagna con ventilatore, tipo B o C, on-off | 90 | 3 |
| Gas o gasolio, aria soffiata o premiscelato, bistadio o modulante | 93 | 2 |
| Gas a camera stagna, bistadio o modulazione aria-gas | 93 | 2 |
| Gas a condensazione, modulante aria-gas | 100 | 1 |

  W_gn = FC·Δt·ΣW_aux.
- **Teleriscaldamento** (sottostazione):
  - Q_gn,in = Q_gn,out + Q_gn,L (11.179), con Q_gn,out = Q_richiesta − Q_gn,L,rvd (11.180);
  - Q_gn,L = Φ_ss·P_ss,env/100·Δt (11.181), con P_ss,env = P'_ss,env·(θ_ss,w,avg − θ_a,ss)/(θ_ss,w,rif − θ_a,rif) (11.182)
    e P'_ss,env = C_2 − C_3·log10(Φ_ss/1000) (11.183), con C_2 = 2,24, C_3 = 0,57, θ_w,rif = 85 °C e θ_a,rif = 20 °C
    (Prospetto 11.XLI). Oltre 3 MW si usa il valore a 3 MW;
  - in alternativa, con K_ss dichiarato: Q_gn,L = K_ss·(θ_ss,w,avg − θ_a,ss)·Δt (11.184);
  - Prospetto 11.XLII (b_gss; θ_a,test; θ_a,ss): in centrale termica 0,3; 20; 15 °C. In ambiente climatizzato 0; 20; θ_i.
    All'esterno 1; 20; θ_e;
  - Prospetto 11.XLIII: rete ad acqua calda a bassa temperatura 70 °C; rete ad acqua surriscaldata 90 °C;
  - Q_rbl = 0,8·Q_gn,L; Q_rvd = (1 − b_gss)·Q_rbl, solo in stagione di riscaldamento (11.185)-(11.186);
  - W_gn = 0 (11.187).

### 5.10 Pompe di calore (§11.8.8, p. 326-366)

Metodo UNI/TS 11300-4 adattato. Vettore principale E_x: elettrico per le PdC a compressione (COP_el include gli
ausiliari di bordo), gas per le PdC ad assorbimento (GUE + AEF), termico per quelle ad assorbimento indiretto.

- **Intervallo** (Prospetto 11.XLVII):
  - **bin mensili** (bin di 1 K della temperatura esterna, dall'Allegato 1) per sorgente aria esterna, aria interna di
    recupero dipendente dal clima e pozzo in aria miscelata (espansione diretta);
  - **mese** per terreno, acqua, aria interna a temperatura indipendente dal clima, circuito idronico e accumulo ACS.
- **Temperature**:
  - θ_c = θ_fonte − Δθ_c,des, con Δθ_c,des = 5 K per acqua o terreno, 0 K per aria a scambio diretto, 10 K per aria a
    scambio indiretto (11.241);
  - terreno dall'Appendice K;
  - pozzo caldo idronico = temperatura media della distribuzione (App. J); pozzo ACS = **55 °C**;
  - aria interna a condensazione diretta = θ_i.
- **Limiti di funzionamento** (11.242)-(11.243): θ_OL ≤ θ_cut-off,min ≤ θ_c e θ_h ≤ θ_cut-off,max
  (per l'ACS default 55 °C; per H dal progetto, altrimenti il valore del fabbricante). Fuori dai limiti FC = 0 e la
  richiesta passa all'integrazione.
- **Richiesta**: Q_req = Q_gn,out − k_pe,c·W_pe,c (11.244), con k = 0,8. Stima non iterativa W_pe,c = W_pe,c·FC·Δt
  (11.245); si ricalcola se |FC − FC_stima| > 0,01 (11.246).
- **Distribuzione nei bin** per H (11.248)-(11.251): GH_bin = t_bin·max(0 ; θ_H,off − θ_bin), con **θ_H,off = 16 °C**;
  Q_req,bin = Q_req·GH_bin/ΣGH; Φ_req,bin = Q_req,bin/t_bin.
  Per l'ACS (11.252)-(11.254) si ripartisce sulle ore dei bin con θ_bin ≥ θ_W,cut-off, in proporzione a t_bin.
- **FC** = min(1 ; Φ_req/Φ_N(θ_h,θ_c)) (11.256) / (11.258). Nel servizio combinato ha priorità l'ACS:
  FC_H = 1 − FC_W come quota residua (11.260).
- **Prestazioni a pieno carico fuori dai punti dichiarati** (§11.8.8.13): interpolazione lineare delle potenze tra i punti
  dichiarati (11.302). Per il COP si interpola il **rendimento di secondo principio**
  η_II = COP·(θ_h − θ_c)/(θ_h + 273,15) (compressione, (11.294)) e poi COP = η_II·(θ_h + 273,15)/(θ_h − θ_c) (11.296).
  Estrapolazione ammessa **fino a 5 K** oltre l'ultimo punto, con η_II o Φ costanti (11.298)-(11.304).
  Punti di prova (Prospetto 11.XLV):
  - aria sorgente: −7 / 2 / 7 / 12 °C;
  - acqua sorgente: 5 / 10 / 15 °C;
  - terreno: −5 / 0 / 5 / 10 °C;
  - pozzo ad aria 20 °C; pozzo idronico 35 / 45 / 55 °C; pozzo ACS 45 / 55 °C.
  - PdC per sola ACS (Prospetto 11.XLVI): aria 7 / 15 / 20 / 35 °C, pozzo 55 °C.
- **Carico parziale** (§11.8.8.14): COP_PL = COP_N·f_COP(FC) (11.305).
  - On-off aria/aria, antigelo/aria, acqua/aria: f = 1 − C_d·(1 − FC), con **C_d = 0,25** se non dichiarato (11.307).
  - On-off aria/acqua, antigelo/acqua, acqua/acqua: f = FC/(C_c·FC + 1 − C_c), con **C_c = 0,9** (11.309).
  - A gradini: si interpola tra i gradini (11.311)-(11.314).
  - **Inverter**: f = 1 fino a FC = 0,5 (o fino al minimo di modulazione); sotto si usa la formula on-off.
  - Assorbimento a gas, f_GUE (Prospetti 11.XLIX on-off e 11.L modulante):

| FC | 0,1 | 0,2 | 0,3 | 0,4 | 0,5 | 0,6 | 0,7 | 0,8 | 0,9 | 1 |
|---|---|---|---|---|---|---|---|---|---|---|
| f_GUE on-off | 0,68 | 0,77 | 0,84 | 0,89 | 0,92 | 0,95 | 0,97 | 0,99 | 1 | 1 |
| f_GUE modulante | 0,72 | 0,81 | 0,88 | 0,93 | 0,97 | 0,99 | 1 | 1 | 1 | 1 |

  - f_AEF = FC (ausiliari costanti) oppure 1 (ausiliari proporzionali) (11.317)-(11.318).
- **Energie**:
  - Φ_out = FC·Φ_N (11.261); Q_out = Φ_out·Δt (mese) oppure Σ Φ_out,bin·t_bin (11.264), (11.277);
  - Q_in = Q_out/COP (11.266)-(11.270);
  - ausiliari virtualmente interni W_aux = Q_out/AEF(FC), nulli per le PdC elettriche a compressione (11.271);
    ausiliari esterni W = ΣW_N·FC·Δt (11.272);
  - Q_GN,out = Q_gn,out + 0,8·W_aux,ve (11.281); COP_GN = Q_GN,out/(Q_in + W_aux) (11.283);
  - **integrazione**: Q_int = Q_req − Q_gn,out (11.288), da assegnare al generatore successivo (sez. 5.6).
- **Energia rinnovabile** (11.212)-(11.215): Q_amb = Q_out·(1 − (1 − α_aux + β_ls)/COP_net) − k·W_pe,e. Per le PdC
  elettriche β_ls = 0. Con fonte rinnovabile E_ren = Q_amb, che entra in f_P,ren (Allegato 2: "energia termica
  dall'ambiente esterno - pompa di calore", f_P,ren = 1).
- **Perdite recuperate**: solo per le PdC per ACS con accumulo integrato, in stagione di riscaldamento (11.284)-(11.287):
  Q_rbl = K_S·(60 − θ_a)·Δt. Se la PdC è in ambiente riscaldato con sorgente esterna, Q_rvd = 0,8·Q_rbl. Per le PdC che
  prelevano aria interna: Q_rvd = Q_rbl − Q_C, con Q_C = 0,9·ρc·V_HP·(60 − θ_a)·Δt **[AMB-30]**.
- **Mancano valori di default del COP**: il testo richiede i dati del fabbricante nei punti dei Prospetti 11.XLV e 11.XLVI.
  Senza dati bisogna decidere una politica (per esempio rifiutare il calcolo) **[AMB-31]**.

---

## 6. Raffrescamento, ventilazione meccanica, fotovoltaico e solare termico (sintesi)

### 6.1 Raffrescamento (Cap. 9 e §11.9, p. 207-240 e 378-396)

- Si parte da Q_NC,adj (+ Q_Z,rvd ACS, (2.60)) e si risale la catena emissione, regolazione, distribuzione, accumulo e
  generazione con la logica "caso b": le perdite sono guadagni e la quota recuperata degli ausiliari si **somma**.
- Emissione (9.16): Q_C,e,ls = Q_NC,adj·(1 − η_eC)/η_eC, con **Prospetto 9.I**:

| Terminale | η_eC |
|---|---|
| Ventilconvettori idronici | 0,98 |
| Espansione diretta, unità interne split | 0,97 |
| Armadi autonomi, ventilconvettori industriali, travi fredde | 0,97 |
| Bocchette, anemostati, diffusori lineari, dislocamento | 0,97 |
| Pannelli isolati annegati a pavimento | 0,97 |
| Pannelli isolati annegati a soffitto | 0,98 |

- Regolazione (9.17): Q_C,c,ls = (Q_NC,adj + Q_C,e,ls)·(1 − η_cC)/η_cC. **Prospetto 9.II**:
  - centralizzata: on-off 0,84; modulante 0,90;
  - di zona: on-off 0,93; modulante banda 2 °C 0,95; banda 1 °C 0,97;
  - singolo ambiente: on-off 0,94; banda 2 °C 0,96; banda 1 °C 0,98.
  Nel raffrescamento i due rendimenti sono **in cascata**, mentre per il riscaldamento vale la (8.29).
- Ventilatori dei terminali (9.18)-(9.19):
  - ventilatore sempre acceso: W = ΣW·Δt;
  - con arresto: W = ΣW·(θ_e − θ_i,C)/(θ_im,des − θ_i,C)·Δt, così come estratto **[AMB-32]**.
- Generazione con macchine frigorifere a compressione (11.360): η_mm = EER(FC)·η_1(FC)·η_2·…·η_7.
  - Curva EER dai punti al 100/75/50/25 % (Prospetto 11.LVI).
  - Sotto il 25 %: aria-aria e acqua-aria EER4 × 0,94 (20 %), 0,85 (15 %), 0,73 (10 %), 0,50 (5 %), 0,26 (2 %),
    0,14 (1 %); aria-acqua e acqua-acqua × 0,95 / 0,94 / 0,87 / 0,71 / 0,46 / 0,29.
  - I coefficienti η_1 (Prospetti 11.LVII-11.LXXIII, per temperature diverse dalle nominali) e η_2…η_7 (§11.9.5)
    sono tabelle lunghe non riportate qui. Per implementarle vanno estratte a p. 384-396.
- Ausiliari esterni di default (Prospetto 11.LV): condensatori ad aria con ventilatori elicoidali 20-40 W/kW, centrifughi
  canalizzati 40-60 W/kW, ecc.

### 6.2 Ventilazione meccanica (Cap. 10 e §3.3.6, App. E)

- Effetto termico: tutto dentro **Q_V,adj**, con V_f,a, b_v (recupero dall'App. E), FC_v e β (sez. 3.5).
  Non c'è una richiesta termica del servizio V (Q_V,g,out = 0, (10.1)).
- Energia elettrica (10.3)-(10.4): **W_V = Σ_zone Σ_flussi W_ve,k · FC_ve,adj,k · Δt**, con FC_ve,adj = FC_v·β_k
  (nel residenziale β = 1). W_ve è la potenza del ventilatore alla portata di progetto (curva), altrimenti la potenza di
  targa. Il servizio V ha solo vettore elettrico.
- Recuperatore: solo statico, senza ausiliari (§10.4). Il surriscaldamento dovuto al ventilatore è trascurabile (§10.5).
- Edificio di riferimento (Allegato B, Tabella 9): E_ve [Wh/m³ d'aria movimentata]:

| Tipologia | E_ve [Wh/m³] |
|---|---|
| Semplice flusso per estrazione | 0,25 |
| Semplice flusso per immissione con filtrazione | 0,30 |
| Doppio flusso senza recupero | 0,35 |
| Doppio flusso con recupero | 0,50 |

### 6.3 Fotovoltaico (§11.11.1, p. 430-432) e centrale elettrica (§11.4.2)

```
W*_PV,gn,out = H_PV · W_PV · F_PV / I_ref                     (11.473)   I_ref = 1 kW/m²
W_PV,gn,out  = W*_PV,gn,out − W_aux,PV · Δt_PV · N / 1000       (11.472)
W_PV         = F_P · A_PV    [kW_p]                             (11.474)
```

- H_PV = irradiazione **giornaliera media mensile** sul piano dei moduli (App. F), ombre comprese. Il testo non
  moltiplica per N: per avere energia mensile serve ×N **[AMB-33]**.
- Δt_PV = ore giornaliere medie mensili di soleggiamento teorico (Prospetto 11.CVI):

| Gen | Feb | Mar | Apr | Mag | Giu | Lug | Ago | Set | Ott | Nov | Dic |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 9,0 | 10,2 | 11,7 | 13,3 | 14,7 | 15,4 | 15,1 | 13,9 | 12,3 | 10,7 | 9,3 | 8,6 |

- **Prospetto 11.CVII - F_PV**: moduli non ventilati 0,70; moderatamente ventilati 0,75; molto ventilati o con
  ventilazione forzata 0,80.
- **Prospetto 11.CVIII - F_P [kW/m²]**:

| Tecnologia | F_P |
|---|---|
| Silicio monocristallino | 0,150 |
| Silicio multicristallino | 0,130 |
| Film sottile di silicio amorfo | 0,060 |
| Altri film sottili | 0,035 |
| CIGS (Copper-Indium-Galium-Diselenide) | 0,105 |
| CdTe (Cadmium-Telloride) | 0,095 |

- **Autoconsumo mensile** (11.48)-(11.49): con W_ES,out = richiesta elettrica mensile dell'edificio (tutti i servizi,
  ausiliari compresi) si ha **f_PV,iu = min(1 ; W_ES,out/W_PV,gn,out)**. Ordine di priorità: PV, eolico, cogeneratore
  rinnovabile, cogeneratore fossile. W_SG,iu = f_PV,iu·W_PV (11.39) e W_el,exp = (1 − f_iu)·W_PV (11.44).
  L'energia prelevata dalla rete è E_el,in = W_ES,out − W_SG,iu ≥ 0 (11.46).
- Ripartizione per servizio con f_ES,S = (W_ds,S + W_g,S)/W_ES,out (11.28), da applicare sia al prelievo di rete sia
  all'autoconsumo (11.40), (11.47).
- Possibile recupero dell'esportato nei mesi successivi (§2.3.3, p. 26), "nel rispetto della quota limite di recupero
  prefissata". Il valore di quel limite **non è indicato** nell'Allegato H **[AMB-34]**.

### 6.4 Solare termico (§11.8.9, p. 367-378), metodo f-chart mensile

```
SF_X,S = a·Y + b·X + c·Y² + d·X² + e·Y³ + f·X³ ,   0 ≤ SF ≤ 1        (11.323)
X = A·P_S·U_loop·η_loop·(θ_ref − θ_e)·Δt·f_ST / Q_S,STG,req          (11.327)   [valido 0 ≤ X ≤ 18]
Y = A·P_S·IAM·η_0·η_loop·H_T / Q_S,STG,req                             (11.338)   [valido 0 ≤ Y ≤ 3]
U_loop = a_1 + 40·a_2 + U_loop,p/A ;  U_loop,p = 5 + 0,5·A  [W/K]      (11.330)-(11.331)
η_loop = 0,8 (default)  oppure  1 − η_0·A·a_1/(U_st)_hx                 (11.328)
f_ST = (V_ref·A/V_sol)^0,25 ,  V_ref = 75 l/m² ,  0,25 ≤ f_ST ≤ 2      (11.332)
V_sol = V_nom (solo preriscaldamento) ;  V_nom·(1 − f_aux) con integrazione, f_aux = x·V_bu/V_nom   (11.333)-(11.335)
      x = 1 integrazione permanente ; 0,7 solo notturna ; 0,3 solo di emergenza
θ_ref = 100 °C (H) ;  θ_ref = 11,6 + 1,18·θ_w + 3,86·θ_cw − 1,32·θ_e (ACS), θ_w = 48 °C, θ_cw = θ media annua  (11.336)-(11.337)
P_H = (Q_H + Q_HA)/Q_STG,req ;  P_W = Q_W/Q_STG,req                    (11.321)-(11.322)
```

- H_T = irradiazione **mensile** sul collettore (giornaliera × N), ombre comprese.
- Coefficienti (Prospetto 11.LI):

| Coefficiente | Accumulo ad acqua | Campo collegato direttamente a un pavimento radiante |
|---|---|---|
| a | 1,029 | 0,863 |
| b | −0,065 | −0,147 |
| c | −0,245 | −0,263 |
| d | 0,0018 | 0,008 |
| e | 0,0215 | 0,029 |
| f | 0 | 0,025 |

- **Prospetto 11.LII - collettori tipici**:

| Collettore | η_0 | a_1 [W/m²K] | a_2 [W/m²K²] | IAM |
|---|---|---|---|---|
| Sottovuoto con assorbitore piano | 0,90 | 1,8 | 0,008 | 0,97 |
| Sottovuoto con assorbitore circolare | 0,90 | 1,8 | 0,008 | 1,00 |
| Piani vetrati | 0,78 | 3,5 | 0,015 | 0,94 |
| Non vetrati | 0,76 | 15 | 0 | 1,00 |

- Ausiliari (11.340)-(11.345): W_cf = W_STG,cf·Δt_cf, con Δt_cf = 2·H_T,m/H_T,yr [kh] (cioè 2000 h/anno ripartite sui mesi in proporzione all'irradiazione) **[AMB-35]** e, senza dati,
  W_STG,cf = 50 + 5·A [W]. Circolatore verso l'ausiliario: W·FC·Δt.
- Perdite dell'accumulo (11.346)-(11.350): K_acc·(θ_set − θ_a)·Δt, con θ_set = 60 °C per l'ACS. Perdite di distribuzione
  verso l'ausiliario: 0,02·SF·Q_req con tubi isolati, 0,05·SF·Q_req con tubi non isolati (11.351)-(11.352).
- Recuperi (11.354)-(11.358):
  - solare solo ACS con accumulo in ambiente riscaldato: le perdite **riducono il fabbisogno di riscaldamento**;
  - solare combinato: 0,8·(1 − b_gs)·Q.
- La quota solare copre la richiesta con priorità 1. Il residuo Q_net·(1 − SF) va agli altri generatori (11.68)-(11.70).
  Il vettore "solare termico" ha f_P,ren = 1 (Allegato 2): l'energia rinnovabile è Q_STG,out.

---

## 7. Energia primaria, quota rinnovabile e CO2 (Cap. 2 e Allegato 2)

### 7.1 Formule (§2.2-2.3, p. 18-27)

```
EP_S,x,m = Σ_y f_P,x,y,del · E_S,y,del,m − Σ_y f_P,x,y,exp · E_S,y,exp,m      (2.12)   x ∈ {nren, ren, tot}
EP_S,x   = Σ_m EP_S,x,m                                                        (2.11)
E_P,gl,x = E_P,H + E_P,HA + E_P,C + E_P,CA + E_P,W + E_P,V + E_P,L + E_P,T       (2.10)
EP_gl,nren = E_P,gl,nren / A ;  EP_gl,tot = E_P,gl,tot / A   [kWh/(m² anno)]   (2.1)-(2.2)
f_P,tot = f_P,nren + f_P,ren   → E_P,tot = E_P,nren + E_P,ren                   (2.13)-(2.14)
QER_S = E_P,S,ren / E_P,S,tot ;  QER = Σ_S E_P,S,ren / Σ_S E_P,S,tot            (2.8)-(2.9)
M_CO2 = Σ_i E_del,fuel,i·f_em,fuel,i + Σ_j E_fuel,ren,j·f_em,fuel,ren,j + E_del,el·f_em,el    (2.7)
EM_CO2 = M_CO2 / A                                                              (2.5)
```

- A = superficie utile (Allegato A, def. 96: superficie netta calpestabile dei volumi climatizzati con altezza
  ≥ 1,50 m, più la proiezione delle scale interne).
- Vettori per servizio: combustibili = ingresso al generatore del servizio (11.29); elettricità = quota del prelievo di
  rete attribuita al servizio, f_ES,S·E_el,in (11.47).
- Fonti in situ: il solare termico e l'energia ambiente delle PdC entrano come vettori con f_P,nren = 0 e f_P,ren = 1.
  Il FV autoconsumato **riduce** il prelievo di rete e si contabilizza anche come vettore "fotovoltaico" con f_P,ren = 1
  **[AMB-36]**.
- Energia esportata: fattori f_P,x,y,exp **non tabulati** nell'Allegato 2 **[AMB-37]**.
- Efficienze globali (§2.8, p. 42-48): per esempio η_gH,yr = Q_BH,yr/E_PH. Sono indicatori informativi.

### 7.2 Allegato 2 - Prospetto I: fattori di conversione in energia primaria (p. 584)

| Vettore | f_P,nren | f_P,ren | f_P,tot |
|---|---|---|---|
| Gas naturale | 1,05 | 0 | 1,05 |
| GPL | 1,05 | 0 | 1,05 |
| Gasolio e olio combustibile | 1,07 | 0 | 1,07 |
| Carbone | 1,10 | 0 | 1,10 |
| Biomasse solide | 0,20 | 0,80 | 1,00 |
| Biomasse liquide e gassose | 0,40 | 0,60 | 1,00 |
| Energia elettrica da rete | 1,95 | 0,47 | 2,42 |
| Teleriscaldamento (*) | 1,50 | 0 | 1,50 |
| Teleraffrescamento (*) | 0,50 | 0 | 0,50 |
| RSU (valori per uso teleriscaldamento) | 0,20 | 0,20 | 0,40 |
| Solare termico | 0 | 1,00 | 1,00 |
| Fotovoltaico, mini-eolico e mini-idraulico | 0 | 1,00 | 1,00 |
| Energia termica dall'ambiente esterno - free cooling | 0 | 1,00 | 1,00 |
| Energia termica dall'ambiente esterno - pompa di calore | 0 | 1,00 | 1,00 |

(*) In assenza di valori dichiarati e asseverati dal fornitore.

**Allegato 2 - Prospetto II - rendimenti di riferimento** (per la cogenerazione): η_el,ref = **0,413**;
η_th,ref = **0,9**.

**Allegato 2 - Prospetto III - fattori di emissione [kg CO2eq/kWh]** (p. 585; fonti: PAE Lombardia D.G.R. VIII/4916,
Terna, UNI EN 15603):

| Vettore | Simbolo | Fattore |
|---|---|---|
| Gas naturale | f_em,fuel | 0,1998 |
| GPL | f_em,fuel | 0,2254 |
| Gasolio | f_em,fuel | 0,2642 |
| Olio combustibile | f_em,fuel | 0,2704 |
| Carbone | f_em,fuel | 0,3402 |
| Biomasse | f_em,fuel,ren | 0 |
| RSU | f_em,fuel,ren | 0,1703 |
| Energia elettrica | f_em,el | 0,4332 |
| Teleriscaldamento (*) | f_em | 0,360 |
| Teleraffrescamento (*) | f_em | 0,1688 |

> Nella (2.7) E_del,el è l'energia elettrica "complessivamente fornita": si usa l'energia prelevata dalla rete, netta
> dell'autoconsumo FV **[AMB-38]**. Tutti i combustibili si intendono riferiti al PCI.

---

## 8. Classificazione energetica (APE) e indicatori

Fonte: Disposizioni (DGR) **§16**, p. 34-36 del file `Disposizioni-per-efficienza-energetica-degli-edifici.txt`;
**Allegato B** §1. L'Allegato H si limita a dire "si calcola la classe energetica" (p. 11).

### 8.1 Indice di classificazione

- La classe si determina con **EP_gl,nren** dell'unità immobiliare (§16.1).
- In EP_gl,nren entrano **solo i servizi presenti**, con due eccezioni: la **climatizzazione invernale** e, **nel solo
  residenziale, l'ACS** si considerano **sempre presenti** (§16.4). Il testo non dice con quale impianto simulare il
  servizio quando manca **[AMB-39]**.

### 8.2 Edificio di riferimento EP_gl,nren,rif,standard (§16.2-16.3 + Allegato B)

È lo stesso edificio (geometria, orientamento, ubicazione, destinazione d'uso, contorno) con:

- **Fabbricato di riferimento** (Allegato B, §1.1):
  - U opache verticali (verso esterno, non climatizzati, terreno): E **0,26**, F **0,24** W/m²K;
  - coperture: E **0,22**, F **0,20**;
  - pavimenti (verso esterno, non climatizzati, terreno): E **0,26**, F **0,24**;
  - chiusure trasparenti e cassonetti (infissi compresi): E **1,40**, F **1,10**;
  - strutture tra edifici o unità confinanti: **0,8** in tutte le zone;
  - verso ambienti non climatizzati si usa la U di tabella divisa per il fattore di correzione dello scambio termico
    (b o F_T) (Allegato B, p. 3, punto 2);
  - le U del terreno sono **equivalenti**, effetto del terreno compreso;
  - ψ di riferimento (Tabella 5-bis, ψ_est su dimensioni esterne; ψ_int tra parentesi):

| Ponte termico | ψ_est E | ψ_est F | (ψ_int E / F) |
|---|---|---|---|
| Aggancio balcone | 0,29 | 0,29 | (0,40 / 0,39) |
| Davanzale serramento | 0,10 | 0,11 | (0,10 / 0,11) |
| Spalla serramento | 0,08 | 0,08 | (0,08 / 0,08) |
| Architrave serramento | 0,12 | 0,12 | (0,12 / 0,12) |
| Cassonetto serramento | 0,22 | 0,23 | (0,22 / 0,23) |

  - Le lunghezze dei ponti termici sono quelle dell'edificio reale. Le U di tabella includono gli altri ponti termici.
  - Il coefficiente di assorbimento solare degli opachi è quello dell'edificio reale.
  - Per le finestre orientate da Est a Ovest passando per Sud, **g_gl+sh = 0,35** (Tabella 6).
- **Impianti standard per la classificazione** (Disposizioni, Tabella 2): per l'ACS e la climatizzazione invernale,
  generatore a **gas naturale**; per la climatizzazione estiva, macchina frigorifera elettrica a compressione;
  per la ventilazione, VMC a **semplice flusso per estrazione**. Si escludono le FER dell'edificio reale (§16.2).
  Efficienze dall'Allegato B:
  - η_u (Tabella 7, utilizzazione: emissione, regolazione, distribuzione, accumulo), H / C / W:
    distribuzione idronica **0,81 / 0,81 / 0,70**; aeraulica 0,83 / 0,83 / -; mista 0,82 / 0,82 / -.
  - η_gn (Tabella 8): generatore a gas **H 0,95**, **W 0,85**; macchina frigorifera elettrica **C 2,50**.
    Altre righe della Tabella 8, H / C / W:
    - combustibile liquido 0,82 / - / 0,80;
    - solido 0,72 / - / 0,70;
    - biomassa solida 0,72 / - / 0,65; biomassa liquida 0,82 / - / 0,75;
    - PdC elettrica 3,0 (*) / - / 2,5;
    - PdC ad assorbimento 1,20 (*) / - / 1,10;
    - frigo a fiamma indiretta - / 0,60·η_gn / -; frigo a fiamma diretta - / 0,60 / -;
    - PdC a motore endotermico 1,15 / 1,00 / 1,05;
    - cogeneratore 0,55 / - / 0,55, elettrico 0,25;
    - resistenza elettrica 1,00 / - / -;
    - teleriscaldamento 0,97; teleraffrescamento C 0,97;
    - solare termico 0,3 / - / 0,3; FV elettrico 0,1.
    (Per il riferimento "standard" di classificazione servono solo gas, frigo elettrico e VMC a estrazione. Le altre
    righe servono all'edificio di riferimento della Legge 10, che usa gli stessi generatori del reale, Allegato B p. 4.)
  - Gli **ausiliari si pongono = 0**, perché sono già inclusi nei rendimenti (Allegato B, p. 4, punto 6).
  - Il fabbisogno utile ACS è **uguale a quello reale** (Allegato B, p. 4, punto 3).
  - Ventilazione di riferimento: stesse portate del reale e E_ve della Tabella 9 (0,25 Wh/m³ per l'estrazione).
  - Il calcolo di Q_H,nd e Q_C,nd del riferimento si fa con l'Allegato H sul fabbricato di riferimento.
- Calcolo pratico del riferimento, per ogni servizio S:
  **E_P,S,nren = Q_S,nd/(η_u·η_gn) · f_P,nren(vettore)**, con i vettori gas (1,05) ed elettricità (1,95).
  Poi EP_gl,nren,rif,standard = Σ_S E_P,S,nren / A.

### 8.3 Scala delle classi (Disposizioni, Tabella 3)

| Classe | Condizione su EP_gl,nren |
|---|---|
| A4 | ≤ 0,40·EP_gl,nren,rif |
| A3 | 0,40·rif < EP ≤ 0,60·rif |
| A2 | 0,60·rif < EP ≤ 0,80·rif |
| A1 | 0,80·rif < EP ≤ 1,00·rif |
| B | 1,00·rif < EP ≤ 1,20·rif |
| C | 1,20·rif < EP ≤ 1,50·rif |
| D | 1,50·rif < EP ≤ 2,00·rif |
| E | 2,00·rif < EP ≤ 2,60·rif |
| F | 2,60·rif < EP ≤ 3,50·rif |
| G | > 3,50·rif |

### 8.4 Indicatori di qualità del fabbricato

- **Invernale** (Tabella 4): confronto tra EP_H,nd e EP_H,nd,limite. EP_H,nd,limite è l'EP_H,nd dell'edificio di
  riferimento con gli elementi dell'Allegato B punto 1 (sez. 8.2).
  - **Alta**: EP_H,nd ≤ 1·limite;
  - **Media**: 1·limite < EP_H,nd ≤ 1,7·limite;
  - **Bassa**: > 1,7·limite.
  - EP_H,nd = Q_BH,yr/A, cioè il fabbisogno di **riferimento** con ventilazione naturale (§3.2) **[AMB-5]**.
- **Estivo** (Tabella 5):
  - **Alta** se A_sol,est/A_sup,utile ≤ 0,03 **e** Y_IE ≤ 0,14;
  - **Media** se una sola delle due condizioni è soddisfatta;
  - **Bassa** se nessuna è soddisfatta.
  - Y_IE è la media pesata sulle superfici, **escluse le verticali esposte a Nord**. Se tutte le verticali sono a Nord,
    Y_IE = 0,14 (§16.7). Y_IE si calcola con l'Appendice H (UNI EN ISO 13786) e A_sol,est con l'Allegato B §2.2.

---

## 9. Algoritmo di calcolo mensile end-to-end (residenziale, una zona)

1. **Clima**: si prende il capoluogo della provincia; θe mensile corretta per l'altitudine (3.14); Hb e Hd orizzontali
   (Allegato 1, Prospetto III); p_v; θe,av.
2. **Geometria e U**: U dei componenti, U_W, U_w,ave con chiusure (f_shut = 0,6), U_b del terreno (App. B), ψ spalmati
   sulle strutture (3.17).
3. **Irradiazione** H_s,j su ogni esposizione (App. F); F_S = min(F_h, F_o, F_f); F_s,d per il diffuso.
4. **Locali non climatizzati**: θ_u mensile (App. A) oppure F_T (Prospetto 3.I) in modalità semplificata.
5. Per ogni mese m di 12 mesi interi:
   - Q_T = H_T·Δθ·Δt + ΔQ_T,R;
   - Q_V (con n = 0,5 × 0,6) e Q_V,adj;
   - Q_I = Φ_a·Δt;
   - Q_SI e Q_SE,O;
   - Q_L,net;
   - γ, τ, a, η;
   - Q_NH, Q_NH,adj, Q_NC, Q_NC,adj.
6. **Stagione**: γ_lim, interpolazione giornaliera, troncamento al Prospetto I; si ricalcolano i mesi estremi con
   N_in e N_fin.
7. **ACS**: Q_NW per unità immobiliare; perdite di erogazione (0), distribuzione, accumulo, G-S; Q_W,g,out;
   **Q_Z,rvd**.
8. **Riscaldamento**:
   - Q*_NH,adj = Q_NH,adj − Q_Z,rvd;
   - emissione e regolazione (8.29);
   - distribuzione (rendimento precalcolato con correzione C, oppure App. J);
   - accumulo;
   - G-S;
   - Q_H,g,out;
   - ausiliari W_H,ds.
9. **Generazione**:
   - richiesta alla centrale (H + W, se integrata) con f_HS,S;
   - priorità (solare, biomassa, PdC, fossile);
   - FC per generatore;
   - perdite e vettori in ingresso (caldaia: precalcolato o EN 15316-4-1; PdC: COP e bin; ecc.);
   - ausiliari di generazione.
10. **Raffrescamento e VMC** (se presenti): Q_C,g,out, EER, W_V.
11. **Centrale elettrica**:
    - W_ES,out = Σ ausiliari + PdC + Joule + frigo + VMC;
    - produzione FV;
    - f_PV,iu, autoconsumo ed esportazione;
    - prelievo di rete per servizio.
12. **Energia primaria**: per servizio, EP_x = Σ_y f_P,x,y·E_y (Allegato 2); EP_gl,nren, EP_gl,ren, EP_gl,tot;
    QER; CO2.
13. **Classe**: EP_gl,nren,rif,standard con fabbricato e impianti standard; scala A4…G; indicatori invernale ed estivo.

---

## 10. Punti ambigui, illeggibili o incoerenti dell'estrazione

Ogni punto dice cosa manca e quale scelta provvisoria si propone. Le scelte vanno **validate confrontando i risultati
con CENED+2.0** su casi test, perché il PDF non basta a scioglierle.

1. **[AMB-1] Frazioni di mese.** Il §1.4 (p. 15, passo 6) chiede di "ricalcolare i dati climatici" per le frazioni dei
   mesi estremi, ma non dice come: θe media del mese intero oppure della sola frazione? Irradiazione × N_frazione?
   Proposta: dati medi mensili invariati e N ridotto.
2. **[AMB-2] Correzione per altitudine** (3.14): vale esplicitamente per θe. Non è chiaro se si applichi anche a θe,av
   (θ_0 dell'ACS, θ_cw del solare), ai bin orari e alle temperature di progetto. L'irradiazione e p_v restano quelle del
   capoluogo.
3. **[AMB-3] Allegato 1, Prospetto III (Hd, Hb)**: le 12 righe numeriche **non hanno il nome del capoluogo** (p. 570).
   Si è assunto l'ordine alfabetico Bergamo…Varese degli altri prospetti. **Da verificare sul PDF**: è un errore critico
   se l'ordine è diverso.
4. **[AMB-4] Bin orari** (Allegato 1, Prospetti VII-XVIII): non è indicato se e come correggerli per l'altitudine del
   Comune (per esempio traslando di δ·Δz).
5. **[AMB-5] EP_H,nd per l'indicatore invernale e i limiti**: il testo definisce Q_BH,yr (riferimento, ventilazione
   naturale) e Q_BH,adj,yr (corretto). Non dice esplicitamente quale dei due sia EP_H,nd. Proposta: Q_BH,yr/A
   (riferimento), coerente con "mettere in evidenza le caratteristiche dell'involucro" (p. 49).
6. **[AMB-6] (3.4) e (3.7)**: "se Q_NH = 0 si pone η = 1" sembra una convenzione per il report. L'estrazione della
   condizione è confusa ("1 … 0 … pone si Q se").
7. **[AMB-7] Chiusure oscuranti** (3.21): non è detto se U_w,ave (con f_shut = 0,6) valga anche nei mesi estivi.
8. **[AMB-8] T_sky** (3.36): l'estratto "1000p sky ve51,6291T −−=" è stato letto come T_sky = 291 − 51,6·e^(−p_v/1000)
   [K]. È plausibile (Δθ_er ≈ 10 K), ma l'esponenziale non è visibile.
9. **[AMB-9] (3.57)**: V'_a,x = V_a,x / [1 + (f/e)·((V_sup − V_ext)/(V·n50/3600))²] ricostruita dalla forma standard
   EN 13790. Anche la (3.47) è ricostruita: V_a,k = V_a,x(1 − β) + (V_f,a·b_v·FC_v + V'_a,x)·β.
10. **[AMB-10] Prospetto 3.XXIV (FC_v)**: le intestazioni (presenza, movimento, CO2, UR, bocchetta, e le sottocolonne
    modulo o ventilatore a velocità variabile) non sono allineabili con certezza agli 8 valori della riga E.1
    (0,80 0,80 0,80 0,70 0,70 0,70 0,70 0,60).
11. **[AMB-11] Schermo integrato** (3.75)-(3.76): la disposizione dei termini (g⊥·τ_e + g⊥·[α_e + (1 − g⊥)·ρ_e]·G/G_3)
    è ricostruita.
12. **[AMB-12] Lamelle a 45°** (3.78)-(3.81): la forma di ρ_e,b(45) e τ_e,d(45) è incerta. La lettura
    "τ_e,d = 0,30 + 0,70·τ_e,b" darebbe τ_d ≥ 0,3 anche per lamelle opache: probabilmente un fattore è andato perso.
13. **[AMB-13] Prospetto 3.XXXII (tende)**: la tabella è estratta per colonne. L'accoppiamento delle righe
    (α, τ, F_sh interno/esterno) è una lettura plausibile.
14. **[AMB-14] (3.105)**: la condizione per η_L,C = 1 è "γ_C … 0" con il simbolo di confronto perso (≤ o <).
15. **[AMB-15] A_tot per C_m**: con il Prospetto D.I la superficie di riferimento è "verticali + 2·pianta·piani"; con il
    metodo analitico è "superfici nette opache che delimitano la zona". Il testo non chiarisce quale usare nella (3.101)
    quando C_m viene dal D.I.
16. **[AMB-16] R_b,y** (F.26)-(F.27): il fattore "π/180" (ω in gradi) e la posizione dei termini sono ricostruiti. Anche le
    radici (F.18) e i casi singolari (F.20)-(F.23) sono estratti in modo parziale.
17. **[AMB-17] Figura C.1**: la formula dell'angolo d'ostruzione α (con i casi d = 0) è illeggibile.
18. **[AMB-18] App. B**: nella (B.6) e nella (B.7) il simbolo λ è perso ("d_t = w + (R_si + R_f + R_se)"). La definizione
    B' = A/(0,5P) e le (B.8)-(B.9) sono ricostruite. L'Allegato B (p. 3, punto 3) parla di confronto con la "UNI EN ISO
    13370", mentre l'Allegato H usa il proprio metodo stazionario.
19. **[AMB-19] θ_0 dell'ACS**: il testo (p. 116) rinvia all'"Allegato 1 - Prospetto I" per la media annua, ma la media
    annua è nel **Prospetto VI**. Lo stesso vale per θ_cw del solare (11.337).
20. **[AMB-20] (7.21)**: con ρ_w·c_w = 4 168 600 J/(m³K) il risultato è in J. La conversione in kWh (÷ 3,6·10⁶) non è
    scritta.
21. **[AMB-21] Prospetto 7.III** (L_V, L_S, L_SL): le formule sono estratte in modo confuso
    ("BBBL0125,0BL2 +", "ffBB hnBL075,0", "fBB nBL075,0"). La lettura adottata è L_V = 2L_B + 0,0125·L_B·B_B;
    L_S = 0,075·L_B·B_B·n_f·h_f; L_SL = 0,075·L_B·B_B·n_f.
22. **[AMB-22] φ_t** (8.30): nel testo Q "annuo" e Δt "del mese". Nella nota del Prospetto 8.I, φ_t è "medio stagionale".
    Resta da decidere se η_ee sia costante in tutta la stagione oppure vari mese per mese.
23. **[AMB-23] Assenza di regolazione ambiente**: "sola climatica − 0,05" è ammessa "ai soli fini di valutazione dei
    miglioramenti". Non è chiaro quale valore usare per l'APE di un impianto con solo termostato di caldaia.
24. **[AMB-24] Prospetto 8.X (pompe)**: le formule sono lette come η = Φ^0,50/25,46, Φ^0,26/10,52, Φ^0,40/26,23.
    Gli esponenti e i divisori sono incerti.
25. **[AMB-25] θ_s dell'accumulo del riscaldamento** (8.90): non ha un valore convenzionale, a differenza dei 60 °C
    dell'ACS. Si può usare la temperatura del circuito G-S (App. J) oppure la mandata di progetto.
26. **[AMB-26] Prospetti 11.VI-11.IX (caldaie) e 11.XXXII-11.XXXVII (biomassa)**: le intestazioni F1…F7 sono separate
    dai valori. L'assegnazione dei valori alle colonne F è una lettura plausibile, da verificare sul PDF. Nel Prospetto
    11.IX la terza riga riporta "24 °C" invece di "> 24 °C".
27. **[AMB-27] (11.98)**: la posizione del fattore f_f (1,05 per la condensazione a gasolio) nella formula
    η_gn,I = f_f·(C + D·log10 Φ)? non è leggibile.
28. **[AMB-28] Prospetto 11.XIII**: nella voce "bassa temperatura, tiraggio forzato" ci sono due righe "dopo 1994"
    (8,0/−0,33 e 5,0/−0,35). Probabilmente una delle due appartiene a un'altra categoria o a un altro periodo.
29. **[AMB-29] (11.172)**: il volume d'accumulo delle caldaie a biomassa manuali (V = 0,015·Δt·Φ_N·(1 − 0,3·Φ_des/Φ_min))
    è ricostruito e le unità non sono chiare.
30. **[AMB-30] (11.286)-(11.287)**: per la PdC per ACS con aria interna, il segno e la temperatura (θ_s,av − θ_a con
    θ_s,av = 60 °C) nella formula di Q_C sono fisicamente dubbi: ci si aspetterebbe la Δθ sull'aria.
31. **[AMB-31] Pompe di calore senza dati**: non esistono COP o potenze di default. Il metodo richiede i dati del
    fabbricante nei punti dei Prospetti 11.XLV e 11.XLVI.
32. **[AMB-32] (9.19)**: il fattore di funzionamento dei ventilatori estivi, (θ_e − θ_i,C)/(θ_im,des − θ_i,C), è
    ricostruito. Ha segno e significato incerti.
33. **[AMB-33] FV** (11.473): H_PV è "giornaliera media mensile" ma la formula non moltiplica per N. La (11.472) invece
    sottrae W_aux·Δt_PV·N. Proposta: W* = H_PV·N·W_PV·F_PV/I_ref.
34. **[AMB-34] Recupero dell'energia esportata** in altri mesi (§2.3.3, p. 26): la "quota limite di recupero prefissata"
    non è definita.
35. **[AMB-35] Δt_cf** (11.342): "yrT,mT,cf HH2Δt =" è letto come Δt_cf = 2·H_T,m/H_T,yr [kh].
36. **[AMB-36] Contabilità FV nell'EP**: il testo tratta l'autoconsumo come riduzione del prelievo (11.46). Non è chiaro
    se la quota autoconsumata debba comparire anche come vettore rinnovabile (f_P,ren = 1) in EP_ren ed EP_tot, cosa
    che influenza QER.
37. **[AMB-37] Fattori f_P,exp** per l'energia esportata: la (2.12) li prevede, ma l'Allegato 2 non li tabula.
38. **[AMB-38] E_del,el nella CO2** (2.7): non è precisato se è il lordo o il prelievo di rete netto dell'autoconsumo.
39. **[AMB-39] Servizi "sempre presenti"** (Disposizioni §16.4): nel residenziale, climatizzazione invernale e ACS si
    considerano sempre presenti. Il testo non specifica con quale impianto simulare un servizio assente nell'edificio
    reale (standard a gas? effetto Joule?).
40. **Riferimenti vuoti nell'estrazione**: "(si veda Allegato )" (p. 18, 20), "I bin mensili per aria esterna sono
    riportati nell'Allegato ." (p. 342), "Allegato ;" (p. 431), "(Prospetto )" (p. 324, 369). Il numero dell'allegato o
    del prospetto è andato perso: per il contesto si tratta dell'Allegato 1 o 2.
41. **Numerazione dei prospetti incoerente**: la continuazione del Prospetto 3.XIV è intitolata "(continua) Prospetto
    3.XV" (p. 76). Il Prospetto 7.IV rimanda a "§ 1.5" inesistente (si intende §1.4). Il Prospetto 11.XIV parla di
    "b_tr,x della zona non climatizzata", concetto che l'Allegato H sostituisce con l'Appendice A.
42. **Dati climatici anomali nel Prospetto I dell'Allegato 1**: per esempio Pavia Gen 4,9 / Feb 1,2 °C, Lecco
    Gen 4,9 > Dic 4,2, Como Gen −0,2, Milano Gen 4,0. I valori sono riportati **tali e quali**, ma vanno confrontati con
    la UNI 10349-1:2016 e con le tabelle di CENED+2.0.
43. **Formule garbled in generale**: tutte le equazioni del PDF sono estratte con pedici e apici separati dai simboli.
    Questo documento ne dà la forma ricostruita. Le ricostruzioni più delicate sono segnalate con [AMB-n]; le altre
    sono coerenti con le norme UNI citate come fonte nel testo.
44. **Tabelle non trascritte qui** (lunghe, non essenziali per il caso base residenziale): coefficienti η_1…η_7 dei
    gruppi frigoriferi (Prospetti 11.LVII-11.LXXV, p. 384-396), cogenerazione (§11.10), UTA e distribuzione aeraulica
    (§8.6), illuminazione (Cap. 6), ascensori (Cap. 12), Appendici G, H, I. Per implementarle vanno estratte dal `.txt`
    alle pagine indicate.
