"""Gestione utenti da riga di comando (sul VPS):

    python -m web.utenti crea <username>
    python -m web.utenti password <username>
"""
import getpass
import sys

from . import db


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("crea", "password"):
        sys.exit(__doc__)
    db.inizializza()
    pw = getpass.getpass("Password (min 10 caratteri): ")
    if pw != getpass.getpass("Ripeti password: "):
        sys.exit("Le password non coincidono")
    (db.crea_utente if sys.argv[1] == "crea" else db.cambia_password)(sys.argv[2], pw)
    print("Fatto.")


if __name__ == "__main__":
    main()
