"""Crea pmse/dati/vincite_ej.json con le quote di ogni concorso Eurojackpot (usato su GitHub)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pmse.core import internet, vincite_ej  # noqa: E402
from pmse.core.gioco import EJ  # noqa: E402

from datetime import date, timedelta  # noqa: E402

t = time.time()
# date dei concorsi: venerdì dal 23/03/2012, anche il martedì dal 29/03/2022 (le date senza concorso non
# hanno pagina e vengono saltate)
date_c = []
d = date(2012, 3, 23)
while d <= date.today():
    if d.weekday() == 4 or (d.weekday() == 1 and d >= date(2022, 3, 29)):
        date_c.append(d)
    d += timedelta(days=1)
print(f"{len(date_c)} concorsi da leggere")
dati = vincite_ej.incluse()
mancanti = [d for d in date_c if d.isoformat() not in dati]


def av(testo, i, n):
    if i % 100 == 0 or i == n:
        print(f"{i}/{n} {testo} ({time.time() - t:.0f}s)", flush=True)


dati.update(vincite_ej.scarica(mancanti, av, pausa=0.2))
vincite_ej.FILE_INCLUSO.parent.mkdir(parents=True, exist_ok=True)
vincite_ej.FILE_INCLUSO.write_text(vincite_ej.a_json(dati), encoding="utf-8")
print(f"Fatto: {len(dati)} concorsi; non letti: {len([d for d in date_c if d.isoformat() not in dati])}")
