"""Lettura "intelligente" di file di estrazioni (CSV, TXT, Excel).

Il formato viene riconosciuto da solo, riga per riga:
- la data può essere 18/07/2026, 18-07-2026, 18.07.2026, 2026-07-18, 20260718
  oppure "18 luglio 2026" (anche con il giorno della settimana davanti);
- separatori ammessi: ; , tab | spazi;
- dopo la data servono almeno 7 numeri (sestina + Jolly), l'ottavo è il SuperStar
  (0 o vuoto = assente). Un numero intero prima della data è il concorso.
- le righe di intestazione o con testo non riconosciuto vengono ignorate;
- importi con virgola/punti (montepremi, quote) vengono ignorati.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .modello import MESI, Estrazione

_MESI_RE = "|".join(MESI)
RE_DATA_TESTO = re.compile(rf"\b(\d{{1,2}})\s+({_MESI_RE})\s+(\d{{4}})\b", re.IGNORECASE)
RE_DATA_DMY = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$")
RE_DATA_YMD = re.compile(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$")
RE_DATA_COMPATTA = re.compile(r"^(19|20)(\d{2})(\d{2})(\d{2})$")
RE_DATA_ORA = re.compile(r"^(.+?)[ T]\d{1,2}:\d{2}(:\d{2})?$")


@dataclass
class RigaLetta:
    numero_riga: int
    testo: str
    estrazione: Estrazione | None = None
    motivo: str = ""          # perché la riga è stata ignorata


@dataclass
class RisultatoLettura:
    righe: list[RigaLetta] = field(default_factory=list)

    @property
    def estrazioni(self) -> list[Estrazione]:
        return [r.estrazione for r in self.righe if r.estrazione]

    @property
    def ignorate(self) -> list[RigaLetta]:
        return [r for r in self.righe if r.estrazione is None and r.testo.strip()]


def _anno4(a: int) -> int:
    if a < 100:
        return 1900 + a if a >= 90 else 2000 + a
    return a


def interpreta_data(cella: str) -> date | None:
    s = cella.strip().strip('"').strip()
    m = RE_DATA_ORA.match(s)
    if m:
        s = m.group(1)
    try:
        m = RE_DATA_DMY.match(s)
        if m:
            return date(_anno4(int(m.group(3))), int(m.group(2)), int(m.group(1)))
        m = RE_DATA_YMD.match(s)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = RE_DATA_COMPATTA.match(s)
        if m:
            return date(int(m.group(1) + m.group(2)), int(m.group(3)), int(m.group(4)))
        m = RE_DATA_TESTO.search(s)
        if m:
            return date(int(m.group(3)), MESI.index(m.group(2).lower()) + 1, int(m.group(1)))
    except ValueError:
        return None
    return None


def _separatore(campione: list[str]) -> str | None:
    righe = [r for r in campione if r.strip()][:50]
    migliori = None
    punteggio = 0
    for sep in (";", "\t", "|", ","):
        conteggi = [r.count(sep) for r in righe]
        validi = [c for c in conteggi if c >= 6]
        if len(validi) > punteggio:
            punteggio, migliori = len(validi), sep
    return migliori


def _celle(riga: str, sep: str | None) -> list[str]:
    if sep:
        return next(csv.reader([riga], delimiter=sep))
    return riga.split()


def interpreta_riga(riga: str, sep: str | None) -> tuple[Estrazione | None, str]:
    testo = riga.strip()
    if not testo:
        return None, "vuota"
    if sep is None or testo.count(sep) < 6:      # separatore diverso dal resto del file
        sep = next((s for s in (";", "\t", "|", ",") if testo.count(s) >= 6), None)
    d = None
    # data testuale ("18 luglio 2026"): la togliamo dalla riga prima di dividerla
    m = RE_DATA_TESTO.search(testo)
    prima: list[int] = []
    dopo: list[int] = []
    if m:
        d = interpreta_data(m.group(0))
        resto_prima, resto_dopo = testo[:m.start()], testo[m.end():]
        celle_prima = _celle(resto_prima, sep) if resto_prima.strip() else []
        celle_dopo = _celle(resto_dopo, sep) if resto_dopo.strip() else []
        prima = [int(c) for c in (x.strip().strip('"') for x in celle_prima) if c.isdigit()]
        dopo = [int(c) for c in (x.strip().strip('"') for x in celle_dopo) if c.isdigit()]
    else:
        trovata = False
        for c in _celle(testo, sep):
            c = c.strip().strip('"').strip()
            if not c:
                continue
            if not trovata:
                dd = interpreta_data(c)
                if dd:
                    d, trovata = dd, True
                    continue
            if c.isdigit():
                (dopo if trovata else prima).append(int(c))
    if d is None:
        return None, "nessuna data riconosciuta"

    concorso = None
    numeri = dopo
    if len(dopo) < 7 and len(prima) >= 7:        # numeri scritti prima della data
        numeri, prima = prima, []
        if len(numeri) >= 9:                       # concorso + 6 + jolly + superstar
            concorso, numeri = numeri[0], numeri[1:]
    elif len(prima) == 1:
        concorso = prima[0]
    if len(numeri) < 7:
        return None, f"servono almeno 7 numeri dopo la data (trovati {len(numeri)})"
    sestina, jolly = numeri[:6], numeri[6]
    superstar = numeri[7] if len(numeri) >= 8 and 1 <= numeri[7] <= 90 else None
    # formato esportato da questa app: dopo il SuperStar c'è l'ordine di estrazione
    if len(numeri) >= 14 and set(numeri[8:14]) == set(sestina):
        sestina = numeri[8:14]
    return Estrazione(data=d, numeri=sestina, jolly=jolly, superstar=superstar,
                      concorso=concorso, fonte="file"), ""


def leggi_testo(testo: str) -> RisultatoLettura:
    righe = testo.splitlines()
    sep = _separatore(righe)
    ris = RisultatoLettura()
    for i, r in enumerate(righe, start=1):
        e, motivo = interpreta_riga(r, sep)
        ris.righe.append(RigaLetta(i, r, e, motivo))
    return ris


def _testo_da_excel(percorso: Path) -> str:
    from openpyxl import load_workbook  # import pigro: serve solo per Excel
    wb = load_workbook(percorso, read_only=True, data_only=True)
    out = io.StringIO()
    for ws in wb.worksheets:
        for riga in ws.iter_rows(values_only=True):
            celle = []
            for v in riga:
                if v is None:
                    celle.append("")
                elif hasattr(v, "strftime"):
                    celle.append(v.strftime("%d/%m/%Y"))
                elif isinstance(v, float) and v.is_integer():
                    celle.append(str(int(v)))
                else:
                    celle.append(str(v).replace(";", " "))
            out.write(";".join(celle) + "\n")
    return out.getvalue()


def leggi_file(percorso: str | Path) -> RisultatoLettura:
    p = Path(percorso)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        return leggi_testo(_testo_da_excel(p))
    grezzo = p.read_bytes()
    for codifica in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return leggi_testo(grezzo.decode(codifica))
        except UnicodeDecodeError:
            continue
    return leggi_testo(grezzo.decode("latin-1", errors="replace"))


def esporta_csv(estrazioni: list[Estrazione], percorso: str | Path) -> None:
    with open(percorso, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Concorso", "Data", "N1", "N2", "N3", "N4", "N5", "N6", "Jolly", "SuperStar",
                    "E1", "E2", "E3", "E4", "E5", "E6"])
        for e in sorted(estrazioni, key=lambda x: x.data):
            w.writerow([e.concorso or "", e.data.strftime("%d/%m/%Y"), *e.sestina, e.jolly,
                        e.superstar or 0, *e.numeri])
