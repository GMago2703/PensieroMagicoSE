"""Analisi delle previsioni rispetto all'estrazione uscita e apprendimento automatico.

Dopo ogni nuova estrazione il programma:
1. rifà il calcolo di Magico Pensiero "com'era prima" dell'estrazione;
2. guarda dove si trovavano i 6 numeri usciti nella classifica di ogni voce
   (eco, affinità, tendenza, maturità, storico) e del punteggio finale:
   una voce che li aveva messi in alto ha "visto giusto", una che li aveva
   messi in basso ha sbagliato;
3. controlla se i filtri (forma della sestina, somiglianza con l'archivio)
   avrebbero lasciato passare la combinazione vincente;
4. se esistevano previsioni salvate (dell'algoritmo o di Claude) le confronta
   con l'estrazione: punti, numeri presi e mancati, Jolly, SuperStar;
5. scrive cosa è andato bene (positivi) e cosa no (mancanze);
6. aggiorna le statistiche di ogni voce: i pesi effettivi crescono per le voci
   che, sommando TUTTE le estrazioni valutate, mettono i numeri usciti più in
   alto del caso, e calano per le altre (vedi magico.pesi_effettivi). Un singolo
   concorso sposta pochissimo: conta l'evidenza accumulata;
7. se un filtro di forma scarta troppo spesso le vere combinazioni vincenti
   (chiaramente oltre la soglia, di solito 25%) lo allenta di un passo.
Il registro delle valutazioni viene usato anche da Claude.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date

import numpy as np

from . import magico, personale
from .analisi import Storico

CHIAVE_REGISTRO = "magico_valutazioni"
CHIAVE_APPRESO = "magico_appreso_fino_a"
PESO_MIN, PESO_MAX = 0.02, 2.0


@dataclass
class Valutazione:
    data_estrazione: str
    estratti: list[int]
    jolly: int
    superstar: int | None
    prestazioni: dict[str, float]               # voce -> posizione media dei numeri usciti (0..1, 0.5 = caso)
    rango_finale: dict[str, int]                 # numero uscito -> posizione nella classifica finale (1-90)
    filtri_superati: dict[str, bool]             # filtro -> la vincente l'avrebbe superato?
    descrizione_filtri: dict[str, str] = field(default_factory=dict)
    correzioni: list[str] = field(default_factory=list)     # modifiche automatiche all'algoritmo
    previsioni: list[dict] = field(default_factory=list)   # [{origine, sestine, punti, presi, jolly_ok, ss_ok}]
    positivi: list[str] = field(default_factory=list)
    mancanze: list[str] = field(default_factory=list)
    pesi_prima: dict[str, float] = field(default_factory=dict)
    pesi_dopo: dict[str, float] = field(default_factory=dict)
    gioco: str = "SE"

    def testo(self) -> str:
        speciali = (f"Euronumeri {self.jolly}-{self.superstar}" if self.gioco == "EJ"
                    else f"Jolly {self.jolly}  SuperStar {self.superstar or '-'}")
        r = [f"Estrazione del {date.fromisoformat(self.data_estrazione):%d/%m/%Y}: "
             f"{' '.join(map(str, self.estratti))}  {speciali}"]
        for p in self.previsioni:
            r.append(f"  {p['origine']}: " + " | ".join(
                f"{' '.join(map(str, s))} → {pt} punti" + (f" ({' '.join(map(str, pr))})" if pr else "")
                for s, pt, pr in zip(p["sestine"], p["punti"], p["presi"])))
        r.append("  Posizione dei numeri usciti nella classifica finale: " +
                 ", ".join(f"{n}→{k}°" for n, k in sorted(self.rango_finale.items(), key=lambda x: x[1])))
        r.append("  ✔ " + "\n  ✔ ".join(self.positivi) if self.positivi else "  ✔ nessun aspetto positivo rilevante")
        r.append("  ✘ " + "\n  ✘ ".join(self.mancanze) if self.mancanze else "  ✘ nessuna mancanza rilevante")
        if self.pesi_dopo and self.pesi_dopo != self.pesi_prima:
            r.append("  Pesi effettivi: " + ", ".join(
                f"{magico.VOCI.get(k, k)} {self.pesi_prima.get(k, 0):.3f}→{v:.3f}" for k, v in self.pesi_dopo.items()))
        for c in self.correzioni:
            r.append("  ⚙ " + c)
        return "\n".join(r)


def _percentili(arr: np.ndarray, numeri: list[int]) -> list[float]:
    """Posizione (0 = ultimo, 1 = primo) di ogni numero nella classifica della voce."""
    v = arr[1:]
    out = []
    for n in numeri:
        x = arr[n]
        out.append(float(((v < x).sum() + 0.5 * ((v == x).sum() - 1)) / (len(v) - 1)))
    return out


def _forma_ok(s: list[int], storico: Storico, imp: magico.Impostazioni) -> dict[str, bool]:
    esiti = magico.controlla_forma(np.array([s]), imp, storico)
    return {k: bool(v[0]) for k, v in esiti.items()}


def valuta(passato: Storico, estratta, imp: magico.Impostazioni, previsioni: list[dict] | None = None,
           m: np.ndarray | None = None) -> Valutazione:
    """Valuta come l'algoritmo 'vedeva' l'estrazione uscita, usando solo i dati precedenti."""
    g = magico.gioco_di(passato)
    totale, voci, _, m = magico.calcola_punteggi(passato, imp, m)
    estratti = sorted(estratta[1])
    prest = {k: round(float(np.mean(_percentili(v, estratti))), 3) for k, v in voci.items() if k in magico.VOCI}
    ordine = [int(k) for k in np.argsort(-totale[1:]) + 1]
    rango = {str(n): ordine.index(n) + 1 for n in estratti}
    filtri = _forma_ok(estratti, passato, imp)
    descr = magico.descrivi_filtri(imp, passato)
    lo, hi = magico.limiti_archivio(passato, imp)
    vett = np.zeros(g.n + 1, dtype=np.float32)
    vett[estratti] = 1
    comuni = int((m @ vett).max()) if len(m) else 0
    filtri["somiglianza"] = bool(lo <= comuni <= hi)
    descr["somiglianza"] = f"da {lo} a {hi} numeri in comune con l'archivio (la vincente ne aveva {comuni})"

    val = Valutazione(estratta[0].isoformat(), estratti, estratta[2], estratta[3], prest, rango, filtri, descr,
                      gioco=g.codice)
    # confronto con le previsioni salvate
    for p in previsioni or []:
        punti = [len(set(s) & set(estratti)) for s in p["sestine"]]
        presi = [sorted(set(s) & set(estratti)) for s in p["sestine"]]
        if g.is_ej:
            euro_presi = len({p.get("jolly"), p.get("superstar")} & {estratta[2], estratta[3]})
            jolly_ok, ss_ok = euro_presi >= 1, euro_presi == 2
        else:
            jolly_ok = p.get("jolly") in estratti or p.get("jolly") == estratta[2]
            ss_ok = bool(p.get("superstar") and p.get("superstar") == estratta[3])
        val.previsioni.append({"origine": p.get("origine", "Algoritmo"), "sestine": p["sestine"], "punti": punti,
                               "presi": presi, "jolly_ok": jolly_ok, "ss_ok": ss_ok})
    # positivi e mancanze
    nomi = magico.VOCI
    for k, v in sorted(prest.items(), key=lambda x: -x[1]):
        if v >= 0.6:
            val.positivi.append(f"La voce «{nomi[k]}» aveva messo i numeri usciti in alto "
                                f"(posizione media {round(100 * v)}%).")
        elif v <= 0.4:
            val.mancanze.append(f"La voce «{nomi[k]}» aveva messo i numeri usciti in basso "
                                f"(posizione media {round(100 * v)}%).")
    primi, oltre = round(g.n * 0.22), round(g.n * 2 / 3)
    in_alto = [int(n) for n, r in rango.items() if r <= primi]
    in_basso = [int(n) for n, r in rango.items() if r > oltre]
    if in_alto:
        val.positivi.append(f"Numeri usciti che erano tra i primi {primi} del punteggio finale: "
                            f"{' '.join(map(str, sorted(in_alto)))}.")
    if in_basso:
        val.mancanze.append(f"Numeri usciti che l'algoritmo considerava poco probabili (oltre il {oltre}° posto): "
                            f"{' '.join(map(str, sorted(in_basso)))}.")
    for nome, ok in filtri.items():
        if not ok:
            val.mancanze.append(f"Il filtro «{nome}» ({descr[nome]}) avrebbe SCARTATO la combinazione vincente.")
    if all(filtri.values()):
        val.positivi.append("La combinazione vincente rispettava tutti i filtri di forma e di somiglianza.")
    for p in val.previsioni:
        migliore = max(p["punti"])
        if migliore >= 2:
            i = p["punti"].index(migliore)
            val.positivi.append(f"{p['origine']}: la sestina {i + 1} ha fatto {migliore} punti "
                                f"({' '.join(map(str, p['presi'][i]))}).")
        else:
            val.mancanze.append(f"{p['origine']}: nessuna sestina ha superato {migliore} punto/i.")
        if g.is_ej:
            if p["ss_ok"]:
                val.positivi.append(f"{p['origine']}: entrambi gli Euronumeri indovinati!")
            elif p["jolly_ok"]:
                val.positivi.append(f"{p['origine']}: un Euronumero indovinato.")
            else:
                val.mancanze.append(f"{p['origine']}: nessun Euronumero indovinato.")
        else:
            if p["jolly_ok"]:
                val.positivi.append(f"{p['origine']}: il Jolly previsto è uscito.")
            if p["ss_ok"]:
                val.positivi.append(f"{p['origine']}: SuperStar indovinato!")
    return val


def gia_appreso(imp: magico.Impostazioni, d: date, periodo: tuple[str, str] | None = None) -> bool:
    da, a = periodo if periodo else (imp.appreso_da, imp.appreso_a)
    return bool(da and a and da <= d.isoformat() <= a)


def segna_appreso(imp: magico.Impostazioni, d: date) -> None:
    iso = d.isoformat()
    imp.appreso_da = min(imp.appreso_da, iso) if imp.appreso_da else iso
    imp.appreso_a = max(imp.appreso_a, iso) if imp.appreso_a else iso


def aggiorna(imp: magico.Impostazioni, prestazioni: dict[str, float], filtri: dict[str, bool]) -> list[str]:
    """Registra l'esito nelle statistiche dell'algoritmo e, se serve, allenta i filtri che
    scartano troppo spesso le vere combinazioni vincenti. Restituisce le correzioni fatte."""
    correzioni: list[str] = []
    if not imp.apprendimento:
        return correzioni
    for k, v in prestazioni.items():
        n, somma = imp.stat_voci.get(k, [0, 0.0])
        imp.stat_voci[k] = [n + 1, round(somma + v, 4)]
    for nome, ok in filtri.items():
        if nome == "somiglianza":
            continue
        n, scartate = imp.stat_filtri.get(nome, [0, 0])
        n, scartate = n + 1, scartate + (0 if ok else 1)
        # si allenta solo se la quota di vincenti scartate supera la soglia in modo statisticamente chiaro
        margine = 1.65 * math.sqrt(imp.soglia_filtri * (1 - imp.soglia_filtri) / max(n, 1))
        if n >= 50 and scartate / n > imp.soglia_filtri + margine:
            if _allenta(imp, nome):
                correzioni.append(f"Il filtro «{nome}» scartava il {round(100 * scartate / n)}% delle vincenti "
                                  f"(su {n}): allentato di un passo.")
            n, scartate = 0, 0
        imp.stat_filtri[nome] = [n, scartate]
    return correzioni


def _allenta(imp: magico.Impostazioni, nome: str) -> bool:
    prima = (imp.pari_min, imp.pari_max, imp.alti_min, imp.alti_max, imp.consecutivi_max,
             imp.somma_percentile, imp.max_stessa_decina)
    if nome == "pari/dispari":
        imp.pari_min, imp.pari_max = max(0, imp.pari_min - 1), min(6, imp.pari_max + 1)
    elif nome == "alti/bassi":
        imp.alti_min, imp.alti_max = max(0, imp.alti_min - 1), min(6, imp.alti_max + 1)
    elif nome == "consecutivi":
        imp.consecutivi_max = min(5, imp.consecutivi_max + 1)
    elif nome == "somma":
        imp.somma_percentile = max(0, imp.somma_percentile - 5)
    elif nome == "decine":
        imp.max_stessa_decina = min(6, imp.max_stessa_decina + 1)
    return prima != (imp.pari_min, imp.pari_max, imp.alti_min, imp.alti_max, imp.consecutivi_max,
                     imp.somma_percentile, imp.max_stessa_decina)


# ------------------------------------------------------------ registro
def leggi_registro(archivio) -> list[dict]:
    try:
        return json.loads(archivio.leggi_impostazione(CHIAVE_REGISTRO, "[]") or "[]")
    except ValueError:
        return []


def _salva_registro(archivio, voci: list[dict]) -> None:
    archivio.scrivi_impostazione(CHIAVE_REGISTRO, json.dumps(voci[-400:]))


def elabora_nuove(archivio) -> list[Valutazione]:
    """Da chiamare dopo ogni aggiornamento dell'archivio: valuta le estrazioni nuove (dalla data di
    attivazione in poi), confronta le previsioni salvate e, se attivo, corregge i pesi."""
    storico = archivio.sestine()
    if len(storico) < 100:
        return []
    date_st = [r[0] for r in storico]
    fino_a = archivio.leggi_impostazione(CHIAVE_APPRESO)
    if not fino_a:      # prima volta: si parte "da oggi in poi"
        archivio.scrivi_impostazione(CHIAVE_APPRESO, date_st[-1].isoformat())
        return []
    limite = date.fromisoformat(fino_a)
    nuove = [i for i, d in enumerate(date_st) if d > limite]
    if not nuove:
        return []
    imp = personale.applica(archivio, magico.Impostazioni.da_json(archivio.leggi_impostazione(magico.CHIAVE_IMP),
                                                                   archivio.gioco))
    previsioni = magico.leggi_previsioni(archivio)
    registro = leggi_registro(archivio)
    m = magico.matrice(storico)
    risultati = []
    for i in nuove:
        dopo = date_st[i - 1].isoformat()
        prev = [p for p in previsioni if p.get("dopo") == dopo]
        val = valuta(storico[:i], storico[i], imp, prev, m[:i])
        val.pesi_prima = magico.pesi_effettivi(imp)
        if not gia_appreso(imp, storico[i][0]):        # mai contare due volte lo stesso concorso
            val.correzioni = aggiorna(imp, val.prestazioni, val.filtri_superati)
            if imp.apprendimento:
                segna_appreso(imp, storico[i][0])
        val.pesi_dopo = magico.pesi_effettivi(imp)
        for p in prev:
            p["valutata"] = True
        registro.append(asdict(val))
        risultati.append(val)
    archivio.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())
    archivio.scrivi_impostazione(magico.CHIAVE_PREV, json.dumps(previsioni[-500:]))
    archivio.scrivi_impostazione(CHIAVE_APPRESO, date_st[-1].isoformat())
    _salva_registro(archivio, registro)
    return risultati


def allena(storico: Storico, imp: magico.Impostazioni, concorsi: int, avanzamento=None, interrompi=None):
    """Allenamento sul passato: ripete la valutazione concorso per concorso sugli ultimi N (usando ogni
    volta solo i dati precedenti) e accumula le statistiche. Restituisce (impostazioni, correzioni, fatti)."""
    m = magico.matrice(storico)
    n = len(storico)
    inizio = max(100, n - concorsi)
    correzioni: list[str] = []
    fatti = 0
    periodo = (imp.appreso_da, imp.appreso_a)          # concorsi già conteggiati prima di iniziare
    for i in range(inizio, n):
        if interrompi and interrompi():
            break
        if gia_appreso(imp, storico[i][0], periodo):   # già conteggiato in precedenza
            continue
        passato = storico[:i]
        _, voci, _, _ = magico.calcola_punteggi(passato, imp, m[:i])
        estratti = sorted(storico[i][1])
        prest = {k: float(np.mean(_percentili(voci[k], estratti))) for k in magico.VOCI}
        filtri = _forma_ok(estratti, passato, imp)
        for c in aggiorna(imp, prest, filtri):
            correzioni.append(f"{storico[i][0]:%d/%m/%Y}: {c}")
        if imp.apprendimento:
            segna_appreso(imp, storico[i][0])
        fatti += 1
        if avanzamento:
            avanzamento(i - inizio + 1, n - inizio)
    return imp, correzioni, fatti


def stato_voci(imp: magico.Impostazioni) -> list[list]:
    """Tabella: voce, valutazioni, posizione media dei numeri usciti, scarto dal caso, peso base, peso effettivo."""
    eff = magico.pesi_effettivi(imp)
    righe = []
    for k, nome in magico.VOCI.items():
        n, somma = imp.stat_voci.get(k, [0, 0.0])
        media = somma / n if n else 0.5
        z = (media - 0.5) / math.sqrt((1 / 12) / imp.G.k / n) if n else 0.0
        righe.append([nome, n, round(100 * media, 1), round(z, 2), imp.pesi.get(k, 0), eff.get(k, 0)])
    return righe


def riepilogo_per_claude(archivio, ultime: int = 10) -> str:
    reg = leggi_registro(archivio)
    if not reg:
        return "Nessuna valutazione ancora disponibile."
    righe = []
    medie = {k: round(float(np.mean([v["prestazioni"].get(k, 0.5) for v in reg])), 3) for k in magico.VOCI}
    righe.append(f"Valutazioni registrate: {len(reg)}. Posizione media dei numeri usciti per voce "
                 f"(0.5 = come il caso): " + ", ".join(f"{magico.VOCI[k]} {v}" for k, v in medie.items()))
    falliti = {}
    for v in reg:
        for nome, ok in v.get("filtri_superati", {}).items():
            falliti[nome] = falliti.get(nome, 0) + (0 if ok else 1)
    righe.append(f"Su {len(reg)} estrazioni valutate, quante volte un filtro avrebbe scartato la vincente: " +
                 ", ".join(f"{k}: {n}" for k, n in falliti.items()))
    for v in reg[-ultime:]:
        righe.append(Valutazione(**{k: v[k] for k in Valutazione.__dataclass_fields__ if k in v}).testo())
    return "\n".join(righe)
