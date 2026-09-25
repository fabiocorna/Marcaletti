"""Archivio SQLite: utenti, sessioni, progetti, dati climatici per comune."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.environ.get("MARCALETTI_DB", os.path.join(os.path.dirname(__file__), "..", "dati", "marcaletti.db"))
DURATA_SESSIONE = 7 * 24 * 3600

SCHEMA = """
CREATE TABLE IF NOT EXISTS utenti (
    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, hash TEXT NOT NULL, sale TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessioni (
    token TEXT PRIMARY KEY, utente_id INTEGER NOT NULL REFERENCES utenti(id), scadenza REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS progetti (
    id INTEGER PRIMARY KEY, utente_id INTEGER NOT NULL REFERENCES utenti(id),
    nome TEXT NOT NULL, intervento TEXT NOT NULL DEFAULT 'esistente',
    dati_rapidi TEXT, progetto_toml TEXT NOT NULL, modello_xml BLOB,
    creato REAL NOT NULL, modificato REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS climi (
    id INTEGER PRIMARY KEY, utente_id INTEGER NOT NULL REFERENCES utenti(id),
    comune TEXT NOT NULL, dati TEXT NOT NULL, UNIQUE(utente_id, comune)
);
"""


@contextmanager
def connessione():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def inizializza():
    with connessione() as con:
        con.executescript(SCHEMA)


# ---------------- utenti e sessioni ----------------
def _hash(password: str, sale: str) -> str:
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(sale), n=2 ** 14, r=8, p=1).hex()


def crea_utente(username: str, password: str):
    if len(password) < 10:
        raise ValueError("la password deve avere almeno 10 caratteri")
    sale = secrets.token_hex(16)
    with connessione() as con:
        con.execute("INSERT INTO utenti (username, hash, sale) VALUES (?, ?, ?)",
                    (username, _hash(password, sale), sale))


def cambia_password(username: str, password: str):
    if len(password) < 10:
        raise ValueError("la password deve avere almeno 10 caratteri")
    sale = secrets.token_hex(16)
    with connessione() as con:
        n = con.execute("UPDATE utenti SET hash = ?, sale = ? WHERE username = ?",
                        (_hash(password, sale), sale, username)).rowcount
    if not n:
        raise ValueError(f"utente '{username}' inesistente")


def autentica(username: str, password: str) -> str | None:
    with connessione() as con:
        u = con.execute("SELECT * FROM utenti WHERE username = ?", (username,)).fetchone()
        if u is None or not hmac.compare_digest(u["hash"], _hash(password, u["sale"])):
            return None
        token = secrets.token_urlsafe(32)
        con.execute("DELETE FROM sessioni WHERE scadenza < ?", (time.time(),))
        con.execute("INSERT INTO sessioni VALUES (?, ?, ?)", (token, u["id"], time.time() + DURATA_SESSIONE))
        return token


def utente_da_token(token: str | None):
    if not token:
        return None
    with connessione() as con:
        return con.execute(
            "SELECT u.id, u.username FROM sessioni s JOIN utenti u ON u.id = s.utente_id "
            "WHERE s.token = ? AND s.scadenza > ?", (token, time.time())).fetchone()


def chiudi_sessione(token: str):
    with connessione() as con:
        con.execute("DELETE FROM sessioni WHERE token = ?", (token,))


# ---------------- progetti ----------------
def elenco_progetti(utente_id: int):
    with connessione() as con:
        return con.execute("SELECT id, nome, intervento, modificato FROM progetti WHERE utente_id = ? "
                           "ORDER BY modificato DESC", (utente_id,)).fetchall()


def leggi_progetto(utente_id: int, pid: int):
    with connessione() as con:
        return con.execute("SELECT * FROM progetti WHERE id = ? AND utente_id = ?", (pid, utente_id)).fetchone()


def crea_progetto(utente_id: int, nome: str, toml: str, dati_rapidi: dict | None, intervento="esistente") -> int:
    ora = time.time()
    with connessione() as con:
        cur = con.execute(
            "INSERT INTO progetti (utente_id, nome, intervento, dati_rapidi, progetto_toml, creato, modificato) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (utente_id, nome, intervento, json.dumps(dati_rapidi) if dati_rapidi else None, toml, ora, ora))
        return cur.lastrowid


def aggiorna_progetto(utente_id: int, pid: int, **campi):
    ammessi = {"nome", "intervento", "progetto_toml", "modello_xml", "dati_rapidi"}
    campi = {k: v for k, v in campi.items() if k in ammessi}
    if not campi:
        return
    sets = ", ".join(f"{k} = ?" for k in campi) + ", modificato = ?"
    with connessione() as con:
        con.execute(f"UPDATE progetti SET {sets} WHERE id = ? AND utente_id = ?",
                    (*campi.values(), time.time(), pid, utente_id))


def elimina_progetto(utente_id: int, pid: int):
    with connessione() as con:
        con.execute("DELETE FROM progetti WHERE id = ? AND utente_id = ?", (pid, utente_id))


# ---------------- climi ----------------
def elenco_climi(utente_id: int):
    with connessione() as con:
        return [dict(r) | {"dati": json.loads(r["dati"])} for r in
                con.execute("SELECT * FROM climi WHERE utente_id = ? ORDER BY comune", (utente_id,))]


def leggi_clima(utente_id: int, comune: str):
    with connessione() as con:
        r = con.execute("SELECT dati FROM climi WHERE utente_id = ? AND comune = ?", (utente_id, comune)).fetchone()
        return json.loads(r["dati"]) if r else None


def salva_clima(utente_id: int, comune: str, dati: dict):
    with connessione() as con:
        con.execute("INSERT INTO climi (utente_id, comune, dati) VALUES (?, ?, ?) "
                    "ON CONFLICT(utente_id, comune) DO UPDATE SET dati = excluded.dati",
                    (utente_id, comune, json.dumps(dati)))


def elimina_clima(utente_id: int, comune: str):
    with connessione() as con:
        con.execute("DELETE FROM climi WHERE utente_id = ? AND comune = ?", (utente_id, comune))
