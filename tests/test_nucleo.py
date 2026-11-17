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
