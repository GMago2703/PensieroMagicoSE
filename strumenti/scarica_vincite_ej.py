"""Crea pmse/dati/vincite_ej.json con le quote di ogni concorso Eurojackpot (usato su GitHub)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pmse.core import internet, vincite_ej  # noqa: E402
from pmse.core.gioco import EJ  # noqa: E402

t = time.time()
estr = internet.scarica_anni(internet.anni_da_aggiornare(None, EJ), gioco=EJ)
date_c = sorted({e.data for e in estr})
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
