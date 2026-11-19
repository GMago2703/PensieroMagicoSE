"""Menu "Le mie giocate": tutte le combinazioni generate dal programma (macchina, Magico Pensiero, AI,
sistemi) e quelle registrate come giocate, con la verifica sull'archivio.

Ogni gioco ha il suo elenco (sta nell'archivio del gioco: SuperEnalotto ed Eurojackpot restano separati).
Le voci si creano da sole quando il programma genera qualcosa; le previsioni di Magico Pensiero (anche con
l'AI) e le giocate del registro (Ricevitoria) vengono riprese con sincronizza().
"""
from __future__ import annotations

import json
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from math import comb

import numpy as np

from . import giocate as gc
from .gioco import Gioco

CHIAVE = "mie_giocate"
MAX_COLONNE = 300_000          # oltre, del sistema si salvano solo le impostazioni (si risviluppa)
MAX_VOCI = 2000

CATEGORIE = [("mie_colonne", "Le mie colonne"),
             ("colonne_casuali", "Colonne casuali"),
             ("sistemi_casuali", "Sistemi casuali"),
             ("magico", "Magico Pensiero"),
             ("magico_ai", "Magico Pensiero + AI"),
             ("colonna_magica", "Colonna magica"),
             ("sistemi", "Sistemi ridotti / condizionati / integrali"),
             ("altre", "Altre giocate")]
NOMI = dict(CATEGORIE)


@dataclass
class Voce:
    categoria: str
    titolo: str
    colonne: list[list[int]] = field(default_factory=list)
    extra: list[list[int]] = field(default_factory=list)   # per colonna: SE [SuperStar] o []; EJ [e1, e2]
    numeri: list[int] = field(default_factory=list)        # numeri del sistema (sistemi casuali / sistemi)
    numeri_extra: list[int] = field(default_factory=list)  # EJ: Euronumeri del sistema casuale
    sistema: str = ""                                      # Sistema.a_json() per riaprirlo nell'editor
    dal: str = ""                                          # primo concorso utile dopo la creazione
    creata: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    giocata_id: str = ""                                   # id nel registro delle giocate ("" = solo generata)
    nascosta: bool = False
    note: str = ""
    chiave: str = ""                                       # origine importata (previsione / registro)
    previsione: dict = field(default_factory=dict)         # previsione di Magico Pensiero (per la home)
    origini: list = field(default_factory=list)            # colonna magica: provenienza di ogni numero
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    @property
    def giocata(self) -> bool:
        return bool(self.giocata_id)

    @property
    def n_colonne(self) -> int:
        if self.colonne:
            return len(self.colonne)
        return comb(len(self.numeri), self._k) if self.numeri else 0

    _k = 6     # impostato da carica() secondo il gioco

    def integrale(self) -> bool:
        """Sistema casuale non sviluppato: si verifica come integrale dei suoi numeri."""
        return not self.colonne and bool(self.numeri)


def primo_concorso(quando: datetime) -> date:
    """Primo concorso che la combinazione può giocare: le estrazioni sono alle 20."""
    return quando.date() if quando.hour < 20 else quando.date() + timedelta(days=1)


# ------------------------------------------------------------------ memoria
def _leggi(archivio) -> dict:
    try:
        d = json.loads(archivio.leggi_impostazione(CHIAVE) or "{}")
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def carica(archivio) -> list[Voce]:
    campi = set(Voce.__dataclass_fields__) - {"_k"}
    out = []
    for x in _leggi(archivio).get("voci", []):
        v = Voce(**{k: y for k, y in x.items() if k in campi})
        v._k = archivio.gioco.k
        out.append(v)
    return out


def salva_tutte(archivio, voci: list[Voce], eliminate: list[str] | None = None) -> None:
    d = _leggi(archivio)
    if eliminate is not None:
        d["eliminate"] = sorted(set(eliminate))[-5000:]
    # le più vecchie, solo generate e non giocate, escono per prime se l'elenco è troppo lungo
    if len(voci) > MAX_VOCI:
        togli = len(voci) - MAX_VOCI
        nuovo = []
        for v in voci:
            if togli and not v.giocata and not v.note:
                togli -= 1
                continue
            nuovo.append(v)
        voci = nuovo
    d["voci"] = [{k: y for k, y in asdict(v).items()} for v in voci]
    archivio.scrivi_impostazione(CHIAVE, json.dumps(d, ensure_ascii=False, separators=(",", ":")))


