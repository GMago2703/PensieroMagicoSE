"""Archivio delle estrazioni su SQLite.

Regole principali:
- la data identifica in modo univoco un concorso (nessun duplicato);
- il numero di concorso è il progressivo dentro l'anno e viene ricalcolato
  automaticamente dopo ogni modifica (come fa Sisal);
- "Pos." è la posizione assoluta dall'inizio dell'archivio.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .modello import CATEGORIE, Estrazione, valida

SCHEMA = """
CREATE TABLE IF NOT EXISTS estrazioni (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    data        TEXT NOT NULL UNIQUE,
    anno        INTEGER NOT NULL,
    concorso    INTEGER,
    n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
    n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL,
    e1 INTEGER, e2 INTEGER, e3 INTEGER, e4 INTEGER, e5 INTEGER, e6 INTEGER,
    jolly       INTEGER NOT NULL,
    superstar   INTEGER,
    montepremi  REAL,
    fonte       TEXT,
    aggiornato  TEXT
);
CREATE INDEX IF NOT EXISTS idx_estr_anno ON estrazioni(anno);
CREATE TABLE IF NOT EXISTS quote (
    data       TEXT NOT NULL,
    categoria  TEXT NOT NULL,
    vincitori  INTEGER,
    quota      REAL,
    PRIMARY KEY (data, categoria)
);
CREATE TABLE IF NOT EXISTS impostazioni (
    chiave TEXT PRIMARY KEY,
    valore TEXT
);
"""


def percorso_predefinito() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    p = Path(base) / "PensieroMagicoSE"
    p.mkdir(parents=True, exist_ok=True)
    return p / "archivio.db"


@dataclass
class EsitoUnione:
    nuove: int = 0
    duplicate: int = 0
    completate: int = 0          # duplicate a cui abbiamo aggiunto dati mancanti (es. SuperStar)
    sostituite: int = 0
    conflitti: list[tuple[Estrazione, Estrazione]] = field(default_factory=list)  # (archivio, nuova)
    scartate: list[tuple[Estrazione, list[str]]] = field(default_factory=list)

    def riepilogo(self) -> str:
        r = [f"Estrazioni nuove aggiunte: {self.nuove}",
             f"Già presenti (saltate): {self.duplicate}"]
        if self.completate:
            r.append(f"Già presenti ma completate con dati mancanti: {self.completate}")
        if self.sostituite:
            r.append(f"Conflitti risolti sostituendo il dato in archivio: {self.sostituite}")
        if self.conflitti:
            r.append(f"Conflitti NON risolti (stessa data, numeri diversi): {len(self.conflitti)}")
        if self.scartate:
            r.append(f"Righe scartate perché non valide: {len(self.scartate)}")
        return "\n".join(r)


class Archivio:
    def __init__(self, percorso: str | Path | None = None):
        self.percorso = Path(percorso) if percorso else percorso_predefinito()
        self.con = sqlite3.connect(str(self.percorso))
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self.con.commit()

    def chiudi(self):
        self.con.close()

    # ------------------------------------------------------------------ lettura
    def _da_riga(self, r: sqlite3.Row, con_quote: bool = False) -> Estrazione:
        ordine = [r["e1"], r["e2"], r["e3"], r["e4"], r["e5"], r["e6"]]
        numeri = ordine if all(ordine) else [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r["n6"]]
        e = Estrazione(
            data=date.fromisoformat(r["data"]), numeri=list(numeri), jolly=r["jolly"],
            superstar=r["superstar"], concorso=r["concorso"], montepremi=r["montepremi"],
            fonte=r["fonte"] or "", id=r["id"],
        )
        if con_quote:
            e.quote = self.quote(e.data)
        return e

    def tutte(self, crescente: bool = True) -> list[Estrazione]:
        ordine = "ASC" if crescente else "DESC"
        return [self._da_riga(r) for r in self.con.execute(f"SELECT * FROM estrazioni ORDER BY data {ordine}")]

    def sestine(self) -> list[tuple[date, list[int], int, int | None, list[int]]]:
        """Accesso veloce per le analisi, in ordine crescente di data:
        (data, sestina ordinata, jolly, superstar, numeri nell'ordine di estrazione)."""
        out = []
        for r in self.con.execute("SELECT data,n1,n2,n3,n4,n5,n6,jolly,superstar,e1,e2,e3,e4,e5,e6 "
                                  "FROM estrazioni ORDER BY data"):
            s = [r[1], r[2], r[3], r[4], r[5], r[6]]
            ordine = [r[9], r[10], r[11], r[12], r[13], r[14]]
            out.append((date.fromisoformat(r[0]), s, r[7], r[8], ordine if all(ordine) else list(s)))
        return out

    def conta(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM estrazioni").fetchone()[0]

    def anni(self) -> list[int]:
        return [r[0] for r in self.con.execute("SELECT DISTINCT anno FROM estrazioni ORDER BY anno")]

    def per_data(self, d: date) -> Estrazione | None:
        r = self.con.execute("SELECT * FROM estrazioni WHERE data=?", (d.isoformat(),)).fetchone()
        return self._da_riga(r, con_quote=True) if r else None

    def ultima(self) -> Estrazione | None:
        r = self.con.execute("SELECT * FROM estrazioni ORDER BY data DESC LIMIT 1").fetchone()
        return self._da_riga(r) if r else None

    def posizione(self, d: date) -> int:
        """Posizione assoluta (1 = primo concorso in archivio)."""
        return self.con.execute("SELECT COUNT(*) FROM estrazioni WHERE data<=?", (d.isoformat(),)).fetchone()[0]

    def date_ordinate(self) -> list[date]:
        return [date.fromisoformat(r[0]) for r in self.con.execute("SELECT data FROM estrazioni ORDER BY data")]

    def quote(self, d: date) -> dict[str, tuple[int | None, float | None]]:
        return {r["categoria"]: (r["vincitori"], r["quota"]) for r in
                self.con.execute("SELECT * FROM quote WHERE data=?", (d.isoformat(),))}

    # ---------------------------------------------------------------- scrittura
    def _scrivi(self, e: Estrazione, sostituisci: bool):
        s = e.sestina
        ordine = list(e.numeri) if e.numeri != s else [None] * 6
        valori = (e.data.isoformat(), e.data.year, e.concorso, *s, *ordine, e.jolly, e.superstar,
                  e.montepremi, e.fonte, datetime.now().isoformat(timespec="seconds"))
        verbo = "INSERT OR REPLACE" if sostituisci else "INSERT"
        self.con.execute(
            f"{verbo} INTO estrazioni (data,anno,concorso,n1,n2,n3,n4,n5,n6,e1,e2,e3,e4,e5,e6,"
            "jolly,superstar,montepremi,fonte,aggiornato) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            valori)
        if e.quote:
            self.con.execute("DELETE FROM quote WHERE data=?", (e.data.isoformat(),))
            for cat, (vinc, quota) in e.quote.items():
                if cat in CATEGORIE and (vinc is not None or quota is not None):
                    self.con.execute("INSERT INTO quote VALUES (?,?,?,?)", (e.data.isoformat(), cat, vinc, quota))

    def salva(self, e: Estrazione, data_originale: date | None = None) -> None:
        """Inserisce o modifica una singola estrazione (uso manuale). Solleva ValueError se non valida."""
        errori, _ = valida(e)
        if errori:
            raise ValueError("\n".join(errori))
        if data_originale and data_originale != e.data:
            if self.per_data(e.data):
                raise ValueError("Esiste già un'estrazione con questa data")
            self.con.execute("DELETE FROM estrazioni WHERE data=?", (data_originale.isoformat(),))
            self.con.execute("DELETE FROM quote WHERE data=?", (data_originale.isoformat(),))
        self._scrivi(e, sostituisci=True)
        self.rinumera({e.anno} | ({data_originale.year} if data_originale else set()))
        self.con.commit()

    def elimina(self, d: date) -> None:
        self.con.execute("DELETE FROM estrazioni WHERE data=?", (d.isoformat(),))
        self.con.execute("DELETE FROM quote WHERE data=?", (d.isoformat(),))
        self.rinumera({d.year})
        self.con.commit()

    def unisci(self, estrazioni: list[Estrazione], sostituisci_conflitti: bool = False) -> EsitoUnione:
        """Aggiunge un blocco di estrazioni evitando duplicati. Usato da import file e Internet."""
        esito = EsitoUnione()
        anni_toccati: set[int] = set()
        visti: dict[date, Estrazione] = {}
        for e in estrazioni:
            errori, _ = valida(e)
            if errori:
                esito.scartate.append((e, errori))
                continue
            # duplicati interni al file stesso
            if e.data in visti:
                if visti[e.data].chiave_numeri() == e.chiave_numeri():
                    esito.duplicate += 1
                    continue
            visti[e.data] = e
            esistente = self.per_data(e.data)
            if esistente is None:
                self._scrivi(e, sostituisci=False)
                esito.nuove += 1
                anni_toccati.add(e.anno)
            elif esistente.chiave_numeri() == e.chiave_numeri() and not (
                    esistente.superstar and e.superstar and esistente.superstar != e.superstar):
                # stessi numeri: completiamo eventuali dati mancanti
                cambiato = False
                if esistente.superstar is None and e.superstar is not None:
                    esistente.superstar = e.superstar
                    cambiato = True
                if esistente.numeri == esistente.sestina and e.numeri != e.sestina:
                    esistente.numeri = list(e.numeri)
                    cambiato = True
                if esistente.montepremi is None and e.montepremi is not None:
                    esistente.montepremi = e.montepremi
                    cambiato = True
                if cambiato:
                    self._scrivi(esistente, sostituisci=True)
                    esito.completate += 1
                else:
                    esito.duplicate += 1
            elif sostituisci_conflitti:
                self._scrivi(e, sostituisci=True)
                esito.sostituite += 1
                anni_toccati.add(e.anno)
            else:
                esito.conflitti.append((esistente, e))
        self.rinumera(anni_toccati)
        self.con.commit()
        return esito

    def rinumera(self, anni: set[int] | None = None) -> None:
        """Ricalcola il numero di concorso come progressivo nell'anno."""
        if anni is None:
            anni = set(self.anni())
        for anno in anni:
            date_anno = [r[0] for r in self.con.execute(
                "SELECT data FROM estrazioni WHERE anno=? ORDER BY data", (anno,))]
            self.con.executemany("UPDATE estrazioni SET concorso=? WHERE data=?",
                                 [(i + 1, d) for i, d in enumerate(date_anno)])

    def svuota(self) -> None:
        self.con.execute("DELETE FROM estrazioni")
        self.con.execute("DELETE FROM quote")
        self.con.commit()

    # ------------------------------------------------------------ impostazioni
    def leggi_impostazione(self, chiave: str, predefinito: str | None = None) -> str | None:
        r = self.con.execute("SELECT valore FROM impostazioni WHERE chiave=?", (chiave,)).fetchone()
        return r[0] if r else predefinito

    def scrivi_impostazione(self, chiave: str, valore: str) -> None:
        self.con.execute("INSERT OR REPLACE INTO impostazioni VALUES (?,?)", (chiave, valore))
        self.con.commit()

    # ---------------------------------------------------------- backup/ripristino
    def backup(self, destinazione: str | Path) -> None:
        dest = sqlite3.connect(str(destinazione))
        with dest:
            self.con.backup(dest)
        dest.close()

    def ripristina(self, sorgente: str | Path) -> None:
        prova = sqlite3.connect(str(sorgente))
        try:
            prova.execute("SELECT COUNT(*) FROM estrazioni").fetchone()
        finally:
            prova.close()
        self.con.close()
        shutil.copyfile(str(sorgente), str(self.percorso))
        self.con = sqlite3.connect(str(self.percorso))
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)


def verifica_integrita(arch: Archivio) -> list[str]:
    """Rapporto testuale su possibili anomalie dell'archivio."""
    righe: list[str] = []
    tutte = arch.tutte()
    if not tutte:
        return ["L'archivio è vuoto."]
    righe.append(f"Estrazioni in archivio: {len(tutte)}")
    righe.append(f"Dal {tutte[0].data:%d/%m/%Y} al {tutte[-1].data:%d/%m/%Y}")
    problemi = 0
    for e in tutte:
        errori, avvisi = valida(e)
        for m in errori:
            righe.append(f"ERRORE  {e.data:%d/%m/%Y}: {m}")
            problemi += 1
        for m in avvisi:
            righe.append(f"Avviso  {e.data:%d/%m/%Y}: {m}")
    for a, b in zip(tutte, tutte[1:]):
        giorni = (b.data - a.data).days
        if giorni > 7:
            righe.append(f"Avviso  intervallo di {giorni} giorni tra {a.data:%d/%m/%Y} e {b.data:%d/%m/%Y} "
                         "(controllare se mancano concorsi)")
    senza_ss = [e for e in tutte if e.superstar is None and e.data.year >= 2007]
    if senza_ss:
        righe.append(f"Avviso  {len(senza_ss)} estrazioni dal 2007 in poi senza SuperStar")
    righe.append("")
    righe.append("Concorsi per anno:")
    conteggio: dict[int, int] = {}
    for e in tutte:
        conteggio[e.anno] = conteggio.get(e.anno, 0) + 1
    for anno, n in conteggio.items():
        righe.append(f"  {anno}: {n}")
    righe.insert(2, "Nessun errore grave trovato." if problemi == 0 else f"Errori gravi: {problemi}")
    return righe
