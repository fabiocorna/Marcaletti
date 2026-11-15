# CRN Manutenzione PC

Programma per Windows 10 e 11 che **controlla lo stato del PC** e propone gli interventi per
**pulirlo, ripararlo e aggiornarlo**, un po' come CCleaner, ma senza installazioni né pubblicità
e usando solo gli strumenti ufficiali di Windows.

## Come si usa

1. Scarica la cartella del programma (dalla pagina *Actions* → *CRN Manutenzione PC* → artefatto
   **CRNManutenzione**, oppure dalla Release) ed estraila dove vuoi.
2. Fai doppio clic su **`Avvia CRN Manutenzione.bat`** e rispondi **Sì** alla richiesta di
   Windows (servono i privilegi di amministratore per i controlli completi).
3. Premi **Analizza il PC**: l'analisi **non modifica nulla**, controlla soltanto.
4. Leggi i risultati (verde = a posto, giallo = attenzione, rosso = problema).
   Doppio clic su una riga per i dettagli.
5. Gli interventi consigliati sono già spuntati: togli o aggiungi le spunte e premi
   **Esegui interventi selezionati**.
6. Se vuoi, premi **Salva report** per avere una pagina con il riepilogo.

Il primo intervento dell'elenco crea un **punto di ripristino**, così si può sempre tornare indietro.

## Cosa controlla

| Categoria | Controllo | Intervento |
|---|---|---|
| Protezione | Punto di ripristino | Ne crea uno nuovo |
| Disco | Spazio libero | — (usa le pulizie) |
| Pulizia | File temporanei | Elimina quelli più vecchi di un giorno |
| Pulizia | Cestino | Lo svuota |
| Pulizia | Cache di Chrome, Edge, Brave, Firefox | La svuota (non tocca cronologia, password, preferiti); salta i browser aperti |
| Pulizia | Rapporti errori e file di dump | Li elimina |
| Pulizia | File di installazione degli aggiornamenti | Elimina i download già usati da Windows Update |
| Pulizia | Vecchi componenti di Windows | Pulizia con DISM (finestra separata) |
| Aggiornamenti | Windows Update | Elenca gli aggiornamenti mancanti e apre Windows Update |
| Aggiornamenti | Programmi installati | Li aggiorna tutti con winget (finestra separata) |
| Sicurezza | Antivirus | Aggiorna le definizioni e fa una scansione rapida |
| Sicurezza | Firewall | Lo riattiva se è spento |
| Sistema | Integrità dei file di Windows | DISM + SFC (finestra separata) |
| Sistema | Riavvio in sospeso, giorni dall'ultimo riavvio | — |
| Sistema | Errori di sistema e schermate blu (7 giorni) | Apre il Visualizzatore eventi |
| Sistema | Dispositivi e driver con problemi | Apre Gestione dispositivi |
| Disco | Salute dei dischi (SMART, usura, temperatura) | Ripara il file system delle unità con errori |
| Disco | Ottimizzazione unità | TRIM per SSD, deframmentazione per HDD |
| Prestazioni | Memoria RAM e programmi che ne usano di più | — |
| Prestazioni | Programmi all'avvio | Apre le impostazioni delle app di avvio |
| Rete | Connessione a Internet | Svuota la cache DNS |

## Gli strumenti (schede in alto)

- **Analisi disco**: mostra quanto occupa ogni cartella di un disco, dalla più grande.
  Doppio clic su una cartella per entrarci e scoprire dove finisce lo spazio.
- **File doppi**: trova i file identici (stesso contenuto, verificato con SHA-256) in una
  cartella, ad esempio foto e video copiati due volte. «Seleziona le copie» tiene il file più
  vecchio di ogni gruppo; i file selezionati vanno **nel cestino**, quindi si possono recuperare.
  Le cartelle di Windows, dei programmi e `AppData` vengono sempre saltate.
- **Programmi**: elenco dei programmi installati con editore, versione, dimensione e data,
  ordinabile e con ricerca; il pulsante **Disinstalla** avvia il programma di disinstallazione.
- **Privacy**: cancella a scelta cookie e cronologia di Chrome, Edge, Brave e Firefox, l'elenco
  dei file recenti, la cronologia di «Esegui» e delle ricerche in Esplora file.
  Nulla è selezionato in partenza; i browser aperti vengono saltati.
- **Pulizia automatica**: ogni settimana, nel giorno e all'ora scelti, esegue in silenzio le
  pulizie selezionate (file temporanei, cache dei browser, rapporti errori, file degli
  aggiornamenti, cestino). L'esito finisce nel registro
  `%LOCALAPPDATA%\CRN Manutenzione PC\pulizia.log`. Il programma deve restare nella cartella
  da cui è stata attivata.

Il programma **non** tocca documenti, foto, password, cronologia e impostazioni, **non** "pulisce
il registro" e **non** disattiva servizi di Windows: sono operazioni che di solito fanno più danni
che benefici.

## Uso da riga di comando

```powershell
# elenco dei controlli
powershell -ExecutionPolicy Bypass -File CRNManutenzione.ps1 -Elenco
# analisi con report
powershell -ExecutionPolicy Bypass -File CRNManutenzione.ps1 -Analizza -Report C:\report.html
# interventi scelti (ad esempio da un'attività pianificata)
powershell -ExecutionPolicy Bypass -File CRNManutenzione.ps1 -Esegui temp,cestino,browser,dump
```

## Sviluppo

- `CRNManutenzione.psm1`: tutti i controlli e gli interventi (`Get-ControlliPC`).
- `CRNManutenzione.ps1`: finestra del programma e riga di comando.
- `CRNStrumenti.ps1`: schede degli strumenti (analisi disco, file doppi, programmi, privacy, pulizia automatica).
- `tests/Test-Manutenzione.ps1`: collaudo, eseguito da GitHub Actions su Windows con
  PowerShell 5.1 e 7 (workflow `pc-manutenzione-windows.yml`).

I file `.ps1`/`.psm1` vanno salvati in **UTF-8 con BOM**, altrimenti Windows PowerShell 5.1
mostra male le lettere accentate (il collaudo lo verifica).
