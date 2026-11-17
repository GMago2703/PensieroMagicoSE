"""Magico Pensiero – prima bozza dell'algoritmo (versione 0.1).

IPOTESI DI LAVORO (come concordato): le estrazioni non sono indipendenti, ma
ognuna conserva una "memoria" delle precedenti. L'algoritmo prova a leggere
questa memoria in quattro modi e ne fa una sintesi.

1. PUNTEGGIO DI OGNI NUMERO (0..1), somma pesata di cinque "voci":
   - Eco      : quanto il numero tende a uscire 1, 2, 3 estrazioni dopo i numeri
                appena usciti (matrice di transizione, corretta per la frequenza
                di base del numero: conta il "di più" rispetto al caso);
   - Affinità : quanto il numero tende a uscire INSIEME ai numeri dell'ultima estrazione;
   - Tendenza : se nelle ultime estrazioni esce più del suo solito ("caldo");
   - Maturità : ritardo attuale rispetto al suo ritardo medio;
   - Storico  : frequenza su tutto l'archivio;
   - più eventuali analisi personalizzate dell'utente con il loro peso.

2. COSTRUZIONE DELLE SESTINE: si generano migliaia di sestine estraendo i numeri
   con probabilità proporzionale al punteggio; si scartano quelle con una
   "forma" rara nello storico (somma, pari/dispari, alti/bassi, consecutivi,
   decine), quelle già uscite e quelle che hanno troppi (o troppo pochi) numeri
   in comune con le estrazioni passate rispetto a quanto accade alle vere
   combinazioni vincenti (analisi "Somiglianza con l'archivio", di solito 3-4).

3. VALUTAZIONE: ogni sestina riceve un voto = punteggio medio dei numeri
   + legame tra i suoi numeri (coppie che storicamente escono insieme più del
   caso) + tipicità della forma.

4. SCELTA: le 3 sestine con voto più alto, con al massimo 2 numeri in comune
   tra loro. Jolly = miglior numero rimasto fuori dalla 1ª sestina. SuperStar =
   stessa logica (eco, tendenza, maturità) applicata alla serie dei SuperStar.

Il risultato è riproducibile: con lo stesso archivio dà sempre le stesse sestine.
La VERIFICA STORICA rifà il calcolo "come se" fossimo in passato e confronta
i punti ottenuti con quelli di sestine scelte a caso.
"""
from __future__ import annotations

import json
import zlib
from dataclasses import asdict, dataclass, field
from datetime import date

import numpy as np

from .analisi import Storico, limiti_consigliati, massimi_in_comune

VOCI = {
    "eco": "Eco (numeri successivi)",
    "affinita": "Affinità con l'ultima estrazione",
    "tendenza": "Tendenza recente",
    "maturita": "Maturità del ritardo",
    "storico": "Frequenza storica",
}


@dataclass
class Impostazioni:
    pesi: dict[str, float] = field(default_factory=lambda: {
        "eco": 0.30, "affinita": 0.20, "tendenza": 0.20, "maturita": 0.20, "storico": 0.10})
    finestra_tendenza: int = 30
    profondita_eco: int = 3             # quante estrazioni precedenti "fanno eco"
    personalizzate: dict[str, float] = field(default_factory=dict)   # nome ricetta -> peso
    nitidezza: float = 3.0              # più alta = sestine più concentrate sui numeri migliori
    candidate: int = 6000
    max_comuni: int = 2                 # numeri in comune ammessi tra le 3 sestine
    # somiglianza con l'archivio: quanti numeri al massimo una sestina può avere in comune con
    # una qualsiasi estrazione passata. 0 = automatico (dall'analisi "Somiglianza con l'archivio")
    limite_archivio: int = 0
    soglia_archivio: float = 90.0       # copertura usata per il limite automatico (%)
    finestra_archivio: int = 500        # ultime estrazioni studiate per il limite automatico

    def a_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def da_json(t: str | None) -> "Impostazioni":
        if not t:
            return Impostazioni()
        try:
            d = json.loads(t)
            imp = Impostazioni()
            for k, v in d.items():
                if hasattr(imp, k):
                    setattr(imp, k, v)
            for k in VOCI:
                imp.pesi.setdefault(k, 0.0)
            return imp
        except (ValueError, TypeError):
            return Impostazioni()


