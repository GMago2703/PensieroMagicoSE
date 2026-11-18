"""Analisi dei concorsi con il 6 e lettura dei vincitori dalle pagine del sito."""
import random
from datetime import date, timedelta
from pathlib import Path

from pmse.core import analisi_sei, vincite
from pmse.core.db import Archivio
from pmse.core.gioco import SE
from pmse.core.modello import Estrazione

DATI = Path(__file__).parent / "dati"


def test_lettura_pagine():
    v = vincite.analizza_pagina((DATI / "vincite_11-09-2026.html").read_text(encoding="utf-8"), date(2026, 9, 11))
    assert v.p6 == 1 and v.premio6.startswith("223.173.416") and v.p3 == 20899 and v.vinto_6
    v = vincite.analizza_pagina((DATI / "vincite_17-11-2026.html").read_text(encoding="utf-8"), date(2026, 11, 17))
    assert v.p6 == 0 and v.p5 == 16 and v.p4 == 1499 and not v.vinto_6
    v = vincite.analizza_pagina((DATI / "vincite_03-01-1998.html").read_text(encoding="utf-8"), date(1998, 1, 3))
    assert v.p6 == 0 and v.p4 == 705 and v.p2 is None
    assert vincite.analizza_pagina("<html>niente</html>", date(2020, 1, 1)) is None


def mondo(n, sei_popolari: bool, seme=4):
    """Estrazioni casuali; i 3 punti (popolarità) crescono con i numeri da 1 a 31; il 6 arriva o a caso o
    più spesso quando la sestina è popolare (come nella realtà)."""
    rnd = random.Random(seme)
    estr, vinc, d = [], {}, date(2005, 1, 4)
    while len(estr) < n:
        if d.weekday() in (1, 3, 5):
            nums = rnd.sample(range(1, 91), 6)
            resto = [x for x in range(1, 91) if x not in nums]
            estr.append(Estrazione(d, nums, rnd.choice(resto), rnd.randint(1, 90)))
            date_n = sum(1 for x in nums if x <= 31)
            pop = (1 + 0.25 * (date_n - 2.07)) * rnd.uniform(0.85, 1.15)
            prob6 = 0.03 * (pop ** 4 if sei_popolari else 1)
            vinc[d.isoformat()] = vincite.Vincite(d.isoformat(), p6=int(rnd.random() < prob6), p3=int(20000 * pop),
                                                  premio6="")
        d += timedelta(days=1)
    return estr, vinc


def test_sei_casuali_nessuna_differenza():
    estr, vinc = mondo(2500, False)
    r = analisi_sei.esegui(estr, vinc, volte=800)
    assert len(r.sei) > 30
    assert not [p for p in r.prove if p.p_holm < 0.05]
    assert "Nessuna differenza solida" in r.testo()


def test_sei_legati_alla_popolarita():
    estr, vinc = mondo(2500, True)
    r = analisi_sei.esegui(estr, vinc, volte=800)
    forti = {p.nome for p in r.prove if p.p_holm < 0.05}
    assert any(n.startswith("Popolarità") for n in forti)
    assert any(n.startswith("Numeri da 1 a 31") for n in forti)
    assert "date di nascita" in r.testo() and "ELENCO DEI CONCORSI CON IL 6" in r.testo()


def test_memoria_vincite(tmp_path):
    a = Archivio(tmp_path / "a.db", gioco=SE)
    estr, vinc = mondo(50, False)
    a.unisci(estr)
    noti = vincite.carica(a)
    mancanti = vincite.mancanti(a)
    assert len(mancanti) == 50 - sum(1 for e in estr if e.data.isoformat() in noti)
    vincite.salva(a, {k: vinc[k] for k in list(vinc)[:10]})
    assert len(vincite.mancanti(a)) == len(mancanti) - sum(1 for k in list(vinc)[:10] if k not in noti)
    con6 = {date.fromisoformat(k) for k, v in list(vinc.items())[:10] if v.p6}
    assert con6 <= vincite.date_con_6(a)
    a.chiudi()


def test_popolarita_e_magico(tmp_path):
    from pmse.core import magico, popolarita
    estr, vinc = mondo(2500, True)
    m = popolarita.costruisci(estr, vinc)
    assert m.r2 > 0.3                                         # nel mondo finto i numeri 1-31 sono più giocati
    assert m.percentile([1, 5, 9, 14, 22, 30]) > m.percentile([40, 52, 63, 71, 80, 88])
    assert popolarita.ModelloPopolarita.da_json(m.a_json()).r2 == m.r2
    a = Archivio(tmp_path / "a.db", gioco=SE)
    a.unisci(estr)
    vincite.salva(a, vinc)
    mp = popolarita.per_archivio(a)
    assert mp and popolarita.per_archivio(a).firma == mp.firma            # in memoria, non ricalcolato
    imp = magico.Impostazioni.predefinite(SE)
    imp.evita_popolari, imp.soglia_popolari = True, 20
    r = magico.genera(a.sestine(), imp, popolarita=mp)
    chiave = "popolarità stimata (percentile, 0 = la meno giocata)"
    assert all(s.dettaglio[chiave] <= 30 for s in r.sestine)
    a.chiudi()
