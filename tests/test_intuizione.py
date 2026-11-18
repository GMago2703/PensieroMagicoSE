"""Suggerimenti AI (intuizione): quadro, interpretazione, sviluppo e correzioni, con un'AI finta."""
import json

import pytest

from pmse.core import condizioni as cnd
from pmse.core import intuizione as it
from pmse.core.claude_ai import ErroreClaude
from pmse.core.gioco import EJ, SE
from tests.test_sistemi import archivio_finto


def _ctx(g, n=500):
    est = archivio_finto(g, n)
    righe = [(e.data, sorted(e.numeri), e.jolly, e.superstar, list(e.numeri)) for e in est]
    return righe, cnd.Contesto(g, est)


def finta(*risposte):
    """AI finta: restituisce le risposte in ordine e registra i messaggi ricevuti."""
    chiamate = []

    def conversa(messaggi):
        chiamate.append(list(messaggi))
        return json.dumps(risposte[min(len(chiamate) - 1, len(risposte) - 1)]), "finta-1", 100, 50
    conversa.chiamate = chiamate
    return conversa


def test_quadro():
    for g in (SE, EJ):
        righe, ctx = _ctx(g)
        q = it.quadro(g, righe, ctx, 20.0, candidate=[sorted(righe[-1][1])], indicazione="punto sul 7")
        assert "BUDGET" in q and "punto sul 7" in q and "- pari –" in q and "RIDUZIONI PRONTE" in q
        assert "somme" in q and "gruppo" in q
        assert "intuizione" in it.istruzioni(g).lower()


def test_proposta_buona():
    righe, ctx = _ctx(SE)
    r = {"titolo": "Le simmetrie", "tipo": "condizionato", "numeri": [3, 7, 12, 21, 33, 45, 58, 69, 77, 88],
         "fisse": [7], "condizioni": [{"codice": "pari", "valori": [2, 3, 4]},
                                      {"codice": "somme", "minimo": 180, "massimo": 330},
                                      {"codice": "gruppo", "numeri": [33, 45, 58], "minimo": 1, "massimo": 2},
                                      {"codice": "inventata", "valori": [1]}],
         "errori_max": 0, "garanzia": 0, "intuizione": "x"}
    e = it.proponi(finta(r), "quadro", SE, ctx, 100.0)
    s = e.proposta.sistema
    assert 0 < len(s.colonne) <= 100 and all(7 in c for c in s.colonne)
    assert any("inventata" in a for a in e.proposta.avvisi) and not e.correzioni


def test_correzione_budget():
    righe, ctx = _ctx(SE)
    grande = {"tipo": "ridotto", "numeri": list(range(1, 21)), "garanzia": 1}
    piccolo = {"tipo": "immediato", "numeri": list(range(1, 11)), "garanzia": 3}
    ai = finta(grande, piccolo)
    e = it.proponi(ai, "quadro", SE, ctx, 10.0)
    assert len(e.correzioni) == 1 and "budget" in e.correzioni[0]
    assert len(e.proposta.sistema.colonne) <= 10 and len(ai.chiamate) == 2
    assert "supera il budget" in ai.chiamate[1][-1]["content"]


def test_rifiuto_dopo_correzioni():
    righe, ctx = _ctx(EJ)
    with pytest.raises(ErroreClaude):
        it.proponi(finta({"tipo": "ridotto", "numeri": [1, 2, 3], "garanzia": 1}), "q", EJ, ctx, 10.0)
