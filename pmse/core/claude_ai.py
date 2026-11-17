"""Intervento di Claude (AI di Anthropic) in Magico Pensiero.

Il programma prepara un "dossier" compatto con tutto ciò che sa dell'archivio
(statistiche per numero, forma delle sestine, ultime estrazioni, coppie forti,
punteggi e migliori candidate di Magico Pensiero, esito della verifica storica)
e lo invia a Claude tramite la Claude API. Claude valuta i dati, fa le sue
analisi, scarta ciò che ritiene meno plausibile e restituisce le 3 sestine,
il Jolly e il SuperStar con le motivazioni.

Serve una chiave API della Claude Console (platform.claude.com): l'uso
dell'API è a pagamento e separato dall'abbonamento a claude.ai.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from . import magico
from .analisi import Storico

URL_API = "https://api.anthropic.com/v1/messages"
VERSIONE_API = "2026-10-21"
MODELLI = [
    ("claude-opus-5-5", "Claude Opus 5.5 – il più accurato (consigliato)"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5 – equilibrato"),
    ("claude-haiku-5-5", "Claude Haiku 5.5 – il più veloce ed economico"),
]
CHIAVE_API = "claude_api_key"
CHIAVE_MODELLO = "claude_modello"
CHIAVE_VERIFICA = "magico_ultima_verifica"

SISTEMA = """Sei "Magico Pensiero", il motore di valutazione finale di un'applicazione Windows che studia \
l'archivio storico del SuperEnalotto (6 numeri estratti da 1 a 90, più Jolly estratto dagli 84 rimanenti \
e SuperStar estratto separatamente da 1 a 90).

Ipotesi di lavoro del progetto, voluta dall'utente: ogni estrazione conserva una "memoria" delle precedenti, \
quindi cerchiamo regolarità e nessi tra estrazioni successive. Lavora dentro questa ipotesi, ma da analista \
rigoroso: dai più fiducia a ciò che è confermato da molti dati e dalla verifica storica, considera rumore le \
differenze piccole, e se un indicatore non ha mai dimostrato di funzionare dagli un peso basso.

Compito:
1. Studia il dossier: statistiche per numero, forma tipica delle sestine, ultime estrazioni, coppie, \
punteggi e candidate dell'algoritmo, esito della verifica storica.
2. Fai le tue analisi e valutazioni (puoi combinare gli indicatori a modo tuo, cercare schemi nelle ultime \
estrazioni, ecc.) e scarta ciò che ritieni meno plausibile.
3. Scegli a tuo insindacabile giudizio le 3 sestine più consone, il Jolly e il SuperStar. Puoi partire dalle \
candidate dell'algoritmo, modificarle o comporne di nuove.

Regole obbligatorie: ogni sestina ha 6 numeri DIVERSI tra 1 e 90, in ordine crescente; le 3 sestine hanno al \
massimo 2 numeri in comune tra loro a due a due; nessuna sestina è identica a una già uscita; il Jolly è tra 1 e \
90 e NON appartiene alla 1ª sestina; il SuperStar è tra 1 e 90.

