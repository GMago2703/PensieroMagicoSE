"""Statistiche, verifica di colonne, tabulato dei sistemi (nucleo, senza interfaccia)."""
from math import comb

import numpy as np

from pmse.core import sistemi as sis
from pmse.core import statistiche as st
from pmse.core.gioco import EJ, SE
from tests.test_sistemi import archivio_finto


def _dati(g, n=600):
    est = archivio_finto(g, n)
    return st.Dati(g, [(e.data, sorted(e.numeri), e.jolly, e.superstar, list(e.numeri)) for e in est])


def test_ritardi_serie():
    s = np.array([0, 1, 0, 0, 1, 0, 0, 0], dtype=bool)
    att, mx, med, usc = st.ritardi_serie(s)
    assert (att, mx, usc) == (3, 3, 2) and med == 2.0
    assert st.ritardi_serie(np.zeros(5, dtype=bool))[:2] == (5, 5)


def test_tutte_le_statistiche():
    for g in (SE, EJ):
        d = _dati(g)
        for s in st.statistiche_del_gioco(g):
            t = s.funzione(d, **{p.nome: p.predefinito for p in s.parametri})
            assert t.righe and t.colonne, s.codice
            assert all(len(r) == len(t.colonne) for r in t.righe), s.codice
            assert t.titolo in t.testo() and ";" in t.csv()


def test_numeri_coerenti():
    d = _dati(SE)
    t = st.tutti_i_numeri(d)
    assert sum(r[1] for r in t.righe) == 600 * 6
    M = d.matrice()
    for r in t.righe[:5]:
        x, att = r[0], r[5]
        assert M[-1 - att, x] and not M[len(M) - att:, x].any()


def test_ambi():
    d = _dati(SE)
    t = st.combinazioni_frequenti(d, 2, 0, 4005)
    assert sum(r[1] for r in t.righe) == 600 * 15
    a, b = map(int, t.righe[0][0].split(" - "))
    assert t.righe[0][1] == sum(1 for r in d.righe if a in r[1] and b in r[1])


def test_verifica_colonne():
    d = _dati(SE)
    c = [sorted(d.righe[10][1])]
    e = st.verifica_colonne(c, d.righe, SE)
    assert e.per_colonna[0]["6"] >= 1 and e.estrazioni == 600
    pr = st.probabilita_se()
    assert abs(sum(pr.values()) - sum(comb(6, m) * comb(84, 6 - m) for m in range(2, 7)) / comb(90, 6)) < 1e-12
    ej = _dati(EJ)
    r = ej.righe[5]
    e = st.verifica_colonne([sorted(r[1]) + sorted([r[2], r[3]])], ej.righe, EJ)
    assert e.per_colonna[0]["5+2"] >= 1
    assert abs(sum(st.probabilita_ej().values()) - 1 / 32) < 0.002      # circa 1 su 32 vince qualcosa
    cols = st.colonne_casuali(EJ, 10, 1)
    assert len(cols) == 10 and all(len(c) == 7 for c in cols)


def test_tabulato():
    s = sis.Sistema(nome="prova", tipo="ridotto", gioco="SE", numeri=list(range(1, 11)), garanzia=2)
    sv = sis.sviluppa(s)
    s.colonne = sv.colonne.tolist()
    P = sis.possibili_del_sistema(s)
    t = sis.tabulato(s, s.colonne, garanzia=sis.verifica_garanzia(sv.colonne, P))
    assert "Garanzia n-2" in t and "Punti garantiti in ogni caso: 4" in t
    assert f"COLONNE ({len(s.colonne)})" in t and "PRESENZE" in t
    assert sum(1 for r in t.splitlines() if ")" in r and r.strip()[0].isdigit()) >= 1
