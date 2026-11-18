"""Chiusura pulita delle prove dell'interfaccia.

Alla fine della sessione chiudiamo e distruggiamo le finestre rimaste e usciamo subito con il codice di
pytest: la distruzione automatica degli oggetti Qt durante lo spegnimento di Python, in ordine casuale,
su Windows può causare un "access violation" anche quando tutte le prove sono passate.
"""
import os
import sys


def pytest_sessionfinish(session, exitstatus):
    qt = sys.modules.get("PySide6.QtWidgets")
    if qt is None:
        return
    app = qt.QApplication.instance()
    if app is None:
        return
    try:
        from pmse.ui import suoni
        suoni._chiudi_tutti()
    except Exception:
        pass
    for w in app.topLevelWidgets():
        try:
            w.close()
            w.deleteLater()
        except Exception:
            pass
    app.processEvents()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(exitstatus))
