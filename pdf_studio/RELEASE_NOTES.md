## CRN PDF Studio 1.3.0

Lettore ed editor PDF per Windows.

### Download
- **CRNPDFStudio-Setup-1.3.0.exe** — installer (consigliato): menu Start, icona sul desktop, associazione facoltativa di `.pdf` e `.p7m`.
- **CRNPDFStudio-portabile-1.3.0.zip** — versione da scompattare e avviare con `CRNPDFStudio.exe`, senza installazione.

Al primo avvio Windows può mostrare «Windows ha protetto il PC» (programma senza firma digitale): *Ulteriori informazioni → Esegui comunque*.

### Novità della 1.3
- **Nuovo nome: CRN PDF Studio** (aggiornando dalla versione precedente, «PDF Studio» viene sostituito).
- **Stampante virtuale «CRN PDF»**: da qualsiasi programma si sceglie Stampa → CRN PDF e si ottiene un PDF, che si apre subito ed è salvato in Documenti\CRN PDF Studio\Stampe.
- Il programma resta nell'area di notifica per ricevere le stampe e può avviarsi con Windows.
- L'installer richiede ora i privilegi di amministratore (necessari per installare la stampante).

### Novità della 1.2
- **Esportazione in DXF** dei disegni vettoriali (File → Esporta → Esporta in DXF): linee, curve, cerchi, retini, tratteggi e testi, con i layer del CAD originale, scala del disegno e unità a scelta.

### Novità della 1.1
- **Modifica del testo esistente** direttamente sulla pagina, con a capo automatico e font originale; modifica di singole righe (Maiusc+clic); **Trova e sostituisci** (Ctrl+H).
- **File firmati .p7m**: apertura, elenco dei firmatari e verifica di integrità delle firme; estrazione dei contenuti non PDF (es. fatture XML).
- **Salva come PDF/A** (1b, 2b, 3b), con Ghostscript incluso; file validati con veraPDF.

### Funzioni già presenti
Lettura e ricerca, commenti ed evidenziazioni, disegno e forme, firma grafica, bianchetto e oscuramento, moduli compilabili, gestione pagine (ruota, elimina, riordina, estrai, dividi, unisci), PDF da immagini, filigrana, numeri di pagina, password, riduzione dimensione, esportazione in immagini, testo e Word.

### Note
- La verifica dei .p7m controlla l'integrità crittografica, non l'attendibilità del certificatore né la revoca del certificato.
- In PDF/A-1b le pagine con trasparenze vengono convertite in immagini: preferire PDF/A-2b.
