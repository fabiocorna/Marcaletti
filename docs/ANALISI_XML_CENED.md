# Analisi del file `calcolo.xml` esportato da CENED+ 2.0

Esempio analizzato: export del lavoro 2335 (Dalmine, via Doria), motore CENED+ 2.0 v1.1.15.
I file di esempio restano in `esempi/`, che è escluso da git perché contengono dati personali
(codici fiscali di certificatore e proprietari).

Lettura rapida di un export qualsiasi:

```
python cened/leggi_export.py percorso/calcolo.xml          # riepilogo leggibile
python cened/leggi_export.py percorso/calcolo.xml --json   # dati strutturati
```

## 1. Struttura generale

```
c:calcolo
├── c:datiInput/d:certificazione        ← TUTTO ciò che inserisce il certificatore
│   ├── software, configurazioneCalcolo
│   ├── dizionario                      ← librerie + risultati dei "servizi" CENED
│   │   ├── servizioDatiClimatici       (comune ISTAT → GG, zona, T mensili, bin)
│   │   ├── servizioPrecalcolate        (abaco strutture: PAR/PAV/SOF/POR…)
│   │   ├── servizioOpache              (strutture opache: U, spessore, k_i, verso)
│   │   ├── servizioSerramenti          (U_g, U_w, g_n, schermature)
│   │   ├── servizioPonti               (ψ da abaco o inserito dall'utente)
│   │   ├── servizioIrraggiamento       (per esposizione: β, γ, latitudine)
│   │   ├── servizioOmbre               (ostruzioni, aggetti → f_s)
│   │   ├── servizioPortate             (ventilazione naturale/meccanica)
│   │   └── servizioTerminali           (radiatori, fan-coil…)
│   ├── datiAnagrafici                  (certificatore, motivazioni APE)
│   ├── datiEdificio
│   │   ├── ambientiConfinanti          (zone non climatizzate: vano scala, cantina…)
│   │   ├── subalterni/subalterno/zone/zona
│   │   │   ├── geometria               (Su, V lordo, h netta)
│   │   │   ├── capacitaTermica         (metodo tabellare)
│   │   │   ├── dispersioni/dispersione ← ogni superficie: rifOpache|rifSerramenti + area
│   │   │   │                              + ponteTermico(rifPonti, lunghezza)
│   │   │   └── sistemaRisc/Acs/Raf     (terminali, regolazione)
│   │   ├── impianti                    (sistemi, centrali termiche/frigo/elettriche,
│   │   │                                generatori)
│   │   └── sopralluoghi
│   └── campiApe                        (tipologia, interventi migliorativi)
├── c:valoriIntermedi                   ← CALCOLATO (fabbisogni mensili per zona/ZNC)
├── c:datiOutput  (277 attributi)       ← CALCOLATO (EP, classe, rendimenti, rif. edificio)
├── sd:messaggi                         ← avvisi del motore (es. trasmittanza "irragionevole")
├── ns5:licenza                         ← dati licenza del software (uguali in tutti gli export)
└── <!-- ...:QUM|<20 byte base64> -->   ← FIRMA/HASH di integrità del file
```

## 2. Cosa va compilato e cosa calcola CENED

| Blocco | Chi lo produce | Note per la generazione automatica |
|---|---|---|
| `datiEdificio`, `datiAnagrafici`, `campiApe` | certificatore | **generabile** da dati forniti + default tabellari |
| `dizionario/*/input` | certificatore | generabile (U, spessori, aree, orientamenti) |
| `dizionario/*/output` | servizi CENED | in parte calcolabile (U, R, ψ utente); clima, irraggiamento e ombre li calcola CENED |
| `valoriIntermedi`, `datiOutput`, `messaggi` | motore CENED | **da non generare**: li ricalcola CENED |

Collegamenti interni: ogni `dispersione` punta alla libreria tramite `rifOpache`, `rifSerramenti`,
`rifIrraggiamento`, `rifOmbre`, `rifAmbienteConfinante`; i ponti termici tramite `rifPonti`.
Gli `id` devono essere coerenti tra `dizionario` e `datiEdificio`.

## 3. Codici osservati (dall'esempio; da confermare con altri export)

