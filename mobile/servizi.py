"""Pensiero Magico per Android – logica dell'app (nessuna grafica).

Riusa senza modifiche il nucleo della versione Windows (pmse/core): stesso archivio, stesso
algoritmo Magico Pensiero, stessa verifica storica, stesso apprendimento, stessa AI.

SuperEnalotto ed Eurojackpot restano rigidamente separati: ogni gioco ha la sua cartella e il
suo archivio (con dentro impostazioni, previsioni, apprendimento e chiavi AI). Un Servizio apre
un solo gioco alla volta.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from pmse.core import apprendimento, claude_ai, internet, laboratorio, magico, personale, personalizzate, popolarita, vincite
from pmse.core.db import Archivio, EsitoUnione
from pmse.core.gioco import EJ, GIOCHI, SE, Gioco

FORNITORI = {"gemini": "Gemini (Google)", "claude": "Claude (Anthropic)"}
CHIAVE_ULTIMO_GIOCO = "ultimo_gioco"


def prepara_certificati() -> None:
    """Su Android Python non trova i certificati di sistema: usa quelli di certifi per HTTPS."""
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass


def ultimo_gioco(cartella: str | Path) -> Gioco:
    try:
        return GIOCHI.get((Path(cartella) / CHIAVE_ULTIMO_GIOCO).read_text().strip(), SE)
    except OSError:
        return SE


def ricorda_gioco(cartella: str | Path, g: Gioco) -> None:
    try:
        Path(cartella).mkdir(parents=True, exist_ok=True)
        (Path(cartella) / CHIAVE_ULTIMO_GIOCO).write_text(g.codice)
    except OSError:
        pass


@dataclass
class EsitoAggiornamento:
    unione: EsitoUnione
    valutazioni: list = field(default_factory=list)      # apprendimento sulle estrazioni nuove
    errore_apprendimento: str = ""

    def testo(self) -> str:
        t = self.unione.riepilogo()
        if self.valutazioni:
            t += "\n\nConfronto delle previsioni con le estrazioni nuove:\n\n" + \
                 "\n\n".join(v.testo() for v in self.valutazioni)
        if self.errore_apprendimento:
            t += f"\n\nAnalisi delle previsioni non riuscita: {self.errore_apprendimento}"
        return t


class Servizio:
    def __init__(self, cartella_base: str | Path, gioco: Gioco):
        self.g = gioco
        cartella = Path(cartella_base) / gioco.cartella        # PensieroMagicoSE / PensieroMagicoEJ
        cartella.mkdir(parents=True, exist_ok=True)
        self.percorso = cartella / "archivio.db"
        self.arch = Archivio(self.percorso, gioco=gioco)

    def chiudi(self) -> None:
        self.arch.chiudi()

    # ---------------------------------------------------------------- condizioni e sistemi condizionati
    def contesto(self):
        """Archivio pronto per le condizioni (calcolato una volta, rifatto dopo un aggiornamento)."""
        if getattr(self, "_ctx", None) is None or self._ctx_n != self.arch.conta():
            from pmse.core import sistemi as sis
            self._ctx = sis.contesto_da_archivio(self.arch)
            self._ctx_n = self.arch.conta()
        return self._ctx

    def tipi_condizioni(self):
        from pmse.core import condizioni as cnd
        ctx = self.contesto() if self.arch.conta() else None
        return [t for t in cnd.tipi_del_gioco(self.g)
                if not (t.codice == "popolarita" and (ctx is None or ctx.popolarita is None))]

    def analizza(self, codice: str, param: int):
        from pmse.core import condizioni as cnd
        return cnd.analizza(codice, self.contesto(), param)

    def analizza_gruppo(self, numeri):
        from pmse.core import condizioni as cnd
        return cnd.analizza_gruppo(numeri, self.contesto())

    def sviluppa_condizionato(self, numeri, fisse, condizioni, errori_max: int, garanzia: int):
        """Sistema condizionato (garanzia 0) o condizionato ridotto (garanzia n-j)."""
        from pmse.core import condizioni as cnd
        from pmse.core import sistemi as sis
        numeri, fisse = sorted(set(numeri)), sorted(set(fisse))
        if len(numeri) > MAX_NUMERI_CONDIZIONATO:
            raise ValueError(f"Sul telefono il condizionato arriva a {MAX_NUMERI_CONDIZIONATO} numeri.")
        s = sis.Sistema(nome="", tipo="condizionato_ridotto" if garanzia else "condizionato", gioco=self.g.codice,
                        numeri=numeri, fisse=fisse, condizioni=cnd.a_json(condizioni), errori_min=0,
                        errori_max=errori_max, garanzia=garanzia, qualita=8)
        if garanzia:
            prova = sis.Sistema.da_json(s.a_json())
            prova.tipo, prova.garanzia = "condizionato", 0
            n = len(sis.sviluppa(prova, self.contesto()).colonne)
            if n > MAX_RIDUZIONE_TELEFONO:
                raise ValueError(f"Le condizioni lasciano {n:,} colonne: troppe da ridurre sul telefono (massimo "
                                 f"{MAX_RIDUZIONE_TELEFONO:,}). Aggiungi condizioni o togli numeri."
                                 .replace(",", "."))
        sv = sis.sviluppa(s, self.contesto())
        s.colonne = sv.colonne.tolist()
        s.info = {"integrale": sv.integrale, "possibili": sv.possibili}
        return s

    # ---------------------------------------------------------------- archivio
    def conta(self) -> int:
        return self.arch.conta()

    def ultima(self):
        return self.arch.ultima()

    def elenco(self, crescente: bool = False):
        return self.arch.tutte(crescente)

    def date_con_6(self) -> set:
        return vincite.date_con_6(self.arch) if self.g.codice == "SE" else set()

    def aggiorna(self, avanzamento=None, interrompi=None) -> EsitoAggiornamento:
        """Scarica da Internet gli anni mancanti, unisce senza doppioni e fa imparare Magico Pensiero."""
        ultima = self.arch.ultima()
        anni = internet.anni_da_aggiornare(ultima.data if ultima else None, self.g)
        estrazioni = internet.scarica_anni(anni, avanzamento, interrompi, gioco=self.g)
        esito = EsitoAggiornamento(self.arch.unisci(estrazioni))
        self.arch.scrivi_impostazione("ultimo_aggiornamento", date.today().isoformat())
        if self.g.codice == "SE":                      # vincitori dei concorsi nuovi (per evidenziare i 6)
            try:
                da_fare = vincite.mancanti(self.arch)
                if len(da_fare) <= 300:
                    vincite.salva(self.arch, vincite.scarica(da_fare, interrompi=interrompi))
            except Exception:
                pass
        if esito.unione.nuove:
            try:
                esito.valutazioni = apprendimento.elabora_nuove(self.arch)
            except Exception as ex:       # l'apprendimento non deve mai bloccare l'app
                esito.errore_apprendimento = str(ex)
        return esito

    # ---------------------------------------------------------- Magico Pensiero
    def impostazioni(self) -> magico.Impostazioni:
        return personale.applica(self.arch, magico.Impostazioni.da_json(
            self.arch.leggi_impostazione(magico.CHIAVE_IMP), self.g))

    def _extra(self, imp, storico):
        extra = {}
        for r in personalizzate.carica(self.arch):
            if imp.personalizzate.get(r.nome):
                extra[r.nome] = personalizzate.esegui(r, storico).punteggi
        return extra

    def genera(self, salva: bool = True) -> magico.RisultatoMagico:
        storico = self.arch.sestine()
        imp = self.impostazioni()
        r = magico.genera(storico, imp, self._extra(imp, storico), popolarita=popolarita.per_archivio(self.arch))
        if salva:
            magico.salva_previsione(self.arch, r)
        return r

    def poco_giocate(self) -> bool:
        return self.impostazioni().evita_popolari

    def imposta_poco_giocate(self, attivo: bool) -> None:
        imp = self.impostazioni()
        imp.evita_popolari = bool(attivo)
        self.arch.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())

    def livello_poco_giocate(self) -> str:
        """'no' oppure 'bassa' / 'moderata' / 'forte' (quanto scartare le combinazioni molto giocate)."""
        imp = self.impostazioni()
        if not imp.evita_popolari:
            return "no"
        return min(personale.POPOLARI, key=lambda k: abs(personale.POPOLARI[k] - imp.soglia_popolari))

    def imposta_livello_poco_giocate(self, livello: str) -> None:
        imp = self.impostazioni()
        imp.evita_popolari = livello != "no"
        if livello in personale.POPOLARI:
            imp.soglia_popolari = personale.POPOLARI[livello]
        self.arch.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())

    def variazione(self) -> str:
        return self.impostazioni().variazione

    def imposta_variazione(self, livello: str) -> None:
        imp = self.impostazioni()
        imp.variazione = livello
        self.arch.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())

    def codice_personale(self) -> str:
        return personale.mostra(personale.codice(self.arch))

    def rigenera_codice(self) -> str:
        return personale.mostra(personale.rigenera(self.arch))

    def previsioni_attuali(self) -> list[dict]:
        """Le previsioni già fatte per il prossimo concorso (algoritmo e/o AI), la più recente per prima."""
        ultima = self.arch.ultima()
        if not ultima:
            return []
        dopo = ultima.data.isoformat()
        return [p for p in reversed(magico.leggi_previsioni(self.arch)) if p.get("dopo") == dopo]

    # ---------------------------------------------------------- verifica storica
    def verifica(self, concorsi: int, apprendi: bool = False, avanzamento=None, interrompi=None):
        """Restituisce (EsitoVerifica, testo dell'apprendimento o '')."""
        storico = self.arch.sestine()
        if len(storico) < 130:
            raise ValueError("Servono almeno 130 estrazioni in archivio: aggiorna prima da Internet.")
        imp = self.impostazioni()
        es = magico.verifica_storica(storico, concorsi, imp, avanzamento, interrompi)
        nota = ""
        if es.prove:     # l'esito, con il dettaglio dei concorsi, viene passato all'AI
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_VERIFICA, magico.dettaglio_per_ai(es))
        if apprendi and es.prove and not (interrompi and interrompi()):
            imp, correzioni, fatti = apprendimento.allena(storico, imp, concorsi, interrompi=interrompi)
            self.arch.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())
            if fatti:
                nota = f"Apprendimento: {fatti} concorsi nuovi studiati."
                if correzioni:
                    nota += "\n" + "\n".join(correzioni[-15:])
                else:
                    nota += " Nessuna correzione necessaria."
            else:
                nota = "Apprendimento: questi concorsi erano già stati studiati, nulla da aggiungere."
        return es, nota

    # ---------------------------------------------------------- laboratorio
    def laboratorio(self, simulazioni: int = 100, avanzamento=None, interrompi=None) -> "laboratorio.Rapporto":
        r = laboratorio.esegui(self.arch.tutte(True), self.g, simulazioni, avanzamento, interrompi)
        self.arch.scrivi_impostazione(laboratorio.CHIAVE_LAB, laboratorio.riassunto_per_ai(r))
        self.arch.scrivi_impostazione(laboratorio.CHIAVE_LAB + "_testo", r.testo())
        return r

    def ultimo_laboratorio(self) -> str:
        return self.arch.leggi_impostazione(laboratorio.CHIAVE_LAB + "_testo", "") or ""

    # ---------------------------------------------------- intelligenza artificiale
    def fornitore(self) -> str:
        return self.arch.leggi_impostazione(claude_ai.CHIAVE_FORNITORE, "gemini") or "gemini"

    def modelli(self, fornitore: str) -> list[tuple[str, str]]:
        return claude_ai.MODELLI_GEMINI if fornitore == "gemini" else claude_ai.MODELLI

    def chiave(self, fornitore: str) -> str:
        k = claude_ai.CHIAVE_GEMINI if fornitore == "gemini" else claude_ai.CHIAVE_API
        return self.arch.leggi_impostazione(k, "") or ""

    def modello(self, fornitore: str) -> str:
        k = claude_ai.CHIAVE_MODELLO_GEMINI if fornitore == "gemini" else claude_ai.CHIAVE_MODELLO
        return self.arch.leggi_impostazione(k, "") or self.modelli(fornitore)[0][0]

    def salva_ai(self, fornitore: str, chiave: str, modello: str) -> None:
        """La chiave resta solo sul telefono, nell'archivio di questo gioco."""
        self.arch.scrivi_impostazione(claude_ai.CHIAVE_FORNITORE, fornitore)
        if fornitore == "gemini":
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_GEMINI, chiave.strip())
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_MODELLO_GEMINI, modello)
        else:
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_API, chiave.strip())
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_MODELLO, modello)

    def prova_chiave(self, fornitore: str, chiave: str, modello: str) -> str:
        if fornitore == "gemini":
            return claude_ai.prova_chiave_gemini(chiave.strip(), modello)
        return claude_ai.prova_chiave(chiave.strip(), modello,
                                      self.arch.leggi_impostazione(claude_ai.CHIAVE_WORKSPACE, "") or "")

    def chiedi_ai(self, fornitore: str, chiave: str, modello: str):
        """Prepara il dossier come la versione Windows e chiede la scelta all'AI.
        Restituisce (RispostaClaude, risultato di partenza dell'algoritmo)."""
        storico = self.arch.sestine()
        if len(storico) < 100:
            raise ValueError("Servono almeno 100 estrazioni in archivio.")
        imp = self.impostazioni()
        base = magico.genera(storico, imp, self._extra(imp, storico), popolarita=popolarita.per_archivio(self.arch))
        gia_uscite = {tuple(x[1]) for x in storico}
        m = magico.matrice(storico)
        dossier = claude_ai.costruisci_dossier(storico, base,
                                               self.arch.leggi_impostazione(claude_ai.CHIAVE_VERIFICA),
                                               lezioni=apprendimento.riepilogo_per_claude(self.arch), imp=imp,
                                               laboratorio=self.arch.leggi_impostazione(laboratorio.CHIAVE_LAB))
        if fornitore == "gemini":
            rc = claude_ai.chiedi_a_gemini(chiave.strip(), modello, dossier, gia_uscite, m,
                                           base.limiti_archivio, g=self.g)
        else:
            rc = claude_ai.chiedi_a_claude(chiave.strip(), modello, dossier, gia_uscite, m, base.limiti_archivio,
                                           workspace=self.arch.leggi_impostazione(claude_ai.CHIAVE_WORKSPACE, "")
                                           or "", g=self.g)
        return rc, base

    def applica_ai(self, rc, base, fornitore: str) -> magico.RisultatoMagico:
        r = claude_ai.come_risultato(rc, base)
        nome = "Gemini" if fornitore == "gemini" else "Claude"
        magico.salva_previsione(self.arch, r, origine=f"{nome} ({rc.modello})")
        return r


