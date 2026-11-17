from datetime import date
from pathlib import Path

import pytest

from pmse.core import analisi
from pmse.core.db import Archivio, verifica_integrita
from pmse.core.importatore import esporta_csv, interpreta_data, leggi_file, leggi_testo
from pmse.core.internet import analizza_pagina_anno
from pmse.core.modello import Estrazione, valida

DATI = Path(__file__).parent / "dati"


def E(d, nums, j, ss=None):
    return Estrazione(data=d, numeri=nums, jolly=j, superstar=ss)


@pytest.fixture
def arch(tmp_path):
    a = Archivio(tmp_path / "t.db")
    yield a
    a.chiudi()


def test_date():
    assert interpreta_data("18/07/2026") == date(2026, 7, 18)
    assert interpreta_data("2026-07-18") == date(2026, 7, 18)
    assert interpreta_data("18.07.26") == date(2026, 7, 18)
    assert interpreta_data("20260718") == date(2026, 7, 18)
    assert interpreta_data("sabato 18 luglio 2026") == date(2026, 7, 18)
    assert interpreta_data("18/07/2026 20:00") == date(2026, 7, 18)
    assert interpreta_data("ciao") is None


def test_validazione():
    assert valida(E(date(2026, 7, 18), [1, 28, 52, 62, 79, 86], 61, 31))[0] == []
    assert valida(E(date(2026, 7, 18), [1, 1, 52, 62, 79, 86], 61))[0]
    assert valida(E(date(2026, 7, 18), [1, 28, 52, 62, 79, 86], 28))[0]
    assert valida(E(date(1990, 1, 1), [1, 28, 52, 62, 79, 86], 61))[0]


@pytest.mark.parametrize("riga", [
    "115;18/07/2026;1;28;52;62;79;86;61;31",
    "18/07/2026,1,28,52,62,79,86,61,31",
    "18/07/2026\t1\t28\t52\t62\t79\t86\t61\t31",
    "sabato 18 luglio 2026 1 28 52 62 79 86 61 31",
    "2026-07-18 1 28 52 62 79 86 61 31",
    "1;28;52;62;79;86;61;31;18/07/2026",
    "10685;115;18/07/2026;1;28;52;62;79;86;61;31;4.859.416,80",
])
def test_righe(riga):
    r = leggi_testo("Intestazione;che;viene;ignorata;a;b;c;d\n" + riga)
    assert len(r.estrazioni) == 1, r.righe
    e = r.estrazioni[0]
    assert e.data == date(2026, 7, 18)
    assert e.sestina == [1, 28, 52, 62, 79, 86]
    assert e.jolly == 61
    assert e.superstar == 31


def test_unione_e_duplicati(arch):
    a = [E(date(2026, 7, 17), [7, 34, 45, 64, 65, 76], 46, 90),
         E(date(2026, 7, 18), [1, 28, 52, 62, 79, 86], 61)]
    es = arch.unisci(a)
    assert es.nuove == 2
    # di nuovo: duplicati, ma la seconda va completata col SuperStar
    es = arch.unisci([E(date(2026, 7, 17), [7, 34, 45, 64, 65, 76], 46, 90),
                      E(date(2026, 7, 18), [86, 79, 62, 52, 28, 1], 61, 31)])
    assert es.nuove == 0 and es.duplicate == 1 and es.completate == 1
    assert arch.per_data(date(2026, 7, 18)).superstar == 31
    # conflitto
    es = arch.unisci([E(date(2026, 7, 18), [2, 28, 52, 62, 79, 86], 61, 31)])
    assert len(es.conflitti) == 1
    es = arch.unisci([E(date(2026, 7, 18), [2, 28, 52, 62, 79, 86], 61, 31)], sostituisci_conflitti=True)
    assert es.sostituite == 1
    assert arch.per_data(date(2026, 7, 18)).sestina[0] == 2
    assert arch.per_data(date(2026, 7, 18)).concorso == 2


def test_concorso_progressivo(arch):
    arch.unisci([E(date(2026, 1, 3), [1, 2, 3, 4, 5, 6], 7), E(date(2026, 1, 2), [1, 2, 3, 4, 5, 8], 7)])
    assert arch.per_data(date(2026, 1, 2)).concorso == 1
    assert arch.per_data(date(2026, 1, 3)).concorso == 2
    arch.elimina(date(2026, 1, 2))
    assert arch.per_data(date(2026, 1, 3)).concorso == 1


