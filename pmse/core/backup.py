"""Salvataggio e ripristino dei dati (archivi, impostazioni, sistemi, giocate, apprendimento, chiavi).

Una copia è un file .zip con un archivio per programma ("SE/archivio.db", "EJ/archivio.db") e un
riepilogo (copia.json). Le copie si fanno con l'API di backup di SQLite, quindi sono coerenti anche
mentre il programma è aperto. SuperEnalotto ed Eurojackpot restano separati anche nella copia.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .gioco import GIOCHI
from .db import percorso_predefinito

CHIAVI_SEGRETE = ("claude_api_key", "claude_workspace_id", "gemini_api_key")
PREFISSO_AUTO = "copia_automatica_"


def cartella_copie() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    p = Path(base) / "PensieroMagico_copie"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class Contenuto:
    creato: str = ""
    programmi: dict = field(default_factory=dict)     # "SE" -> {"estrazioni": n, "ultima": "AAAA-MM-GG", ...}
    chiavi: bool = True
    nota: str = ""


def _riassunto(db: Path) -> dict:
    con = sqlite3.connect(str(db))
    try:
        n, ultima = con.execute("SELECT COUNT(*), MAX(data) FROM estrazioni").fetchone()
        imp = dict(con.execute("SELECT chiave, valore FROM impostazioni").fetchall())
    finally:
        con.close()
    def conta(chiave):
        try:
            return len(json.loads(imp.get(chiave) or "[]"))
        except ValueError:
            return 0
    return {"estrazioni": n or 0, "ultima": ultima or "", "sistemi": conta("sistemi_salvati"),
            "giocate": conta("giocate")}


def crea(destinazione: str | Path, percorsi: dict[str, Path] | None = None, chiavi: bool = True,
         nota: str = "") -> Contenuto:
    """Crea la copia in destinazione (.zip). percorsi: gioco -> file archivio (predefiniti se None)."""
    percorsi = percorsi or {c: percorso_predefinito(g) for c, g in GIOCHI.items()}
    cont = Contenuto(datetime.now().isoformat(timespec="seconds"), {}, chiavi, nota)
    destinazione = Path(destinazione)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = destinazione.with_suffix(destinazione.suffix + ".tmp")
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(temporaneo, "w", zipfile.ZIP_DEFLATED) as z:
        for codice, src in percorsi.items():
            if not Path(src).exists():
                continue
            copia = Path(tmp) / f"{codice}.db"
            a, b = sqlite3.connect(str(src)), sqlite3.connect(str(copia))
            try:
                a.backup(b)
                if not chiavi:
                    b.executemany("DELETE FROM impostazioni WHERE chiave=?", [(k,) for k in CHIAVI_SEGRETE])
                    b.commit()
                    b.execute("VACUUM")
            finally:
                a.close()
                b.close()
            cont.programmi[codice] = _riassunto(copia)
            z.write(copia, f"{codice}/archivio.db")
        z.writestr("copia.json", json.dumps(cont.__dict__, ensure_ascii=False, indent=1))
    os.replace(temporaneo, destinazione)
    return cont


def leggi(file: str | Path) -> Contenuto:
    """Il riepilogo di una copia (solleva ValueError se il file non è una copia di Pensiero Magico)."""
    try:
        with zipfile.ZipFile(file) as z:
            d = json.loads(z.read("copia.json").decode("utf-8"))
            nomi = set(z.namelist())
    except (KeyError, zipfile.BadZipFile, OSError, ValueError) as ex:
        raise ValueError("Il file non è una copia dei dati di Pensiero Magico.") from ex
    c = Contenuto(**{k: v for k, v in d.items() if k in Contenuto.__dataclass_fields__})
    c.programmi = {k: v for k, v in c.programmi.items() if f"{k}/archivio.db" in nomi}
    return c


def ripristina(file: str | Path, programmi: list[str], percorsi: dict[str, Path] | None = None,
               copia_prima: bool = True) -> list[str]:
    """Sostituisce gli archivi dei programmi scelti con quelli della copia. Gli archivi devono essere
    CHIUSI. Prima di sostituirli ne fa una copia di sicurezza. Restituisce i programmi ripristinati."""
    percorsi = percorsi or {c: percorso_predefinito(g) for c, g in GIOCHI.items()}
    cont = leggi(file)
    scelti = [p for p in programmi if p in cont.programmi and p in percorsi]
    if not scelti:
        return []
    if copia_prima:
        crea(cartella_copie() / f"prima_del_ripristino_{datetime.now():%Y-%m-%d_%H%M%S}.zip",
             {p: percorsi[p] for p in scelti if Path(percorsi[p]).exists()}, nota="prima del ripristino")
    with zipfile.ZipFile(file) as z:
        for p in scelti:
            dest = Path(percorsi[p])
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".ripristino")
            with z.open(f"{p}/archivio.db") as src, open(tmp, "wb") as out:
                out.write(src.read())
            con = sqlite3.connect(str(tmp))
            try:
                if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError(f"L'archivio {p} nella copia è danneggiato.")
            finally:
                con.close()
            for extra in ("-wal", "-shm", "-journal"):
                try:
                    os.remove(str(dest) + extra)
                except OSError:
                    pass
            os.replace(tmp, dest)
    return scelti


# ------------------------------------------------------------------ copie automatiche
def automatiche() -> list[Path]:
    return sorted(cartella_copie().glob(PREFISSO_AUTO + "*.zip"), reverse=True)


def automatica_se_serve(ogni_giorni: int = 7, quante: int = 10, percorsi: dict[str, Path] | None = None,
                        adesso: datetime | None = None) -> Path | None:
    """Fa una copia automatica se l'ultima è più vecchia di ogni_giorni; tiene solo le ultime 'quante'."""
    adesso = adesso or datetime.now()
    copie = automatiche()
    if copie:
        try:
            ultima = datetime.strptime(copie[0].stem[len(PREFISSO_AUTO):], "%Y-%m-%d_%H%M%S")
        except ValueError:
            ultima = datetime.fromtimestamp(copie[0].stat().st_mtime)
        if adesso - ultima < timedelta(days=ogni_giorni):
            return None
    dest = cartella_copie() / f"{PREFISSO_AUTO}{adesso:%Y-%m-%d_%H%M%S}.zip"
    crea(dest, percorsi, nota="copia automatica")
    for vecchia in automatiche()[quante:]:
        try:
            vecchia.unlink()
        except OSError:
            pass
    return dest
