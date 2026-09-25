# Calibrazione del motore (Allegato H) contro CENED+2.0

`python -m cened confronta calcolo.xml` legge un export CENED (componenti con i valori calcolati da
CENED) e ricalcola il fabbisogno invernale con `cened/bilancio_h.py`, confrontandolo mese per mese.

## Verificato esattamente

| Elemento | Esito |
|---|---|
| Temperature mensili del comune (capoluogo corretto per quota, 1/178 °C/m) | identiche |
| Irradiazione su superficie orientata (App. F, isotropo, albedo 0,2) | scarto max 9·10⁻⁶ kWh/m² su 82 superfici |
| U equivalente pavimento su terreno (UNI EN ISO 13370) | identica al 4° decimale |
| H_T della zona (con locali non climatizzati a F_T = 0,40 per `tipoZnc` 2) | identico (A, C) |
| Durata della stagione (γ_lim, troncata al Prospetto I) | identica su 4 casi su 5 |
| Apporti mensili (interni + solari con schermature f_shd, F_gl) | identici su A e C |

## Risultato su EP_H,nd (5 export reali, provincia di Bergamo)

| Caso | Nostro | CENED | Scarto |
|---|---|---|---|
| A (appartamento, molto isolato) | 9,3 | 11,1 | −16 % (valori molto bassi: stagione e 2,1 W/K) |
| B (villa, metodo analitico ZNC/terreno) | ≈ 71 | 69,8 | ≈ +2 % |
| C (appartamento anni '70) | ≈ 110 | 111,0 | ≈ −1 % |
| SUB13 (nuova costruzione) | ≈ 38,8 | 38,0 | ≈ +2 % |
| SUB4 (nuova costruzione) | 41,7 | 41,0 | +1,7 % |

## Punti aperti

1. **2,1 W/K costanti in più nelle perdite di CENED** su A e C (non dipendono dal mese né dalle U):
   termine non ancora identificato (ventilazione? locale non climatizzato?).
2. **Frazioni di mese [AMB-1]**: il ricalcolo della temperatura come media dei valori giornalieri
   interpolati sui giorni riscaldati riduce l'errore di 4 volte, ma non lo annulla.
3. **B e SUB***: apporti diversi del 3–20 % (ombre con aggetti, schermature, serre?) e H_T di B (+1,4 %).
4. `tipoZnc` → riga del Prospetto 3.I dedotta (verificata solo per 2 = 0,40).
5. Capacità termica tabellare (Prospetto D.I) con superficie di riferimento dedotta
   (superfici verticali disperdenti + 2 × superficie utile).
