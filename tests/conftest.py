"""Chiusura delle prove dell'interfaccia.

Alla fine della sessione usciamo subito con il codice di pytest, senza far distruggere a Python gli
oggetti Qt rimasti: su Windows la loro distruzione in ordine casuale può causare un "access violation"
anche quando tutte le prove sono passate.
"""
import os
import sys


def pytest_sessionfinish(session, exitstatus):
    if "PySide6.QtWidgets" not in sys.modules:
        return
    try:
        from pmse.ui import suoni
        suoni._chiudi_tutti()
    except Exception:
        pass
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(exitstatus))
