"""Applicazione web: archivio progetti, input rapido, calcolo, verifiche, export."""
import os
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cened.bilancio import calcola
from cened.esporta_xml import ErroreModello, genera_xml
from cened.progetto import da_dizionario
from cened.rapido import EPOCHE, a_toml, genera_progetto
from cened.scheda import genera_scheda
from cened import comuni
from cened.schema import disponibile as schema_disponibile
from cened.dinamica import dinamica
from cened.igrotermia import glaser
from cened.verifiche import INTERVENTI, verifica
from cened.modello import ESPOSIZIONI

from . import db

QUI = Path(__file__).parent
COOKIE = "sessione"
COOKIE_SECURE = os.environ.get("MARCALETTI_COOKIE_SECURE", "0") == "1"
ETICHETTE_INTERVENTO = {
    "esistente": "APE edificio esistente (verifiche informative)",
    "riqualificazione": "Riqualificazione energetica",
    "ristr2": "Ristrutturazione importante di 2° livello",
    "ristr1": "Ristrutturazione importante di 1° livello",
    "nuova": "Nuova costruzione / ampliamento",
}

@asynccontextmanager
async def _ciclo_vita(_app):
    db.inizializza()
    yield


app = FastAPI(title="Marcaletti — APE e Legge 10", docs_url=None, redoc_url=None, lifespan=_ciclo_vita)
app.mount("/static", StaticFiles(directory=QUI / "static"), name="static")
tpl = Jinja2Templates(directory=QUI / "templates")
tpl.env.filters["num"] = lambda v, d=2: f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


class NonAutenticato(Exception):
    pass


@app.exception_handler(NonAutenticato)
def _vai_al_login(request, exc):
    return RedirectResponse("/login", status_code=303)


def utente(request: Request):
    u = db.utente_da_token(request.cookies.get(COOKIE))
    if u is None:
        raise NonAutenticato()
    return u


def pagina(request, nome, **ctx):
    return tpl.TemplateResponse(request, nome, ctx)


# ---------------- autenticazione ----------------
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return pagina(request, "login.html", errore=None)


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    token = db.autentica(username, password)
    if not token:
        return pagina(request, "login.html", errore="Credenziali non valide")
    r = RedirectResponse("/", status_code=303)
    r.set_cookie(COOKIE, token, httponly=True, secure=COOKIE_SECURE, samesite="lax",
                 max_age=db.DURATA_SESSIONE)
    return r


@app.post("/logout")
def logout(request: Request):
    token = request.cookies.get(COOKIE)
    if token:
        db.chiudi_sessione(token)
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie(COOKIE)
    return r


@app.get("/salute", response_class=PlainTextResponse)
def salute():
    return "ok"


# ---------------- progetti ----------------
@app.get("/", response_class=HTMLResponse)
def elenco(request: Request):
    u = utente(request)
    return pagina(request, "elenco.html", u=u, progetti=db.elenco_progetti(u["id"]),
                  etichette=ETICHETTE_INTERVENTO)


@app.get("/progetti/nuovo", response_class=HTMLResponse)
def nuovo_form(request: Request):
    u = utente(request)
    return pagina(request, "nuovo.html", u=u, climi=db.elenco_climi(u["id"]), epoche=EPOCHE,
                  interventi=ETICHETTE_INTERVENTO, errore=None, v={})


def _lati(form) -> dict:
    lati = {}
    for esp in ("N", "E", "S", "O", "NE", "SE", "SO", "NO"):
        val = form.get(f"lato_{esp}")
        if val:
            lati[esp] = val
    return lati


@app.post("/progetti/nuovo", response_class=HTMLResponse)
async def nuovo(request: Request):
    u = utente(request)
    form = await request.form()
    v = dict(form)
    try:
        clima = db.leggi_clima(u["id"], form["comune"])
        if clima is None:
            raise ValueError(f"mancano i dati climatici di '{form['comune']}': inserirli in 'Dati climatici'")
        dati = {
            "nome": form["nome"].strip() or "Nuovo progetto",
            "comune": form["comune"],
            "anno_costruzione": int(form["anno_costruzione"]),
            "tipologia": form["tipologia"],
            "piano": form.get("piano", "intermedio"),
            "numero_piani": int(form.get("numero_piani") or 1),
            "sotto": form.get("sotto", "terreno"),
            "superficie_utile": float(form["superficie_utile"].replace(",", ".")),
            "altezza_netta": float((form.get("altezza_netta") or "2.70").replace(",", ".")),
            "lati": _lati(form),
            "clima": clima,
        }
        if form.get("lato_lungo"):
            dati["lato_lungo"] = form["lato_lungo"]
        if form.get("vetro") or form.get("telaio"):
            dati["serramenti"] = {k: form[k] for k in ("vetro", "telaio") if form.get(k)}
        imp = {k: form[k] for k in ("generatore", "combustibile", "potenza_kW", "anno_generatore",
                                     "terminali", "regolazione") if form.get(k)}
        if imp:
            dati["impianto"] = {"riscaldamento": imp}
        if not dati["lati"]:
            raise ValueError("indicare almeno un lato")
        progetto = genera_progetto(dati)
        da_dizionario(progetto)  # validazione
    except (ValueError, KeyError) as e:
        return pagina(request, "nuovo.html", u=u, climi=db.elenco_climi(u["id"]), epoche=EPOCHE,
                      interventi=ETICHETTE_INTERVENTO, errore=str(e), v=v)
    pid = db.crea_progetto(u["id"], dati["nome"], a_toml(progetto), dati,
                           form.get("intervento", "esistente"))
    return RedirectResponse(f"/progetti/{pid}", status_code=303)


