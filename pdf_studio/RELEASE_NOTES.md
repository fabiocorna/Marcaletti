## CRN PDF Studio 1.5.1

Lettore ed editor PDF per Windows.

### Download
- **CRNPDFStudio-Setup-1.5.1.exe** — installer (consigliato): menu Start, icona sul desktop, associazione facoltativa di `.pdf` e `.p7m`.
- **CRNPDFStudio-portabile-1.5.1.zip** — versione da scompattare e avviare con `CRNPDFStudio.exe`, senza installazione.

Al primo avvio Windows può mostrare «Windows ha protetto il PC» (programma senza firma digitale): *Ulteriori informazioni → Esegui comunque*.

### Correzioni della 1.5.1 (revisione del codice)
- Salvando (Ctrl+S), stampando o esportando mentre si scrive in un campo del modulo o in un paragrafo, l'ultimo testo digitato ora viene sempre incluso.
- Stampante «CRN PDF»: niente più copie doppie nella cartella Stampe quando Windows tiene ancora bloccato il file.
- Doppio clic su un'evidenziazione o un commento: apre di nuovo il testo del commento.
- Esc annulla la compilazione di un campo e la selezione del testo.
- Annulla/Ripeti usa al massimo circa 400 MB di memoria anche con PDF molto grandi.
- Selezione del testo più rapida sulle pagine con molto testo (tavole, tabelle).
- Aprire molti file insieme da Esplora risorse con il programma già aperto funziona sempre.
- Trova e sostituisci con «maiuscole/minuscole» non segna più il documento come modificato se non sostituisce nulla.

### Novità della 1.5
- **Selezione e copia del testo come in Acrobat**: con lo strumento Mano basta trascinare sul testo (il cursore diventa una «I»); doppio clic seleziona una parola, triplo clic la riga, **Ctrl+A** tutto il testo della pagina, **Ctrl+C** copia. Il testo copiato mantiene i paragrafi interi, pronto da incollare in Word.
- **Clic destro** sul testo selezionato: Copia, Evidenzia, Sottolinea, Barra, Cerca nel documento.
- Strumento *Seleziona testo*: **Alt+trascina** per copiare un riquadro (utile per le tabelle).

### Novità della 1.4
- **Moduli PDF compilabili** come in Acrobat: i campi sono evidenziati in azzurro, si scrive direttamente nel campo, **Tab** / **Maiusc+Tab** per passare al campo successivo o precedente, clic per caselle e pulsanti di scelta, menu a discesa per gli elenchi. Ogni modifica si annulla con Ctrl+Z. Evidenziazione attivabile da *Visualizza → Evidenzia campi dei moduli*.
- **PDF/A riconoscibile**: aprendo un file PDF/A compare una barra verde «✔ Documento PDF/A-2b» con l'esito dei controlli di conformità (anche in Proprietà e nella barra di stato); se lo modifichi, al salvataggio viene proposto di mantenerlo PDF/A.
- **Moduli XFA** (Adobe LiveCycle): quelli ibridi si compilano normalmente e i valori vengono salvati nei campi standard, leggibili da tutti i programmi; per quelli dinamici, che solo Adobe Reader sa mostrare, compare un avviso che spiega cosa fare.

### Correzioni della 1.3.1
- Corretto il blocco all'avvio della 1.3.0 («No such file or directory … layout_rf2.4.1+imf1.yaml»), causato da un aggiornamento automatico della libreria PDF. Le librerie sono ora bloccate sulle versioni collaudate e ogni build verifica il programma installato.

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
