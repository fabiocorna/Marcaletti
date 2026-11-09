"""Avvio di CRN Computo: ``python main.py [progetto.crcm]``.

Con ``--selftest percorso.txt`` collauda l'eseguibile senza mostrare finestre.
"""
import os
import sys
import traceback


def selftest(report_path: str) -> int:
    """Carica tutti i moduli, crea un progetto con una voce, lo salva, lo riapre e
    produce tutte le stampe. Scrive l'esito in ``report_path``."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    lines = []
    try:
        import tempfile
        from decimal import Decimal

        from PySide6.QtWidgets import QApplication

        from crncomputo import assistant, export
        from crncomputo.mainwindow import MainWindow
        from crncomputo.model import Articolo, Misura

        app = QApplication(sys.argv[:1])
        app.setOrganizationName("CRN")
        app.setApplicationName("CRN Computo Selftest")
        tmp = tempfile.mkdtemp(prefix="crncomputo_selftest_")
        win = MainWindow()
        d = win.doc
        d.set_articolo(Articolo("A.01", "Intonaco civile", "m²", Decimal("20")))
        cap = d.add_capitolo("Finiture")
        d.add_voce("A.01", cap.id, [Misura("Parete", "2", "4", "", "2,5")])
        win.refresh()
        assert d.p.totale_voci() == Decimal("400.00"), "calcolo"
        path = os.path.join(tmp, "prova.crcm")
        d.save(path)
        win.open_project(path)
        assert win.doc.p.totale_voci() == Decimal("400.00"), "riapertura"
        export.export_computo_pdf(win.doc.p, os.path.join(tmp, "c.pdf"))
        export.export_xlsx(win.doc.p, os.path.join(tmp, "c.xlsx"))
        assert assistant.validate_input("leggi_progetto", {}) is None
        win.doc.modified = False
        win.close()
        win.deleteLater()
        app.processEvents()
        lines.append("ESITO: OK")
        code = 0
    except Exception:
        lines.append(traceback.format_exc())
        lines.append("ESITO: ERRORE")
        code = 1
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    _hard_exit(code)


def _hard_exit(code: int) -> None:
    """Esce senza lo smontaggio delle librerie: su Windows lo scarico delle DLL di Qt
    con l'applicazione ancora attiva può andare in crash e cambiare il codice di uscita."""
    sys.stdout.flush()
    sys.stderr.flush()
    if sys.platform == "win32":
        import ctypes
        k = ctypes.windll.kernel32
        k.TerminateProcess(k.GetCurrentProcess(), code)
    os._exit(code)


def main() -> int:
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        return selftest(sys.argv[i + 1] if len(sys.argv) > i + 1 else "selftest.txt")
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CRN.Computo")
        except Exception:
            pass
    from PySide6.QtWidgets import QApplication

    from crncomputo.mainwindow import MainWindow, app_icon

    app = QApplication(sys.argv)
    app.setOrganizationName("CRN")
    app.setApplicationName("CRN Computo")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    if files:
        win.open_project(os.path.abspath(files[0]))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
