"""Laboratorio: la casualità delle estrazioni è davvero casuale?

Il laboratorio non parte da un'idea preconcetta: interroga l'archivio con il metodo scientifico.

1. LA MACCHINA – cerca le "impronte" che un difetto fisico sistematico lascerebbe nei numeri:
   palline che escono più di altre (peso, dimensione), una posizione di uscita diversa dalle altre
   (la prima pallina rispetto alla sesta, o per il SuperEnalotto fino al 2009 una ruota del Lotto
   rispetto a un'altra), palline vicine nel caricamento che escono insieme o una dopo l'altra,
   coppie privilegiate, cambiamenti nel tempo (macchine o set di palline diversi), giorno della
   settimana, numeri speciali (Jolly, SuperStar, Euronumeri).
2. LA MEMORIA – cerca legami tra un concorso e i successivi: ripetizioni, numeri vicini,
   intervalli tra un'uscita e l'altra dello stesso numero.
3. LA PREVISIONE – una gara tra regole (frequenze, ritardi, catene di Markov, coppie, un modello
   di apprendimento automatico): ogni regola usa solo il passato e viene giudicata sui concorsi
   che non ha mai visto, contro il valore atteso del caso.

Ogni prova restituisce una probabilità p: quanto è probabile vedere un risultato così (o più
estremo) se le estrazioni fossero perfettamente casuali. Poiché si fanno molte prove, qualcuna
può sembrare "strana" per pura fortuna: per questo le p vengono corrette con il metodo di Holm
prima di dichiarare un'anomalia.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from .gioco import SE, Gioco

CAMBIO_SE = date(2009, 7, 1)          # fino al 30/6/2009 la sestina veniva dalle ruote del Lotto
RUOTE_SE = ["Bari", "Firenze", "Milano", "Napoli", "Palermo", "Roma"]
SOGLIA = 0.05                          # anomalia se p corretta (Holm) < 5%
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


# ------------------------------------------------------------------ statistica (senza librerie esterne)
def _gamma_q(a: float, x: float) -> float:
    """Funzione gamma incompleta superiore regolarizzata Q(a, x)."""
    if x <= 0:
        return 1.0
    lg = math.lgamma(a)
    if x < a + 1:                                   # serie
        s = t = 1.0 / a
        ap = a
        for _ in range(10000):
            ap += 1
            t *= x / ap
            s += t
            if abs(t) < abs(s) * 1e-14:
                break
        return max(0.0, 1.0 - s * math.exp(-x + a * math.log(x) - lg))
    b = x + 1 - a                                   # frazione continua (Lentz)
    c, d = 1e300, 1.0 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        h *= d * c
        if abs(d * c - 1) < 1e-14:
            break
    return min(1.0, math.exp(-x + a * math.log(x) - lg) * h)


def chi2_p(x: float, gl: int) -> float:
    return _gamma_q(gl / 2.0, x / 2.0)


def norm_p2(z: float) -> float:
    """p a due code della normale."""
    return math.erfc(abs(z) / math.sqrt(2))


def norm_p1(z: float) -> float:
    """p a una coda (valori alti)."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def holm(ps: list[float]) -> list[float]:
    m = len(ps)
    ordine = sorted(range(m), key=lambda i: ps[i])
    out, massimo = [0.0] * m, 0.0
    for r, i in enumerate(ordine):
        massimo = max(massimo, min(1.0, (m - r) * ps[i]))
        out[i] = massimo
    return out


# ------------------------------------------------------------------ risultati
@dataclass
class Prova:
    gruppo: str              # "Macchina", "Memoria", "Previsione"
    epoca: str
    nome: str
    domanda: str             # che cosa cerca, in parole semplici
    risultato: str           # che cosa si è misurato
    p: float
    p_holm: float = 1.0
    sospetti: list[str] = field(default_factory=list)   # dettagli più "strani" (solo informativi)

    @property
    def esito(self) -> str:
        if self.p_holm < SOGLIA:
            return "ANOMALIA"
        if self.p < 0.01:
            return "da tenere d'occhio"
        return "compatibile con il caso"


