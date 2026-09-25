# Installazione sul VPS

Requisiti: VPS Linux (consigliato Ubuntu 24.04, 2 vCPU / 4 GB RAM; 8 GB se si attiva il motore
CENED), un dominio (es. `ape.tuostudio.it`) con record DNS A verso l'IP del VPS.

## 1. Preparazione (una volta)
```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER   # poi uscire e rientrare
git clone https://github.com/fabiocorna/marcaletti.git && cd marcaletti
```

## 2. Avvio
```bash
DOMINIO=ape.tuostudio.it docker compose up -d --build
docker compose exec app python -m web.utenti crea fabio      # crea l'utente (chiede la password)
```
Caddy ottiene da solo il certificato HTTPS (Let's Encrypt). L'app risponde su `https://<DOMINIO>`.

### Risorse non versionate
Copiare sul VPS, nella cartella `risorse/` del progetto, i file di dati che non stanno nel
repository (es. `comuni_istat.json`): vengono montati in sola lettura nel container.

## 3. Aggiornamento
```bash
git pull && DOMINIO=ape.tuostudio.it docker compose up -d --build
```

## 4. Backup
I dati (utenti, progetti, climi) sono nel volume `dati` (`/dati/marcaletti.db`):
```bash
docker compose exec app sqlite3 /dati/marcaletti.db ".backup /dati/backup.db"   # se sqlite3 presente
docker compose cp app:/dati/marcaletti.db ./backup-$(date +%F).db
```
Programmare il backup con cron e copiarlo fuori dal VPS (contiene dati personali dei clienti).

## 5. Motore CENED+2.0 (facoltativo)
Il servizio `motore` espone il motore di calcolo regionale via HTTP (`POST /calcola`).
Il jar del motore **non è nel repository**: va copiato dalla propria installazione di CENED+2.0
(`cened2-lib-*-full.jar` e librerie collegate) in `motore/engine/`, poi:
```bash
DOMINIO=ape.tuostudio.it docker compose --profile motore up -d --build
```
Il servizio è raggiungibile solo dalla rete interna di Docker (non è esposto su Internet).

> Nota di licenza: il motore è software di Regione Lombardia / ARIA S.p.A. Va usato per le
> proprie certificazioni, dietro login. Metterlo a disposizione di terzi (servizio pubblico o
> software distribuito) richiede la convenzione con ARIA come per le software house autorizzate.

## 6. Sicurezza
- Accesso solo con utente e password (hash scrypt), cookie di sessione `HttpOnly`/`Secure`.
- Aprire sul firewall solo le porte 22, 80, 443 (`sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable`).
- Aggiornare periodicamente il sistema e le immagini (`docker compose pull`).
