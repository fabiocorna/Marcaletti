"""Stampante virtuale «CRN PDF»: da qualsiasi programma si stampa e si ottiene un PDF.

La stampante usa il driver «Microsoft Print To PDF» di Windows con una porta che
scrive su un file fisso (``%ProgramData%\\CRN PDF Studio\\spool\\stampa.pdf``).
CRN PDF Studio, attivo nell'area di notifica, controlla quel file: quando una
stampa è completa la sposta in ``Documenti\\CRN PDF Studio\\Stampe`` e la apre.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

PRINTER_NAME = "CRN PDF"


def spool_dir() -> str:
    base = os.environ.get("ProgramData") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "CRN PDF Studio", "spool")


def port_file() -> str:
    return os.path.join(spool_dir(), "stampa.pdf")


def output_dir() -> str:
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    if sys.platform == "win32":
        try:  # cartella Documenti reale (anche se spostata su OneDrive o altro disco)
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # CSIDL_PERSONAL
            if buf.value:
                docs = buf.value
        except Exception:
            pass
    return os.path.join(docs, "CRN PDF Studio", "Stampe")


def is_complete_pdf(path: str) -> bool:
    """Il PDF è stato scritto per intero (termina con %%EOF)?"""
    try:
        size = os.path.getsize(path)
        if size < 64:
            return False
        with open(path, "rb") as f:
            head = f.read(5)
            f.seek(max(0, size - 1024))
            tail = f.read()
        return head == b"%PDF-" and b"%%EOF" in tail
    except OSError:
        return False


def unique_name(folder: str, when: datetime | None = None) -> str:
    when = when or datetime.now()
    base = f"Stampa {when:%Y-%m-%d %H.%M.%S}"
    path = os.path.join(folder, base + ".pdf")
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{base} ({n}).pdf")
        n += 1
    return path


def collect(port: str, out_folder: str) -> str | None:
    """Sposta la stampa completata nella cartella delle stampe. Ritorna il nuovo percorso."""
    if not os.path.exists(port) or not is_complete_pdf(port):
        return None
    os.makedirs(out_folder, exist_ok=True)
    dest = unique_name(out_folder)
    try:
        os.replace(port, dest)
    except OSError:
        # Il file può essere ancora bloccato dallo spooler oppure su un altro disco
        try:
            import shutil
            shutil.copyfile(port, dest)
            os.remove(port)
        except OSError:
            if os.path.exists(dest) and not os.path.exists(port):
                return dest
            return None
    return dest


class PrintWatcher(QObject):
    """Controlla periodicamente la porta della stampante e segnala i nuovi PDF."""

    pdfReady = Signal(str)

    def __init__(self, port: str | None = None, out_folder: str | None = None, interval_ms: int = 800,
                 parent=None):
        super().__init__(parent)
        self.port = port or port_file()
        self.out_folder = out_folder or output_dir()
        self._last: tuple[float, int] | None = None
        self._timer = QTimer(self, interval=interval_ms, timeout=self.check)

    def start(self) -> None:
        self._timer.start()
        self.check()

    def stop(self) -> None:
        self._timer.stop()

    def check(self) -> None:
        try:
            st = os.stat(self.port)
        except OSError:
            self._last = None
            return
        sig = (st.st_mtime, st.st_size)
        # Si raccoglie solo quando dimensione e data sono stabili tra due controlli
        if sig != self._last:
            self._last = sig
            return
        path = collect(self.port, self.out_folder)
        if path:
            self._last = None
            self.pdfReady.emit(path)


# ------------------------------------------------------------- installazione
def _tools_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "tools")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")


def _powershell(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    kwargs = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", *args],
                          capture_output=True, text=True, timeout=timeout, **kwargs)


def is_installed() -> bool:
    if sys.platform != "win32":
        return False
    try:
        r = _powershell(["-Command", f"if (Get-Printer -Name '{PRINTER_NAME}' -ErrorAction SilentlyContinue) "
                                     "{ 'si' } else { 'no' }"])
        return r.stdout.strip() == "si"
    except Exception:
        return False


def run_elevated(script: str) -> bool:
    """Esegue uno script PowerShell come amministratore (richiesta UAC). Ritorna False se annullato."""
    if sys.platform != "win32":
        raise RuntimeError("La stampante virtuale è disponibile solo su Windows")
    path = os.path.join(_tools_dir(), script)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    import ctypes
    params = f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{path}"'
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", params, None, 0)
    if rc <= 32:
        return False
    # Attende che la stampante compaia (fino a 30 s)
    want = script.startswith("install")
    for _ in range(60):
        if is_installed() == want:
            return True
        time.sleep(0.5)
    return is_installed() == want