def test_salva_e_quote(arch):
    e = E(date(2026, 7, 18), [1, 28, 52, 62, 79, 86], 61, 31)
    e.montepremi = 4859416.80
    e.quote = {"Due": (339749, 5.72), "Sei": (0, 196263929.43)}
    arch.salva(e)
    r = arch.per_data(date(2026, 7, 18))
    assert r.quote["Due"] == (339749, 5.72)
    assert r.montepremi == pytest.approx(4859416.80)


def test_pagina_internet():
    estr = analizza_pagina_anno((DATI / "pagina_1997.html").read_text(encoding="utf-8"))
    assert len(estr) == 3
    assert estr[0].data == date(1997, 12, 31)
    assert estr[0].numeri == [76, 71, 36, 89, 34, 86]      # ordine di estrazione conservato
    assert estr[0].jolly == 82 and estr[0].superstar is None
    assert estr[2].superstar == 31


def test_esporta_reimporta(arch, tmp_path):
    estr = analizza_pagina_anno((DATI / "pagina_1997.html").read_text(encoding="utf-8"))
    arch.unisci(estr)
    f = tmp_path / "x.csv"
    esporta_csv(arch.tutte(), f)
    r = leggi_file(f)
    assert len(r.estrazioni) == 3
    assert r.estrazioni[0].numeri == [43, 35, 26, 67, 8, 55]
    arch2 = Archivio(tmp_path / "u.db")
    arch2.unisci(r.estrazioni)
    assert arch2.conta() == 3
    assert arch2.unisci(r.estrazioni).duplicate == 3


def test_excel(tmp_path, arch):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Data", "N1", "N2", "N3", "N4", "N5", "N6", "Jolly", "SS"])
    ws.append([date(2026, 7, 18), 1, 28, 52, 62, 79, 86, 61, 31])
    p = tmp_path / "a.xlsx"
    wb.save(p)
    r = leggi_file(p)
    assert len(r.estrazioni) == 1 and r.estrazioni[0].superstar == 31


def test_analisi(arch):
    estr = analizza_pagina_anno((DATI / "pagina_1997.html").read_text(encoding="utf-8"))
    arch.unisci(estr)
    st = arch.sestine()
    for d in analisi.REGISTRO.values():
        ris = d.funzione(st)
        assert ris.colonne
    fr = analisi.frequenze_ritardi(st)
    riga86 = [r for r in fr.righe if r[0] == 86][0]
    assert riga86[1] == 2 and riga86[3] == 0
    assert verifica_integrita(arch)


def storico_finto(n=400, seme=7):
    import random
    from datetime import timedelta
    rnd = random.Random(seme)
    out = []
    d = date(2010, 1, 2)
    for i in range(n):
        s = rnd.sample(range(1, 91), 8)
        out.append(Estrazione(data=d + timedelta(days=2 * i + (1 if (d + timedelta(days=2 * i)).weekday() in (0, 6) else 0)),
                              numeri=s[:6], jolly=s[6], superstar=s[7]))
    return out


def test_nuove_analisi_e_personalizzate(arch):
    from pmse.core import personalizzate as pz
    arch.unisci(storico_finto())
    st = arch.sestine()
    for codice in ("consecutivi", "somme", "sequenze", "pari_dispari", "posizioni"):
        ris = analisi.REGISTRO[codice].funzione(st)
        assert ris.righe and len(ris.numeri_riga) == len(ris.righe), codice
    pos = analisi.posizioni(st, tipo=1)
    assert sum(r[7] for r in pos.righe) == 6 * len(st)
    pd = analisi.pari_dispari(st)
    assert round(sum(r[3] for r in pd.righe)) == 100
    assert analisi.progressioni([10, 20, 30, 41, 42, 43], 3, 10) == [(10, [10, 20, 30]), (1, [41, 42, 43])]
    for m in pz.MISURE.values():
        v = pz.calcola_misura(m.codice, st, m.param_predefinito)
        assert len(v) == 90
    r = pz.esempio()
    r.filtri.parita = 1
    ris = pz.esegui(r, st)
    assert all(riga[0] % 2 == 0 for riga in ris.righe)
    pz.salva_tutte(arch, [r])
    assert pz.carica(arch)[0].nome == r.nome
    assert r.codice in pz.tutte_le_analisi(arch)


