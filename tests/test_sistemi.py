"""Sistemi: condizioni, sviluppo, riduzione a garanzia, riduzioni pronte, spoglio, memorizzazione."""
import random
from datetime import date, timedelta
from itertools import combinations

import numpy as np
import pytest

from pmse.core import condizioni as cnd
from pmse.core import ridotti_pronti
from pmse.core import sistemi as sis
from pmse.core.db import Archivio
from pmse.core.gioco import EJ, SE
from pmse.core.modello import Estrazione


def archivio_finto(g=SE, n=800, seme=3):
    rnd, out, d = random.Random(seme), [], date(2012, 3, 2)
    while len(out) < n:
        if d.weekday() in g.giorni_estrazione:
            nums = rnd.sample(range(1, g.n + 1), g.k)
            if g.is_ej:
                e = rnd.sample(range(1, g.euro_max(d) + 1), 2)
                out.append(Estrazione(d, nums, e[0], e[1], gioco=EJ))
            else:
                resto = [x for x in range(1, 91) if x not in nums]
                out.append(Estrazione(d, nums, rnd.choice(resto), rnd.randint(1, 90)))
        d += timedelta(days=1)
    return out


def test_valori_condizioni_come_a_mano():
    ctx = cnd.Contesto(SE, archivio_finto())
    rng = np.random.default_rng(1)
    C = np.sort(np.argsort(rng.random((300, 90)), axis=1)[:, :6] + 1, axis=1)
    for r, c in zip(C.tolist(), range(300)):
        pass
    a_mano = {
        "somme": lambda r: sum(r), "pari": lambda r: sum(x % 2 == 0 for x in r),
        "consecutivi": lambda r: sum(b - a == 1 for a, b in zip(r, r[1:])),
        "cifre": lambda r: len({x % 10 for x in r}), "decine": lambda r: len({(x - 1) // 10 for x in r}),
        "distanza_globale": lambda r: r[-1] - r[0], "distanza_massima": lambda r: max(b - a for a, b in zip(r, r[1:])),
        "simmetrie": lambda r: sum(1 for a, b in combinations(r, 2) if a + b == 91),
        "differenziata": lambda r: sum(1 for a, b in combinations(r, 2) if b - a == 2),
        "alti": lambda r: sum(x > 45 for x in r),
    }
    for codice, f in a_mano.items():
        v = cnd.TIPI_PER_CODICE[codice].funzione(C, ctx, 2)
        assert v.tolist() == [f(r) for r in C.tolist()], codice
    # sequenze: blocchi di consecutivi
    S = np.array([[1, 2, 3, 10, 20, 21], [5, 7, 9, 11, 13, 15], [1, 2, 4, 5, 7, 8]])
    assert cnd.v_sequenze(S, ctx, 0).tolist() == [2, 0, 3]
    # ripetizioni con l'archivio: una colonna uguale a un'estrazione = 6
    uscita = sorted(ctx.estrazioni[10].numeri)
    assert cnd.v_ripetizioni(np.array([uscita]), ctx, 0)[0] == 6


def test_analisi_e_suggerimento():
    ctx = cnd.Contesto(SE, archivio_finto())
    a = cnd.analizza("pari", ctx)
    assert a.piu_frequente in (2, 3, 4) and "più comune" in a.suggerimento
    assert abs(sum(r[2] for r in a.righe) - 100) < 1e-6
    c = cnd.consigliata("somme", ctx)
    assert c.minimo < 273 < c.massimo
    for t in cnd.tipi_del_gioco(SE):
        cnd.analizza(t.codice, ctx, t.param_def)          # nessuna condizione va in errore
    rend = cnd.rendimento([cnd.consigliata("pari", ctx), cnd.consigliata("somme", ctx)], ctx)
    assert rend[-1][0] == "Tutte le condizioni insieme" and 40 < rend[-1][1] < 100


def test_filtro_errori_e_gruppi():
    ctx = cnd.Contesto(SE, archivio_finto())
    C = np.array(list(combinations(range(1, 16), 6)), dtype=np.int16)
    pari3 = cnd.Condizione("pari", valori=[3])
    somma = cnd.Condizione("somme", minimo=40, massimo=50)
    ok0 = cnd.filtra(C, [pari3, somma], ctx, 0, 0)
    ok1 = cnd.filtra(C, [pari3, somma], ctx, 0, 1)
    att0 = [(sum(x % 2 == 0 for x in r) == 3) and 40 <= sum(r) <= 50 for r in C.tolist()]
    att1 = [(sum(x % 2 == 0 for x in r) == 3) or 40 <= sum(r) <= 50 for r in C.tolist()]
    assert ok0.tolist() == att0 and ok1.tolist() == att1
    gr = cnd.gruppo([1, 2, 3, 4], 2, 2)
    assert cnd.filtra(C, [gr], ctx).tolist() == [len({1, 2, 3, 4} & set(r)) == 2 for r in C.tolist()]
    filtro = cnd.Condizione("filtro", combinazioni=[[1, 2, 3, 4, 5, 6]], minimo=0, massimo=3)
    assert cnd.filtra(C, [filtro], ctx).tolist() == [len({1, 2, 3, 4, 5, 6} & set(r)) <= 3 for r in C.tolist()]
    assert cnd.da_json(cnd.a_json([gr, filtro]))[1].combinazioni == [[1, 2, 3, 4, 5, 6]]


@pytest.mark.parametrize("n,j", [(9, 1), (12, 1), (14, 2), (18, 3), (20, 4)])
def test_ridotto_garantisce(n, j):
    s = sis.Sistema(tipo="ridotto", numeri=list(range(31, 31 + n)), garanzia=j, qualita=8)
    sv = sis.sviluppa(s)
    assert len(sv.colonne) < sv.integrale
    assert sis.verifica_garanzia(sv.colonne, sv.possibili_colonne).garantiti >= 6 - j


def test_condizionato_ridotto_con_fisse():
    ctx = cnd.Contesto(SE, archivio_finto())
    s = sis.Sistema(tipo="condizionato_ridotto", numeri=list(range(1, 25)), fisse=[7], garanzia=2,
                    condizioni=cnd.a_json([cnd.Condizione("pari", valori=[2, 3, 4])]))
    sv = sis.sviluppa(s, ctx)
    assert all(7 in c for c in sv.colonne.tolist())
    assert all(2 <= sum(x % 2 == 0 for x in c) <= 4 for c in sv.colonne.tolist())
    assert sis.verifica_garanzia(sv.colonne, sv.possibili_colonne).garantiti >= 4


def test_riduzioni_pronte_tutte_garantite():
    tab = ridotti_pronti.tabella()
    assert len(tab) > 300
    for chiave, schema in tab.items():
        k, n, f, punti = map(int, chiave.split("/"))
        numeri = list(range(1, n + 1))
        C = ridotti_pronti.applica(numeri, numeri[:f], k, punti)
        P = np.vstack(list(sis.integrale(numeri, k, numeri[:f])))
        assert sis.verifica_garanzia(C, P).garantiti >= punti, chiave
        assert all(set(numeri[:f]) <= set(c) for c in C.tolist()), chiave


def test_immediato_e_spoglio():
    s = sis.Sistema(tipo="immediato", numeri=[3, 8, 15, 22, 34, 41, 56, 67, 72, 88], garanzia=1)
    sv = sis.sviluppa(s)
    assert len(sv.colonne) == len(ridotti_pronti.tabella()["6/10/0/5"])
    r = sis.spoglio(sv.colonne, [3, 8, 15, 22, 34, 41], 88)
    assert r["6"] + r["5+1"] + r["5"] >= 1
    st = sis.spoglio_storico(sv.colonne, archivio_finto(), SE, 100)
    assert st["estrazioni"] == 100 and len(st["migliori"]) == 100
    ej = sis.Sistema(tipo="immediato", gioco="EJ", numeri=list(range(10, 20)), garanzia=1)
    svj = sis.sviluppa(ej)
    rj = sis.spoglio(svj.colonne, [10, 11, 12, 13, 14], None, EJ)
    assert set(rj) == {"5", "4", "3", "2"} and rj["5"] + rj["4"] >= 1


def test_limiti_e_validazione():
    with pytest.raises(ValueError):
        sis.sviluppa(sis.Sistema(tipo="ridotto", numeri=[1, 2, 3], garanzia=1))
    with pytest.raises(ValueError):
        sis.sviluppa(sis.Sistema(tipo="ridotto", numeri=list(range(1, 11)), garanzia=0))
    with pytest.raises(ValueError):
        sis.sviluppa(sis.Sistema(tipo="condizionato", numeri=list(range(1, 91))))      # integrale enorme
    assert sis.costo(10, SE, {}, superstar=True) == 15 and sis.costo(10, EJ) == 20


def test_memorizzazione(tmp_path):
    a = Archivio(tmp_path / "a.db", gioco=SE)
    s = sis.Sistema(nome="Prova 1", tipo="ridotto", numeri=list(range(1, 11)), garanzia=2)
    s.colonne = sis.sviluppa(s).colonne.tolist()
    sis.salva(a, s)
    letto = sis.salvati(a)["Prova 1"]
    assert letto.colonne == s.colonne and letto.creato
    assert "Garanzia n-2" in letto.descrizione()
    sis.elimina(a, "Prova 1")
    assert sis.salvati(a) == {}
    a.chiudi()


def test_gruppi_tra():
    from pmse.core.gioco import SE
    est = archivio_finto(SE, 400)
    ctx = cnd.Contesto(SE, est)
    c = cnd.gruppi_tra([([1, 2, 3, 4, 5], 1, 2), ([10, 11, 12, 13, 14], 1, 1), ([20, 21, 22], 0, 1)])
    s = sis.Sistema(tipo="condizionato", gioco="SE", numeri=list(range(1, 23)), condizioni=cnd.a_json([c]))
    C = sis.sviluppa(s, ctx).colonne.tolist()
    assert C and all(1 <= len(set(r) & {1, 2, 3, 4, 5}) <= 2 and len(set(r) & {10, 11, 12, 13, 14}) == 1
                     and len(set(r) & {20, 21, 22}) <= 1 for r in C)
    # almeno 2 gruppi su 3: più colonne
    c2 = cnd.gruppi_tra([([1, 2, 3, 4, 5], 1, 2), ([10, 11, 12, 13, 14], 1, 1), ([20, 21, 22], 0, 1)], 2, 3)
    s.condizioni = cnd.a_json([c2])
    assert len(sis.sviluppa(s, ctx).colonne) > len(C)
    assert "Gruppi tra" in c.descrivi() and cnd.da_json(cnd.a_json([c]))[0].gruppi == c.gruppi
    a = cnd.analizza_gruppo(list(range(1, 11)), ctx)
    assert abs(sum(r[3] for r in a.righe) - 100) < 1e-6 and sum(r[1] for r in a.righe) == 400
    # le condizioni salvate prima (senza "gruppi") si leggono ancora
    vecchia = {"codice": "pari", "attiva": True, "valori": [3], "minimo": 0, "massimo": 0, "param": 0,
               "numeri": [], "combinazioni": []}
    assert cnd.da_json([vecchia])[0].gruppi == []


def test_suoni_generati(tmp_path):
    import wave
    from pmse.ui import suoni
    p = suoni.scrivi(str(tmp_path / "s"))
    assert set(p) >= {"rotola", "aria", "palline", "annuncio", "toc"}
    with wave.open(p["rotola"]) as w:
        assert w.getframerate() == 44100 and w.getnframes() > 44100


def test_miscelatore():
    import numpy as np
    from pmse.ui import suoni
    m = suoni.Miscelatore.__new__(suoni.Miscelatore)
    m.voci, m.lock = [], __import__("threading").Lock()
    m.aggiungi("a", np.ones(3000, dtype=np.float32) * 0.5, 0.5, loop=True)
    m.aggiungi("b", np.ones(500, dtype=np.float32), 0.4)
    x = np.frombuffer(m._mescola(), dtype="<i2")
    assert len(x) == suoni.Miscelatore.BLOCCO and abs(x[0] / 32767 - 0.65) < 0.01 and abs(x[-1] / 32767 - 0.25) < 0.01
    assert [v["nome"] for v in m.voci] == ["a"]          # il suono breve è finito, il ciclo continua
    m.aggiungi("a", np.ones(3000, dtype=np.float32), 0.1, loop=True)
    assert len(m.voci) == 1 and m.voci[0]["vol"] == 0.1
