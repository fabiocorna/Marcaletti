# Codici CENED+2.0 ricavati da export reali

Fonte: 5 `calcolo.xml` reali (CENED+2.0 v1.1.14–1.1.15, tutti validi contro l'XSD), provincia di
Bergamo, appartamenti esistenti, villa e nuova costruzione. Dove il significato è dedotto dal
contesto è indicato "(dedotto)". Da integrare con altri export (pompe di calore, split, ecc.).

## Strutture opache (`servizioOpache/opache/input`)

| Attributo | Valore | Significato |
|---|---|---|
| `tipoStrutturaOpache` (= `tipoStruttura`) | 1 | parete |
| | 2 | pavimento |
| | 3 | soffitto (verso ambiente interno) |
| | 4 | copertura |
| | 5 | porta / portoncino |
| | 6 | cassonetto |
| `versoDispersione` (= `versoDispersioneOpache`) | 1 | verso esterno |
| | 2 | verso terreno (pavimento riferito da `servizioTerreno`) |
| | 3 | verso zona non climatizzata (vano scala, box, vano tecnico) |
| | 5 | verso altra zona/unità climatizzata (divisori, solai tra appartamenti) |
| | 6 | partizione interna alla zona (tramezzi, contropareti) — conta per la capacità termica |
| `coloreEsterno` | 1, 2, 3 | colore superficie esterna (dedotto: 1 chiaro, 2 medio, 3 scuro) |
| `pontiTermici` | true/false | struttura con ponti termici associati |
| `tipoPosIsolante` | 3 | posizione isolante (3 = esterno/cappotto, dedotto) |
| `codice` | PAR1001, PAV…, SOF…, POR…, CAS… | codice libero con prefisso per tipo |

Strati (`datiStrato`, dall'interno all'esterno, `posStrato` 1…n):

| `tipoStrato` | `categoriaStrato` | Uso | Valori |
|---|---|---|---|
| 2 | 16 | resistenza superficiale ("ADDUTTANZE UNI EN ISO 6946") | `r_i`, `rho_i`=1.2 |
| 1 | 13 (e altre) | materiale omogeneo | `lambda_i`, `rho_i`, `c_i` [kJ/kgK], `d_i` [**mm**] |
| 1 | 13 | materiale a resistenza nota (blocchi) | `r_i`, `rho_i`, `c_i`, `d_i` |
| 3 | 6 | intercapedine d'aria | `lambda_i` equivalente, `rho_i`=1.3, `d_i` |

Materiali (`servizioMateriali/materiale`): `input codiceMateriale="MUR1022" custom="true" nome=…`,
`output codiceCategoria codiceTipologia codiceCarattTermica rho lambda|r s mu c_p`.
`codiceCarattTermica` 2 = definito da λ, 1 = definito da R. `codiceTipologia` 1 = materiale,
2 = resistenza superficiale, 3 = intercapedine.

## Dispersioni (`zona/dispersioni/dispersione`)

- Opache: `rifOpache`, `area` (lorda), `areaNetta`, `colorazione` (= colore), `rifIrraggiamento`,
  `rifOmbre` (se verso esterno), nessun `verso`.
- Serramenti: `verso="esterno"`, `rifSerramenti`, `rifIrraggiamento`, `rifOmbre`; l'area è quella
  del serramento (`a_w` in output del servizio).
- Terreno: `verso="terreno"`, `rifTerreno` → `servizioTerreno` (UNI EN ISO 13370): `tipoElemento`=1
  pavimento su terreno, `p` perimetro esposto, `a` area, `lambda_g`=2.0, `rifOpacheGf` struttura del
  pavimento, `r_gf` = R_si+R_f+R_se, `w_w` spessore muri [mm], `k_i_pav`, `tipoIsolamento`=1 (nessun
  isolamento perimetrale). Verificato: `cened/terreno.py` riproduce `u_b` di CENED al 4° decimale.
- Più serramenti uguali: una dispersione per ciascuno, tutte con lo stesso `rifSerramenti`, senza `area`.
- Ponti: `<ponteTermico rifPonti lunghezza/>`; ponti utente `custom="true" psi_e_utente psi_i_utente`.

## Serramenti (`servizioSerramenti/serramenti/input`)

`doppio="false"` (serramento singolo, dati nel gruppo `…2`): `tipoVetro2`=2, `tipoGas2` 1/2,
`u_g_2`, `a_g_2`, `a_t_2` (area telaio), `tipoTelaio2` 2/3, `u_t_2`, `l_g_2`, `tipoDistanziatore2` 1/2,
`psi_g_2` 0.06/0.08, `epsilon_ne_2`, `chiusura` + `tipoChiusura`/`tipoPermChiusura`/`deltaR`,
`tipoSchermatura` 1/6/7, `tipoPosizSchermatura`, `tipoColoreSchermatura`.

## Irraggiamento e ombre

- `irraggiamento/input`: `phi_gradi`, `phi_primi` (latitudine), `z` (quota), `beta` (90 verticale,
  0 orizzontale), `gamma` (0 Sud, −90 Est, +90 Ovest, 180 Nord); `datiMensili mese=0..11 h_bh h_dh`
  = irradiazione diretta e diffusa sul piano orizzontale della località (uguale per tutte le
  esposizioni dello stesso comune).
- `ombre/input`: `trasparente`, `rifIrraggiamento`, `beta`, `gamma`, aggetti/ostruzioni
  (`a_h b_h c_h alpha_h`, `a_o b_o alpha_o`, `c_f_sx d_f_sx …`), `rifSerramenti` per i trasparenti.

## Zona, subalterno, ZNC

- `zona`: `destinazioneUso`=2 per E.1(1) residenziale; `pubblico`, `acsAttivo`, `riscAttivo`…
- `geometria`: `superficieUtile`, `superficieLorda`, `volumeNetto`, `volumeLordo`, `altezzaMediaNetta`.
- `subalterno`: `periodoCostruzione` 1/2 (1 = esistente, 2 = nuova costruzione, dedotto),
  `intervalloTemporale` (1 ante 1930 … 7 post 2006), `anno`.
- `zonaNonClimatizzata`: `tipoZnc` 2 (vano scala), 3, 12; `apportiTrascurabili`, `volumeNetto`.
- `configurazioneCalcolo`: `dispersioniProfiloLordo`, `metodoAnaliticoZNCTerreno`,
  `metodoCapacitaTermicaPuntuale`, `metodoTabellareDistribuzioneACS`, `certificazione`.