def eliminate(archivio) -> list[str]:
    return list(_leggi(archivio).get("eliminate", []))


def aggiungi(archivio, voce: Voce) -> Voce:
    voci = carica(archivio)
    if not voce.dal:
        voce.dal = primo_concorso(datetime.fromisoformat(voce.creata)).isoformat()
    # stessa cosa generata di nuovo (es. stesso sistema risviluppato): si aggiorna la voce esistente
    for v in reversed(voci[-30:]):
        if v.categoria == voce.categoria and _uguali(v, voce):
            v.creata, v.dal = voce.creata, voce.dal
            v.sistema = voce.sistema or v.sistema
            v.colonne = voce.colonne or v.colonne
            v.origini = voce.origini or v.origini
            salva_tutte(archivio, voci)
            return v
        # sistema casuale estratto e poi sviluppato: la voce dei soli numeri prende le colonne
        if (v.categoria == voce.categoria == "sistemi_casuali" and not v.colonne and voce.colonne
                and sorted(v.numeri) == sorted(voce.numeri)):
            v.colonne, v.sistema, v.titolo = voce.colonne, voce.sistema, voce.titolo
            salva_tutte(archivio, voci)
            return v
    voci.append(voce)
    salva_tutte(archivio, voci)
    return voce


def _norm(cols) -> list[tuple]:
    return sorted(tuple(sorted(c)) for c in cols)


def _uguali(a: Voce, b: Voce) -> bool:
    if a.colonne or b.colonne:
        return len(a.colonne) == len(b.colonne) and _norm(a.colonne) == _norm(b.colonne) and a.extra == b.extra
    return sorted(a.numeri) == sorted(b.numeri) and a.numeri_extra == b.numeri_extra


def modifica(archivio, id_: str, **campi) -> None:
    voci = carica(archivio)
    for v in voci:
        if v.id == id_:
            for k, x in campi.items():
                setattr(v, k, x)
    salva_tutte(archivio, voci)


def elimina(archivio, id_: str) -> None:
    voci = carica(archivio)
    tolte = [c for v in voci if v.id == id_ for c in (v.chiave, f"reg:{v.giocata_id}" if v.giocata_id else "") if c]
    salva_tutte(archivio, [v for v in voci if v.id != id_], eliminate(archivio) + tolte)


# ------------------------------------------------------------------ voci create dal programma
def da_macchina(archivio, modo: str, risultati: list[dict]) -> Voce | None:
    g = archivio.gioco
    if not risultati:
        return None
    if modo == "sistema":
        r = risultati[0]
        v = Voce("sistemi_casuali", f"Sistema casuale di {len(r['numeri'])} numeri (macchina)",
                 numeri=sorted(r["numeri"]), numeri_extra=list(r["extra"]) if g.is_ej else [])
    else:
        cols = [sorted(r["numeri"]) for r in risultati]
        extra = [list(r["extra"]) for r in risultati]
        nome = g.nome_comb_pl if len(cols) > 1 else g.nome_comb
        v = Voce("colonne_casuali", f"{len(cols)} {nome} casual{'i' if len(cols) > 1 else 'e'} (macchina)",
                 colonne=cols, extra=extra)
    return aggiungi(archivio, v)


def da_sistema(archivio, s, categoria: str = "sistemi", titolo: str = "") -> Voce:
    """Sistema sviluppato (oggetto core.sistemi.Sistema con le colonne)."""
    from . import sistemi as sis
    tipo = sis.TIPI.get(s.tipo, s.tipo)
    if s.tipo == "condizionato" and not s.condizioni:
        tipo = "Integrale"
    titolo = titolo or (f"«{s.nome}» – " if s.nome else "") + f"{tipo} di {len(s.numeri)} numeri"
    if s.garanzia:
        titolo += f", garanzia n-{s.garanzia}"
    cols = [list(map(int, c)) for c in s.colonne]
    js = s.a_json()
    if len(cols) > MAX_COLONNE:
        cols = []
        d = json.loads(js)
        d["colonne"] = []
        js = json.dumps(d)
    extra = []
    if archivio.gioco.is_ej and "Euronumeri estratti" in (s.note or ""):
        try:
            eu = [int(x) for x in s.note.split("Euronumeri estratti:")[1].replace("e", " ").split()[:2]]
            extra = [eu for _ in cols]
        except (ValueError, IndexError):
            extra = []
    v = Voce(categoria, titolo, colonne=cols, extra=extra, numeri=sorted(s.numeri), sistema=js)
    if categoria == "sistemi_casuali" and extra:
        v.numeri_extra = extra[0]
    return aggiungi(archivio, v)


