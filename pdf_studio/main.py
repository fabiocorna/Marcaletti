"""Avvio di CRN PDF Studio: ``python main.py [--background] [file.pdf ...]``.

Una sola istanza per utente: un secondo avvio passa i file da aprire a quella già
attiva. Con ``--background`` (avvio con Windows) parte nascosto nell'area di
notifica, pronto a ricevere le stampe della stampante virtuale «CRN PDF».
"""
import getpass
import json
import os
import sys
import traceback


def selftest(report_path: str) -> int:
    """Collaudo dell'eseguibile: carica tutti i moduli, apre un PDF e usa le funzioni
    principali senza mostrare finestre. Scrive l'esito in ``report_path``."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    lines = []
    try:
        import tempfile

        import pymupdf
        from PySide6.QtWidgets import QApplication

        from pdfstudio import dxf_export, p7m, pdfa, printer, textedit  # noqa: F401
        from pdfstudio.mainwindow import MainWindow

        app = QApplication(sys.argv[:1])
        tmp = tempfile.mkdtemp(prefix="crnpdf_selftest_")
        src = os.path.join(tmp, "prova.pdf")
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 100), "Collaudo CRN PDF Studio", fontsize=14)
        page.draw_circle((300, 300), 50)
        doc.save(src)
        win = MainWindow()
        win.open_file(src)
        d = win.doc()
        assert d is not None and d.page_count == 1, "apertura PDF non riuscita"
        lines.append(f"PyMuPDF {pymupdf.VersionBind}")
        assert d.find_replace("Collaudo", "Verifica") == 1
        rep = dxf_export.export_page(d.doc, 0, os.path.join(tmp, "prova.dxf"))
        assert rep.circles == 1, "esportazione DXF non riuscita"
        gs = pdfa.find_ghostscript()
        lines.append(f"Ghostscript: {gs}")
        if gs:
            issues = pdfa.convert_to_pdfa(d.to_bytes(), os.path.join(tmp, "a.pdf"), 2)
            assert pdfa.pdfa_part(os.path.join(tmp, "a.pdf")) == "2B", issues
        d.modified = False
        win.quit_app()
        app.processEvents()
        lines.append("ESITO: OK")
        code = 0
    except Exception:
        lines.append(traceback.format_exc())
        lines.append("ESITO: ERRORE")
        code = 1
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os._exit(code)


if "--selftest" in sys.argv:
    i = sys.argv.index("--selftest")
    selftest(sys.argv[i + 1] if len(sys.argv) > i + 1 else "selftest.txt")

from PySide6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pdfstudio.mainwindow import MainWindow, app_icon  # noqa: E402

SERVER_NAME = "CRNPDFStudio-" + "".join(c for c in getpass.getuser() if c.isalnum())


def _send_to_running(files: list[str], show: bool) -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(500):
        return False
    sock.write(json.dumps({"files": files, "show": show}).encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(2000)
    sock.disconnectFromServer()
    return True


def main() -> int:
    if sys.platform == "win32":
        # Icona corretta nella barra delle applicazioni di Windows
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CRN.PDFStudio")
        except Exception:
            pass
    args = sys.argv[1:]
    background = "--background" in args
    files = [os.path.abspath(a) for a in args if not a.startswith("--")]

    app = QApplication(sys.argv)
    app.setApplicationName("CRN PDF Studio")
    app.setOrganizationName("PDFStudio")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")

    if _send_to_running(files, show=not background):
        return 0

    server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)
    server.listen(SERVER_NAME)

    win = MainWindow()
    if win.tray is not None:
        app.setQuitOnLastWindowClosed(False)

    def on_connection():
        sock = server.nextPendingConnection()

        def read():
            try:
                msg = json.loads(bytes(sock.readAll()).decode("utf-8") or "{}")
            except ValueError:
                return
            for path in msg.get("files", []):
                win.open_file(path)
            if msg.get("show", True) or msg.get("files"):
                win.bring_to_front()
        sock.readyRead.connect(read)
        sock.disconnected.connect(sock.deleteLater)

    server.newConnection.connect(on_connection)

    if not background or files:
        win.show()
    for path in files:
        win.open_file(path)
    win.start_print_watcher()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
