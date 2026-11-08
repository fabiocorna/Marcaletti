# Bubble Beats

Platform a schermata singola in stile arcade anni '80, con grafica pixel retrò (o HD, a scelta)
e un beat hip hop boom-bap generato in tempo reale (Web Audio API: cassa, rullante, charleston
con swing, basso, accordi Rhodes lo-fi, melodia, scratch e fruscio da vinile).

Protagonisti: **Dexo** (verde, cappellino rosso) e **Mixa** (viola, cappellino azzurro), due
draghetti tondi con il cappellino all'indietro che sparano bolle. Si gioca da soli o in due.

## Come giocare

Apri `index.html` in un browser (desktop o telefono). Non serve installare nulla.
Nel menu iniziale scegli **1 GIOCATORE** o **2 GIOCATORI** (frecce ↑↓ oppure tasti 1/2, poi Invio).

| Azione | Giocatore 1 | Giocatore 2 | Touch |
|---|---|---|---|
| Muovi | A D | ← → | ◀ ▶ |
| Salta | W | ↑ | SALTA |
| Bolla (tieni premuto per la raffica) | Spazio / F | Invio / . / 0 tastierino | BOLLA |

In modalità 1 giocatore vanno bene entrambi gli schemi di tasti. Sono supportati anche fino a due
gamepad (A salta, X/B bolla, Start pausa).

Altri tasti: **P** pausa · **M** musica on/off · **R** stile pixel/HD (anche con i pulsanti ♪ e PX).

## Regole

- Colpisci un nemico con la bolla per intrappolarlo, poi tocca la bolla per farla scoppiare.
- Le bolle a contatto scoppiano a catena: ogni nemico in più nella stessa catena raddoppia i punti
  (1000, 2000, 4000…).
- Tieni premuto SALTA mentre atterri su una bolla per rimbalzarci sopra e salire.
- I nemici sconfitti diventano bonus: monete, microfoni, cassette, gemme e corone.
- La **bolla dorata** (cassa 808) emette un'onda d'urto che elimina i nemici vicini.
- Se resti troppo in un livello compare «SBRIGATI!»: nemici più veloci e beat più rapido.
- Cadendo dal varco nel pavimento si riappare dall'alto.
- Nemici: stereo portatili che camminano, bombolette spray che sparano vernice, vinili volanti.
- In due, ognuno ha 3 vite e il proprio punteggio; la partita finisce quando entrambi le hanno perse.

8 livelli disegnati a mano, poi livelli generati all'infinito con difficoltà crescente.
Record e stile grafico vengono salvati nel browser.