def _carica(u, pid):
    r = db.leggi_progetto(u["id"], pid)
    if r is None:
        raise NonAutenticato()
    return r


def _analizza(riga):
    """Restituisce (prog, ris, verifiche, errore)."""
    try:
        prog = da_dizionario(tomllib.loads(riga["progetto_toml"]))
        ris = calcola(prog)
        ver = verifica(prog, ris, riga["intervento"])
        return prog, ris, ver, None
    except (ValueError, KeyError, tomllib.TOMLDecodeError, ZeroDivisionError) as e:
        return None, None, [], f"{type(e).__name__}: {e}"


def _analisi_strutture(prog):
    """Per le strutture con stratigrafia: Y_ie/sfasamento e, se c'è l'UR esterna, Glaser."""
    out = {}
    if prog is None:
        return out
    for s in prog.strutture.values():
        if not s.strati or s.verso == "adiacente":
            continue
        voce = {"din": dinamica(s)}
        if prog.clima.ur and s.verso == "esterno":
            voce["glaser"] = glaser(s, prog.clima.te, prog.clima.ur)
        out[s.id] = voce
    return out


@app.get("/progetti/{pid}", response_class=HTMLResponse)
def dettaglio(request: Request, pid: int):
    u = utente(request)
    riga = _carica(u, pid)
    prog, ris, ver, errore = _analizza(riga)
    return pagina(request, "progetto.html", u=u, riga=riga, prog=prog, ris=ris, ver=ver,
                  errore=errore, interventi=ETICHETTE_INTERVENTO, analisi=_analisi_strutture(prog),
                  modello_predefinito=db.leggi_modello(u["id"]))


@app.post("/progetti/{pid}/toml")
def salva_toml(request: Request, pid: int, progetto_toml: str = Form(...), nome: str = Form(...),
               intervento: str = Form("esistente")):
    u = utente(request)
    _carica(u, pid)
    if intervento not in INTERVENTI:
        intervento = "esistente"
    db.aggiorna_progetto(u["id"], pid, progetto_toml=progetto_toml.replace("\r\n", "\n"),
                         nome=nome, intervento=intervento)
    return RedirectResponse(f"/progetti/{pid}", status_code=303)


@app.post("/progetti/{pid}/elimina")
def elimina(request: Request, pid: int):
    u = utente(request)
    db.elimina_progetto(u["id"], pid)
    return RedirectResponse("/", status_code=303)


def _nome_file(riga, est):
    base = "".join(c if c.isalnum() or c in "-_" else "_" for c in riga["nome"])[:60]
    return f'attachment; filename="{base}.{est}"'


@app.get("/progetti/{pid}/progetto.toml")
def scarica_toml(request: Request, pid: int):
    riga = _carica(utente(request), pid)
    return Response(riga["progetto_toml"], media_type="application/toml",
                    headers={"Content-Disposition": _nome_file(riga, "toml")})


