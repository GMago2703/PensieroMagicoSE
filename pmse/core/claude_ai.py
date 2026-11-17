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
from .gioco import SE, Gioco, gioco_di

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
CHIAVE_WORKSPACE = "claude_workspace_id"

def istruzioni(g: Gioco = SE) -> str:
    """Istruzioni di sistema per Claude, adattate al gioco."""
    C, K = g.combinazioni_magico, g.k
    if g.is_ej:
        descr = ("dell'Eurojackpot (5 numeri estratti da 1 a 50, più 2 Euronumeri estratti da un'urna separata: "
                 "oggi da 1 a 12, in passato da 1 a 8 e poi da 1 a 10)")
        scelta = "la cinquina più consona e i 2 Euronumeri"
        regole = ("la cinquina ha 5 numeri DIVERSI tra 1 e 50, in ordine crescente; non è identica a una già "
                  "uscita; i 2 Euronumeri sono DIVERSI, tra 1 e 12, in ordine crescente.")
        formato = ('{"cinquina": [n,n,n,n,n],\n "euronumeri": [n,n],\n'
                   ' "motivazioni": ["perché questa cinquina"],\n'
                   ' "jolly_superstar": "perché questi Euronumeri",')
    else:
        descr = ("del SuperEnalotto (6 numeri estratti da 1 a 90, più Jolly estratto dagli 84 rimanenti e "
                 "SuperStar estratto separatamente da 1 a 90)")
        scelta = "le 3 sestine più consone, il Jolly e il SuperStar"
        regole = ("ogni sestina ha 6 numeri DIVERSI tra 1 e 90, in ordine crescente; le 3 sestine hanno al "
                  "massimo 2 numeri in comune tra loro a due a due; nessuna sestina è identica a una già uscita; "
                  "il Jolly è tra 1 e 90 e NON appartiene alla 1ª sestina; il SuperStar è tra 1 e 90.")
        formato = ('{"sestine": [[n,n,n,n,n,n],[n,n,n,n,n,n],[n,n,n,n,n,n]],\n "jolly": n, "superstar": n,\n'
                   ' "motivazioni": ["perché la sestina 1", "perché la sestina 2", "perché la sestina 3"],\n'
                   ' "jolly_superstar": "perché questo Jolly e questo SuperStar",')
    comb = g.nome_comb
    return f"""Sei "Magico Pensiero", il motore di valutazione finale di un'applicazione Windows che studia \
l'archivio storico {descr}.

Ipotesi di lavoro del progetto, voluta dall'utente: ogni estrazione conserva una "memoria" delle precedenti, \
quindi cerchiamo regolarità e nessi tra estrazioni successive. Lavora dentro questa ipotesi, ma da analista \
rigoroso: dai più fiducia a ciò che è confermato da molti dati e dalla verifica storica, considera rumore le \
differenze piccole, e se un indicatore non ha mai dimostrato di funzionare dagli un peso basso.

Compito:
1. Studia il dossier: statistiche per numero, forma tipica delle combinazioni, ultime estrazioni, coppie, \
punteggi e candidate dell'algoritmo, esito della verifica storica e le "Lezioni dalle ultime estrazioni" \
(dove le previsioni passate hanno sbagliato e dove hanno visto giusto): tienine conto per correggere le \
mancanze ricorrenti e rafforzare ciò che ha funzionato.
2. Fai le tue analisi e valutazioni (puoi combinare gli indicatori a modo tuo, cercare schemi nelle ultime \
estrazioni, ecc.) e scarta ciò che ritieni meno plausibile.
3. Scegli a tuo insindacabile giudizio {scelta}. Puoi partire dalle candidate dell'algoritmo, modificarle o \
comporne di nuove.

Regole obbligatorie: {regole}
Regola di SOMIGLIANZA CON L'ARCHIVIO (fondamentale): l'analisi delle combinazioni vincenti rispetto a tutte le \
precedenti mostra quanti numeri, al massimo, una nuova combinazione vincente ha di solito in comune con una \
qualsiasi estrazione passata. Ogni tua {comb} deve rispettare il limite indicato nel dossier alla sezione \
"Somiglianza con l'archivio": confrontata con OGNI estrazione dell'archivio deve avere al massimo il numero di \
numeri in comune indicato, e il suo massimo deve cadere nell'intervallo consigliato. Le candidate dell'algoritmo \
riportano già questo valore; se componi combinazioni nuove tienine conto (il programma lo verifica).

Rispondi in italiano e SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura:
{formato}
 "analisi": "le tue valutazioni principali sui dati (5-10 frasi)",
 "scartati": "cosa hai scartato e perché",
 "affidabilita": "una frase onesta su quanto ritieni affidabile questa scelta"}}"""