def descrivi_risposta(rc, base, g: Gioco) -> str:
    """Testo semplice della risposta dell'AI (per lo schermo del telefono)."""
    r = []
    comuni = rc.in_comune_archivio or [None] * len(rc.sestine)
    for i, (s, mot, k) in enumerate(zip(rc.sestine, rc.motivazioni + [""] * 3, comuni), 1):
        extra = f"  (max {k} in comune con l'archivio)" if k is not None else ""
        r.append(f"{g.C()} {i}: {' '.join(map(str, s))}{extra}\n{mot}".strip())
    spec = f"Euronumeri {rc.jolly} e {rc.superstar}" if g.is_ej else f"Jolly {rc.jolly} e SuperStar {rc.superstar}"
    r.append(f"{spec}\n{rc.jolly_superstar}".strip())
    for titolo, testo in (("Analisi", rc.analisi), ("Scartati", rc.scartati), ("Affidabilità", rc.affidabilita)):
        if testo:
            r.append(f"{titolo}\n{testo}")
    if rc.avvisi:
        r.append("Attenzione: " + " ".join(rc.avvisi))
    if rc.corretta:
        r.append("La prima risposta non rispettava tutte le regole: l'app ha chiesto di correggerla.")
    lo, hi = base.limiti_archivio
    r.append(f"Limite di somiglianza con l'archivio: da {lo} a {hi} numeri in comune.")
    r.append(f"Modello {rc.modello} – token inviati {rc.token_ingresso}, ricevuti {rc.token_uscita}")
    return "\n\n".join(r)


