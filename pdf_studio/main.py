"""Avvio di PDF Studio: ``python main.py [file.pdf ...]``."""
import sys

from PySide6.QtWidgets import QApplication

from pdfstudio.mainwindow import MainWindow, app_icon


def main() -> int:
    if sys.platform == "win32":
        # Icona corretta nella barra delle applicazioni di Windows
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PDFStudio.PDFStudio")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Studio")
    app.setOrganizationName("PDFStudio")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    for path in sys.argv[1:]:
        win.open_file(path)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
