"""Calcola pmse/dati/ridotti_pronti.json (riduzioni già pronte per i Ridotti immediati)."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pmse.core import ridotti_pronti as R  # noqa: E402

t0 = time.time()
vecchi = R.tabella()                     # si tiene sempre la riduzione migliore mai trovata
out = {}
for k, numeri in R.NUMERI.items():
    for n in numeri:
        for f in R.FISSE:
            if f >= k or n - f < k - f:
                continue
            for punti in range(2, k):
                if punti <= f:                    # garanzia già data dalle fisse: basta una colonna
                    continue
                tent = 60 if n <= 16 else 20
                c = R.chiave(k, n, f, punti)
                nuovo = R.calcola(k, n, f, punti, tentativi=tent, qualita=48)
                out[c] = nuovo if c not in vecchi or len(nuovo) < len(vecchi[c]) else vecchi[c]
        print(f"k={k} n={n} fatto ({time.time() - t0:.0f}s)", flush=True)
R.FILE.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print(len(out), "riduzioni,", R.FILE.stat().st_size // 1024, "KB")
