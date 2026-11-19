"""Le mie giocate: memoria, sincronizzazione e verifica sull'archivio."""
from collections import Counter
from datetime import date, datetime
from itertools import combinations

import numpy as np

from pmse.core import giocate as gc
from pmse.core import magico
from pmse.core import mie_giocate as mg
from pmse.core import sistemi as sis
from pmse.core.db import Archivio
from pmse.core.gioco import EJ, SE
from tests.test_sistemi import archivio_finto


def _arch(tmp_path, g, n=300):
    a = Archivio(tmp_path / f"{g.codice}.db", g)
    a.unisci(archivio_finto(g, n))
    return a


def test_conteggio_uguale_al_registro(tmp_path):
    rng = np.random.default_rng(3)
    for g in (SE, EJ):
        a = _arch(tmp_path, g)
        righe = list(a.sestine())
        cols = [sorted(rng.choice(np.arange(1, g.n + 1), g.k, replace=False).tolist()) for _ in range(40)]
        cols += [sorted(r[1]) for r in righe[-5:]]                  # qualche vincita sicura
        if g.is_ej:
            extra = [sorted(rng.choice(np.arange(1, 13), 2, replace=False).tolist()) for _ in cols]
        else:
            extra = [[int(rng.integers(1, 91))] if i % 3 == 0 else [] for i in range(len(cols))]
        attese = [Counter() for _ in righe]
        for i, j, c in gc.categorie(g, cols, extra, righe):
            attese[i][c] += 1
        per, pmax, _ = mg._conta_colonne(g, cols, extra, righe)
        assert per == attese
        assert max(pmax) == g.k
        a.chiudi()


def test_integrale_esatto(tmp_path):
    for g in (SE, EJ):
        a = _arch(tmp_path, g)
        righe = list(a.sestine())[-80:]
        numeri = sorted(set(righe[-1][1]) | set(range(1, 12)))[:10]
        eu = [1, 2] if g.is_ej else []
        per, _ = mg._conta_integrale(g, numeri, eu, righe)
        cols = [list(c) for c in combinations(numeri, g.k)]
        per2, _, _ = mg._conta_colonne(g, cols, [eu for _ in cols] if eu else [], righe)
        assert per == per2
        a.chiudi()


def test_voci_sincronizza_e_verifica(tmp_path):
    a = _arch(tmp_path, SE)
    v = mg.da_macchina(a, "sestine", [{"numeri": [1, 2, 3, 4, 5, 6], "extra": [7]},
                                      {"numeri": [10, 20, 30, 40, 50, 60], "extra": []}])
    assert v.categoria == "colonne_casuali" and v.dal
    mg.da_macchina(a, "sistema", [{"numeri": list(range(1, 11)), "extra": []}])
    s = sis.Sistema(tipo="condizionato", gioco="SE", numeri=list(range(1, 11)))
    sv = sis.sviluppa(s)
    s.colonne = sv.colonne.tolist()
    mg.da_sistema(a, s, "sistemi_casuali")
    voci = mg.carica(a)
    assert len(voci) == 2 and len(voci[1].colonne) == 210            # i numeri hanno preso le colonne
    mg.da_sistema(a, s, "sistemi")
    mg.da_sistema(a, s, "sistemi")                                   # risviluppato: non si ripete
    assert len(mg.carica(a)) == 3
    # previsione di Magico Pensiero e giocata registrata con le stesse colonne della macchina
    r = magico.genera(a.sestine())
    magico.salva_previsione(a, r)
    gc.aggiungi(a, gc.Giocata("SE", [[1, 2, 3, 4, 5, 6], [10, 20, 30, 40, 50, 60]], [[7], []],
                              date.today().isoformat(), 2, 2.5, "Mia", "Macchina dell'estrazione"))
    voci = mg.sincronizza(a)
    assert any(x.categoria == "magico" for x in voci)
    assert voci[0].giocata and len(voci) == 4
    # storico: tutte le estrazioni
    ver = mg.verifica(SE, voci[2], list(a.sestine()), "storico")
    assert len(ver.concorsi) == 300 and ver.spesa == 210 * 300
    # nascondi, elimina; la previsione eliminata non torna
    mg.modifica(a, voci[0].id, nascosta=True)
    assert mg.carica(a)[0].nascosta
    pm = next(x for x in mg.carica(a) if x.categoria == "magico")
    mg.elimina(a, pm.id)
    assert not any(x.categoria == "magico" for x in mg.sincronizza(a))
    gc.elimina(a, gc.carica(a)[0].id)
    assert not mg.sincronizza(a)[0].giocata                           # torna "generata"
    assert mg.primo_concorso(datetime(2026, 1, 1, 21)) == date(2026, 1, 2)
    a.chiudi()
