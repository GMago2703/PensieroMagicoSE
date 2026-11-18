"""Suggerimenti AI (menu Magico Pensiero): l'intelligenza artificiale già registrata (Claude o Gemini)
propone, per INTUIZIONE, un piccolo sistema da giocare: tipo, numeri, fisse, condizioni e riduzione.

Il programma le dà un quadro sintetico (ultime estrazioni, ritardi, numeri recenti, analisi di ogni
condizione con il suggerimento dell'archivio, candidate di Magico Pensiero, riduzioni pronte, budget) e
le chiede di non rifare le analisi ma di "sentire" una combinazione di scelte. Poi il programma controlla
la proposta, sviluppa davvero il sistema e, se è troppo grande, vuoto o non valido, le chiede di
correggerla (al massimo due volte).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from . import condizioni as cnd
from . import ridotti_pronti
from . import sistemi as sis
from . import statistiche as st
from .claude_ai import (ErroreClaude, _estrai_json, _invia, _invia_gemini, _testo, _testo_gemini)
from .gioco import Gioco, SE

CHIAVE_BUDGET = "intuizione_budget"
TIPI_AMMESSI = ("condizionato", "condizionato_ridotto", "ridotto", "immediato")


def istruzioni(g: Gioco = SE) -> str:
    k = g.k
    garanzie = ", ".join(f"{j} = n-{j} (almeno {k - j} punti)" for j in range(1, k - 1))
    return f"""Sei "Magico Pensiero – Intuizione", dentro un programma Windows per il {g.nome} \
({k} numeri da 1 a {g.n}). Il programma ha già fatto tutte le analisi: le trovi riassunte nel quadro che segue.

Questa volta NON ti chiediamo un'altra analisi. Ti chiediamo un'INTUIZIONE: guarda il quadro come lo \
guarderebbe un giocatore esperto con buon fiuto, lasciati colpire da ciò che ti sembra "chiamare" (un numero \
che torna, un ritardo che ti incuriosisce, un valore delle condizioni che ti pare maturo, un gruppo di numeri \
che sta bene insieme, una data, una simmetria) e trasformalo in UN PICCOLO SISTEMA da giocare. Puoi tenere \
conto delle analisi e dei suggerimenti delle condizioni, ma la scelta finale è tua e deve avere un'idea, un \
filo conduttore che sai raccontare. Sii onesto: ogni estrazione è casuale, l'intuizione non cambia le \
probabilità; il sistema deve però essere sensato, coerente e dentro il budget.

Tipi di sistema:
- "condizionato": numeri + condizioni, si giocano tutte le colonne che rispettano le condizioni;
- "condizionato_ridotto": come sopra, poi ridotto con una garanzia;
- "ridotto": integrale dei numeri ridotto con una garanzia (niente condizioni);
- "immediato": riduzione già pronta (vedi elenco nel quadro: numeri, fisse, punti garantiti → colonne).
Garanzia (campo "garanzia"): 0 = nessuna riduzione; {garanzie}. Vale se la combinazione vincente è tra quelle \
possibili del sistema.
Fisse: numeri presenti in tutte le colonne (al massimo 2), devono essere tra i numeri giocati.
Condizioni: usa SOLO i codici elencati nel quadro. Formato: {{"codice": "pari", "valori": [2,3,4]}} per le \
condizioni a valori, {{"codice": "somme", "minimo": 200, "massimo": 330}} per quelle a intervallo, \
{{"codice": "gruppo", "numeri": [7,21,33], "minimo": 1, "massimo": 2}} per un gruppo di numeri di cui ne \
devono uscire da minimo a massimo. Facoltativo "param" dove la condizione ha un parametro. Da 0 a 6 condizioni.
"errori_max": quante condizioni una colonna può non rispettare (0 o 1).