SISTEMA = istruzioni(SE)


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
    in_comune_archivio: list[int] = field(default_factory=list)
    corretta: bool = False          # True se Claude ha dovuto correggere una prima risposta


# ------------------------------------------------------------------ dossier
def _riga(*v) -> str:
    return ";".join(str(x) for x in v)


def costruisci_dossier(storico: Storico, r: magico.RisultatoMagico, verifica: str | None = None,
                       ultime: int = 40, lezioni: str | None = None, imp: magico.Impostazioni | None = None) -> str:
    g = gioco_di(storico)
    N, K, comb = g.n, g.k, g.nome_comb
    n = len(storico)
    m = magico.matrice(storico)
    rit, medio = magico._ritardi(m)
    freq = m.sum(axis=0)
    f100 = m[-100:].sum(axis=0)
    f30 = m[-30:].sum(axis=0)
    jolly = Counter(x[2] for x in storico)
    speciali = "euronumeri" if g.is_ej else "jolly;superstar"
    out = [f"# DOSSIER ARCHIVIO {g.nome.upper()}",
           f"Estrazioni: {n}, dal {storico[0][0]:%d/%m/%Y} al {storico[-1][0]:%d/%m/%Y}. "
           f"Il prossimo concorso è quello successivo al {storico[-1][0]:%d/%m/%Y}.", ""]

    out.append(f"## Ultime {ultime} estrazioni (dalla più recente): data;{comb} ordinata;{speciali}")
    for x in reversed(storico[-ultime:]):
        if g.is_ej:
            out.append(_riga(f"{x[0]:%d/%m/%Y}", " ".join(map(str, x[1])), f"{x[2]} {x[3]}"))
        else:
            out.append(_riga(f"{x[0]:%d/%m/%Y}", " ".join(map(str, x[1])), x[2], x[3] or "-"))
    out.append("")

    out.append("## Statistiche per numero")
    out.append("numero;uscite_totali;uscite_ultime100;uscite_ultime30;ritardo_attuale;ritardo_medio;"
               + ("" if g.is_ej else "volte_jolly;") + ";".join(f"voce_{k}" for k in r.voci)
               + ";punteggio_algoritmo")
    for k in range(1, N + 1):
        out.append(_riga(k, int(freq[k]), int(f100[k]), int(f30[k]), int(rit[k]), round(float(medio[k]), 1),
                         *([] if g.is_ej else [jolly[k]]), *[round(r.voci[v][k], 3) for v in r.voci],
                         round(r.punteggi[k], 3)))
    out.append("(voci dell'algoritmo in scala 0-1: " + ", ".join(f"{k} = {magico.VOCI.get(k, k)}" for k in r.voci)
               + ")")
    out.append("")

    sestine = np.array([x[1] for x in storico])
    somme = sestine.sum(axis=1)
    pari = (sestine % 2 == 0).sum(axis=1)
    alti = (sestine > g.soglia_alti).sum(axis=1)
    cons = (np.diff(sestine, axis=1) == 1).sum(axis=1)
    q = np.percentile(somme, [10, 25, 50, 75, 90]).round().astype(int)
    out.append(f"## Forma delle {g.nome_comb_pl} nello storico")
    out.append(f"Somma: percentili 10/25/50/75/90 = {' / '.join(map(str, q))}; ultima somma {int(somme[-1])}")
    for nome, arr in (("numeri pari", pari), (f"numeri alti {g.soglia_alti + 1}-{N}", alti),
                      ("coppie consecutive", cons)):
        c = Counter(arr.tolist())
        out.append(f"{nome}: " + ", ".join(f"{k}→{round(100 * c[k] / n, 1)}%" for k in sorted(c)))
    rip = Counter(len(set(a[1]) & set(b[1])) for a, b in zip(storico, storico[1:]))
    out.append("numeri ripetuti dall'estrazione precedente: " +
               ", ".join(f"{k}→{round(100 * rip[k] / (n - 1), 1)}%" for k in sorted(rip)))
    out.append("")

    lift = magico._lift_coppie(m)
    cnt = m.T @ m
    coppie = [(lift[a, b], int(cnt[a, b]), a, b) for a in range(1, N + 1) for b in range(a + 1, N + 1)
              if cnt[a, b] >= 8]
    coppie.sort(reverse=True)
    out.append("## Coppie uscite insieme più del previsto (coppia;volte;rapporto sul caso)")
    out.extend(_riga(f"{a}-{b}", c, round(float(l), 2)) for l, c, a, b in coppie[:30])
    out.append("")

    from .analisi import massimi_in_comune
    lo, hi = r.limiti_archivio
    massimi = massimi_in_comune(storico, 500)
    cm = Counter(massimi)
    out.append("## Somiglianza con l'archivio")
    out.append("Per ognuna delle ultime 500 estrazioni: massimo di numeri in comune con una qualsiasi estrazione "
               "precedente → " + ", ".join(f"{k} numeri: {round(100 * cm[k] / len(massimi), 1)}%" for k in sorted(cm)))
    out.append(f"INTERVALLO CONSIGLIATO E OBBLIGATORIO per le tue {g.nome_comb_pl}: massimo in comune con "
               f"l'archivio da {lo} a {hi} (cioè nessuna estrazione passata deve avere più di {hi} numeri in "
               f"comune con la {comb}, e almeno una deve averne {lo} o più).")
    out.append("")

    out.append("## Proposta dell'algoritmo Magico Pensiero 0.1")
    for i, s in enumerate(r.sestine, 1):
        out.append(f"{comb} {i}: {' '.join(map(str, s.numeri))} (voto {s.voto}; max in comune con l'archivio "
                   f"{s.dettaglio.get("max numeri in comune con l'archivio", '?')})")
    out.append(f"euronumeri {r.jolly} {r.superstar}" if g.is_ej else f"jolly {r.jolly}; superstar {r.superstar}")
    out.append(f"Migliori candidate ({comb};voto;max numeri in comune con l'archivio):")
    comuni = r.in_comune_migliori or [""] * len(r.migliori)
    out.extend(_riga(" ".join(map(str, c)), v, k) for (c, v), k in zip(r.migliori[:30], comuni))
    out.append("")

    if g.is_ej:
        pe = magico.punteggi_euronumeri(storico, imp or magico.Impostazioni.predefinite(g))
        attuali = [x for x in storico if g.euro_max(x[0]) == 12]
        ce = Counter(e for x in attuali for e in (x[2], x[3]))
        ultimo_e = {}
        for i, x in enumerate(attuali):
            ultimo_e[x[2]] = ultimo_e[x[3]] = i
        out.append("## Euronumeri (estrazioni con la formula attuale 1-12)")
        out.append("ultime 30 coppie (dalla più recente): " +
                   ", ".join(f"{x[2]}-{x[3]}" for x in reversed(attuali[-30:])))
        out.append("euronumero;uscite;ritardo_attuale;punteggio_algoritmo")
        out.extend(_riga(e, ce[e], len(attuali) - 1 - ultimo_e.get(e, -1), round(float(pe[e]), 3))
                   for e in range(1, 13))
        out.append("")
    serie_ss = [x[3] for x in storico if x[3]] if not g.is_ej else []
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
    out.append("")
    out.append("## Lezioni dalle ultime estrazioni (confronto tra previsioni e numeri usciti)")
    if imp is not None:
        eff = magico.pesi_effettivi(imp)
        out.append("Pesi effettivi attuali delle voci dopo l'apprendimento: " +
                   ", ".join(f"{magico.VOCI[k]} {v}" for k, v in eff.items()))
        out.append("Filtri di forma attuali: " + "; ".join(magico.descrivi_filtri(imp, storico).values()))
    out.append(lezioni.strip() if lezioni else "Nessuna valutazione ancora disponibile.")
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


def in_comune_archivio(sestine: list[list[int]], m: np.ndarray) -> list[int]:
    v = np.zeros((len(sestine), m.shape[1] if len(m.shape) == 2 else 91), dtype=np.float32)
    for i, s in enumerate(sestine):
        v[i, s] = 1
    return [int(x) for x in (v @ m.T).max(axis=1)] if len(m) else [0] * len(sestine)


def valida_risposta(d: dict, gia_uscite: set[tuple], m: np.ndarray | None = None,
                    limiti: tuple[int, int] | None = None, g: Gioco = SE) -> RispostaClaude:
    C, K, N, comb = g.combinazioni_magico, g.k, g.n, g.nome_comb
    try:
        if g.is_ej:
            sestine = [sorted(int(x) for x in d["cinquina"])]
            jolly, superstar = sorted(int(x) for x in d["euronumeri"])[:2]
        else:
            sestine = [sorted(int(x) for x in s) for s in d["sestine"]][:C]
            jolly = int(d["jolly"])
            superstar = int(d["superstar"])
    except (KeyError, TypeError, ValueError):
        raise ErroreClaude("Nella risposta di Claude mancano numeri o numeri speciali.")
    if len(sestine) != C:
        raise ErroreClaude(f"Claude non ha indicato {C} {g.nome_comb_pl}.")
    for s in sestine:
        if len(s) != K or len(set(s)) != K or any(not 1 <= x <= N for x in s):
            raise ErroreClaude(f"{g.C()} non valida nella risposta di Claude: {s}")
    if g.is_ej:
        if jolly == superstar or not (1 <= jolly <= 12 and 1 <= superstar <= 12):
            raise ErroreClaude("Euronumeri non validi (devono essere 2 numeri diversi da 1 a 12).")
    elif not 1 <= superstar <= 90 or not 1 <= jolly <= 90:
        raise ErroreClaude("Jolly o SuperStar fuori intervallo.")
    avvisi = []
    if not g.is_ej and jolly in sestine[0]:
        avvisi.append("Il Jolly indicato è nella 1ª sestina.")
    for i in range(C):
        for j in range(i + 1, C):
            comuni = len(set(sestine[i]) & set(sestine[j]))
            if comuni > 2:
                avvisi.append(f"Le {g.nome_comb_pl} {i + 1} e {j + 1} hanno {comuni} numeri in comune.")
    for i, s in enumerate(sestine, 1):
        if tuple(s) in gia_uscite:
            avvisi.append(f"La {comb} {i} è già uscita in passato.")
    comuni_arch = in_comune_archivio(sestine, m) if m is not None else []
    if limiti and comuni_arch:
        lo, hi = limiti
        for i, k in enumerate(comuni_arch, 1):
            if not lo <= k <= hi:
                avvisi.append(f"La {comb} {i} ha al massimo {k} numeri in comune con l'archivio "
                              f"(limite consigliato da {lo} a {hi}).")
    mot = d.get("motivazioni") or []
    return RispostaClaude(sestine, jolly, superstar, [str(x) for x in mot][:C],
                          str(d.get("jolly_superstar", "")), str(d.get("analisi", "")),
                          str(d.get("scartati", "")), str(d.get("affidabilita", "")), avvisi=avvisi,
                          in_comune_archivio=comuni_arch)


def _invia(chiave: str, corpo: dict, timeout: int, workspace: str = "") -> dict:
    intestazioni = {
        "x-api-key": chiave,
        "anthropic-version": VERSIONE_API,
        "content-type": "application/json",
    }
    if workspace:        # serve solo per chiavi non legate a un workspace
        intestazioni["anthropic-workspace-id"] = workspace
    req = urllib.request.Request(URL_API, data=json.dumps(corpo).encode("utf-8"), method="POST",
                                 headers=intestazioni)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        dettaglio = ex.read().decode("utf-8", errors="replace")
        try:
            dettaglio = json.loads(dettaglio)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            pass
        spiegazioni = {400: "richiesta non accettata (se la chiave non è legata a un workspace, indica l'ID "
                            "workspace)", 401: "chiave API non valida", 402: "credito API esaurito",
                       403: "chiave senza permessi", 404: "modello non disponibile per questa chiave",
                       429: "troppe richieste o limite di spesa raggiunto", 529: "servizio momentaneamente sovraccarico"}
        raise ErroreClaude(f"Errore {ex.code} ({spiegazioni.get(ex.code, 'errore del servizio')}): {dettaglio}")
    except (urllib.error.URLError, TimeoutError) as ex:
        raise ErroreClaude(f"Impossibile contattare Claude: {ex}")


def _testo(dati: dict) -> str:
    testo = "".join(b.get("text", "") for b in dati.get("content", []) if b.get("type") == "text")
    if dati.get("stop_reason") == "max_tokens" and "}" not in testo:
        raise ErroreClaude("La risposta di Claude è stata troncata: riprova.")
    return testo


def prova_chiave(chiave: str, modello: str, workspace: str = "") -> str:
    """Piccola richiesta di prova: restituisce un messaggio di esito o solleva ErroreClaude."""
    if not chiave:
        raise ErroreClaude("Manca la chiave API.")
    if not chiave.startswith("sk-ant-"):
        raise ErroreClaude("La chiave dovrebbe iniziare con «sk-ant-»: controlla di averla copiata per intero.")
    corpo = {"model": modello, "max_tokens": 20,
             "messages": [{"role": "user", "content": "Rispondi soltanto: OK"}]}
    dati = _invia(chiave, corpo, 60, workspace)
    testo = "".join(b.get("text", "") for b in dati.get("content", []) if b.get("type") == "text").strip()
    return f"Collegamento riuscito con {dati.get('model', modello)}. Risposta di prova: «{testo[:40]}»."


def chiedi_a_claude(chiave: str, modello: str, dossier: str, gia_uscite: set[tuple],
                    m: np.ndarray | None = None, limiti: tuple[int, int] | None = None,
                    timeout: int = 300, workspace: str = "", g: Gioco = SE) -> RispostaClaude:
    """Chiede a Claude la scelta. Se la risposta viola le regole, gli chiede UNA volta di correggerla."""
    if not chiave:
        raise ErroreClaude("Manca la chiave API di Claude.")
    cosa = "la cinquina e i 2 Euronumeri" if g.is_ej else "le 3 sestine, il Jolly e il SuperStar"
    messaggi = [{"role": "user", "content": dossier + f"\n\nOra scegli {cosa} e rispondi solo con il JSON "
                                                       "richiesto."}]
    corpo = {"model": modello, "max_tokens": 6000, "system": istruzioni(g), "messages": messaggi}
    dati = _invia(chiave, corpo, timeout, workspace)
    testo = _testo(dati)
    r = valida_risposta(_estrai_json(testo), gia_uscite, m, limiti, g)
    ing, usc = int(dati.get("usage", {}).get("input_tokens", 0)), int(dati.get("usage", {}).get("output_tokens", 0))
    if r.avvisi:
        messaggi += [{"role": "assistant", "content": testo},
                     {"role": "user", "content": "Il programma ha verificato la tua risposta e non rispetta queste "
                                                 "regole obbligatorie:\n- " + "\n- ".join(r.avvisi) +
                                                 "\nCorreggi ciò che non va e rispondi di nuovo solo con il "
                                                 "JSON completo."}]
        dati2 = _invia(chiave, corpo, timeout, workspace)
        try:
            r2 = valida_risposta(_estrai_json(_testo(dati2)), gia_uscite, m, limiti, g)
            r2.corretta = True
            if len(r2.avvisi) <= len(r.avvisi):
                r = r2
        except ErroreClaude:
            pass
        ing += int(dati2.get("usage", {}).get("input_tokens", 0))
        usc += int(dati2.get("usage", {}).get("output_tokens", 0))
    r.modello = dati.get("model", modello)
    r.token_ingresso, r.token_uscita = ing, usc
    return r


def come_risultato(rc: RispostaClaude, base: magico.RisultatoMagico) -> magico.RisultatoMagico:
    """Trasforma la risposta di Claude in un risultato mostrabile in home e salvabile nello storico."""
    return magico.RisultatoMagico(
        [magico.SestinaMagica(s, 0.0, {"motivazione": 0.0}) for s in rc.sestine], rc.jolly, rc.superstar,
        base.punteggi, base.voci, base.basata_su, base.estrazioni_usate, [], base.limiti_archivio,
        gioco=base.gioco)