@dataclass
class Rapporto:
    gioco: str
    estrazioni: int
    epoche: list[tuple[str, int]]
    prove: list[Prova]
    simulazioni: int
    sensibilita: list[tuple[str, float]] = field(default_factory=list)   # (epoca, % minimo visibile)

    @property
    def anomalie(self) -> list[Prova]:
        return [p for p in self.prove if p.esito == "ANOMALIA"]

    def testo(self) -> str:
        r = [f"LABORATORIO – {self.gioco}: la casualità è davvero casuale?",
             f"Estrazioni studiate: {self.estrazioni}. Epoche: " +
             "; ".join(f"{n} ({k} concorsi)" for n, k in self.epoche),
             f"Prove eseguite: {len(self.prove)} (confronto con {self.simulazioni} archivi simulati "
             "perfettamente casuali dove serve).", ""] + [
                f"Sensibilità ({e}): una pallina dovrebbe uscire almeno il {pct:.0f}% più (o meno) del normale "
                "per essere scoperta in modo affidabile; difetti più piccoli resterebbero invisibili con questi dati."
                for e, pct in self.sensibilita] + ["",
             "Come leggere: p = probabilità di vedere un risultato così, o più strano, se le estrazioni fossero "
             "perfettamente casuali. Con tante prove qualche p piccola esce per fortuna: si parla di ANOMALIA "
             f"solo se resta sotto il {int(SOGLIA * 100)}% dopo la correzione di Holm (p corr.).", ""]
        for gruppo in ("Macchina", "Memoria", "Previsione"):
            prove = [p for p in self.prove if p.gruppo == gruppo]
            if not prove:
                continue
            titolo = {"Macchina": "1. LA MACCHINA (impronte di difetti fisici)",
                      "Memoria": "2. LA MEMORIA (legami tra un concorso e i successivi)",
                      "Previsione": "3. LA PREVISIONE (gara tra regole, giudicate solo sul futuro)"}[gruppo]
            r += [titolo, "-" * len(titolo)]
            for p in prove:
                r.append(f"[{p.esito.upper()}] {p.nome} – {p.epoca}")
                r.append(f"   Cerca: {p.domanda}")
                r.append(f"   Misura: {p.risultato}")
                r.append(f"   p = {p.p:.4f}   p corr. = {p.p_holm:.4f}")
                for s in p.sospetti[:3]:
                    r.append(f"   · {s}")
            r.append("")
        an = self.anomalie
        r.append("VERDETTO")
        r.append("--------")
        if an:
            r.append(f"Trovate {len(an)} anomalie statisticamente solide:")
            for p in an:
                r.append(f"  - {p.nome} ({p.epoca})")
            r.append("Vanno confermate sulle estrazioni future prima di usarle: se un difetto è reale continuerà "
                     "a vedersi; se era un caso, sparirà.")
        else:
            r.append("Nessuna anomalia statisticamente solida: con questi dati le estrazioni si comportano come "
                     "una sorgente perfettamente casuale. Nessuna regola di previsione batte il caso in modo "
                     "affidabile sui concorsi che non ha visto.")
            sosp = [p for p in self.prove if p.esito == "da tenere d'occhio"]
            if sosp:
                r.append("Da tenere d'occhio (p < 1% prima della correzione, ma non significative dopo): " +
                         "; ".join(f"{p.nome} ({p.epoca})" for p in sosp) +
                         ". Rifai il laboratorio fra qualche mese: se sono vere, diventeranno più forti.")
        return "\n".join(r)


# ------------------------------------------------------------------ dati
def _matrice(righe: list[list[int]], N: int) -> np.ndarray:
    M = np.zeros((len(righe), N), dtype=np.float32)
    for i, r in enumerate(righe):
        M[i, [x - 1 for x in r]] = 1
    return M


