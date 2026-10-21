"""Avvio di CRN PDF Studio: ``python main.py [--background] [file.pdf ...]``.

Una sola istanza per utente: un secondo avvio passa i file da aprire a quella già
attiva. Con ``--background`` (avvio con Windows) parte nascosto nell'area di
notifica, pronto a ricevere le stampe della stampante virtuale «CRN PDF».
"""
import getpass
import json
import os
import sys

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from pdfstudio.mainwindow import MainWindow, app_icon

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