def _categoria_da_origine(origine: str) -> str:
    o = (origine or "").lower()
    if "mie colonne" in o:
        return "mie_colonne"
    if "colonna magica" in o:
        return "colonna_magica"
    if "magico" in o and any(x in o for x in ("ai", "gemini", "claude", "intelligenza")):
        return "magico_ai"
    if "magico" in o:
        return "magico"
    if "sistema casuale" in o:
        return "sistemi_casuali"
    if "macchina" in o or "casual" in o:
        return "colonne_casuali"
    if "sistema" in o or "sviluppo" in o:
        return "sistemi"
    return "altre"


def sincronizza(archivio) -> list[Voce]:
    """Riprende le previsioni di Magico Pensiero e le giocate del registro; collega le voci generate alle
    giocate registrate con le stesse colonne. Restituisce l'elenco aggiornato."""
    from . import magico
    g = archivio.gioco
    voci = carica(archivio)
    via = set(eliminate(archivio))
    chiavi = {v.chiave for v in voci if v.chiave}
    cambiato = False
    for p in magico.leggi_previsioni(archivio):
        o = p.get("origine", "Algoritmo")
        ch = f"prev:{p.get('dopo')}|{o}"
        if ch in chiavi or ch in via or not p.get("sestine"):
            continue
        dopo = date.fromisoformat(p["dopo"]) if p.get("dopo") else None
        if g.is_ej:
            cols = [sorted(p["sestine"][0])]
            extra = [[x for x in (p.get("jolly"), p.get("superstar")) if x]]
        else:
            cols = [sorted(s) for s in p["sestine"]]
            extra = [[p["superstar"]] if p.get("superstar") else [] for _ in cols]
        ai = o != "Algoritmo"
        quando = f" per il concorso dopo il {dopo:%d/%m/%Y}" if dopo else ""
        titolo = (f"Scelta di {o}" if ai else "Proposta di Magico Pensiero") + quando
        gen = p.get("generata") or (dopo.isoformat() if dopo else date.today().isoformat())
        voci.append(Voce("magico_ai" if ai else "magico", titolo, colonne=cols, extra=extra,
                         dal=(dopo + timedelta(days=1)).isoformat() if dopo else gen,
                         creata=gen + "T12:00:00", chiave=ch, previsione=p))
        chiavi.add(ch)
        cambiato = True
    registro = {x.id: x for x in gc.carica(archivio)}
    collegate = {v.giocata_id for v in voci if v.giocata_id}
    for v in voci:                                    # giocata tolta dal registro: torna "generata"
        if v.giocata_id and v.giocata_id not in registro:
            v.giocata_id = ""
            cambiato = True
    nuove = []
    for v in voci:
        if v.chiave.startswith("reg:") and v.chiave[4:] not in registro:
            cambiato = True                           # importata dal registro e poi eliminata là
            continue
        nuove.append(v)
    voci = nuove
    for x in registro.values():
        if x.id in collegate or f"reg:{x.id}" in via:
            continue
        cx = _norm(x.colonne)
        simile = next((v for v in reversed(voci) if not v.giocata_id and v.colonne
                       and len(v.colonne) == len(x.colonne) and _norm(v.colonne) == cx), None)
        if simile is not None:
            simile.giocata_id = x.id
        else:
            voci.append(Voce(_categoria_da_origine(x.origine), x.nome or "Giocata", colonne=x.colonne,
                             extra=x.extra, dal=x.dal, creata=x.creata, giocata_id=x.id, chiave=f"reg:{x.id}"))
        cambiato = True
    if cambiato:
        salva_tutte(archivio, voci)
    for v in voci:
        v._k = g.k
    return voci


def collega(archivio, id_voce: str, giocata: gc.Giocata) -> None:
    modifica(archivio, id_voce, giocata_id=giocata.id)


