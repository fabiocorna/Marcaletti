# Analisi: cosa serve per un software APE compatibile CENED+2.0

## 1. Quadro normativo e tecnico

- **Regione Lombardia**: DGR 3868/2015, DDUO 2456/2017 e **DDUO 18546/2019** e s.m.i.
  (procedura di calcolo, format APE, obblighi del certificatore).
- **Calcolo**: UNI/TS 11300 parti 1–6 (involucro, impianti di riscaldamento/ACS, raffrescamento,
  rinnovabili, energia primaria, trasporto), UNI EN ISO 6946, 10077-1, 13786, 13370, 14683,
  UNI 10349 (dati climatici), UNI/TR 11552 (abaco strutture).
- **Motore di calcolo**: l'APE lombardo è calcolato solo dal **motore CENED+2.0** gestito da
  ARIA S.p.A.; il Catasto (CEER) accetta solo XML prodotti da quel motore.
  - Le software house **autorizzate** (convenzione con ARIA) integrano il motore e generano
    direttamente l'XML da depositare.
  - I software **non autorizzati** possono produrre XML *parziali* (involucro, parte degli
    impianti) da importare in CENED+2.0 con *File > Importa file XML*; il certificatore
    completa i dati in CENED+2.0, calcola ed esporta il file firmato.

**Conseguenza per questo progetto:** la strada conforme e percorribile subito è la seconda.
La firma/impronta in fondo al `calcolo.xml` non va riprodotta né aggirata (vedi
ANALISI_XML_CENED.md §4): la produce CENED+2.0 al momento del calcolo. Per diventare
software "autorizzato" (deposito diretto senza passare dal client CENED) serve la
convenzione con ARIA S.p.A., che fornisce motore e specifiche: è un passo commerciale/formale,
non tecnico, da valutare più avanti.

## 2. Cosa è fatto (fase 1 — involucro)

- [x] Modello dati del progetto (TOML) con registro ipotesi.
- [x] Trasmittanza strutture opache, intercapedini, k_i, massa superficiale.
- [x] Serramenti: U_w da U_g, U_f, ψ_g; tabelle di default per vetro/telaio.
- [x] Ponti termici con ψ inserito dall'utente, ZNC con b_tr.
- [x] Pre-calcolo UNI/TS 11300-1 mensile di Q_H,nd, H'_T.
- [x] Scheda di compilazione assistita.
- [x] Generatore XML "a modello" (sperimentale, da validare con import reale).
- [x] Lettore di export CENED.

## 3. Cosa serve dal certificatore (bloccante per la validazione)

1. **Alcuni `calcolo.xml` reali** esportati da CENED+2.0 (in `esempi/`, esclusi da git):
   villetta, ultimo piano, piano terra su cantina/terreno, con caldaia a condensazione,
   pompa di calore, split. Servono a completare la tabella dei codici
   (`versoDispersione` verso terreno/adiacente, `tipoZnc`, generatori, vettori).
2. **Un XML prodotto da un software commerciale per l'import** (es. Namirial Termo,
   "esporta per CENED"): mostra esattamente quale sottoinsieme di dati CENED accetta in
   import da software non autorizzati — è il riferimento più prezioso.
3. **Test di import**: importare in CENED+2.0 l'XML generato da `python -m cened xml` e
   annotare errori/avvisi.
4. **Installazione di CENED+2.0 per Linux**: permetterebbe di eseguire il test di import
   in automatico e di leggere lo schema XSD eventualmente incluso nel pacchetto
   (solo a fini di interoperabilità, nel rispetto della licenza d'uso).

## 4. Prossime fasi

- **Fase 2 — involucro completo**: pavimenti su terreno (UNI EN ISO 13370), abaco ponti
  termici (UNI EN ISO 14683 / abaco CENED), ombreggiamenti (aggetti, ostruzioni),
  verifica igrometrica (Glaser, UNI EN ISO 13788), dati climatici UNI 10349 per tutti i
  comuni lombardi.
- **Fase 3 — impianti**: UNI/TS 11300-2 (riscaldamento e ACS: emissione, regolazione,
  distribuzione, generazione), -3 (raffrescamento), -4 (pompe di calore, FV, solare
  termico), -5 (energia primaria, fattori di conversione), per EP_gl,nren ed EP_gl,ren
  indicativi; export dei blocchi impianto nell'XML.
- **Fase 4 — classe e interventi**: edificio di riferimento (DM 26/06/2015), stima
  della classe, raccomandazioni di intervento con confronto costi/benefici.
- **Fase 5 — interfaccia**: applicazione grafica (web locale) per inserimento dati,
  disegno semplificato di pianta, gestione progetti.
