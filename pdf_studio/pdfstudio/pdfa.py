"""Conversione in PDF/A tramite Ghostscript e controlli di base di conformità.

Ghostscript viene cercato (in ordine) nella cartella dell'applicazione
(``ghostscript/bin``, incluso nell'installer), nel PATH e nelle installazioni
standard di Windows (``C:\\Program Files\\gs``).
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import tempfile

import pymupdf

LEVELS = {
    "PDF/A-1b (ISO 19005-1)": 1,
    "PDF/A-2b (ISO 19005-2) — consigliato": 2,
    "PDF/A-3b (ISO 19005-3)": 3,
}


class PdfAError(Exception):
    pass


def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resource(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", _app_dir())
    return os.path.join(base, *parts)


def find_ghostscript() -> str | None:
    candidates = []
    for name in ("gswin64c.exe", "gswin32c.exe", "gs"):
        candidates.append(os.path.join(_app_dir(), "ghostscript", "bin", name))
    for name in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for pf in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
        if pf:
            candidates += sorted(glob.glob(os.path.join(pf, "gs", "gs*", "bin", "gswin*c.exe")), reverse=True)
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return subprocess.run(cmd, capture_output=True, timeout=timeout, **kwargs)


def _icc_profile(gs: str, level: int) -> str:
    """Profilo sRGB per l'OutputIntent. PDF/A-1 richiede un profilo ICC v2."""
    if level >= 2:
        own = _resource("assets", "srgb.icc")
        if os.path.exists(own):
            return own
    # Profili v2 distribuiti con Ghostscript
    gs_root = os.path.dirname(os.path.dirname(gs))
    for p in (os.path.join(gs_root, "iccprofiles", "default_rgb.icc"),
              "/usr/share/color/icc/ghostscript/default_rgb.icc",
              "/usr/share/ghostscript/iccprofiles/default_rgb.icc"):
        if os.path.exists(p):
            return p
    # Le build Windows di Ghostscript includono i profili nella ROM interna
    return "%rom%iccprofiles/default_rgb.icc"


def _ps_string(path: str) -> str:
    return "(" + path.replace("\\", "/").replace("(", r"\(").replace(")", r"\)") + ")"


def convert_to_pdfa(pdf_bytes: bytes, out_path: str, level: int = 2, title: str | None = None) -> list[str]:
    """Converte in PDF/A-<level>b. Ritorna l'elenco di eventuali problemi residui."""
    gs = find_ghostscript()
    if not gs:
        raise PdfAError("Ghostscript non trovato. Installarlo da https://ghostscript.com/releases/gsdnld.html "
                        "oppure usare l'installer completo di PDF Studio, che lo include.")
    # Ghostscript non accetta PDF cifrati: lavora su una copia in chiaro e senza JavaScript
    src = pymupdf.open("pdf", pdf_bytes)
    if src.is_encrypted:
        raise PdfAError("Il PDF/A non può essere protetto da password: rimuovere prima la protezione.")
    for page in src:
        for annot in page.annots() or []:
            # Le annotazioni devono essere stampabili e avere un aspetto (requisito PDF/A)
            annot.set_flags(annot.flags | pymupdf.PDF_ANNOT_IS_PRINT)
            try:
                annot.update()
            except Exception:
                pass
    if title is not None or not src.metadata.get("title"):
        meta = dict(src.metadata)
        meta["title"] = title or meta.get("title") or os.path.splitext(os.path.basename(out_path))[0]
        src.set_metadata(meta)
    data = src.tobytes(garbage=3, deflate=True)
    src.close()

    icc = _icc_profile(gs, level)
    with tempfile.TemporaryDirectory(prefix="pdfstudio_") as tmp:
        inp = os.path.join(tmp, "in.pdf")
        out = os.path.join(tmp, "out.pdf")
        defs = os.path.join(tmp, "PDFA_def.ps")
        with open(inp, "wb") as f:
            f.write(data)
        with open(defs, "w", encoding="ascii") as f:
            f.write(PDFA_DEF.format(icc=_ps_string(icc)))
        cmd = [gs, f"-dPDFA={level}", "-dBATCH", "-dNOPAUSE", "-dQUIET", "-dNOOUTERSAVE",
               "-dPDFACompatibilityPolicy=1", "-sColorConversionStrategy=RGB",
               "-sProcessColorModel=DeviceRGB", "-dEmbedAllFonts=true", "-dSubsetFonts=true",
               "-sDEVICE=pdfwrite", f"--permit-file-read={tmp.replace(os.sep, '/')}/",
               f"--permit-file-read={icc.replace(os.sep, '/')}",
               f"-sOutputFile={out}", defs, inp]
        if level == 1:
            cmd.insert(1, "-dCompatibilityLevel=1.4")
        proc = _run(cmd)
        if proc.returncode != 0 or not os.path.exists(out):
            err = (proc.stderr or proc.stdout or b"").decode("utf-8", "replace")[-1500:]
            raise PdfAError(f"Conversione non riuscita:\n{err}")
        shutil.move(out, out_path)
    issues = check_pdfa(out_path)
    # PDF/A-1 non ammette trasparenze: Ghostscript converte quelle pagine in immagini
    before = pymupdf.open("pdf", data)
    after = pymupdf.open(out_path)
    rasterized = [i + 1 for i in range(min(before.page_count, after.page_count))
                  if before[i].get_text().strip() and not after[i].get_text().strip()]
    before.close()
    after.close()
    if rasterized:
        issues.append("Pagine convertite in immagine (testo non più selezionabile): "
                      + ", ".join(map(str, rasterized))
                      + ". Contengono trasparenze non ammesse in PDF/A-1: usare PDF/A-2b.")
    return issues


