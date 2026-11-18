"""Copie dei dati (backup e ripristino), registro delle giocate, simulatore, testo incollato."""
from datetime import date, datetime, timedelta

import pytest

from pmse.core import backup
from pmse.core.db import Archivio
from pmse.core.gioco import EJ, SE
from tests.test_sistemi import archivio_finto


N = {}


def _archivi(tmp_path):
    perc = {"SE": tmp_path / "se.db", "EJ": tmp_path / "ej.db"}
    for c, g in (("SE", SE), ("EJ", EJ)):
        a = Archivio(perc[c], gioco=g)
        a.unisci(archivio_finto(g, 60))
        N[c] = a.conta()
        a.scrivi_impostazione("gemini_api_key", "SEGRETA")
        a.scrivi_impostazione("sistemi_salvati", '[1, 2]')
        a.chiudi()
    return perc


def test_copia_e_ripristino(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    perc = _archivi(tmp_path)
    z = tmp_path / "copia.zip"
    c = backup.crea(z, perc)
    assert c.programmi["SE"]["estrazioni"] == N["SE"] > 40 and c.programmi["EJ"]["sistemi"] == 2
    assert backup.leggi(z).programmi.keys() == {"SE", "EJ"}
    # senza chiavi
    z2 = tmp_path / "senza.zip"
    backup.crea(z2, perc, chiavi=False)
    # si rovina l'archivio SE e si ripristina solo quello
    a = Archivio(perc["SE"], gioco=SE)
    a.cancella_tutto() if hasattr(a, "cancella_tutto") else a.con.execute("DELETE FROM estrazioni")
    a.con.commit()
    assert a.conta() == 0
    a.chiudi()
    assert backup.ripristina(z, ["SE"], perc) == ["SE"]
    a = Archivio(perc["SE"], gioco=SE)
    assert a.conta() == N["SE"] and a.leggi_impostazione("gemini_api_key") == "SEGRETA"
    a.chiudi()
    assert backup.ripristina(z2, ["EJ"], perc) == ["EJ"]
    a = Archivio(perc["EJ"], gioco=EJ)
    assert a.conta() == N["EJ"] and not a.leggi_impostazione("gemini_api_key")
    a.chiudi()
    assert any("prima_del_ripristino" in p.name for p in backup.cartella_copie().iterdir())
    with pytest.raises(ValueError):
        (tmp_path / "x.zip").write_text("non è una copia")
        backup.leggi(tmp_path / "x.zip")


def test_copie_automatiche(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    perc = _archivi(tmp_path)
    t0 = datetime(2026, 1, 1, 10, 0, 0)
    assert backup.automatica_se_serve(7, 3, perc, t0)
    assert backup.automatica_se_serve(7, 3, perc, t0 + timedelta(days=2)) is None
    for i in range(1, 6):
        backup.automatica_se_serve(7, 3, perc, t0 + timedelta(days=8 * i))
    assert len(backup.automatiche()) == 3


def _righe(g, n=300):
    est = archivio_finto(g, n)
    return [(e.data, sorted(e.numeri), e.jolly, e.superstar, list(e.numeri)) for e in est]


def test_giocate_spoglio_e_quote(tmp_path):
    from pmse.core import giocate as gc
    from pmse.core import vincite
    righe = _righe(SE)
    r0 = righe[100]
    # una colonna uguale all'estrazione (6), una con 5 + jolly, una con la SuperStar giusta
    c6 = list(r0[1])
    c51 = sorted(r0[1][:5] + [r0[2]])
    c_ss = [x for x in range(1, 91) if x not in r0[1]][:6]
    gi = gc.Giocata("SE", [c6, c51, c_ss], [[], [], [r0[3]]], dal=r0[0].isoformat(), concorsi=3,
                    costo=gc.costo_giocata(SE, [c6, c51, c_ss], [[], [], [r0[3]]]))
    assert gi.costo == 3.5
    v = vincite.Vincite(r0[0].isoformat(), q6=1e7, q51=5e5, q5=3e4, q4=300, q3=25, q2=5,
                        qs={"0": 5.0, "1": 10.0, "2": 100.0})
    quote = gc.Quote(g=SE, dati={r0[0].isoformat(): v})
    e = gc.esito(SE, gi, righe, quote)
    cat = {(x.data, x.categoria) for x in e.vincite}
    assert (r0[0], "6") in cat and (r0[0], "5+1") in cat and (r0[0], "SS0") in cat
    assert e.vinto >= 1e7 + 5e5 + 5 and len(e.concorsi_estratti) == 3 and e.spesa == 3 * 3.5
    # registro: salva, carica, avvisi solo per le estrazioni nuove
    a = Archivio(tmp_path / "g.db", gioco=SE)
    gc.aggiungi(a, gi)
    tutte = gc.carica(a)
    nuove = gc.nuove_vincite(SE, tutte, righe, quote)
    assert nuove and nuove[0][1] and len(nuove[0][2]) == 3
    assert gc.nuove_vincite(SE, tutte, righe, quote) == []
    a.chiudi()


def test_giocate_ej_e_simulatore():
    from pmse.core import giocate as gc
    from pmse.core import vincite_ej
    righe = _righe(EJ)
    r0 = righe[50]
    col = list(r0[1])
    gi = gc.Giocata("EJ", [col], [[r0[2], r0[3]]], dal=r0[0].isoformat(), concorsi=1, costo=2.0)
    q = gc.Quote(g=EJ, dati={r0[0].isoformat(): vincite_ej.VinciteEJ(r0[0].isoformat(), {"5+2": 5e7})})
    e = gc.esito(EJ, gi, righe, q)
    assert [x.categoria for x in e.vincite] == ["5+2"] and e.vinto == 5e7
    s = gc.simula(EJ, [col], [[r0[2], r0[3]]], righe, righe[0][0], righe[-1][0], q, 2.0)
    assert s.estrazioni == len(righe) and s.spesa == 2.0 * len(righe) and s.vinto >= 5e7
    assert sum(a for a, _ in s.per_anno.values()) == s.spesa


def test_testo_incollato():
    from pmse.core.testo import leggi_riga, numeri_da_testo
    assert leggi_riga(" 1)  3 15 27 44 61 88   SuperStar 42", 6) == ([3, 15, 27, 44, 61, 88], {"superstar": [42]})
    assert leggi_riga("3 15 27 44 49 + 2 11", 5) == ([3, 15, 27, 44, 49], {"euro": [2, 11]})
    assert numeri_da_testo("Sistema  3  7 12 21\n2) 5 9") == [3, 7, 12, 21, 5, 9]


def test_quote_dalle_pagine():
    from pathlib import Path
    from pmse.core import vincite, vincite_ej
    d = Path(__file__).parent / "dati"
    v = vincite.analizza_pagina((d / "vincite_17-11-2026.html").read_text(encoding="utf-8"), date(2026, 11, 17))
    assert v.q3 == 14.48 and v.q2 == 5.0 and v.qs["3"] == 1448.0
    v = vincite.analizza_pagina((d / "vincite_03-01-1998.html").read_text(encoding="utf-8"), date(1998, 1, 3))
    assert 13 < v.q3 < 14                                              # lire convertite in euro
    assert vincite.jackpot_da_pagina((d / "se_home.html").read_text(encoding="utf-8")) == 55_900_000
    e = vincite_ej.analizza_pagina((d / "ej_risultato_17-11-2026.html").read_text(encoding="utf-8"),
                                   date(2026, 11, 17))
    assert e.quote["5+2"] == 38370583.3 and e.vincitori["2+1"] == 456310 and e.jackpot == 76741167