Rispondi in italiano e SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura:
{"sestine": [[n,n,n,n,n,n],[n,n,n,n,n,n],[n,n,n,n,n,n]],
 "jolly": n, "superstar": n,
 "motivazioni": ["perché la sestina 1", "perché la sestina 2", "perché la sestina 3"],
 "jolly_superstar": "perché questo Jolly e questo SuperStar",
 "analisi": "le tue valutazioni principali sui dati (5-10 frasi)",
 "scartati": "cosa hai scartato e perché",
 "affidabilita": "una frase onesta su quanto ritieni affidabile questa scelta"}"""


class ErroreClaude(Exception):
    pass


@dataclass
class RispostaClaude:
    sestine: list[list[int]]
    jolly: int
    superstar: int
    motivazioni: list[str] = field(default_factory=list)
    jolly_superstar: str = ""
    analisi: str = ""
    scartati: str = ""
    affidabilita: str = ""
    modello: str = ""
    token_ingresso: int = 0
    token_uscita: int = 0
    avvisi: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ dossier
def _riga(*v) -> str:
    return ";".join(str(x) for x in v)


def costruisci_dossier(storico: Storico, r: magico.RisultatoMagico, verifica: str | None = None,
                       ultime: int = 40) -> str:
    n = len(storico)
    m = magico.matrice(storico)
    rit, medio = magico._ritardi(m)
    freq = m.sum(axis=0)
    f100 = m[-100:].sum(axis=0)
    f30 = m[-30:].sum(axis=0)
    jolly = Counter(x[2] for x in storico)
    out = [f"# DOSSIER ARCHIVIO SUPERENALOTTO",
           f"Estrazioni: {n}, dal {storico[0][0]:%d/%m/%Y} al {storico[-1][0]:%d/%m/%Y}. "
           f"Il prossimo concorso è quello successivo al {storico[-1][0]:%d/%m/%Y}.", ""]

    out.append(f"## Ultime {ultime} estrazioni (dalla più recente): data;sestina ordinata;jolly;superstar")
    for x in reversed(storico[-ultime:]):
        out.append(_riga(f"{x[0]:%d/%m/%Y}", " ".join(map(str, x[1])), x[2], x[3] or "-"))
    out.append("")

    out.append("## Statistiche per numero")
    out.append("numero;uscite_totali;uscite_ultime100;uscite_ultime30;ritardo_attuale;ritardo_medio;"
               "volte_jolly;" + ";".join(f"voce_{k}" for k in r.voci) + ";punteggio_algoritmo")
    for k in range(1, 91):
        out.append(_riga(k, int(freq[k]), int(f100[k]), int(f30[k]), int(rit[k]), round(float(medio[k]), 1),
                         jolly[k], *[round(r.voci[v][k], 3) for v in r.voci], round(r.punteggi[k], 3)))
    out.append("(voci dell'algoritmo in scala 0-1: " + ", ".join(f"{k} = {magico.VOCI.get(k, k)}" for k in r.voci)
               + ")")
    out.append("")

    sestine = np.array([x[1] for x in storico])
    somme = sestine.sum(axis=1)
    pari = (sestine % 2 == 0).sum(axis=1)
    alti = (sestine > 45).sum(axis=1)
    cons = (np.diff(sestine, axis=1) == 1).sum(axis=1)
    q = np.percentile(somme, [10, 25, 50, 75, 90]).round().astype(int)
    out.append("## Forma delle sestine nello storico")
    out.append(f"Somma: percentili 10/25/50/75/90 = {' / '.join(map(str, q))}; ultima somma {int(somme[-1])}")
    for nome, arr in (("numeri pari", pari), ("numeri alti 46-90", alti), ("coppie consecutive", cons)):
        c = Counter(arr.tolist())
        out.append(f"{nome}: " + ", ".join(f"{k}→{round(100 * c[k] / n, 1)}%" for k in sorted(c)))
    rip = Counter(len(set(a[1]) & set(b[1])) for a, b in zip(storico, storico[1:]))
    out.append("numeri ripetuti dall'estrazione precedente: " +
               ", ".join(f"{k}→{round(100 * rip[k] / (n - 1), 1)}%" for k in sorted(rip)))
    out.append("")

    lift = magico._lift_coppie(m)
    cnt = m.T @ m
    coppie = [(lift[a, b], int(cnt[a, b]), a, b) for a in range(1, 91) for b in range(a + 1, 91) if cnt[a, b] >= 8]
    coppie.sort(reverse=True)
    out.append("## Coppie uscite insieme più del previsto (coppia;volte;rapporto sul caso)")
    out.extend(_riga(f"{a}-{b}", c, round(float(l), 2)) for l, c, a, b in coppie[:30])
    out.append("")

    out.append("## Proposta dell'algoritmo Magico Pensiero 0.1")
    for i, s in enumerate(r.sestine, 1):
        out.append(f"sestina {i}: {' '.join(map(str, s.numeri))} (voto {s.voto})")
    out.append(f"jolly {r.jolly}; superstar {r.superstar}")
    out.append("Migliori candidate (sestina;voto):")
    out.extend(_riga(" ".join(map(str, c)), v) for c, v in r.migliori[:30])
    out.append("")

    serie_ss = [x[3] for x in storico if x[3]]
    if serie_ss:
        css = Counter(serie_ss)
        ultimo_ss = {v: i for i, v in enumerate(serie_ss)}
        out.append("## SuperStar")
        out.append("ultimi 30 (dal più recente): " + " ".join(map(str, reversed(serie_ss[-30:]))))
        piu = ", ".join(f"{k}({v})" for k, v in css.most_common(10))
        ritardatari = sorted(range(1, 91), key=lambda k: -(len(serie_ss) - 1 - ultimo_ss.get(k, -1)))[:10]
        out.append(f"più frequenti: {piu}")
        out.append("più in ritardo: " + ", ".join(f"{k}({len(serie_ss) - 1 - ultimo_ss.get(k, -1)})"
                                                for k in ritardatari))
        out.append("")

    out.append("## Verifica storica dell'algoritmo")
    out.append(verifica.strip() if verifica else "Non ancora eseguita.")
    return "\n".join(out)


# ------------------------------------------------------------- chiamata API
def chiave_api(archivio) -> str:
    return (archivio.leggi_impostazione(CHIAVE_API) or os.environ.get("ANTHROPIC_API_KEY") or "").strip()


def _estrai_json(testo: str) -> dict:
    testo = testo.strip()
    testo = re.sub(r"^```(?:json)?\s*|\s*```$", "", testo)
    inizio, fine = testo.find("{"), testo.rfind("}")
    if inizio < 0 or fine < inizio:
        raise ErroreClaude("La risposta di Claude non contiene dati leggibili.")
    try:
        return json.loads(testo[inizio:fine + 1])
    except ValueError as ex:
        raise ErroreClaude(f"La risposta di Claude non è un JSON valido: {ex}")


def valida_risposta(d: dict, gia_uscite: set[tuple]) -> RispostaClaude:
    try:
        sestine = [sorted(int(x) for x in s) for s in d["sestine"]][:3]
        jolly = int(d["jolly"])
        superstar = int(d["superstar"])
    except (KeyError, TypeError, ValueError):
        raise ErroreClaude("Nella risposta di Claude mancano sestine, Jolly o SuperStar.")
    if len(sestine) != 3:
        raise ErroreClaude("Claude non ha indicato 3 sestine.")
    for s in sestine:
        if len(s) != 6 or len(set(s)) != 6 or any(not 1 <= x <= 90 for x in s):
            raise ErroreClaude(f"Sestina non valida nella risposta di Claude: {s}")
    if not 1 <= superstar <= 90 or not 1 <= jolly <= 90:
        raise ErroreClaude("Jolly o SuperStar fuori intervallo.")
    avvisi = []
    if jolly in sestine[0]:
        avvisi.append("Il Jolly indicato è nella 1ª sestina.")
    for i in range(3):
        for j in range(i + 1, 3):
            comuni = len(set(sestine[i]) & set(sestine[j]))
            if comuni > 2:
                avvisi.append(f"Le sestine {i + 1} e {j + 1} hanno {comuni} numeri in comune.")
    for i, s in enumerate(sestine, 1):
        if tuple(s) in gia_uscite:
            avvisi.append(f"La sestina {i} è già uscita in passato.")
    mot = d.get("motivazioni") or []
    return RispostaClaude(sestine, jolly, superstar, [str(x) for x in mot][:3],
                          str(d.get("jolly_superstar", "")), str(d.get("analisi", "")),
                          str(d.get("scartati", "")), str(d.get("affidabilita", "")), avvisi=avvisi)


def chiedi_a_claude(chiave: str, modello: str, dossier: str, gia_uscite: set[tuple],
                    timeout: int = 300) -> RispostaClaude:
    if not chiave:
        raise ErroreClaude("Manca la chiave API di Claude.")
    corpo = {
        "model": modello,
        "max_tokens": 6000,
        "system": SISTEMA,
        "messages": [{"role": "user", "content": dossier + "\n\nOra scegli le 3 sestine, il Jolly e il "
                                                            "SuperStar e rispondi solo con il JSON richiesto."}],
    }
    req = urllib.request.Request(URL_API, data=json.dumps(corpo).encode("utf-8"), method="POST", headers={
        "x-api-key": chiave,
        "anthropic-version": VERSIONE_API,
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dati = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        dettaglio = ex.read().decode("utf-8", errors="replace")
        try:
            dettaglio = json.loads(dettaglio)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            pass
        spiegazioni = {401: "chiave API non valida", 402: "credito API esaurito",
                       403: "chiave senza permessi", 404: "modello non disponibile per questa chiave",
                       429: "troppe richieste o limite di spesa raggiunto", 529: "servizio momentaneamente sovraccarico"}
        raise ErroreClaude(f"Errore {ex.code} ({spiegazioni.get(ex.code, 'errore del servizio')}): {dettaglio}")
    except (urllib.error.URLError, TimeoutError) as ex:
        raise ErroreClaude(f"Impossibile contattare Claude: {ex}")
    testo = "".join(b.get("text", "") for b in dati.get("content", []) if b.get("type") == "text")
    if dati.get("stop_reason") == "max_tokens" and "}" not in testo:
        raise ErroreClaude("La risposta di Claude è stata troncata: riprova.")
    r = valida_risposta(_estrai_json(testo), gia_uscite)
    r.modello = dati.get("model", modello)
    uso = dati.get("usage", {})
    r.token_ingresso = int(uso.get("input_tokens", 0))
    r.token_uscita = int(uso.get("output_tokens", 0))
    return r


def come_risultato(rc: RispostaClaude, base: magico.RisultatoMagico) -> magico.RisultatoMagico:
    """Trasforma la risposta di Claude in un risultato mostrabile in home e salvabile nello storico."""
    return magico.RisultatoMagico(
        [magico.SestinaMagica(s, 0.0, {"motivazione": 0.0}) for s in rc.sestine], rc.jolly, rc.superstar,
        base.punteggi, base.voci, base.basata_su, base.estrazioni_usate, [])
