"""Connessioni HTTPS sicure su ogni sistema.

Su Windows bastano i certificati di sistema. Su Android Python non sempre li trova da solo
(errore CERTIFICATE_VERIFY_FAILED): qui si caricano esplicitamente quelli del pacchetto certifi
e, se presenti, quelli di sistema di Android. La verifica dei certificati resta sempre attiva.
"""
from __future__ import annotations

import os
import ssl

CARTELLE_ANDROID = ("/apex/com.android.conscrypt/cacerts", "/system/etc/security/cacerts")
_contesto: ssl.SSLContext | None = None


def contesto_ssl() -> ssl.SSLContext:
    global _contesto
    if _contesto is None:
        c = ssl.create_default_context()
        try:
            import certifi
            c.load_verify_locations(cafile=certifi.where())
        except Exception:        # certifi non installato (es. versione Windows): restano quelli di sistema
            pass
        for cartella in CARTELLE_ANDROID:
            if os.path.isdir(cartella):
                try:
                    c.load_verify_locations(capath=cartella)
                except Exception:
                    pass
        _contesto = c
    return _contesto
