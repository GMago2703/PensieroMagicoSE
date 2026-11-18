"""Crea pmse/dati/vincite_se.json con i vincitori di ogni concorso del SuperEnalotto (usato su GitHub)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pmse.core import internet, vincite  # noqa: E402
from pmse.core.gioco import SE  # noqa: E402

t = time.time()
estr = internet.scarica_anni(internet.anni_da_aggiornare(None, SE), gioco=SE)
date_c = sorted({e.data for e in estr if e.data.year >= 1998})
print(f"{len(date_c)} concorsi da leggere")
dati = vincite.incluse()
mancanti = [d for d in date_c if d.isoformat() not in dati or dati[d.isoformat()].q3 is None]


def av(testo, i, n):
    if i % 200 == 0 or i == n:
        print(f"{i}/{n} {testo} ({time.time() - t:.0f}s)", flush=True)


dati.update(vincite.scarica(mancanti, av, pausa=0.2))
vincite.FILE_INCLUSO.parent.mkdir(parents=True, exist_ok=True)
vincite.FILE_INCLUSO.write_text(vincite.a_json(dati), encoding="utf-8")
con6 = [v for v in dati.values() if v.vinto_6]
print(f"Fatto: {len(dati)} concorsi, {len(con6)} con almeno un 6, vincitori del 6 totali {sum(v.p6 for v in con6)}")
mancano = [d for d in date_c if d.isoformat() not in dati]
print(f"Concorsi non letti: {len(mancano)} {mancano[:20]}")
