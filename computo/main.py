"""Avvio di CRN Computo: ``python main.py [progetto.crcm]``.

Con ``--selftest percorso.txt`` collauda l'eseguibile senza mostrare finestre.
"""
import os
import sys
import traceback


def _shutdown(app, win, code: int) -> None:
    """Chiusura ordinata: prima la finestra, poi l'applicazione Qt, poi il processo.

    Su Windows uscire con la finestra Qt ancora viva fa andare in crash lo scarico delle
    librerie (0xC0000005, «il programma ha smesso di funzionare»): distruggerle prima
    lo evita. Le impostazioni sono già salvate alla chiusura della finestra."""
    import shiboken6
    if win is not None and shiboken6.isValid(win):
        win.close()
        shiboken6.delete(win)
    if app is not None and shiboken6.isValid(app):
        app.processEvents()
        app.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


def selftest(report_path: str) -> None:
    """Carica tutti i moduli, crea un progetto con una voce, lo salva, lo riapre e
    produce le stampe. Scrive l'avanzamento in ``report_path`` passo per passo, così
    un blocco o un crash indicano dove sono avvenuti."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    log = open(report_path, "w", encoding="utf-8", buffering=1)
    import faulthandler
    faulthandler.enable(log)               # su Windows registra anche gli access violation
    if sys.platform == "win32":
        import ctypes
        # niente finestra «il programma ha smesso di funzionare»: il collaudo non si blocca
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)

    def step(text):
        log.write(text + "\n")
        log.flush()
        os.fsync(log.fileno())

    app = win = None
    try:
        import tempfile
        from decimal import Decimal

        from PySide6.QtWidgets import QApplication

        from crncomputo import assistant, export
        from crncomputo.mainwindow import MainWindow
        from crncomputo.model import Articolo, Misura
        step("moduli caricati")

        app = QApplication(sys.argv[:1])
        app.setOrganizationName("CRN")
        app.setApplicationName("CRN Computo Selftest")
        tmp = tempfile.mkdtemp(prefix="crncomputo_selftest_")
        win = MainWindow()
        step("finestra creata")
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
        step("progetto salvato e riaperto")
        export.export_computo_pdf(win.doc.p, os.path.join(tmp, "c.pdf"))
        export.export_xlsx(win.doc.p, os.path.join(tmp, "c.xlsx"))
        step("stampe PDF ed Excel")
        assert assistant.validate_input("leggi_progetto", {}) is None
        win.doc.modified = False
        step("ESITO: OK")
        code = 0
    except Exception:
        step(traceback.format_exc())
        step("ESITO: ERRORE")
        code = 1
    faulthandler.disable()
    log.close()
    _shutdown(app, win, code)


def main() -> int:
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        selftest(sys.argv[i + 1] if len(sys.argv) > i + 1 else "selftest.txt")
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
    code = app.exec()
    win.settings.sync()
    _shutdown(app, win, code)
    return code


if __name__ == "__main__":
    sys.exit(main())