# ------------------------------------------------------------------ verifica sull'archivio
@dataclass
class Verifica:
    concorsi: list[date]
    per_concorso: list[Counter]              # categoria -> quante colonne
    importi: list[float]                     # vinto per concorso (quote note)
    ignote: int                              # vincite con quota non nota
    punti_max: list[int]                     # punti migliori per concorso
    spesa: float
    esempi: list[tuple[int, int, str]] = field(default_factory=list)   # (concorso, colonna, categoria)

    @property
    def totale(self) -> Counter:
        t: Counter = Counter()
        for c in self.per_concorso:
            t.update(c)
        return t

    @property
    def vinto(self) -> float:
        return sum(self.importi)

    @property
    def migliore(self) -> int:
        return max(self.punti_max, default=0)


def _ordine(g: Gioco) -> list[str]:
    return gc.ORDINE_EJ if g.is_ej else gc.ORDINE_SE


def migliore_categoria(g: Gioco, cont: Counter) -> str:
    for c in _ordine(g):
        if cont.get(c):
            return c
    return ""


def _conta_colonne(g: Gioco, colonne, extra, righe, esempi_max=300):
    """Per ogni estrazione: Counter delle categorie vincenti, punti massimi; a blocchi di colonne."""
    C_tutte = np.asarray(colonne, dtype=np.int64)
    nr = len(righe)
    M = np.zeros((nr, g.n + 1), dtype=bool)
    for i, r in enumerate(righe):
        M[i, r[1]] = True
    a1 = np.array([r[2] or 0 for r in righe])        # Jolly / Euronumero 1
    a2 = np.array([r[3] or 0 for r in righe])        # SuperStar / Euronumero 2
    if g.is_ej:
        EX = np.array([(list(e) + [0, 0])[:2] if e else [0, 0] for e in (extra or [[]] * len(C_tutte))]
                      if extra else np.zeros((len(C_tutte), 2)), dtype=np.int64).reshape(-1, 2)
    else:
        SS = np.array([(e[0] if e else 0) for e in extra] if extra else np.zeros(len(C_tutte)), dtype=np.int64)
    per = [Counter() for _ in range(nr)]
    pmax = np.zeros(nr, dtype=int)
    esempi = []
    blocco = 1500
    due_dal = np.array([r[0] >= date(2016, 2, 1) for r in righe])
    for b0 in range(0, len(C_tutte), blocco):
        C = C_tutte[b0:b0 + blocco]
        P = M[:, C].sum(axis=2, dtype=np.int8)                 # estrazioni × colonne
        pmax = np.maximum(pmax, P.max(axis=1))
        if g.is_ej:
            E = EX[b0:b0 + blocco]
            eu = ((a1[:, None] == E[None, :, 0]) & (E[None, :, 0] > 0)).astype(np.int8) + \
                 ((a2[:, None] == E[None, :, 1]) & (E[None, :, 1] > 0)) + \
                 ((a1[:, None] == E[None, :, 1]) & (E[None, :, 1] > 0)) + \
                 ((a2[:, None] == E[None, :, 0]) & (E[None, :, 0] > 0))
            for p in range(1, 6):
                for e in range(0, 3):
                    cat = f"{p}+{e}"
                    if cat not in gc.ORDINE_EJ:
                        continue
                    I, J = np.nonzero((P == p) & (eu == e))
                    _accumula(per, esempi, I, J, b0, cat, esempi_max)
        else:
            S = SS[b0:b0 + blocco]
            ss = (a2[:, None] == S[None, :]) & (S[None, :] > 0)
            J1 = np.zeros_like(P, dtype=bool)
            if (P == 5).any():
                for i in np.flatnonzero((P == 5).any(axis=1)):
                    J1[i] = (C == a1[i]).any(axis=1)
            for p in range(0, 7):
                if p < 6:
                    I, J = np.nonzero(ss & (P == p))
                    _accumula(per, esempi, I, J, b0, f"SS{p}", esempi_max)
                base = ~ss if p < 6 else np.ones_like(ss)
                if p == 6:
                    I, J = np.nonzero(P == 6)
                    _accumula(per, esempi, I, J, b0, "6", esempi_max)
                elif p == 5:
                    I, J = np.nonzero(base & (P == 5) & J1)
                    _accumula(per, esempi, I, J, b0, "5+1", esempi_max)
                    I, J = np.nonzero(base & (P == 5) & ~J1)
                    _accumula(per, esempi, I, J, b0, "5", esempi_max)
                elif p >= 3:
                    I, J = np.nonzero(base & (P == p))
                    _accumula(per, esempi, I, J, b0, str(p), esempi_max)
                elif p == 2:
                    I, J = np.nonzero(base & (P == 2) & due_dal[:, None])
                    _accumula(per, esempi, I, J, b0, "2", esempi_max)
    return per, [int(x) for x in pmax], esempi