def _simula(rng, n: int, N: int, k: int) -> tuple[np.ndarray, np.ndarray]:
    ordine = np.argsort(rng.random((n, N)), axis=1)[:, :k]
    M = np.zeros((n, N), dtype=np.float32)
    M[np.arange(n)[:, None], ordine] = 1
    return M, ordine + 1


def _epoche(estrazioni, g: Gioco) -> list[tuple[str, list]]:
    if g.codice == "SE":
        prima = [e for e in estrazioni if e.data < CAMBIO_SE]
        dopo = [e for e in estrazioni if e.data >= CAMBIO_SE]
        ep = []
        if len(prima) >= 200:
            ep.append(("ruote del Lotto 1997-2009", prima))
        if len(dopo) >= 200:
            ep.append(("macchina SuperEnalotto dal 2009", dopo))
        return ep or [("tutto l'archivio", estrazioni)]
    return [("tutto l'archivio", estrazioni)]


# ------------------------------------------------------------------ statistiche usate anche sugli archivi simulati
def _stat_coppie(M: np.ndarray, e_coppia: float) -> float:
    C = M.T @ M
    iu = np.triu_indices(M.shape[1], 1)
    return float(((C[iu] - e_coppia) ** 2).sum())


def _stat_consecutivi(M: np.ndarray) -> float:
    return float((M[:, :-1] * M[:, 1:]).sum(axis=1).mean())


def _stat_decina(M: np.ndarray) -> float:
    N = M.shape[1]
    tot = 0.0
    for d in range(0, N, 10):
        c = M[:, d:d + 10].sum(axis=1)
        tot += float((c * (c - 1) / 2).sum())
    return tot / M.shape[0]


def _stat_vicini_prec(M: np.ndarray) -> float:
    prec = M[:-1]
    vicini = np.zeros_like(prec)
    vicini[:, 1:] += prec[:, :-1]
    vicini[:, :-1] += prec[:, 1:]
    vicini = np.clip(vicini, 0, 1) * (1 - prec)          # vicini ±1 del concorso prima (ripetizioni escluse)
    return float((vicini * M[1:]).sum(axis=1).mean())


def _stat_salto_ordine(ordini: np.ndarray) -> float:
    return float(np.abs(np.diff(ordini, axis=1)).mean())