def check_pdfa(path_or_bytes) -> list[str]:
    """Controlli essenziali (non sostituisce un validatore completo come veraPDF)."""
    doc = pymupdf.open(path_or_bytes) if isinstance(path_or_bytes, str) else pymupdf.open("pdf", path_or_bytes)
    issues = []
    try:
        if doc.is_encrypted or doc.needs_pass:
            issues.append("Il documento è cifrato")
        xmp = doc.get_xml_metadata() or ""
        if "pdfaid:part" not in xmp:
            issues.append("Metadati XMP di identificazione PDF/A mancanti")
        cat = doc.pdf_catalog()
        if "OutputIntents" not in doc.xref_object(cat):
            issues.append("OutputIntent (profilo colore) mancante")
        missing = set()
        for page in doc:
            for f in page.get_fonts(full=True):
                if f[1] == "n/a":
                    missing.add(f[3])
        if missing:
            issues.append("Font non incorporati: " + ", ".join(sorted(missing)))
        if "/JavaScript" in doc.xref_object(cat) or "/JS" in doc.xref_object(cat):
            issues.append("Il documento contiene JavaScript")
    finally:
        doc.close()
    return issues


def pdfa_part(path_or_bytes) -> str | None:
    """Ritorna es. '2B' se il file (percorso, bytes o documento aperto) dichiara la conformità PDF/A."""
    if isinstance(path_or_bytes, pymupdf.Document):
        xmp = path_or_bytes.get_xml_metadata() or ""
    else:
        doc = pymupdf.open(path_or_bytes) if isinstance(path_or_bytes, str) else pymupdf.open("pdf", path_or_bytes)
        try:
            xmp = doc.get_xml_metadata() or ""
        finally:
            doc.close()
    import re
    part = re.search(r"pdfaid:part(?:>|=[\"'])(\d)", xmp)
    conf = re.search(r"pdfaid:conformance(?:>|=[\"'])([ABU])", xmp, re.I)
    if not part:
        return None
    return part.group(1) + (conf.group(1).upper() if conf else "")


# Definizione dell'OutputIntent sRGB per Ghostscript (da PDFA_def.ps)
PDFA_DEF = """%!
/ICCProfile {icc} def
[/_objdef {{icc_PDFA}} /type /stream /OBJ pdfmark
[{{icc_PDFA}} << /N 3 >> /PUT pdfmark
[{{icc_PDFA}} ICCProfile (r) file /PUT pdfmark
[/_objdef {{OutputIntent_PDFA}} /type /dict /OBJ pdfmark
[{{OutputIntent_PDFA}} <<
  /Type /OutputIntent
  /S /GTS_PDFA1
  /DestOutputProfile {{icc_PDFA}}
  /OutputConditionIdentifier (sRGB IEC61966-2.1)
  /Info (sRGB IEC61966-2.1)
  /RegistryName (http://www.color.org)
>> /PUT pdfmark
[{{Catalog}} << /OutputIntents [ {{OutputIntent_PDFA}} ] >> /PUT pdfmark
"""