def test_sestine_e_magico(arch):
    from pmse.core import magico, sestine
    arch.unisci(storico_finto())
    st = arch.sestine()
    idx = sestine.IndiceArchivio(st)
    c = idx.confronta(st[-1][1])
    assert c.gia_uscita and c.max_punti == 6
    crit = sestine.Criteri(max_punti_archivio=3, somma_min=200, somma_max=320, pari_min=3, pari_max=3,
                           obbligatori=[7], max_comuni_tra_risultati=2)
    trovate, _ = sestine.cerca(idx, crit, 5, seed=1)
    assert len(trovate) == 5
    for s in trovate:
        assert 7 in s and 200 <= sum(s) <= 320 and sum(1 for n in s if n % 2 == 0) == 3
    assert idx.punti(trovate).max() <= 3
    r = magico.genera(st)
    assert len(r.sestine) == 3 and all(len(set(s.numeri)) == 6 for s in r.sestine)
    assert r.jolly not in r.sestine[0].numeri
    assert magico.genera(st).sestine[0].numeri == r.sestine[0].numeri      # riproducibile
    es = magico.verifica_storica(st, 20)
    assert es.prove == 20
    magico.salva_previsione(arch, r)
    assert magico.leggi_previsioni(arch)[-1]["sestine"][0] == r.sestine[0].numeri


def test_claude_ai(arch):
    import io
    import json
    from unittest import mock

    from pmse.core import claude_ai, magico
    arch.unisci(storico_finto(300))
    st = arch.sestine()
    r = magico.genera(st)
    dossier = claude_ai.costruisci_dossier(st, r, "verifica di prova")
    assert "Statistiche per numero" in dossier and "verifica di prova" in dossier
    scelta = {"sestine": [[1, 2, 3, 4, 5, 7], [10, 20, 30, 40, 50, 60], [11, 21, 31, 41, 51, 61]],
              "jolly": 1, "superstar": 33, "motivazioni": ["a", "b", "c"], "analisi": "x"}
    risposta = {"model": "claude-opus-5-5", "stop_reason": "end_turn", "usage": {"input_tokens": 5, "output_tokens": 6},
                "content": [{"type": "text", "text": "```json\n" + json.dumps(scelta) + "\n```"}]}

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    corretta = dict(scelta, jolly=77)
    risposta2 = dict(risposta, content=[{"type": "text", "text": json.dumps(corretta)}])
    with mock.patch("urllib.request.urlopen", side_effect=[R(json.dumps(risposta).encode()),
                                                           R(json.dumps(risposta2).encode())]) as u:
        rc = claude_ai.chiedi_a_claude("chiave", "claude-opus-5-5", dossier, set())
        req = u.call_args[0][0]
        assert req.get_header("Anthropic-version") == claude_ai.VERSIONE_API
        corpo = json.loads(req.data)
        assert "temperature" not in corpo and len(corpo["messages"]) == 3     # richiesta di correzione
    assert rc.sestine[1] == [10, 20, 30, 40, 50, 60] and rc.superstar == 33 and rc.token_uscita == 12
    assert rc.corretta and rc.jolly == 77 and not rc.avvisi
    m = magico.matrice(st)
    v = claude_ai.valida_risposta(scelta, set(), m, (5, 5))
    assert any("in comune con l'archivio" in a for a in v.avvisi)
    with pytest.raises(claude_ai.ErroreClaude):
        claude_ai.valida_risposta({"sestine": [[1, 1, 2, 3, 4, 5]] * 3, "jolly": 9, "superstar": 2}, set())
    ris = claude_ai.come_risultato(rc, r)
    magico.salva_previsione(arch, r)
    magico.salva_previsione(arch, ris, origine="Claude (prova)")
    assert [p["origine"] for p in magico.leggi_previsioni(arch)] == ["Algoritmo", "Claude (prova)"]


def test_somiglianza(arch):
    from pmse.core import magico
    arch.unisci(storico_finto(600))
    st = arch.sestine()
    massimi = analisi.massimi_in_comune(st, 200)
    assert len(massimi) == 200
    # controllo con il calcolo "a mano"
    i = len(st) - 1
    assert massimi[-1] == max(len(set(st[i][1]) & set(st[j][1])) for j in range(i))
    lo, hi = analisi.limiti_consigliati([3] * 60 + [4] * 35 + [5] * 3 + [2] * 2, 90)
    assert (lo, hi) == (3, 4)
    ris = analisi.somiglianza(st, 200)
    assert any(r[6] for r in ris.righe)
    r = magico.genera(st, magico.Impostazioni(limite_archivio=3))
    m = magico.matrice(st)
    from pmse.core.claude_ai import in_comune_archivio
    assert all(k <= 3 for k in in_comune_archivio([s.numeri for s in r.sestine], m))
    assert r.limiti_archivio[1] == 3