# ------------------------------------------------------------------ le prove
def _prove_macchina(nome_ep, ests, g: Gioco, M, sim) -> list[Prova]:
    n, N, k = M.shape[0], g.n, g.k
    out = []
    # 1. frequenze dei numeri (peso / dimensione delle palline)
    f = M.sum(axis=0)
    E = n * k / N
    chi = float(((f - E) ** 2 / E).sum() * (N - 1) / (N - k))
    alti = np.argsort(-f)[:3]
    bassi = np.argsort(f)[:3]
    out.append(Prova("Macchina", nome_ep, "Frequenza di ogni numero",
                     "palline che escono più o meno delle altre (peso, dimensione, usura)",
                     f"uscite per numero da {int(f.min())} a {int(f.max())}, atteso {E:.1f} ciascuno",
                     chi2_p(chi, N - 1),
                     sospetti=[f"più uscito: {', '.join(f'{a + 1} ({int(f[a])})' for a in alti)}",
                               f"meno uscito: {', '.join(f'{b + 1} ({int(f[b])})' for b in bassi)}",
                               "differenze di questa ampiezza sono normali con il caso se p non è piccola"]))
    # 1b. il singolo numero più anomalo (un difetto su UNA pallina non si diluisce tra le 90)
    pn = k / N
    zn = (f - n * pn) / math.sqrt(n * pn * (1 - pn))
    j = int(np.argmax(np.abs(zn)))
    p_max = min(1.0, N * norm_p2(float(zn[j])))
    out.append(Prova("Macchina", nome_ep, "Il numero più anomalo",
                     "una singola pallina difettosa (più pesante, più leggera, rovinata)",
                     f"il {j + 1} è uscito {int(f[j])} volte (atteso {n * pn:.1f}, {zn[j]:+.2f} deviazioni)",
                     p_max))
    # 2. posizione di uscita (solo dove l'archivio conserva l'ordine)
    ordinate = [e.numeri for e in ests if len(e.numeri) == k and list(e.numeri) != sorted(e.numeri)]
    if len(ordinate) >= 200:
        O = np.array(ordinate)
        chi_tot, sosp = 0.0, []
        Ep = len(O) / N
        nomi = RUOTE_SE if (g.codice == "SE" and "ruote" in nome_ep) else [f"{i + 1}ª pallina" for i in range(k)]
        peggiore = (0.0, "")
        for j in range(k):
            cj = np.bincount(O[:, j], minlength=N + 1)[1:]
            cj_chi = float(((cj - Ep) ** 2 / Ep).sum())
            chi_tot += cj_chi
            pj = chi2_p(cj_chi, N - 1)
            media = O[:, j].mean()
            if -math.log10(max(pj, 1e-300)) > peggiore[0]:
                peggiore = (-math.log10(max(pj, 1e-300)), f"posizione più irregolare: {nomi[j]} (p={pj:.3f})")
            sosp.append(f"{nomi[j]}: numero medio {media:.1f} (atteso {(N + 1) / 2:.1f})")
        out.append(Prova("Macchina", nome_ep, "Posizione di uscita" + (" (ruota)" if "ruote" in nome_ep else ""),
                         "una posizione (la prima pallina, o una ruota) che preferisce certi numeri",
                         f"{len(O)} concorsi con l'ordine di uscita conservato",
                         chi2_p(chi_tot, k * (N - 1)), sospetti=[peggiore[1]] + sosp[:2]))
        # 2b. palline vicine estratte una dopo l'altra
        oss = _stat_salto_ordine(O)
        nulla = sim.get("salto_" + nome_ep)
        if nulla is not None:
            z = (oss - nulla.mean()) / (nulla.std() or 1)
            out.append(Prova("Macchina", nome_ep, "Palline vicine estratte una dopo l'altra",
                             "se le palline restano 'in fila' come sono state caricate, un'estratta tira l'altra",
                             f"distanza media tra due estratti consecutivi {oss:.2f} (caso {nulla.mean():.2f})",
                             norm_p2(z)))
    # 3. coppie privilegiate
    e_c = n * k * (k - 1) / (N * (N - 1))
    oss = _stat_coppie(M, e_c)
    nulla = sim["coppie_" + nome_ep]
    z = (oss - nulla.mean()) / (nulla.std() or 1)
    C = M.T @ M
    iu = np.triu_indices(N, 1)
    top = np.argsort(-C[iu])[:3]
    out.append(Prova("Macchina", nome_ep, "Coppie che escono insieme",
                     "palline che tendono a uscire nella stessa estrazione (attrito, cariche elettrostatiche)",
                     f"dispersione delle {len(iu[0])} coppie: {z:+.2f} deviazioni dal caso",
                     norm_p2(z), sospetti=["coppie più frequenti: " + ", ".join(
                         f"{iu[0][t] + 1}-{iu[1][t] + 1} ({int(C[iu][t])} volte, atteso {e_c:.1f})" for t in top)]))
    # 3b. la singola coppia più frequente, confrontata con la più frequente degli archivi casuali
    nulla = sim.get("coppiamax_" + nome_ep)
    if nulla is not None:
        massimo = float(C[iu].max())
        p_cm = (1 + int((nulla >= massimo).sum())) / (len(nulla) + 1)
        out.append(Prova("Macchina", nome_ep, "La coppia più frequente",
                         "due palline che si 'attirano' in modo particolare",
                         f"coppia più frequente {int(massimo)} volte; negli archivi casuali in media "
                         f"{nulla.mean():.1f} (massimo {int(nulla.max())})", p_cm))
    # 4. numeri consecutivi nella stessa estrazione
    oss = _stat_consecutivi(M)
    nulla = sim["consec_" + nome_ep]
    z = (oss - nulla.mean()) / (nulla.std() or 1)
    out.append(Prova("Macchina", nome_ep, "Numeri consecutivi nella stessa estrazione",
                     "palline con numeri vicini (spesso caricate vicine) che escono insieme",
                     f"{oss:.3f} coppie consecutive per estrazione (caso {nulla.mean():.3f})", norm_p2(z)))
    # 5. stessa decina
    oss = _stat_decina(M)
    nulla = sim["decina_" + nome_ep]
    z = (oss - nulla.mean()) / (nulla.std() or 1)
    out.append(Prova("Macchina", nome_ep, "Numeri della stessa decina",
                     "gruppi di palline (per esempio caricate per decine) che non si mescolano bene",
                     f"{oss:.3f} coppie della stessa decina per estrazione (caso {nulla.mean():.3f})", norm_p2(z)))
    # 6. somma
    somme = M @ np.arange(1, N + 1)
    mu = k * (N + 1) / 2
    var = k * (N * N - 1) / 12 * (N - k) / (N - 1)
    z = (somme.mean() - mu) / math.sqrt(var / n)
    out.append(Prova("Macchina", nome_ep, "Somma dei numeri estratti",
                     "una macchina che preferisce numeri bassi o alti",
                     f"somma media {somme.mean():.1f} (attesa {mu:.1f})", norm_p2(z)))
    # 7. stabilità nel tempo (macchine, set di palline, manutenzioni)
    blocchi = np.array_split(np.arange(n), 4)
    T = np.array([M[b].sum(axis=0) for b in blocchi])          # 4 x N
    att = T.sum(axis=1, keepdims=True) * T.sum(axis=0, keepdims=True) / T.sum()
    chi = float((((T - att) ** 2) / np.where(att > 0, att, 1)).sum() * (N - 1) / (N - k))
    out.append(Prova("Macchina", nome_ep, "Stabilità nel tempo",
                     "un cambio di macchina, di palline o di regolazione che sposta le preferenze",
                     "frequenze confrontate in 4 periodi consecutivi", chi2_p(chi, 3 * (N - 1))))
    # 8. giorno della settimana
    gg = np.array([e.data.weekday() for e in ests])
    usati = [d for d in range(7) if (gg == d).sum() >= 100]
    if len(usati) >= 2:
        T = np.array([M[gg == d].sum(axis=0) for d in usati])
        att = T.sum(axis=1, keepdims=True) * T.sum(axis=0, keepdims=True) / T.sum()
        chi = float((((T - att) ** 2) / np.where(att > 0, att, 1)).sum() * (N - 1) / (N - k))
        out.append(Prova("Macchina", nome_ep, "Giorno della settimana",
                         "condizioni diverse nei vari giorni (personale, temperatura, umidità, macchina)",
                         "frequenze confrontate tra " + ", ".join(GIORNI[d] for d in usati),
                         chi2_p(chi, (len(usati) - 1) * (N - 1))))
    # 9. numeri speciali
    if g.codice == "SE":
        jolly = [e.jolly for e in ests if e.jolly]
        if len(jolly) >= 200:
            c = np.bincount(jolly, minlength=N + 1)[1:]
            Ej = len(jolly) / N
            out.append(Prova("Macchina", nome_ep, "Frequenza del Jolly",
                             "palline che escono più spesso come Jolly", f"{len(jolly)} Jolly",
                             chi2_p(float(((c - Ej) ** 2 / Ej).sum()), N - 1)))
        ss = [e.superstar for e in ests if e.superstar]
        if len(ss) >= 200:
            c = np.bincount(ss, minlength=N + 1)[1:]
            Es = len(ss) / N
            out.append(Prova("Macchina", nome_ep, "Frequenza del SuperStar",
                             "palline che escono più spesso come SuperStar", f"{len(ss)} SuperStar",
                             chi2_p(float(((c - Es) ** 2 / Es).sum()), N - 1)))
    else:
        eu = [(e.jolly, e.superstar) for e in ests if e.jolly and e.superstar and g.euro_max(e.data) == 12]
        if len(eu) >= 100:
            c = np.bincount([x for p in eu for x in p], minlength=13)[1:]
            Ee = len(eu) * 2 / 12
            chi = float(((c - Ee) ** 2 / Ee).sum() * 11 / 10)
            out.append(Prova("Macchina", nome_ep, "Frequenza degli Euronumeri (formula 2 su 12)",
                             "palline degli Euronumeri che escono più delle altre",
                             f"{len(eu)} concorsi", chi2_p(chi, 11)))
    return out


