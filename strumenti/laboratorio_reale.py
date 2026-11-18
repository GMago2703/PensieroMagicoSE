"""Esegue il Laboratorio sugli archivi veri scaricati da Internet (usato dalla build su GitHub).
Scrive i rapporti in CARTELLA (predefinita: foto_android)."""
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pmse.core import analisi_sei, internet, laboratorio, popolarita, vincite  # noqa: E402
from pmse.core.gioco import EJ, SE  # noqa: E402

cartella = Path(os.environ.get("CARTELLA", "foto_android"))
cartella.mkdir(parents=True, exist_ok=True)
for g in (SE, EJ):
    try:
        t = time.time()
        anni = internet.anni_da_aggiornare(None, g)
        estr = internet.scarica_anni(anni, gioco=g)
        uniche = {e.data: e for e in estr}
        estr = sorted(uniche.values(), key=lambda e: e.data)
        print(f"{g.nome}: {len(estr)} estrazioni scaricate in {time.time() - t:.0f}s")
        t = time.time()
        r = laboratorio.esegui(estr, g, simulazioni=500)
        testo = r.testo()
        print(f"{g.nome}: laboratorio in {time.time() - t:.0f}s, anomalie {len(r.anomalie)}")
        campione = ["", "CAMPIONE DELL'ARCHIVIO (numeri nell'ordine in cui sono pubblicati)"]
        for e in estr[:12] + estr[len(estr) // 2:len(estr) // 2 + 12] + estr[-25:]:
            campione.append(f"{e.data:%d/%m/%Y}  {' '.join(f'{n:2d}' for n in e.numeri)}  "
                            f"{'ordinati' if list(e.numeri) == sorted(e.numeri) else ''}")
        for anno in sorted({e.data.year for e in estr}):
            del_anno = [e for e in estr if e.data.year == anno]
            ordinati = sum(1 for e in del_anno if list(e.numeri) == sorted(e.numeri))
            campione.append(f"anno {anno}: {len(del_anno)} concorsi, già in ordine crescente {ordinati}")
        (cartella / f"laboratorio_{g.codice}.txt").write_text(
            f"Archivio vero scaricato il {date.today():%d/%m/%Y}\n\n" + testo + "\n".join(campione),
            encoding="utf-8")
        print(testo)
        if g.codice == "SE":
            rs = analisi_sei.esegui(estr, vincite.incluse(), volte=10000)
            mp = popolarita.costruisci(estr, vincite.incluse())
            righe_p = [f"MODELLO DI POPOLARITÀ: R² fuori campione {mp.r2:.3f} su {mp.concorsi} concorsi",
                       "Più giocati: " + ", ".join(f"{n} (+{e:.0f}%)" for n, e in mp.numeri()[:15]),
                       "Meno giocati: " + ", ".join(f"{n} ({e:.0f}%)" for n, e in mp.numeri()[-15:]),
                       f"Peso delle coppie consecutive: {mp.pesi[90]:+.3f}",
                       "Popolarità (percentile) delle sestine del 6: " +
                       ", ".join(str(mp.percentile(c.numeri)) for c in rs.sei)]
            pct6 = [mp.percentile(c.numeri) for c in rs.sei]
            righe_p.append(f"Media percentile sestine del 6: {sum(pct6) / len(pct6):.1f} (50 = come il caso)")
            (cartella / "concorsi_con_il_6.txt").write_text(rs.testo() + "\n\n" + "\n".join(righe_p),
                                                             encoding="utf-8")
            print("\n".join(righe_p))
            print(rs.testo())
    except Exception as ex:
        print(f"{g.nome}: non riuscito: {ex}")
        (cartella / f"laboratorio_{g.codice}.txt").write_text(f"Non riuscito: {ex}\n", encoding="utf-8")
