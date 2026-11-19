"""Colonna magica: una colonna (sestina o cinquina) i cui numeri arrivano da fonti diverse, ognuna con la
sua "provenienza":

  🎲 un numero casuale
  ✨ un numero scelto da Magico Pensiero (il migliore della sua proposta)
  🤖✨ un numero scelto dall'intelligenza artificiale che ha davanti anche il dossier di Magico Pensiero
  🤖 un numero scelto dall'intelligenza artificiale con i soli dati dell'archivio (solo SuperEnalotto: nella
     cinquina dell'Eurojackpot i posti sono 5, quindi questa fonte non c'è)
  📈 il numero che, aggiunto agli altri, rende la colonna più probabile secondo TUTTE le condizioni
  📉 il numero che la rende meno probabile secondo tutte le condizioni

«Probabile» qui significa: quanto spesso nelle estrazioni reali sono usciti i valori che la colonna ha in ogni
condizione (somma, pari/dispari, consecutivi, decine, distanze, ritardi...). Non è la probabilità di vincere,
uguale per tutte le colonne.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np

from . import condizioni as cnd
from . import magico
from .claude_ai import ErroreClaude, _estrai_json
from .gioco import Gioco

FONTI = [("casuale", "🎲", "Numero casuale"),
         ("magico", "✨", "Magico Pensiero"),
         ("magico_ai", "🤖✨", "Magico Pensiero + AI"),
         ("ai", "🤖", "Intelligenza artificiale"),
         ("piu_probabile", "📈", "Il più probabile (analisi)"),
         ("meno_probabile", "📉", "Il meno probabile (analisi)")]
NOME_FONTE = {c: n for c, _, n in FONTI}
ICONA_FONTE = {c: i for c, i, _ in FONTI}
ORDINE_SCELTA = ["magico", "magico_ai", "ai", "casuale", "piu_probabile", "meno_probabile"]


def fonti_del_gioco(g: Gioco) -> list[str]:
    """Le fonti, nell'ordine di visualizzazione: nell'Eurojackpot (5 numeri) manca l'AI da sola."""
    return [c for c, _, _ in FONTI if not (g.is_ej and c == "ai")]


@dataclass
class NumeroMagico:
    numero: int
    fonte: str
    nota: str
    sostituito: bool = False         # True: la fonte non era disponibile (es. AI senza chiave)

    def a_dict(self) -> dict:
        return {"numero": self.numero, "fonte": self.fonte, "nota": self.nota, "sostituito": self.sostituito}


@dataclass
class ColonnaMagica:
    numeri: list[NumeroMagico]       # nell'ordine di FONTI
    gioco: str
    euronumeri: list[int] = field(default_factory=list)    # Eurojackpot: suggeriti da Magico Pensiero

    @property
    def colonna(self) -> list[int]:
        return sorted(n.numero for n in self.numeri)


# ------------------------------------------------------------------ probabilità secondo le condizioni
@dataclass
class _Voce:
    nome: str
    tipo: object
    param: int
    logp: dict[int, float]
    fuori: float                     # log-probabilità di un valore mai uscito
    modo: str
    lo: int
    hi: int
    valori_80: set[int]