def _prove_memoria(nome_ep, g: Gioco, M, sim) -> list[Prova]:
    n, N, k = M.shape[0], g.n, g.k
    out = []
    att = k * k / N
    var = k * (k / N) * ((N - k) / N) * ((N - k) / (N - 1))
    # ripetizioni dal concorso precedente e da quelli prima (fino a 10)
    zs = []
    for lag in range(1, 11):
        comuni = (M[lag:] * M[:-lag]).sum(axis=1)
        zs.append((comuni.mean() - att) / math.sqrt(var / len(comuni)))
    comuni1 = (M[1:] * M[:-1]).sum(axis=1).mean()
    out.append(Prova("Memoria", nome_ep, "Numeri ripetuti dal concorso precedente",
                     "palline appena uscite che tornano (o evitano di tornare) subito",
                     f"in comune con il concorso prima: {comuni1:.3f} numeri (caso {att:.3f})", norm_p2(zs[0])))
    chi = float(sum(z * z for z in zs[1:]))
    out.append(Prova("Memoria", nome_ep, "Ripetizioni a distanza di 2-10 concorsi",
                     "una 'memoria' più lunga, come se la macchina ricordasse le estrazioni recenti",
                     "numeri in comune con ognuno dei 9 concorsi precedenti", chi2_p(chi, 9)))
    # vicini del concorso precedente
    oss = _stat_vicini_prec(M)
    nulla = sim["vicprec_" + nome_ep]
    z = (oss - nulla.mean()) / (nulla.std() or 1)
    out.append(Prova("Memoria", nome_ep, "Vicini dei numeri appena usciti",
                     "dopo l'uscita del 40, più probabilità per 39 e 41 nel concorso dopo",
                     f"{oss:.3f} vicini per estrazione (caso {nulla.mean():.3f})", norm_p2(z)))
    # intervalli tra le uscite dello stesso numero (ritardi)
    gaps = []
    for j in range(N):
        pos = np.flatnonzero(M[:, j])
        if len(pos) > 1:
            gaps.extend(np.diff(pos).tolist())
    gaps = np.array(gaps)
    p = k / N
    limiti = list(range(1, 41))
    oss_c = [int((gaps == b).sum()) for b in limiti] + [int((gaps > 40).sum())]
    tot = len(gaps)
    att_c = [tot * p * (1 - p) ** (b - 1) for b in limiti] + [tot * (1 - p) ** 40]
    chi = float(sum((o - a) ** 2 / a for o, a in zip(oss_c, att_c)))
    out.append(Prova("Memoria", nome_ep, "Ritardi (intervalli tra due uscite dello stesso numero)",
                     "numeri 'maturi' che, dopo un lungo ritardo, escono più del dovuto (o il contrario)",
                     f"{tot} intervalli, ritardo medio {gaps.mean():.1f} (caso {1 / p:.1f})",
                     chi2_p(chi, len(limiti))))
    return out