@dataclass
class SestinaMagica:
    numeri: list[int]
    voto: float
    dettaglio: dict[str, float]


@dataclass
class RisultatoMagico:
    sestine: list[SestinaMagica]
    jolly: int
    superstar: int | None
    punteggi: dict[int, float]
    voci: dict[str, dict[int, float]]
    basata_su: date | None
    estrazioni_usate: int
    migliori: list[tuple[list[int], float]] = field(default_factory=list)   # le candidate con voto più alto
    limiti_archivio: tuple[int, int] = (0, 6)    # numeri in comune con l'archivio ammessi (min, max)
    in_comune_migliori: list[int] = field(default_factory=list)


# ------------------------------------------------------------------ utilità
def _norm(v: np.ndarray) -> np.ndarray:
    v = v.astype(float)
    lo, hi = v[1:].min(), v[1:].max()
    out = np.zeros(91)
    out[1:] = 0.5 if hi == lo else (v[1:] - lo) / (hi - lo)
    return out


def matrice(storico: Storico) -> np.ndarray:
    m = np.zeros((len(storico), 91), dtype=np.float32)
    for i, r in enumerate(storico):
        m[i, r[1]] = 1
    return m


def _serie_eco(m: np.ndarray, profondita: int) -> np.ndarray:
    """Eccesso di uscite dopo i numeri delle ultime estrazioni (lift rispetto al caso)."""
    n = len(m)
    base = m.mean(axis=0) + 1e-9
    tot = np.zeros(91)
    for d in range(1, profondita + 1):
        if n <= d:
            break
        ultimi = m[n - d] > 0                       # numeri usciti d estrazioni fa
        w = m[:n - d][:, ultimi].sum(axis=1)        # quante volte erano presenti in ogni estrazione
        if w.sum() == 0:
            continue
        osservati = w @ m[d:]                       # cosa è uscito d estrazioni dopo
        attesi = w.sum() * base
        tot += (osservati / attesi) / d             # le eco più vicine contano di più
    return tot


def _affinita(m: np.ndarray, pairs_lift: np.ndarray) -> np.ndarray:
    ultimi = np.where(m[-1] > 0)[0]
    return pairs_lift[:, ultimi].mean(axis=1)