Rispondi in italiano e SOLO con un oggetto JSON valido, senza testo prima o dopo:
{{"titolo": "un nome breve ed evocativo per il sistema",
 "tipo": "condizionato" | "condizionato_ridotto" | "ridotto" | "immediato",
 "numeri": [da {k + 1} a 20 numeri diversi tra 1 e {g.n}],
 "fisse": [0, 1 o 2 numeri tra quelli giocati],
 "condizioni": [ ... ],
 "errori_max": 0,
 "garanzia": 0,
 "intuizione": "il racconto della tua intuizione, da dove nasce (4-8 frasi)",
 "perche_numeri": "perché questi numeri (e queste fisse)",
 "perche_condizioni": "perché queste condizioni",
 "perche_riduzione": "perché questo tipo di sistema e questa garanzia",
 "affidabilita": "una frase onesta"}}"""


# ------------------------------------------------------------------ quadro (dossier)
def _fmt_lista(v) -> str:
    return " ".join(str(x) for x in v)


def quadro(g: Gioco, righe, ctx: cnd.Contesto, budget: float, prezzi: dict | None = None,
           candidate: list[list[int]] | None = None, indicazione: str = "", ultime: int = 12) -> str:
    """Il riassunto che viene inviato all'intelligenza artificiale."""
    prezzi = prezzi or {}
    prezzo = sis.costo(1, g, prezzi)
    max_col = max(1, int(budget // prezzo)) if prezzo else 50
    out = [f"QUADRO PER L'INTUIZIONE – {g.nome}", ""]
    out.append(f"Archivio: {len(righe)} estrazioni, dal {righe[0][0]:%d/%m/%Y} al {righe[-1][0]:%d/%m/%Y}.")
    out.append(f"BUDGET: al massimo {budget:.2f} € = {max_col} colonne (una colonna costa {prezzo:.2f} €). "
               "Il sistema sviluppato NON deve superarlo; meglio un sistema piccolo e pensato.")
    if indicazione.strip():
        out.append(f"INDICAZIONE DEL GIOCATORE (rispettala se possibile): {indicazione.strip()}")
    out += ["", f"ULTIME {ultime} ESTRAZIONI (la più recente per prima)"]
    for r in reversed(righe[-ultime:]):
        extra = (f" + Euronumeri {r[2]} {r[3]}" if g.is_ej else f"  Jolly {r[2]}  SuperStar {r[3]}")
        out.append(f"  {r[0]:%d/%m/%Y}: {_fmt_lista(r[1])}{extra}")
    d = st.Dati(g, righe)
    t = st.tutti_i_numeri(d, recenti=50)
    per_rit = sorted(t.righe, key=lambda r: -r[5])
    out += ["", "NUMERI PIÙ IN RITARDO (numero: ritardo attuale / record storico)",
            "  " + ", ".join(f"{r[0]}: {r[5]}/{r[6]}" for r in per_rit[:15])]
    per_rec = sorted(t.righe, key=lambda r: -r[9])
    atteso = 50 * g.k / g.n
    out += [f"NUMERI PIÙ USCITI NELLE ULTIME 50 (atteso {atteso:.1f})",
            "  " + ", ".join(f"{r[0]} ({r[9]})" for r in per_rec[:12]),
            "NUMERI MENO USCITI NELLE ULTIME 50",
            "  " + ", ".join(f"{r[0]} ({r[9]})" for r in per_rec[-12:])]
    if ctx.popolarita is not None:
        pn = ctx.popolarita.numeri()
        out += ["POPOLARITÀ (stima di quanto i giocatori puntano su ogni numero)",
                "  più giocati: " + ", ".join(str(n) for n, _ in pn[:12]),
                "  meno giocati: " + ", ".join(str(n) for n, _ in pn[-12:])]
    if candidate:
        out += ["", "CANDIDATE DELL'ALGORITMO MAGICO PENSIERO"]
        out += ["  " + _fmt_lista(c) for c in candidate[:6]]
    out += ["", "CONDIZIONI DISPONIBILI (codice – nome – tipo – analisi sull'archivio – valore nell'ultima estrazione)"]
    ultima = np.array([sorted(righe[-1][1])], dtype=np.int64)
    for tp in cnd.tipi_del_gioco(g):
        if tp.codice == "popolarita" and ctx.popolarita is None:
            continue
        try:
            a = cnd.analizza(tp.codice, ctx, tp.param_def)
            v = cnd._valori_archivio(tp, ctx, tp.param_def, 1)[-1] if tp.codice in (
                "ripetizioni", "ultima", "ritardatari") else tp.funzione(ultima, ctx, tp.param_def)[0]
        except Exception:
            continue
        modo = "intervallo (minimo/massimo)" if tp.modo == "intervallo" else "valori"
        par = f", parametro «{tp.param_nome}» (predefinito {tp.param_def})" if tp.param_nome else ""
        out.append(f"- {tp.codice} – {tp.nome} – {modo}{par}. {tp.descrizione} {a.suggerimento} "
                   f"Ultima estrazione: {int(v)}.")
    out.append("- gruppo – Gruppo di numeri – numeri + minimo/massimo presenti.")
    try:
        cl = st.classifica_condizioni(d, ctx=ctx)
        cl.righe.sort(key=lambda r: -r[7])
        out += ["VALORI DELLE CONDIZIONI CHE MANCANO DA PIÙ TEMPO RISPETTO ALLA LORO ABITUDINE "
                "(condizione, valore: ritardo / ritardo medio)",
                "  " + "; ".join(f"{r[0]} = {r[1]}: {r[4]}/{r[6]}" for r in cl.righe[:10])]
    except Exception:
        pass
    pronti = [x for x in ridotti_pronti.disponibili(g.k) if x[0] <= 16 and x[3] <= max_col]
    if pronti:
        out += ["", "RIDUZIONI PRONTE DENTRO IL BUDGET (numeri, fisse, punti garantiti → colonne)",
                "  " + "; ".join(f"{n}n {f}f {p}pt→{c}" for n, f, p, c in pronti)]
    return "\n".join(out)


# ------------------------------------------------------------------ interpretazione della risposta
@dataclass
class Proposta:
    sistema: sis.Sistema
    titolo: str = ""
    intuizione: str = ""
    perche_numeri: str = ""
    perche_condizioni: str = ""
    perche_riduzione: str = ""
    affidabilita: str = ""
    avvisi: list[str] = field(default_factory=list)


def interpreta(d: dict, g: Gioco) -> Proposta:
    """Dal JSON dell'AI a un Sistema; gli errori gravi sollevano ErroreClaude, quelli lievi diventano avvisi."""
    k = g.k
    try:
        numeri = sorted({int(x) for x in d.get("numeri", [])})
        fisse = sorted({int(x) for x in d.get("fisse", []) or []})
        tipo = str(d.get("tipo", "condizionato")).strip().lower().replace(" ", "_")
        garanzia = int(d.get("garanzia", 0) or 0)
        errori_max = int(d.get("errori_max", 0) or 0)
    except (TypeError, ValueError):
        raise ErroreClaude("La proposta non contiene numeri leggibili.")
    avvisi = []
    if tipo not in TIPI_AMMESSI:
        raise ErroreClaude(f"Tipo di sistema sconosciuto: «{tipo}».")
    if not k + 1 <= len(numeri) <= 20 or any(not 1 <= x <= g.n for x in numeri):
        raise ErroreClaude(f"Servono da {k + 1} a 20 numeri diversi tra 1 e {g.n} (ricevuti {len(numeri)}).")
    if len(fisse) > 2 or not set(fisse) <= set(numeri):
        raise ErroreClaude("Le fisse devono essere al massimo 2 e tra i numeri giocati.")
    if tipo in ("condizionato_ridotto", "ridotto", "immediato") and not 1 <= garanzia <= k - 2:
        raise ErroreClaude(f"Per il tipo «{tipo}» serve una garanzia da 1 a {k - 2}.")
    if tipo == "condizionato":
        garanzia = 0 if garanzia < 1 else min(garanzia, k - 2)
        if garanzia:
            tipo = "condizionato_ridotto"
    condizioni = []
    validi = {t.codice: t for t in cnd.tipi_del_gioco(g)}
    for c in d.get("condizioni", []) or []:
        if not isinstance(c, dict):
            continue
        cod = str(c.get("codice", "")).strip().lower()
        try:
            if cod == "gruppo":
                nums = sorted({int(x) for x in c.get("numeri", []) if 1 <= int(x) <= g.n})
                if not nums:
                    raise ValueError
                condizioni.append(cnd.gruppo(nums, int(c.get("minimo", 1)), int(c.get("massimo", len(nums)))))
                continue
            t = validi.get(cod)
            if t is None:
                avvisi.append(f"Condizione «{cod}» sconosciuta: ignorata.")
                continue
            param = int(c.get("param", t.param_def) or t.param_def)
            if t.param_nome:
                param = max(t.param_min, min(t.param_max, param))
            if t.modo == "intervallo":
                lo, hi = int(c["minimo"]), int(c["massimo"])
                condizioni.append(cnd.Condizione(cod, minimo=min(lo, hi), massimo=max(lo, hi), param=param))
            else:
                vals = sorted({int(x) for x in c["valori"]})
                if not vals:
                    raise ValueError
                condizioni.append(cnd.Condizione(cod, valori=vals, param=param))
        except (KeyError, TypeError, ValueError):
            avvisi.append(f"Condizione «{cod}» scritta male: ignorata.")
    if tipo in ("ridotto", "immediato") and condizioni:
        avvisi.append("Nei sistemi «ridotto» e «immediato» le condizioni non si applicano: ignorate.")
        condizioni = []
    titolo = str(d.get("titolo", "")).strip()[:60]
    s = sis.Sistema(nome=titolo, tipo=tipo, gioco=g.codice, numeri=numeri, fisse=fisse,
                    condizioni=cnd.a_json(condizioni), errori_min=0, errori_max=max(0, min(errori_max, 2)),
                    garanzia=garanzia, qualita=12, note="Suggerito dall'intelligenza artificiale (intuizione)")
    return Proposta(s, titolo, str(d.get("intuizione", "")), str(d.get("perche_numeri", "")),
                    str(d.get("perche_condizioni", "")), str(d.get("perche_riduzione", "")),
                    str(d.get("affidabilita", "")), avvisi)


# ------------------------------------------------------------------ dialogo con l'AI
@dataclass
class Esito:
    proposta: Proposta
    sviluppo: sis.Sviluppo
    costo: float
    correzioni: list[str] = field(default_factory=list)   # cosa il programma ha fatto correggere
    modello: str = ""
    token_ingresso: int = 0
    token_uscita: int = 0
    secondi: float = 0.0


def conversatore(fornitore: str, chiave: str, modello: str, sistema: str, workspace: str = "",
                 timeout: int = 300):
    """Funzione conversa(messaggi) -> (testo, modello, token_in, token_out) per Claude o Gemini."""
    if not chiave:
        raise ErroreClaude("Manca la chiave API: impostala in Magico Pensiero → intelligenza artificiale.")
    if fornitore == "gemini":
        def conversa(messaggi):
            contenuti = [{"role": "model" if x["role"] == "assistant" else "user", "parts": [{"text": x["content"]}]}
                         for x in messaggi]
            corpo = {"systemInstruction": {"parts": [{"text": sistema}]}, "contents": contenuti,
                     "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 16000,
                                          "temperature": 1.0}}
            dati = _invia_gemini(chiave, modello, corpo, timeout)
            uso = dati.get("usageMetadata", {})
            return (_testo_gemini(dati), dati.get("modelVersion", modello), int(uso.get("promptTokenCount", 0)),
                    int(uso.get("candidatesTokenCount", 0)) + int(uso.get("thoughtsTokenCount", 0)))
        return conversa

    def conversa(messaggi):
        dati = _invia(chiave, {"model": modello, "max_tokens": 6000, "system": sistema, "messages": messaggi},
                      timeout, workspace)
        uso = dati.get("usage", {})
        return (_testo(dati), dati.get("model", modello), int(uso.get("input_tokens", 0)),
                int(uso.get("output_tokens", 0)))
    return conversa


def proponi(conversa, testo_quadro: str, g: Gioco, ctx: cnd.Contesto, budget: float,
            prezzi: dict | None = None, correzioni_max: int = 2, avanzamento=None) -> Esito:
    """Chiede l'intuizione, sviluppa il sistema e, se serve, fa correggere la proposta."""
    t0 = time.time()
    prezzo = sis.costo(1, g, prezzi)
    max_col = max(1, int(budget // prezzo)) if prezzo else 50
    messaggi = [{"role": "user", "content": testo_quadro + "\n\nOra lasciati guidare dall'intuizione e "
                                                           "proponi il tuo piccolo sistema: rispondi solo con il JSON."}]
    correzioni, modello, ing, usc = [], "", 0, 0
    ultimo_errore = ""
    for giro in range(correzioni_max + 1):
        if avanzamento:
            avanzamento("L'intelligenza artificiale sta pensando..." if giro == 0 else
                        f"Correzione {giro}: l'intelligenza artificiale sistema la proposta...")
        testo, modello, i, u = conversa(messaggi)
        ing, usc = ing + i, usc + u
        problema = ""
        try:
            p = interpreta(_estrai_json(testo, "L'intelligenza artificiale"), g)
            if avanzamento:
                avanzamento("Sviluppo del sistema proposto...")
            sv = sis.sviluppa(p.sistema, ctx)
            n = len(sv.colonne)
            if n == 0:
                problema = ("Il sistema sviluppato ha 0 colonne: le condizioni sono troppo strette per questi "
                            "numeri. Allargale o cambiale.")
            elif n > max_col:
                problema = (f"Il sistema sviluppato ha {n} colonne ({sis._euro(sis.costo(n, g, prezzi))} €): supera "
                            f"il budget di {max_col} colonne ({sis._euro(budget)} €). Rendilo più piccolo (meno numeri, "
                            "condizioni più strette, oppure una riduzione con garanzia più bassa).")
        except (ErroreClaude, ValueError) as ex:
            problema = f"La proposta non è valida: {ex}"
            p = sv = None
        if not problema:
            p.sistema.colonne = sv.colonne.tolist()
            p.sistema.info = {"integrale": sv.integrale, "possibili": sv.possibili, "secondi": round(sv.secondi, 2)}
            return Esito(p, sv, sis.costo(len(sv.colonne), g, prezzi), correzioni, modello, ing, usc,
                         time.time() - t0)
        correzioni.append(problema)
        ultimo_errore = problema
        messaggi += [{"role": "assistant", "content": testo},
                     {"role": "user", "content": "Il programma ha controllato e sviluppato la tua proposta: "
                                                 f"{problema}\nMantieni l'idea della tua intuizione, correggi e "
                                                 "rispondi di nuovo solo con il JSON completo."}]
    raise ErroreClaude("Dopo le correzioni la proposta non è ancora giocabile: " + ultimo_errore)