# ------------------------------------------------------------------ gara di previsione
REGOLE = {
    "frequenti": "I più frequenti di sempre",
    "frequenti50": "I più frequenti negli ultimi 50 concorsi",
    "frequenti200": "I più frequenti negli ultimi 200 concorsi",
    "rari": "I meno frequenti di sempre",
    "ritardatari": "I ritardatari (assenti da più tempo)",
    "ripetizione": "Ripetere i numeri appena usciti",
    "vicini": "I vicini (±1) dei numeri appena usciti",
    "markov": "Catena di Markov (chi segue chi)",
    "coppie": "Gli amici abituali dei numeri appena usciti",
    "modello": "Modello di apprendimento automatico (regressione logistica)",
}


def _caratteristiche(cum, cum50, rit, ultimo, T, P):
    vicini = np.zeros_like(ultimo)
    vicini[1:] += ultimo[:-1]
    vicini[:-1] += ultimo[1:]
    tot = cum.sum() or 1.0
    return np.stack([cum / tot * len(cum), cum50 / 50.0 * 10, np.log1p(rit), ultimo,
                     np.clip(vicini, 0, 1), ultimo @ T / (T.sum() / len(cum) + 1),
                     ultimo @ P / (P.sum() / len(cum) + 1)], axis=1)


def _gara(nome_ep, g: Gioco, M, avanzamento=None, interrompi=None) -> list[Prova]:
    n, N, k = M.shape[0], g.n, g.k
    if n < 400:
        return []
    inizio = int(n * 0.7)
    rng = np.random.default_rng(7)
    cum = np.zeros(N)
    rit = np.zeros(N)
    T = np.zeros((N, N))
    P = np.zeros((N, N))
    finestra = []
    colpi = {r: [] for r in REGOLE}
    X_tr, y_tr, w = [], [], None
    for t in range(n):
        if interrompi and interrompi():
            break
        if t >= 30:
            cum50 = M[max(0, t - 50):t].sum(axis=0)
            cum200 = M[max(0, t - 200):t].sum(axis=0)
            ultimo = M[t - 1]
            F = _caratteristiche(cum, cum50, rit, ultimo, T, P)
            if t < inizio:
                if t % 3 == 0:                       # campione per addestrare il modello
                    X_tr.append(F)
                    y_tr.append(M[t])
            else:
                if w is None:                         # addestramento una volta sola, solo sul passato
                    X = np.concatenate(X_tr)
                    y = np.concatenate(y_tr)
                    mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-9
                    Xn = np.hstack([(X - mu) / sd, np.ones((len(X), 1))])
                    w = np.zeros(Xn.shape[1])
                    for _ in range(300):
                        pr = 1 / (1 + np.exp(-Xn @ w))
                        w -= 0.5 * Xn.T @ (pr - y) / len(y)
                    norm = (mu, sd)
                rumore = rng.random(N) * 1e-6
                pun = {
                    "frequenti": cum, "frequenti50": cum50, "frequenti200": cum200, "rari": -cum,
                    "ritardatari": rit, "ripetizione": ultimo, "vicini": F[:, 4], "markov": ultimo @ T,
                    "coppie": ultimo @ P,
                    "modello": np.hstack([(F - norm[0]) / norm[1], np.ones((N, 1))]) @ w,
                }
                estratti = M[t]
                for r, s in pun.items():
                    scelta = np.argsort(-(s + rumore))[:k]
                    colpi[r].append(float(estratti[scelta].sum()))
        # aggiorna la memoria con il concorso t (solo dopo averlo "previsto")
        if t >= 1:
            T += np.outer(M[t - 1], M[t])
        P += np.outer(M[t], M[t])
        np.fill_diagonal(P, 0)
        cum += M[t]
        rit += 1
        rit[M[t] > 0] = 0
        if avanzamento and t % 200 == 0:
            avanzamento(t, n)
    att = k * k / N
    var = k * (k / N) * ((N - k) / N) * ((N - k) / (N - 1))
    out = []
    for r, c in colpi.items():
        if not c:
            continue
        media = float(np.mean(c))
        z = (media - att) / math.sqrt(var / len(c))
        tre = sum(1 for x in c if x >= 3)
        out.append(Prova("Previsione", nome_ep, REGOLE[r],
                         "se questa regola indovina più numeri del caso sui concorsi che non ha mai visto",
                         f"{len(c)} concorsi di prova: {media:.3f} numeri indovinati in media (caso {att:.3f}), "
                         f"{tre} volte almeno 3 punti", norm_p1(z)))
    return out


