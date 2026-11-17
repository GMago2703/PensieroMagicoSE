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

from pmse.core import apprendimento, claude_ai, internet, magico, personalizzate
from pmse.core.db import Archivio, EsitoUnione
from pmse.core.gioco import EJ, GIOCHI, SE, Gioco

FORNITORI = {"gemini": "Gemini (Google)", "claude": "Claude (Anthropic)"}
CHIAVE_ULTIMO_GIOCO = "ultimo_gioco"


def prepara_certificati() -> None:
    """Su Android Python non trova i certificati di sistema: usa quelli di certifi per HTTPS."""
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
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

    # ---------------------------------------------------------------- archivio
    def conta(self) -> int:
        return self.arch.conta()

    def ultima(self):
        return self.arch.ultima()

    def elenco(self, crescente: bool = False):
        return self.arch.tutte(crescente)

    def aggiorna(self, avanzamento=None, interrompi=None) -> EsitoAggiornamento:
        """Scarica da Internet gli anni mancanti, unisce senza doppioni e fa imparare Magico Pensiero."""
        ultima = self.arch.ultima()
        anni = internet.anni_da_aggiornare(ultima.data if ultima else None, self.g)
        estrazioni = internet.scarica_anni(anni, avanzamento, interrompi, gioco=self.g)
        esito = EsitoAggiornamento(self.arch.unisci(estrazioni))
        self.arch.scrivi_impostazione("ultimo_aggiornamento", date.today().isoformat())
        if esito.unione.nuove:
            try:
                esito.valutazioni = apprendimento.elabora_nuove(self.arch)
            except Exception as ex:       # l'apprendimento non deve mai bloccare l'app
                esito.errore_apprendimento = str(ex)
        return esito

    # ---------------------------------------------------------- Magico Pensiero
    def impostazioni(self) -> magico.Impostazioni:
        return magico.Impostazioni.da_json(self.arch.leggi_impostazione(magico.CHIAVE_IMP), self.g)

    def _extra(self, imp, storico):
        extra = {}
        for r in personalizzate.carica(self.arch):
            if imp.personalizzate.get(r.nome):
                extra[r.nome] = personalizzate.esegui(r, storico).punteggi
        return extra

    def genera(self, salva: bool = True) -> magico.RisultatoMagico:
        storico = self.arch.sestine()
        imp = self.impostazioni()
        r = magico.genera(storico, imp, self._extra(imp, storico))
        if salva:
            magico.salva_previsione(self.arch, r)
        return r

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
        base = magico.genera(storico, imp, self._extra(imp, storico))
        gia_uscite = {tuple(x[1]) for x in storico}
        m = magico.matrice(storico)
        dossier = claude_ai.costruisci_dossier(storico, base,
                                               self.arch.leggi_impostazione(claude_ai.CHIAVE_VERIFICA),
                                               lezioni=apprendimento.riepilogo_per_claude(self.arch), imp=imp)
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