class Tabella:
    """Per ogni condizione: la frequenza che ogni valore ha avuto nell'archivio."""

    def __init__(self, g: Gioco, ctx: cnd.Contesto):
        self.g, self.ctx = g, ctx
        self.voci: list[_Voce] = []
        for t in cnd.tipi_del_gioco(g):
            for par, et in (((1, "1ª posizione"), (g.k, f"{g.k}ª posizione")) if t.codice == "posizione"
                            else ((t.param_def, ""),)):
                try:
                    a = cnd.analizza(t.codice, ctx, par)
                    t.funzione(np.array([list(range(1, g.k + 1))]), ctx, par)      # prova: deve funzionare
                except Exception:            # noqa: BLE001 – es. popolarità senza modello
                    continue
                usc = {r[0]: r[1] for r in a.righe}
                tot = a.estrazioni + 0.5 * (len(usc) + 1)
                p = {v: (c + 0.5) / tot for v, c in usc.items()}
                pmax = max(p.values())
                nome = f"{t.nome} ({et})" if et else t.nome
                self.voci.append(_Voce(nome, t, par, {v: math.log(x / pmax) for v, x in p.items()},
                                       math.log(0.5 / tot / pmax), t.modo, a.copertura[0], a.copertura[1],
                                       set(a.valori_80)))

    def punteggio(self, C: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(punteggio, caratteristiche tipiche) per ogni colonna di C. Punteggio = somma dei log delle
        frequenze (0 = il valore più comune in ogni condizione; più basso = più insolita)."""
        C = np.asarray(C, dtype=np.int64)
        tot = np.zeros(len(C))
        tip = np.zeros(len(C), dtype=int)
        for v in self.voci:
            val = np.asarray(v.tipo.funzione(C, self.ctx, v.param)).astype(int)
            tot += np.array([v.logp.get(int(x), v.fuori) for x in val])
            tip += ((val >= v.lo) & (val <= v.hi)) if v.modo == "intervallo" else np.isin(val, list(v.valori_80))
        return tot, tip


def scegli_coppia_analisi(tab: Tabella, presi: list[int]) -> tuple[tuple[int, str], tuple[int, str]]:
    """Gli ultimi due numeri della colonna (mancano esattamente 2 numeri) secondo tutte le condizioni.

    Il PIÙ PROBABILE è il numero che in media rende più tipiche (secondo tutte le condizioni) le colonne che lo
    contengono, qualunque sia l'ultimo numero. Il MENO PROBABILE è, una volta preso quello, il numero che
    completa la colonna nel modo più insolito. Restituisce ((numero, nota), (numero, nota))."""
    g = tab.g
    liberi = [n for n in range(1, g.n + 1) if n not in presi]
    L = len(liberi)
    ia, ib = np.triu_indices(L, 1)
    C = np.array([sorted(list(presi) + [liberi[a], liberi[b]]) for a, b in zip(ia, ib)])
    s, tip = tab.punteggio(C)
    S = np.zeros((L, L))
    T = np.zeros((L, L))
    S[ia, ib] = S[ib, ia] = s
    T[ia, ib] = T[ib, ia] = tip
    medio = S.sum(axis=1) / (L - 1)
    tmedio = T.sum(axis=1) / (L - 1)
    a = int(np.argmax(medio))
    riga = S[a].copy()
    riga[a] = np.inf
    b = int(np.argmin(riga))
    n_cond = len(tab.voci)
    nota_a = (f"In media le colonne che lo contengono hanno {tmedio[a]:.1f} caratteristiche tipiche su {n_cond} "
              f"(punteggio medio {medio[a]:.1f}, il migliore tra i {L} numeri liberi; 0 = tutte le condizioni al "
              "valore più frequente).")
    nota_b = (f"Con questo numero la colonna ha {int(T[a, b])} caratteristiche tipiche su {n_cond} "
              f"(punteggio {S[a, b]:.1f}, il più basso tra i {L - 1} numeri possibili): è il completamento più "
              "insolito rispetto alle estrazioni reali.")
    return (liberi[a], nota_a), (liberi[b], nota_b)


# ------------------------------------------------------------------ le altre fonti
def numero_casuale(g: Gioco, esclusi: set[int], rng: random.Random | None = None) -> tuple[int, str]:
    rng = rng or random.SystemRandom()
    n = rng.choice([x for x in range(1, g.n + 1) if x not in esclusi])
    return n, "Estratto a caso tra i numeri ancora liberi."


def numero_magico(r: magico.RisultatoMagico, esclusi: set[int]) -> tuple[int, str]:
    """Il numero col punteggio più alto della proposta migliore di Magico Pensiero."""
    classifica = sorted(r.punteggi, key=lambda k: -r.punteggi[k])
    pos = {k: i + 1 for i, k in enumerate(classifica)}
    liberi = [n for n in r.sestine[0].numeri if n not in esclusi] or [n for n in classifica if n not in esclusi]
    n = max(liberi, key=lambda k: r.punteggi[k])
    return n, (f"Il numero col punteggio più alto ({r.punteggi[n]:.2f}) della proposta di Magico Pensiero: "
               f"{pos[n]}° su {len(classifica)} nella classifica dei numeri.")


def _alternativa_magico(r: magico.RisultatoMagico, esclusi: set[int]) -> int:
    return next(k for k in sorted(r.punteggi, key=lambda k: -r.punteggi[k]) if k not in esclusi)


def _alternativa_ritardo(r: magico.RisultatoMagico, esclusi: set[int]) -> int:
    m = r.voci.get("maturita") or r.punteggi
    return max((k for k in m if k not in esclusi), key=lambda k: m[k])


# ------------------------------------------------------------------ intelligenza artificiale: un solo numero
def sistema_ai(g: Gioco) -> str:
    return (f"Sei un assistente di un programma che analizza le estrazioni storiche del {g.nome}. Ti si chiede di "
            f"scegliere UN SOLO numero da 1 a {g.n} per completare una colonna. I numeri del lotto sono casuali: "
            "nessun numero è davvero più probabile degli altri, quindi lasciati guidare dai dati che ti vengono "
            "mostrati (frequenze, ritardi, tendenze) e dal tuo fiuto, ed essere onesto sui limiti. Rispondi SOLO "
            'con un oggetto JSON: {"numero": N, "motivazione": "una frase in italiano"}.')


def testo_ai_sola(g: Gioco, storico, ultime: int = 30) -> str:
    """Dati minimi dell'archivio (niente analisi di Magico Pensiero): ultime estrazioni e tabella dei numeri."""
    m = magico.matrice(storico)
    rit, _ = magico._ritardi(m)
    f_tot, f100 = m.sum(axis=0), m[-100:].sum(axis=0)
    out = [f"# ARCHIVIO {g.nome.upper()}: {len(storico)} estrazioni, ultima del {storico[-1][0]:%d/%m/%Y}", "",
           f"## Ultime {ultime} estrazioni (dalla più recente)"]
    for x in reversed(storico[-ultime:]):
        out.append(f"{x[0]:%d/%m/%Y};{' '.join(map(str, x[1]))}")
    out += ["", "## Numeri: numero;uscite in tutto l'archivio;uscite nelle ultime 100;ritardo attuale (estrazioni)"]
    for n in range(1, g.n + 1):
        out.append(f"{n};{int(f_tot[n])};{int(f100[n])};{int(rit[n])}")
    return "\n".join(out)


def chiedi_numero(conversa, testo: str, g: Gioco, esclusi: set[int]) -> tuple[int, str, str]:
    """Chiede all'AI un numero; se non è valido glielo fa correggere UNA volta.
    conversa(messaggi) -> (testo, modello, token_in, token_out). Restituisce (numero, motivazione, modello)."""
    richiesta = (testo + f"\n\nOra scegli UN SOLO numero tra 1 e {g.n}" +
                 (f", diverso da questi già presi: {' '.join(map(str, sorted(esclusi)))}" if esclusi else "") +
                 '. Rispondi solo con il JSON {"numero": N, "motivazione": "..."}.')
    messaggi = [{"role": "user", "content": richiesta}]
    modello = ""
    for giro in range(2):
        testo_r, modello, _, _ = conversa(messaggi)
        try:
            d = _estrai_json(testo_r, "L'intelligenza artificiale")
            n = int(d["numero"])
            if 1 <= n <= g.n and n not in esclusi:
                return n, str(d.get("motivazione", "")).strip(), modello
            problema = f"il numero {n} non è valido: deve essere tra 1 e {g.n} e non tra quelli già presi"
        except (ErroreClaude, KeyError, ValueError, TypeError):
            problema = "la risposta non è un JSON con il campo «numero»"
        messaggi += [{"role": "assistant", "content": testo_r},
                     {"role": "user", "content": f"Risposta non valida: {problema}. Rispondi di nuovo solo con "
                                                 'il JSON {"numero": N, "motivazione": "..."}.'}]
    raise ErroreClaude("L'intelligenza artificiale non ha restituito un numero valido.")


# ------------------------------------------------------------------ la colonna
def genera(g: Gioco, tab: Tabella, base: magico.RisultatoMagico, ai_magico=None, ai_sola=None,
           rng: random.Random | None = None) -> ColonnaMagica:
    """ai_magico(esclusi) / ai_sola(esclusi) -> (numero, motivazione, modello); None = AI non disponibile.
    Se una chiamata fallisce il numero viene sostituito e la scheda lo dice."""
    scelti: dict[str, NumeroMagico] = {}
    presi: set[int] = set()
    coppia = None

    def metti(fonte, n, nota, sost=False):
        scelti[fonte] = NumeroMagico(int(n), fonte, nota, sost)
        presi.add(int(n))

    for fonte in ORDINE_SCELTA:
        if fonte not in fonti_del_gioco(g):
            continue
        if fonte == "magico":
            metti(fonte, *numero_magico(base, presi))
        elif fonte in ("magico_ai", "ai"):
            chiama = ai_magico if fonte == "magico_ai" else ai_sola
            motivo = "intelligenza artificiale non disponibile"
            if chiama is not None:
                try:
                    n, mot, modello = chiama(set(presi))
                    metti(fonte, n, (mot or "Scelto dall'intelligenza artificiale") + (f" ({modello})" if modello
                                                                                       else ""))
                    continue
                except ErroreClaude as ex:
                    motivo = str(ex)
                except Exception as ex:      # noqa: BLE001 – rete o formato imprevisti: la colonna si completa
                    motivo = f"errore imprevisto: {ex}"
            n = (_alternativa_magico if fonte == "magico_ai" else _alternativa_ritardo)(base, presi)
            metti(fonte, n, f"Al posto dell'AI ({motivo}): " + (
                "il successivo numero della classifica di Magico Pensiero." if fonte == "magico_ai"
                else "il numero più in ritardo secondo Magico Pensiero."), True)
        elif fonte == "casuale":
            metti(fonte, *numero_casuale(g, presi, rng))
        elif fonte == "piu_probabile":
            coppia = scegli_coppia_analisi(tab, sorted(presi))
            metti(fonte, *coppia[0])
        else:
            metti(fonte, *coppia[1])
    numeri = [scelti[f] for f in fonti_del_gioco(g)]
    euro = [base.jolly, base.superstar] if g.is_ej else []
    return ColonnaMagica(numeri, g.codice, [int(x) for x in euro if x])