@app.get("/progetti/{pid}/scheda.md")
def scarica_scheda(request: Request, pid: int):
    riga = _carica(utente(request), pid)
    prog, ris, _, errore = _analizza(riga)
    if errore:
        return PlainTextResponse(errore, status_code=400)
    return Response(genera_scheda(prog, ris), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": _nome_file(riga, "md")})


def _controlla_modello(contenuto: bytes) -> str | None:
    """Errore se il file non è un calcolo.xml CENED+2.0 utilizzabile, altrimenti None."""
    import xml.etree.ElementTree as ET
    if len(contenuto) > 20 * 1024 * 1024:
        return "file troppo grande (max 20 MB)"
    try:
        radice = ET.fromstring(contenuto)
    except ET.ParseError as e:
        return f"XML non leggibile: {e}"
    if radice.tag != "{http://www.cened.it/cenedplus2/calcolo}calcolo":
        return "non è un calcolo.xml esportato da CENED+2.0"
    return None


@app.post("/progetti/{pid}/modello")
async def carica_modello(request: Request, pid: int, file: UploadFile):
    u = utente(request)
    _carica(u, pid)
    contenuto = await file.read()
    errore = _controlla_modello(contenuto)
    if errore:
        return PlainTextResponse(errore, status_code=400)
    db.aggiorna_progetto(u["id"], pid, modello_xml=contenuto)
    return RedirectResponse(f"/progetti/{pid}", status_code=303)


@app.get("/impostazioni", response_class=HTMLResponse)
def impostazioni(request: Request):
    u = utente(request)
    return pagina(request, "impostazioni.html", u=u, modello=db.leggi_modello(u["id"]), errore=None,
                  xsd=schema_disponibile())


@app.post("/impostazioni/modello", response_class=HTMLResponse)
async def carica_modello_predefinito(request: Request, file: UploadFile):
    u = utente(request)
    contenuto = await file.read()
    errore = _controlla_modello(contenuto)
    if errore:
        return pagina(request, "impostazioni.html", u=u, modello=db.leggi_modello(u["id"]),
                      errore=errore, xsd=schema_disponibile())
    db.salva_modello(u["id"], file.filename or "calcolo.xml", contenuto)
    return RedirectResponse("/impostazioni", status_code=303)


@app.get("/progetti/{pid}/import.xml")
def scarica_xml(request: Request, pid: int):
    import tempfile
    u = utente(request)
    riga = _carica(u, pid)
    modello = riga["modello_xml"] or (db.leggi_modello(u["id"]) or {"xml": None})["xml"]
    if not modello:
        return PlainTextResponse("caricare un calcolo.xml di CENED come modello (nel progetto o in "
                                 "Impostazioni)", status_code=400)
    prog, _, _, errore = _analizza(riga)
    if errore:
        return PlainTextResponse(errore, status_code=400)
    with tempfile.NamedTemporaryFile(suffix=".xml") as t:
        t.write(modello)
        t.flush()
        try:
            xml, avvisi = genera_xml(prog, t.name)
        except ErroreModello as e:
            return PlainTextResponse(f"Modello non utilizzabile: {e}", status_code=400)
    intestazione = "".join(f"<!-- avviso: {a.replace('--', '-')} -->\n" for a in avvisi)
    xml = xml.replace("?>\n", "?>\n" + intestazione, 1)
    return Response(xml, media_type="application/xml",
                    headers={"Content-Disposition": _nome_file(riga, "xml")})


# ---------------- dati climatici ----------------
def _serie(testo: str) -> list[float]:
    valori = [float(x.replace(",", ".")) for x in testo.replace(";", " ").split()]
    if len(valori) != 12:
        raise ValueError("servono 12 valori mensili separati da spazio")
    return valori


@app.get("/climi", response_class=HTMLResponse)
def climi(request: Request):
    u = utente(request)
    return pagina(request, "climi.html", u=u, climi=db.elenco_climi(u["id"]), esposizioni=ESPOSIZIONI,
                  errore=None, nomi_comuni=sorted(comuni.tutti()))


@app.post("/climi", response_class=HTMLResponse)
async def salva_clima(request: Request):
    u = utente(request)
    form = await request.form()
    try:
        comune = form["comune"].strip()
        ufficiale = comuni.cerca(comune)
        zona = form.get("zona_climatica", "").strip().upper() or (ufficiale or {}).get("zc")
        if not zona:
            raise ValueError("indicare la zona climatica")
        dati = {"comune": comune, "provincia": form.get("provincia", "").strip().upper() or None,
                "zona_climatica": zona, "te": _serie(form["te"]), "irradianza": {}}
        if ufficiale:
            dati["codice_istat"] = ufficiale["istat"]
            if not form.get("gg") and ufficiale.get("gg"):
                dati["gg"] = ufficiale["gg"]
        if form.get("ur", "").strip():
            dati["ur"] = _serie(form["ur"])
        if form.get("gg"):
            dati["gg"] = float(form["gg"].replace(",", "."))
        for esp in ESPOSIZIONI:
            if form.get(f"irr_{esp}", "").strip():
                dati["irradianza"][esp] = _serie(form[f"irr_{esp}"])
        from cened.modello import Clima
        Clima(**{k: v for k, v in dati.items()})
    except (ValueError, KeyError, TypeError) as e:
        return pagina(request, "climi.html", u=u, climi=db.elenco_climi(u["id"]), esposizioni=ESPOSIZIONI,
                      errore=str(e), nomi_comuni=sorted(comuni.tutti()))
    dati = {k: v for k, v in dati.items() if v is not None}
    db.salva_clima(u["id"], comune, dati)
    return RedirectResponse("/climi", status_code=303)


@app.post("/climi/{comune}/elimina")
def elimina_clima(request: Request, comune: str):
    u = utente(request)
    db.elimina_clima(u["id"], comune)
    return RedirectResponse("/climi", status_code=303)