__all__ = ["Servizio", "EsitoAggiornamento", "FORNITORI", "SE", "EJ", "GIOCHI", "prepara_certificati",
           "ultimo_gioco", "ricorda_gioco", "descrivi_risposta"]


# ------------------------------------------------------------------ sistemi ridotti (versione Android)
MAX_NUMERI_RIDOTTO = 25          # sul telefono: integrali ridotti fino a 25 numeri (177.100 colonne per il SE)
MAX_NUMERI_CONDIZIONATO = 35     # condizionati fino a 35 numeri (1.623.160 colonne da filtrare per il SE)
MAX_RIDUZIONE_TELEFONO = 200_000 # colonne rimaste dopo le condizioni che il telefono riduce ancora bene


def combinazioni_casuali(g: Gioco, quante: int) -> list[list[int]]:
    """Combinazioni casuali (generatore del sistema operativo); per l'Eurojackpot solo i 5 numeri."""
    import random
    caso = random.SystemRandom()
    return [sorted(caso.sample(range(1, g.n + 1), g.k)) for _ in range(quante)]


def numeri_casuali(g: Gioco, quanti: int) -> list[int]:
    import random
    return random.SystemRandom().sample(range(1, g.n + 1), quanti)


def ridotti_disponibili(g: Gioco, numeri: int, fisse: int) -> list[tuple[int, int]]:
    """Riduzioni già pronte per quanti numeri e fisse: [(punti garantiti, colonne)], la garanzia più alta prima."""
    from pmse.core import ridotti_pronti
    out = [(p, c) for n, f, p, c in ridotti_pronti.disponibili(g.k) if n == numeri and f == fisse]
    return sorted(out, reverse=True)


