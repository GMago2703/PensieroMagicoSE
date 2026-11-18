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
    if sys.platform == "win32":          # termina senza le notifiche di chiusura delle DLL (Qt)
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        k.TerminateProcess(k.GetCurrentProcess(), int(exitstatus))
    os._exit(int(exitstatus))