def _ritardi(m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(m)
    rit = np.full(91, n, dtype=float)
    presenti = m > 0
    for k in range(1, 91):
        idx = np.flatnonzero(presenti[:, k])
        if len(idx):
            rit[k] = n - 1 - idx[-1]
    freq = m.sum(axis=0)
    medio = (n - freq) / (freq + 1)
    return rit, medio


def _lift_coppie(m: np.ndarray) -> np.ndarray:
    n = len(m)
    c = m.T @ m
    f = np.diag(c).copy()
    attesi = np.outer(f, f) / max(n, 1) + 1e-9
    lift = c / attesi
    np.fill_diagonal(lift, 1.0)
    lift[0, :] = 1.0
    lift[:, 0] = 1.0
    return lift


def _profilo(s: np.ndarray) -> tuple[np.ndarray, ...]:
    pari = (s % 2 == 0).sum(axis=1)
    alti = (s > 45).sum(axis=1)
    cons = (np.diff(s, axis=1) == 1).sum(axis=1)
    somma = s.sum(axis=1)
    dec = (s - 1) // 10
    maxdec = np.zeros(len(s), dtype=int)
    for d in range(9):
        maxdec = np.maximum(maxdec, (dec == d).sum(axis=1))
    return pari, alti, cons, somma, maxdec


# ---------------------------------------------------------------- algoritmo
def calcola_punteggi(storico: Storico, imp: Impostazioni, m: np.ndarray | None = None,
                     extra: dict[str, dict[int, float]] | None = None):
    if m is None:
        m = matrice(storico)
    lift = _lift_coppie(m)
    rit, medio = _ritardi(m)
    n = len(m)
    breve = min(imp.finestra_tendenza, n)
    tendenza = m[-breve:].sum(axis=0) - m.sum(axis=0) * breve / n
    maturita = np.clip(rit / np.maximum(medio, 1e-9), 0, 3)       # oltre 3 volte il solito non aggiunge
    voci = {
        "eco": _norm(_serie_eco(m, imp.profondita_eco)),
        "affinita": _norm(_affinita(m, lift)),
        "tendenza": _norm(tendenza),
        "maturita": _norm(maturita),
        "storico": _norm(m.sum(axis=0)),
    }
    totale = np.zeros(91)
    somma_pesi = 0.0
    for k, v in voci.items():
        p = float(imp.pesi.get(k, 0))
        totale += p * v
        somma_pesi += abs(p)
    for nome, punteggi in (extra or {}).items():
        p = float(imp.personalizzate.get(nome, 0))
        if p:
            arr = np.zeros(91)
            for k2, val in punteggi.items():
                arr[k2] = val
            voci["★ " + nome] = _norm(arr)
            totale += p * voci["★ " + nome]
            somma_pesi += abs(p)
    totale = _norm(totale / max(somma_pesi, 1e-9))
    return totale, voci, lift, m


def _limiti_forma(m: np.ndarray, storico: Storico):
    somme = np.array([sum(r[1]) for r in storico]) if storico else np.array([273])
    lo, hi = np.percentile(somme, [15, 85])
    return int(lo), int(hi)


def _superstar(storico: Storico, imp: Impostazioni) -> int | None:
    serie = [r[3] for r in storico if r[3]]
    if len(serie) < 20:
        return None
    s = np.zeros((len(serie), 91), dtype=np.float32)
    s[np.arange(len(serie)), serie] = 1
    eco = _serie_eco(s, 1)
    breve = min(imp.finestra_tendenza * 3, len(serie))
    tend = s[-breve:].sum(axis=0) - s.sum(axis=0) * breve / len(serie)
    rit, medio = _ritardi(s)
    mat = np.clip(rit / np.maximum(medio, 1e-9), 0, 3)
    tot = 0.4 * _norm(eco) + 0.3 * _norm(tend) + 0.3 * _norm(mat)
    tot[0] = -1
    return int(np.argmax(tot))


def genera(storico: Storico, imp: Impostazioni | None = None,
           extra: dict[str, dict[int, float]] | None = None, m: np.ndarray | None = None) -> RisultatoMagico:
    imp = imp or Impostazioni()
    if len(storico) < 30:
        raise ValueError("Servono almeno 30 estrazioni in archivio.")
    punteggi, voci, lift, m = calcola_punteggi(storico, imp, m, extra)
    seme = zlib.crc32(f"{storico[-1][0].isoformat()}{len(storico)}{imp.a_json()}".encode())
    rng = np.random.default_rng(seme)

    # 2. candidate: campionamento pesato senza ripetizione
    pesi = np.maximum(punteggi[1:], 1e-4) ** imp.nitidezza
    chiavi = rng.random((imp.candidate, 90)) ** (1.0 / (pesi / pesi.sum() * 90))
    cand = np.sort(np.argpartition(-chiavi, 5, axis=1)[:, :6] + 1, axis=1)
    cand = np.unique(cand, axis=0)
    pari, alti, cons, somma, maxdec = _profilo(cand)
    s_lo, s_hi = _limiti_forma(m, storico)
    ok = ((pari >= 2) & (pari <= 4) & (alti >= 2) & (alti <= 4) & (cons <= 1)
          & (somma >= s_lo) & (somma <= s_hi) & (maxdec <= 2))
    if ok.sum() < 10:      # forma troppo restrittiva per questi punteggi: allenta
        ok = (pari >= 1) & (pari <= 5) & (cons <= 2) & (maxdec <= 3)
    cand = cand[ok]
    usciti = {tuple(r[1]) for r in storico}
    cand = np.array([c for c in cand if tuple(int(x) for x in c) not in usciti])
    if not len(cand):
        raise ValueError("Nessuna sestina candidata: prova a ridurre la nitidezza.")

    # somiglianza con l'archivio: massimo di numeri in comune con una qualsiasi estrazione passata
    lo, hi = limiti_archivio(storico, imp)
    vett = np.zeros((len(cand), 91), dtype=np.float32)
    np.put_along_axis(vett, cand.astype(np.int64), 1, axis=1)
    in_comune = (vett @ m.T).max(axis=1).astype(int)
    for allarga in range(0, 4):           # se i limiti lasciano troppe poche candidate, si allargano
        ok = (in_comune >= lo - allarga) & (in_comune <= hi + allarga)
        if ok.sum() >= 3:
            break
    cand, in_comune = cand[ok], in_comune[ok]

    # 3. voto
    media = punteggi[cand].mean(axis=1)
    i_a, i_b = np.triu_indices(6, 1)
    coppie = np.log(np.maximum(lift[cand[:, i_a], cand[:, i_b]], 1e-3)).mean(axis=1)
    # tipicità: quanto è comune nello storico la combinazione (pari, alti) della sestina
    sp, sa, _, _, _ = _profilo(np.array([r[1] for r in storico]))
    freq_forma = np.zeros((7, 7))
    np.add.at(freq_forma, (sp, sa), 1)
    freq_forma /= freq_forma.sum()
    pari_c, alti_c = _profilo(cand)[:2]
    tipicita = freq_forma[pari_c, alti_c] / freq_forma.max()
    coppie_n = (coppie - coppie.min()) / (np.ptp(coppie) + 1e-9)
    voto = 0.6 * media + 0.25 * coppie_n + 0.15 * tipicita

    # 4. scelta delle 3 sestine diverse tra loro
    scelte: list[SestinaMagica] = []
    for i in np.argsort(-voto):
        s = [int(x) for x in cand[i]]
        if all(len(set(s) & set(x.numeri)) <= imp.max_comuni for x in scelte):
            scelte.append(SestinaMagica(s, round(float(voto[i]), 4), {
                "max numeri in comune con l'archivio": int(in_comune[i]),
                "punteggio medio numeri": round(float(media[i]), 3),
                "legame tra i numeri": round(float(coppie_n[i]), 3),
                "tipicità della forma": round(float(tipicita[i]), 3)}))
        if len(scelte) == 3:
            break
    fuori = [k for k in np.argsort(-punteggi) if k > 0 and k not in scelte[0].numeri]
    jolly = int(fuori[0])
    ordine = np.argsort(-voto)[:40]
    migliori = [([int(x) for x in cand[i]], round(float(voto[i]), 4)) for i in ordine]
    return RisultatoMagico(scelte, jolly, _superstar(storico, imp),
                           {k: round(float(punteggi[k]), 4) for k in range(1, 91)},
                           {k: {n: round(float(v[n]), 4) for n in range(1, 91)} for k, v in voci.items()},
                           storico[-1][0], len(storico), migliori, (lo, hi), [int(in_comune[i]) for i in ordine])


def limiti_archivio(storico: Storico, imp: Impostazioni) -> tuple[int, int]:
    """Numeri in comune con l'archivio ammessi per una sestina: automatici (dall'analisi della
    somiglianza delle combinazioni vincenti con le precedenti) oppure fissati dall'utente."""
    if imp.limite_archivio:
        auto_lo, _ = limiti_consigliati(massimi_in_comune(storico, imp.finestra_archivio), imp.soglia_archivio)
        return min(auto_lo, imp.limite_archivio), imp.limite_archivio
    return limiti_consigliati(massimi_in_comune(storico, imp.finestra_archivio), imp.soglia_archivio)


# ---------------------------------------------------------- verifica storica
@dataclass
class EsitoVerifica:
    prove: int = 0
    distrib_mp: dict[int, int] = field(default_factory=dict)       # miglior punteggio tra le 3 sestine
    distrib_caso: dict[int, int] = field(default_factory=dict)
    numeri_mp: int = 0               # numeri indovinati in totale (3 sestine)
    numeri_caso: int = 0
    jolly_mp: int = 0
    superstar_mp: int = 0
    dettagli: list[tuple] = field(default_factory=list)   # (data, sestine, estratta, punti)

    def testo(self) -> str:
        if not self.prove:
            return "Nessuna prova eseguita."
        atteso = round(3 * 6 * 6 / 90 * self.prove, 1)
        r = [f"Concorsi provati: {self.prove}",
             f"Numeri indovinati in totale (3 sestine per concorso): Magico Pensiero {self.numeri_mp} — "
             f"sestine a caso {self.numeri_caso} — atteso teorico {atteso}",
             "", "Miglior risultato delle 3 sestine in ogni concorso:",
             "  punti   Magico Pensiero   A caso"]
        for k in range(7):
            if self.distrib_mp.get(k) or self.distrib_caso.get(k):
                r.append(f"   {k}         {self.distrib_mp.get(k, 0):5d}          {self.distrib_caso.get(k, 0):5d}")
        r.append("")
        r.append(f"Jolly indovinato (fra i 6 estratti): {self.jolly_mp}   SuperStar indovinato: {self.superstar_mp}")
        r.append("")
        # scarto dal valore atteso misurato in "deviazioni standard" (z): sotto 2 è normale oscillazione
        var = 3 * 6 * (6 / 90) * (84 / 90) * (84 / 89)
        z = (self.numeri_mp - atteso) / ((var * self.prove) ** 0.5)
        r.append(f"Scarto di Magico Pensiero dall'atteso: {z:+.2f} deviazioni standard.")
        if z >= 2:
            r.append("Lettura: risultato SUPERIORE al caso in modo statisticamente significativo.")
        elif z <= -2:
            r.append("Lettura: risultato INFERIORE al caso in modo statisticamente significativo.")
        else:
            r.append("Lettura: risultato in linea con il caso (le differenze sono normali oscillazioni). "
                     "Per giudicare servono molti concorsi: prova con 500 o più.")
        return "\n".join(r)


def verifica_storica(storico: Storico, concorsi: int = 100, imp: Impostazioni | None = None,
                     avanzamento=None, interrompi=None) -> EsitoVerifica:
    imp = imp or Impostazioni()
    es = EsitoVerifica()
    m_tot = matrice(storico)
    n = len(storico)
    inizio = max(100, n - concorsi)
    rng = np.random.default_rng(12345)
    for i in range(inizio, n):
        if interrompi and interrompi():
            break
        passato = storico[:i]
        estratta = set(storico[i][1])
        try:
            r = genera(passato, imp, m=m_tot[:i])
        except ValueError:
            continue
        punti = [len(estratta & set(s.numeri)) for s in r.sestine]
        caso = [len(estratta & set(rng.choice(np.arange(1, 91), 6, replace=False).tolist())) for _ in range(3)]
        es.prove += 1
        es.distrib_mp[max(punti)] = es.distrib_mp.get(max(punti), 0) + 1
        es.distrib_caso[max(caso)] = es.distrib_caso.get(max(caso), 0) + 1
        es.numeri_mp += sum(punti)
        es.numeri_caso += sum(caso)
        es.jolly_mp += int(r.jolly in estratta)
        es.superstar_mp += int(r.superstar is not None and r.superstar == storico[i][3])
        es.dettagli.append((storico[i][0], [s.numeri for s in r.sestine], sorted(estratta), punti))
        if avanzamento:
            avanzamento(i - inizio + 1, n - inizio)
    return es


# ------------------------------------------------------- storico previsioni
CHIAVE_IMP = "magico_impostazioni"
CHIAVE_PREV = "magico_previsioni"


def salva_previsione(archivio, r: RisultatoMagico, origine: str = "Algoritmo") -> None:
    elenco = json.loads(archivio.leggi_impostazione(CHIAVE_PREV, "[]") or "[]")
    voce = {"generata": date.today().isoformat(), "dopo": r.basata_su.isoformat() if r.basata_su else None,
            "sestine": [s.numeri for s in r.sestine], "jolly": r.jolly, "superstar": r.superstar,
            "origine": origine}
    # una previsione per concorso e per origine (algoritmo / Claude)
    elenco = [e for e in elenco
              if not (e.get("dopo") == voce["dopo"] and e.get("origine", "Algoritmo") == origine)] + [voce]
    archivio.scrivi_impostazione(CHIAVE_PREV, json.dumps(elenco[-500:]))


def leggi_previsioni(archivio) -> list[dict]:
    try:
        return json.loads(archivio.leggi_impostazione(CHIAVE_PREV, "[]") or "[]")
    except ValueError:
        return []