# ------------------------------------------------------------------ esecuzione
def esegui(estrazioni, g: Gioco = SE, simulazioni: int = 200, avanzamento=None, interrompi=None) -> Rapporto:
    """estrazioni: elenco di Estrazione in ordine di data (archivio.tutte(True))."""
    estrazioni = sorted(estrazioni, key=lambda e: e.data)
    if len(estrazioni) < 200:
        raise ValueError("Servono almeno 200 estrazioni in archivio.")
    epoche = _epoche(estrazioni, g)
    rng = np.random.default_rng(2026)
    prove: list[Prova] = []
    passi = len(epoche) * 3
    for i, (nome_ep, ests) in enumerate(epoche):
        M = _matrice([sorted(e.numeri) for e in ests], g.n)
        n = M.shape[0]
        # archivi simulati perfettamente casuali, della stessa lunghezza
        sim: dict[str, np.ndarray] = {}
        racc = {"coppie": [], "coppiamax": [], "consec": [], "decina": [], "vicprec": [], "salto": []}
        e_c = n * g.k * (g.k - 1) / (g.n * (g.n - 1))
        m_ord = sum(1 for e in ests if len(e.numeri) == g.k and list(e.numeri) != sorted(e.numeri))
        for s in range(max(20, int(simulazioni))):
            if interrompi and interrompi():
                break
            Ms, Os = _simula(rng, n, g.n, g.k)
            racc["coppie"].append(_stat_coppie(Ms, e_c))
            Cs = Ms.T @ Ms
            racc["coppiamax"].append(float(Cs[np.triu_indices(g.n, 1)].max()))
            racc["consec"].append(_stat_consecutivi(Ms))
            racc["decina"].append(_stat_decina(Ms))
            racc["vicprec"].append(_stat_vicini_prec(Ms))
            if m_ord >= 2:
                racc["salto"].append(_stat_salto_ordine(Os[:m_ord]))
            if avanzamento and s % 20 == 0:
                avanzamento(f"{nome_ep}: simulazione {s} di {simulazioni}", i * 3, passi)
        for chiave, v in racc.items():
            if v:
                sim[f"{chiave}_{nome_ep}"] = np.array(v)
        if avanzamento:
            avanzamento(f"{nome_ep}: prove sulla macchina e sulla memoria", i * 3 + 1, passi)
        prove += _prove_macchina(nome_ep, ests, g, M, sim)
        prove += _prove_memoria(nome_ep, g, M, sim)
        if avanzamento:
            avanzamento(f"{nome_ep}: gara di previsione", i * 3 + 2, passi)
        prove += _gara(nome_ep, g, M, None, interrompi)
    for p, ph in zip(prove, holm([p.p for p in prove])):
        p.p_holm = ph
    if avanzamento:
        avanzamento("Fatto", passi, passi)
    sens = []
    for nome_ep, ests in epoche:
        n = len(ests)
        pn = g.k / g.n
        sens.append((nome_ep, 100 * 4.5 * math.sqrt(n * pn * (1 - pn)) / (n * pn)))
    return Rapporto(g.nome, len(estrazioni), [(n, len(e)) for n, e in epoche], prove, simulazioni, sens)


CHIAVE_LAB = "laboratorio_ultimo"


def riassunto_per_ai(r: Rapporto) -> str:
    """Poche righe per l'intelligenza artificiale."""
    righe = [f"Laboratorio sulla casualità ({r.estrazioni} estrazioni, {len(r.prove)} prove):"]
    for p in r.prove:
        if p.esito != "compatibile con il caso":
            righe.append(f"- {p.esito}: {p.nome} ({p.epoca}), p={p.p:.4f}, p corr.={p.p_holm:.4f}")
    if len(righe) == 1:
        righe.append("- nessuna anomalia: estrazioni compatibili con il caso, nessuna regola batte il caso.")
    return "\n".join(righe)