def _accumula(per, esempi, I, J, b0, cat, esempi_max):
    if not len(I):
        return
    for i, n in zip(*np.unique(I, return_counts=True)):
        per[int(i)][cat] += int(n)
    if len(esempi) < esempi_max:
        for i, j in list(zip(I, J))[:esempi_max - len(esempi)]:
            esempi.append((int(i), int(j) + b0, cat))


def _conta_integrale(g: Gioco, numeri, numeri_extra, righe):
    """Sistema integrale dei 'numeri': quante colonne fanno p punti in ogni estrazione (calcolo esatto)."""
    k, K = len(numeri), g.k
    S = set(numeri)
    per, pmax = [], []
    for r in righe:
        h = len(S & set(r[1]))
        c: Counter = Counter()
        if g.is_ej:
            eu = sum(1 for x in numeri_extra if x in (r[2], r[3]))
            for p in range(1, 6):
                n = comb(h, p) * comb(k - h, K - p)
                if n and f"{p}+{eu}" in gc.ORDINE_EJ:
                    c[f"{p}+{eu}"] += n
        else:
            jolly_dentro = r[2] in S
            for p in range(2, 7):
                n = comb(h, p) * comb(k - h, K - p)
                if not n:
                    continue
                if p == 5 and jolly_dentro:
                    c["5+1"] += comb(h, 5)
                    n -= comb(h, 5)
                if p == 2 and r[0] < date(2016, 2, 1):
                    continue
                if n:
                    c[str(p)] += n
        per.append(c)
        pmax.append(min(h, K))
    return per, pmax


def righe_per(voce: Voce, righe_archivio, modo: str) -> list:
    """modo "dopo": i concorsi dalla creazione in poi; "storico": tutto l'archivio."""
    if modo == "storico":
        return list(righe_archivio)
    dal = date.fromisoformat(voce.dal) if voce.dal else date.min
    return [r for r in righe_archivio if r[0] >= dal]


def verifica(g: Gioco, voce: Voce, righe_archivio, modo: str = "dopo", quote=None,
             prezzi: dict | None = None) -> Verifica:
    righe = righe_per(voce, righe_archivio, modo)
    if voce.integrale():
        per, pmax = _conta_integrale(g, voce.numeri, voce.numeri_extra, righe)
        esempi = []
        n_col = comb(len(voce.numeri), g.k)
        from . import sistemi as sis
        costo = sis.costo(n_col, g, prezzi or {})
    else:
        per, pmax, esempi = _conta_colonne(g, voce.colonne, voce.extra, righe)
        costo = gc.costo_giocata(g, voce.colonne, voce.extra or [[] for _ in voce.colonne], prezzi)
    importi, ignote = [], 0
    for r, c in zip(righe, per):
        tot = 0.0
        for cat, n in c.items():
            q = quote(r[0], cat) if quote else None
            if q is None:
                ignote += n
            else:
                tot += q * n
        importi.append(tot)
    return Verifica([r[0] for r in righe], per, importi, ignote, pmax, costo * len(righe), esempi)


def riassunto(g: Gioco, v: Verifica) -> str:
    """Una riga: concorsi controllati e vincita migliore."""
    if not v.concorsi:
        return "nessun concorso ancora estratto"
    t = v.totale
    if not t:
        return f"{len(v.concorsi)} concorsi: nessuna vincita (al massimo {v.migliore} punti)"
    m = migliore_categoria(g, t)
    return f"{len(v.concorsi)} concorsi: {sum(t.values())} vincite, la migliore {gc.nome_categoria(m)}"