| Attributo | Valore | Significato dedotto |
|---|---|---|
| `tipoStruttura` (precalcolata) | 1 / 2 / 3 / 8 | parete / pavimento / solaio-soffitto / porta |
| `tipoStrutturaOpache` | 1 / 2 / 3 / 5 | parete / pavimento / soffitto / porta |
| `versoDispersione` | 1 / 3 / 6 | verso esterno / verso ZNC / verso ZNC superiore (sottotetto) |
| `codiceStruttura` prefisso | PAR, PAV, SOF, POR, SER | pareti, pavimenti, solai, porte, serramenti |
| `tipoZnc` | 2 | vano scala |
| `destinazioneUso` | 2 | E.1(1) residenziale |
| `tipoGeneratoreCombustione` | 5 | caldaia (tipo da confermare: tradizionale/condensazione) |
| `tipoVettoreEnergetico` | 1 / 8 | gas naturale / energia elettrica |
| `gamma` (irraggiamento) | 0.0 | orientamento Sud (azimut) — nell'esempio tutte le superfici sono a 0° |

Servono **altri export** (con pompa di calore, condensazione, gasolio, pellet, orientamenti diversi,
ultimo piano, villetta) per completare la tabella dei codici. `leggi_export.py --json` serve a questo.

## 4. Punto critico: la firma in fondo al file

Il file termina con un commento del tipo:

```
<!--QUM4NEY4...=:QUM|0FjykR0arHNPq4m1VjTTkx0ry/s=-->
```

La prima parte è la chiave di licenza in base64 (`AC84F8219F…`); la seconda è un'impronta di
20 byte (SHA-1/HMAC) calcolata sul contenuto. Con ogni probabilità CENED la usa per verificare
che il file non sia stato modificato fuori dal programma.

**Conseguenza:** un XML generato o modificato da uno script potrebbe essere rifiutato all'importazione.
Falsificare o ricalcolare questa firma **non è una strada percorribile** (sarebbe aggirare un
controllo di integrità del sistema regionale, e l'APE depositato deve essere affidabile).

Strade corrette, da verificare prima di sviluppare il generatore completo:

1. **Test rapido**: in una copia di un export, cambiare a mano un valore innocuo (es. il nome di
   una struttura) e provare a importarla in CENED+ 2.0.
   - Se viene accettata → la firma non è vincolante e si può procedere con il generatore XML.
   - Se viene rifiutata → servono le strade 2 o 3.
2. **Tracciato ufficiale per software terzi**: gli attributi `dichiarazioneSoftware`,
   `numeroCertificatoSoftware`, `rispondenzaSoftware` mostrano che CENED prevede XML prodotti da
   software commerciali. Si può chiedere ad ARIA S.p.A. / Regione Lombardia lo schema XSD e la
   procedura di accreditamento.
3. **Compilazione assistita**: lo script produce tutti i valori già calcolati (U, aree, ψ, codici,
   generatori) in una scheda ordinata nello stesso ordine delle maschere CENED; l'inserimento
   in CENED resta manuale ma diventa rapido e senza errori.

## 5. Architettura proposta per il generatore

```
dati_forniti.yaml  ──►  completamento con default tabellari  ──►  modello edificio  ──►  XML (o scheda)
(comune, anno,          (U per epoca, serramenti, ψ,             (zone, dispersioni,
 Su, h, piano,           rendimenti, potenze)                     libreria strutture,
 esposizioni,                                                      impianti)
 impianto…)
```

- **Involucro**: superfici calcolate da geometria semplificata (pianta, altezza, posizione
  dell'unità: piano terra / intermedio / ultimo, cielo-terra, villetta), U prese da tabelle per
  epoca costruttiva (abaco UNI/TR 11552, allineato alle strutture "precalcolate" di CENED)
  quando mancano dati misurati.
- **Serramenti**: U_w e g_n per epoca e tipo di vetro (UNI/TS 11300-1, UNI EN ISO 10077).
- **Ponti termici**: ψ da abaco UNI EN ISO 14683 / abaco CENED per tipologia di nodo.
- **Impianti**: modelli per casistica (caldaia tradizionale, a condensazione, pompa di calore,
  split per raffrescamento) presi da export reali, per usare solo codici validi, con potenze e
  anni sostituiti dai dati forniti; rendimenti tabellari UNI/TS 11300-2/-4 quando mancano dati
  di targa.
- **Normativa di riferimento**: DDUO Regione Lombardia n. 18546/2019 e s.m.i., UNI/TS 11300
  parti 1–6, UNI 10349 (clima, calcolato da CENED dal codice ISTAT del comune).

Ogni valore di default applicato viene riportato in un registro, così il certificatore sa
esattamente cosa è stato ipotizzato e può giustificarlo nella relazione e nel sopralluogo.

## 6. Aggiornamento: import da software non autorizzati

CENED+2.0 prevede esplicitamente l'import di XML **parziali** prodotti da software commerciali
non autorizzati (*File > Importa file XML*): il certificatore completa i dati in CENED+2.0 e
da lì calcola ed esporta il file firmato per il Catasto. È la strada adottata da
`cened/esporta_xml.py`, che toglie blocchi calcolati e firma e lascia a CENED il calcolo.
