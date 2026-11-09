"""Avvio di CRN Computo: ``python main.py [progetto.crcm]``.

Con ``--selftest percorso.txt`` collauda l'eseguibile senza mostrare finestre.
"""
import os
import sys
import traceback


class _Stop(Exception):
    pass


def selftest(report_path: str, fase: int = 99, uscita: str = "terminate") -> int:
    """Carica tutti i moduli, crea un progetto con una voce, lo salva, lo riapre e
    produce le stampe. Scrive l'avanzamento in ``report_path`` passo per passo, così
    un blocco o un crash indicano dove sono avvenuti.

    Per la diagnosi su Windows: ``--fase N`` si ferma dopo la fase N (1 Qt, 2 moduli del
    programma, 3 QApplication, 4 finestra) e ``--uscita terminate|exit|normale`` sceglie
    come terminare il processo."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    log = open(report_path, "w", encoding="utf-8", buffering=1)
    import faulthandler
    faulthandler.enable(log)               # su Windows registra anche gli access violation
    if sys.platform == "win32":
        import ctypes
        # niente finestra «il programma ha smesso di funzionare»: il collaudo non si blocca
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)

    def step(text, n=None):
        log.write(text + "\n")
        log.flush()
        os.fsync(log.fileno())
        if n is not None and n >= fase:
            raise _Stop

    app = win = None
    try:
        import tempfile
        from decimal import Decimal

        from PySide6.QtWidgets import QApplication
        step("Qt caricato", 1)

        from crncomputo import assistant, export
        from crncomputo.mainwindow import MainWindow
        from crncomputo.model import Articolo, Misura
        step("moduli caricati", 2)

        app = QApplication(sys.argv[:1])
        app.setOrganizationName("CRN")
        app.setApplicationName("CRN Computo Selftest")
        step("QApplication creata", 3)
        tmp = tempfile.mkdtemp(prefix="crncomputo_selftest_")
        win = MainWindow()
        step("finestra creata", 4)
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
        win.close()
        step("finestra chiusa")
        win.deleteLater()
        app.processEvents()
        step("finestra distrutta")
        step("ESITO: OK")
        code = 0
    except _Stop:
        step(f"ESITO: OK (fermato alla fase {fase})")
        code = 0
    except Exception:
        step(traceback.format_exc())
        step("ESITO: ERRORE")
        code = 1
    step(f"uscita: {uscita}")
    if uscita == "normale":
        faulthandler.disable()
        log.close()
        return code
    if uscita == "exit":
        os._exit(code)
    faulthandler.disable()
    log.close()
    _hard_exit(code)
    return code


def _hard_exit(code: int) -> None:
    """Esce senza lo smontaggio delle librerie: su Windows lo scarico delle DLL di Qt
    con l'applicazione ancora attiva può andare in crash e cambiare il codice di uscita."""
    sys.stdout.flush()
    sys.stderr.flush()
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        # tipi espliciti: senza, l'handle a 64 bit viene troncato e la chiamata fallisce
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k.TerminateProcess.restype = wintypes.BOOL
        k.TerminateProcess(k.GetCurrentProcess(), code & 0xFFFFFFFF)
    os._exit(code)


def main() -> int:
    if "--selftest" in sys.argv:
        def arg(name, default):
            return sys.argv[sys.argv.index(name) + 1] if name in sys.argv[:-1] else default
        return selftest(arg("--selftest", "selftest.txt"), int(arg("--fase", "99")),
                        arg("--uscita", "terminate"))
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
    # Impostazioni già salvate in closeEvent: si esce senza lo smontaggio di Qt, che su
    # Windows può terminare con un crash e il messaggio «il programma ha smesso di funzionare».
    win.settings.sync()
    _hard_exit(code)
    return code


if __name__ == "__main__":
    sys.exit(main())