# ------------------------------------------------------------------ le mie colonne (scritte dall'utente)
def aggiungi_mie_colonne(archivio, titolo: str, colonne, extra=None, note: str = "") -> Voce:
    """Colonne scritte dall'utente: restano nell'elenco finché non le elimina (anche se uguali a altre)."""
    voci = carica(archivio)
    v = Voce("mie_colonne", titolo.strip() or "Le mie colonne", colonne=[sorted(c) for c in colonne],
             extra=[list(e) for e in (extra or [[] for _ in colonne])], note=note.strip())
    v.dal = primo_concorso(datetime.fromisoformat(v.creata)).isoformat()
    voci.append(v)
    salva_tutte(archivio, voci)
    return v


# ------------------------------------------------------------------ analisi di una colonna
@dataclass
class Caratteristica:
    nome: str
    valore: int
    perc_archivio: float        # % delle estrazioni che hanno questo valore
    perc_caso: float            # % attesa da combinazioni casuali (nan se non calcolabile)
    tipica: bool                # nell'insieme / intervallo che copre l'80% delle estrazioni


@dataclass
class ProfiloColonna:
    colonna: list[int]
    caratteristiche: list[Caratteristica]
    migliore: int                # numeri in comune con l'estrazione più simile
    quando: list[date]           # estrazioni (al massimo 5) in cui è successo
    uscite: dict[int, int]       # punti -> quante volte la colonna avrebbe fatto quel punteggio (>=2)

    @property
    def tipiche(self) -> int:
        return sum(1 for c in self.caratteristiche if c.tipica)


def profilo(g: Gioco, colonne, ctx, righe_archivio) -> list[ProfiloColonna]:
    """Per ogni colonna: il valore di ogni condizione (somma, pari, consecutivi...) con la frequenza che quel
    valore ha avuto nelle estrazioni reali, e l'estrazione dell'archivio più simile."""
    from . import condizioni as cnd
    C = np.asarray(colonne, dtype=np.int64).reshape(-1, g.k)
    analisi: list[tuple[str, object, object, object]] = []
    for t in cnd.tipi_del_gioco(g):
        if t.codice == "posizione":
            params = [(1, "1ª posizione"), (g.k, f"{g.k}ª posizione")]
        else:
            params = [(t.param_def, "")]
        for par, etichetta in params:
            try:
                a = cnd.analizza(t.codice, ctx, par)
                val = t.funzione(C, ctx, par)
            except Exception:                # noqa: BLE001 – es. popolarità senza modello
                continue
            nome = f"{t.nome} ({etichetta})" if etichetta else t.nome
            if t.param_nome and not etichetta and t.codice != "posizione":
                nome += f" – {t.param_nome.lower()} {par}"
            analisi.append((nome, t, a, val))
    nr = len(righe_archivio)
    M = np.zeros((max(nr, 1), g.n + 1), dtype=np.int8)
    for i, r in enumerate(righe_archivio):
        M[i, r[1]] = 1
    punti = M[:, C].sum(axis=2) if nr else np.zeros((1, len(C)), dtype=int)       # estrazioni × colonne
    out = []
    for j, c in enumerate(C):
        car = []
        for nome, t, a, val in analisi:
            v = int(val[j])
            riga = next((r for r in a.righe if r[0] == v), None)
            perc, caso = (riga[2], riga[3]) if riga else (0.0, float("nan"))
            tip = (a.copertura[0] <= v <= a.copertura[1]) if t.modo == "intervallo" else v in a.valori_80
            car.append(Caratteristica(nome, v, perc, caso, bool(tip)))
        col = punti[:, j]
        mx = int(col.max()) if nr else 0
        quando = [righe_archivio[i][0] for i in np.flatnonzero(col == mx)[-5:]] if nr and mx else []
        uscite = {p: int((col == p).sum()) for p in range(2, g.k + 1) if nr and (col == p).any()}
        out.append(ProfiloColonna(c.tolist(), car, mx, quando, uscite))
    return out


def aggiungi_colonna_magica(archivio, r) -> Voce:
    """Salva una colonna magica (core.colonna_magica.ColonnaMagica) con la provenienza di ogni numero."""
    from datetime import datetime as _dt
    voce = Voce("colonna_magica", f"Colonna magica del {_dt.now():%d/%m/%Y %H:%M}", colonne=[r.colonna],
                extra=[list(r.euronumeri)] if r.euronumeri else [[]], origini=[n.a_dict() for n in r.numeri])
    return aggiungi(archivio, voce)