def sviluppa_ridotto(g: Gioco, numeri, fisse, garanzia: int, immediato: bool, avanzamento=None):
    """Sviluppa un ridotto immediato (riduzione pronta) o un integrale ridotto a garanzia (n-garanzia).
    Restituisce il Sistema con le colonne."""
    from pmse.core import sistemi as sis
    numeri, fisse = sorted(set(numeri)), sorted(set(fisse))
    if not immediato and len(numeri) > MAX_NUMERI_RIDOTTO:
        raise ValueError(f"Sul telefono il ridotto a garanzia arriva a {MAX_NUMERI_RIDOTTO} numeri.")
    s = sis.Sistema(nome="", tipo="immediato" if immediato else "ridotto", gioco=g.codice, numeri=numeri,
                    fisse=fisse, garanzia=garanzia, qualita=10)
    sv = sis.sviluppa(s, avanzamento=avanzamento)
    s.colonne = sv.colonne.tolist()
    s.info = {"integrale": sv.integrale, "possibili": sv.possibili}
    return s


def tabulato(s) -> str:
    from pmse.core import sistemi as sis
    return sis.tabulato(s, s.colonne, per_riga=2)


def documento(s, formato: str) -> tuple[str, bytes]:
    """(nome del file, contenuto) del tabulato in PDF o TXT."""
    from datetime import datetime

    from pmse.core import pdf
    g = s.G
    from pmse.core import sistemi as sis
    testo = sis.tabulato(s, s.colonne)
    nome = f"PensieroMagico{g.codice}_sistema_{len(s.numeri)}numeri_{datetime.now():%Y%m%d_%H%M%S}"
    if formato == "pdf":
        return nome + ".pdf", pdf.crea(f"Sistema {len(s.numeri)} numeri – {g.nome}", testo)
    return nome + ".txt", testo.encode("utf-8")
