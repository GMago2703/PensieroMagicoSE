"""Pensiero Magico – app Android (versione ridotta).

Funzioni: archivio con aggiornamento da Internet, Magico Pensiero, verifica storica (con
apprendimento) e scelta con l'intelligenza artificiale (Gemini o Claude).
SuperEnalotto ed Eurojackpot sono rigidamente separati: si sceglie il gioco in alto e ognuno
ha il suo archivio, le sue previsioni, il suo apprendimento e le sue chiavi.
"""
from __future__ import annotations

import os
import threading
import traceback

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.utils import get_color_from_hex as hexc

import servizi
from pmse import __version__
from pmse.core.gioco import EJ, SE

# colori Sisal (come la versione Windows)
VERDE_SCURO, VERDE, LIME, ARANCIO, ARDESIA = "#00653B", "#0B7D3E", "#BED62F", "#FF8E0D", "#2F3C43"
COLORI_COMB = ["#e53935", "#43a047", "#8e24aa"]
COLORE_JOLLY, COLORE_SUPERSTAR, COLORE_EURO = "#fb8c00", "#d4a017", "#1565c0"
EVIDENZIA = "c62828"


def colore_gioco(g) -> str:
    return ARDESIA if g.is_ej else VERDE_SCURO


def sfondo(widget, colore: str, raggio: float = 0):
    """Disegna uno sfondo pieno (anche arrotondato) che segue il widget; restituisce il Color."""
    with widget.canvas.before:
        c = Color(*hexc(colore))
        r = RoundedRectangle(radius=[dp(raggio)]) if raggio else Rectangle()

    def segui(*_):
        r.pos, r.size = widget.pos, widget.size
    widget.bind(pos=segui, size=segui)
    return c


def bottone(testo, azione=None, colore=ARANCIO, alto=dp(54), **kw) -> Button:
    b = Button(text=testo, bold=True, font_size=sp(17), size_hint_y=None, height=alto,
               background_normal="", background_down="", background_color=hexc(colore), **kw)
    if azione:
        b.bind(on_release=lambda *_: azione())
    return b


class Testo(Label):
    """Testo che va a capo e si allunga quanto serve (dentro le pagine scorrevoli)."""

    def __init__(self, testo="", colore=(0.12, 0.12, 0.12, 1), **kw):
        kw.setdefault("font_size", sp(15))
        super().__init__(text=testo, color=colore, markup=True, size_hint_y=None, halign="left",
                         valign="top", **kw)
        self.bind(width=lambda *_: setattr(self, "text_size", (self.width, None)),
                  texture_size=lambda *_: setattr(self, "height", self.texture_size[1]))


class Scheda(BoxLayout):
    """Riquadro bianco arrotondato."""

    def __init__(self, **kw):
        kw.setdefault("padding", dp(12))
        kw.setdefault("spacing", dp(8))
        super().__init__(orientation="vertical", size_hint_y=None, **kw)
        self.bind(minimum_height=self.setter("height"))
        sfondo(self, "#ffffff", 14)


class Palla(Label):
    def __init__(self, numero, colore, testo_scuro=False, **kw):
        super().__init__(text=str(numero) if numero else "-", bold=True, font_size=sp(17),
                         color=(0, 0, 0, 1) if testo_scuro else (1, 1, 1, 1),
                         size_hint=(None, None), size=(dp(40), dp(40)), **kw)
        with self.canvas.before:
            Color(*hexc(colore))
            self._e = Ellipse()
        self.bind(pos=self._segui, size=self._segui)

    def _segui(self, *_):
        self._e.pos, self._e.size = self.pos, self.size


def riga_palle(titolo, numeri, colore, testo_scuro=False) -> BoxLayout:
    r = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
    r.add_widget(Label(text=titolo, color=(0.15, 0.15, 0.15, 1), bold=True, font_size=sp(14),
                       size_hint_x=None, width=dp(78), halign="left", valign="middle",
                       text_size=(dp(78), dp(46))))
    for n in numeri:
        r.add_widget(Palla(n, colore, testo_scuro))
    r.add_widget(Label())
    return r


def palle_previsione(g, sestine, jolly, superstar) -> list:
    """Righe di palline per una previsione (3 sestine + Jolly/SuperStar, o cinquina + Euronumeri)."""
    righe = [riga_palle(f"{g.C()} {i + 1}" if len(sestine) > 1 else g.C(), s, COLORI_COMB[i % 3])
             for i, s in enumerate(sestine)]
    if g.is_ej:
        righe.append(riga_palle("Euro", [jolly, superstar], COLORE_EURO))
    else:
        r = riga_palle("Jolly", [jolly], COLORE_JOLLY)
        r.add_widget(Label(text="SuperStar", color=(0.15, 0.15, 0.15, 1), bold=True, font_size=sp(14),
                           size_hint_x=None, width=dp(84)), index=1)
        r.add_widget(Palla(superstar, COLORE_SUPERSTAR, True), index=1)
        righe.append(r)
    return righe


def evidenzia(numeri, presi) -> str:
    return " ".join(f"[b][color={EVIDENZIA}]{n}[/color][/b]" if n in presi else str(n) for n in numeri)


def avviso(titolo, testo):
    corpo = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
    sv = ScrollView()
    t = Testo(testo, colore=(1, 1, 1, 1))
    sv.add_widget(t)
    corpo.add_widget(sv)
    p = Popup(title=titolo, content=corpo, size_hint=(0.92, 0.75))
    corpo.add_widget(bottone("OK", p.dismiss, VERDE))
    p.open()
    return p


# ------------------------------------------------------------------ pagine
class Pagina(Screen):
    titolo = ""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.colore = sfondo(self, VERDE_SCURO)
        box = BoxLayout(orientation="vertical")
        if self.name != "home":
            testa = BoxLayout(size_hint_y=None, height=dp(56), padding=(dp(4), dp(4)), spacing=dp(6))
            sfondo(testa, "#00000040")
            testa.add_widget(bottone("<", lambda: app.vai("home"), ARANCIO, alto=dp(48),
                                     size_hint_x=None, width=dp(56)))
            self.l_titolo = Label(text=self.titolo, bold=True, italic=True, font_size=sp(21),
                                  color=hexc(LIME), halign="left", valign="middle")
            self.l_titolo.bind(size=lambda w, s: setattr(w, "text_size", s))
            testa.add_widget(self.l_titolo)
            box.add_widget(testa)
        self.sv = ScrollView(do_scroll_x=False)
        self.corpo = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(12), spacing=dp(10))
        self.corpo.bind(minimum_height=self.corpo.setter("height"))
        self.sv.add_widget(self.corpo)
        box.add_widget(self.sv)
        self.add_widget(box)

    @property
    def s(self) -> servizi.Servizio:
        return self.app.serv

    @property
    def g(self):
        return self.app.serv.g

    def on_pre_enter(self, *_):
        self.colore.rgba = hexc(colore_gioco(self.g))
        if hasattr(self, "l_titolo"):
            self.l_titolo.text = f"{self.titolo} – {self.g.nome}"
        self.mostra()

    def mostra(self):
        pass


class Home(Pagina):
    def __init__(self, app, **kw):
        super().__init__(app, name="home", **kw)

    def mostra(self):
        c = self.corpo
        c.clear_widgets()
        scelta = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(6))
        for g in (SE, EJ):
            b = ToggleButton(text=g.nome, group="gioco", state="down" if g is self.g else "normal",
                             bold=True, font_size=sp(17), background_normal="", background_down="",
                             background_color=hexc(LIME if g is self.g else "#ffffff30"),
                             color=(0, 0, 0, 1) if g is self.g else (1, 1, 1, 1), allow_no_selection=False)
            b.bind(on_release=lambda _b, gg=g: self.app.cambia_gioco(gg))
            scelta.add_widget(b)
        c.add_widget(scelta)
        c.add_widget(Label(text=self.g.nome, bold=True, italic=True, font_size=sp(44),
                           color=hexc(LIME), size_hint_y=None, height=dp(70)))
        c.add_widget(Label(text=f"Pensiero Magico {self.g.codice}", italic=True, font_size=sp(18),
                           color=hexc(ARANCIO), bold=True, size_hint_y=None, height=dp(24)))

        sch = Scheda()
        n, ultima = self.s.conta(), self.s.ultima()
        if ultima:
            sch.add_widget(Testo(f"[b]Archivio:[/b] {n} estrazioni\n[b]Ultima:[/b] "
                                 f"{ultima.data:%d/%m/%Y}" + (f" (concorso {ultima.concorso})"
                                                             if ultima.concorso else "")))
            sch.add_widget(riga_palle("Estratti", sorted(ultima.numeri), VERDE))
            if self.g.is_ej:
                sch.add_widget(riga_palle("Euro", [ultima.jolly, ultima.superstar], COLORE_EURO))
            else:
                r = riga_palle("Jolly", [ultima.jolly], COLORE_JOLLY)
                r.add_widget(Label(text="SuperStar", color=(0.15, 0.15, 0.15, 1), bold=True, font_size=sp(14),
                                   size_hint_x=None, width=dp(84)), index=1)
                r.add_widget(Palla(ultima.superstar, COLORE_SUPERSTAR, True), index=1)
                sch.add_widget(r)
        else:
            sch.add_widget(Testo("[b]Archivio vuoto.[/b]\nTocca [b]Aggiorna da Internet[/b] per scaricare "
                                 f"tutte le estrazioni dal {self.g.prima_estrazione.year} a oggi "
                                 "(serve una connessione, circa un minuto)."))
        c.add_widget(sch)

        c.add_widget(bottone("Aggiorna da Internet", self.app.aggiorna, VERDE))
        c.add_widget(bottone("Magico Pensiero", lambda: self.app.vai("magico"), ARANCIO))
        c.add_widget(bottone("Verifica storica", lambda: self.app.vai("verifica"), ARANCIO))
        c.add_widget(bottone("Intelligenza artificiale", lambda: self.app.vai("ai"), ARANCIO))
        c.add_widget(bottone("Archivio estrazioni", lambda: self.app.vai("archivio"), VERDE))
        c.add_widget(Label(text=f"versione {__version__} – i numeri del lotto sono casuali: gioca con "
                                "moderazione", font_size=sp(11), color=(1, 1, 1, 0.7),
                           size_hint_y=None, height=dp(30)))


class PaginaArchivio(Pagina):
    titolo = "Archivio"

    def __init__(self, app, **kw):
        super().__init__(app, name="archivio", **kw)
        self.crescente = False
        # al posto della pagina scorrevole: una lista veloce anche con migliaia di righe
        box = self.children[0]
        box.remove_widget(self.sv)
        self.b_ordine = bottone("", self._inverti, VERDE, alto=dp(46))
        box.add_widget(self.b_ordine)
        self.lista = RecycleView(viewclass="Label")
        lay = RecycleBoxLayout(default_size=(None, dp(34)), default_size_hint=(1, None), size_hint_y=None,
                               orientation="vertical", padding=(dp(8), 0))
        lay.bind(minimum_height=lay.setter("height"))
        self.lista.add_widget(lay)
        box.add_widget(self.lista)

    def _inverti(self):
        self.crescente = not self.crescente
        self.mostra()

    def mostra(self):
        self.b_ordine.text = ("Ordine: dalla più vecchia" if self.crescente else "Ordine: dalla più recente") + \
                             "  (tocca per invertire)"
        g, righe = self.g, []
        for e in self.s.elenco(self.crescente):
            spec = (f"[color=90caf9]{e.jolly} {e.superstar}[/color]" if g.is_ej else
                    f"[color=ffb74d]J {e.jolly}[/color] [color=fff176]SS {e.superstar or '-'}[/color]")
            righe.append({"text": f"{e.data:%d/%m/%Y}   [b]{'  '.join(f'{n:2d}' for n in e.numeri)}[/b]   {spec}",
                          "markup": True, "font_size": sp(15), "font_name": "RobotoMono-Regular",
                          "halign": "left", "color": (1, 1, 1, 1)})
        if not righe:
            righe = [{"text": "Archivio vuoto: aggiorna da Internet dalla home.", "color": (1, 1, 1, 1)}]
        self.lista.data = righe
        self.lista.scroll_y = 1


class PaginaMagico(Pagina):
    titolo = "Magico Pensiero"

    def __init__(self, app, **kw):
        super().__init__(app, name="magico", **kw)

    def mostra(self):
        c = self.corpo
        c.clear_widgets()
        ultima = self.s.ultima()
        if self.s.conta() < 30:
            c.add_widget(Testo("Servono almeno 30 estrazioni: aggiorna l'archivio da Internet.", (1, 1, 1, 1)))
            return
        c.add_widget(Testo(f"Proposte per il concorso dopo quello del [b]{ultima.data:%d/%m/%Y}[/b].",
                           (1, 1, 1, 1)))
        prev = self.s.previsioni_attuali()
        for p in prev:
            sch = Scheda()
            sch.add_widget(Testo(f"[b]{p.get('origine', 'Algoritmo')}[/b]  –  generata il "
                                 f"{p.get('generata', '')[8:10]}/{p.get('generata', '')[5:7]}"))
            for w in palle_previsione(self.g, p["sestine"], p["jolly"], p["superstar"]):
                sch.add_widget(w)
            c.add_widget(sch)
        if not any(p.get("origine", "Algoritmo") == "Algoritmo" for p in prev):
            c.add_widget(bottone("Genera con Magico Pensiero", self._genera, ARANCIO))
        c.add_widget(bottone("Chiedi all'intelligenza artificiale", lambda: self.app.vai("ai"), VERDE))
        c.add_widget(Testo(
            "Magico Pensiero combina eco, affinità, tendenza, maturità e storico dei numeri, scarta le "
            "combinazioni con forma insolita o troppo simili a quelle già uscite e impara da sola dopo ogni "
            "estrazione (quando aggiorni l'archivio). Per lo stesso concorso la proposta dell'algoritmo è "
            "sempre la stessa.", (1, 1, 1, 0.85), font_size=sp(13)))

    def _genera(self):
        def lavoro():
            self.s.genera()
        self.app.in_background("Magico Pensiero sta elaborando...", lavoro, lambda _: self.mostra())


class PaginaVerifica(Pagina):
    titolo = "Verifica storica"

    def __init__(self, app, **kw):
        super().__init__(app, name="verifica", **kw)
        self.stop = False
        self.risultato = None

    def mostra(self):
        c = self.corpo
        c.clear_widgets()
        sch = Scheda()
        sch.add_widget(Testo("Previsioni su quanto già avvenuto: per ogni concorso passato Magico Pensiero "
                             "usa solo i dati precedenti e si confronta con i numeri usciti e con il caso."))
        self.l_n = Testo("")
        sch.add_widget(self.l_n)
        self.slider = Slider(min=10, max=1000, step=10, value=100, size_hint_y=None, height=dp(44),
                             cursor_size=(dp(30), dp(30)))
        self.slider.bind(value=lambda *_: self._etichetta())
        sch.add_widget(self.slider)
        self._etichetta()
        r = BoxLayout(size_hint_y=None, height=dp(40))
        self.cb = CheckBox(active=True, size_hint_x=None, width=dp(40), color=hexc(VERDE_SCURO))
        r.add_widget(self.cb)
        r.add_widget(Testo("Impara dai risultati (corregge l'algoritmo)"))
        sch.add_widget(r)
        c.add_widget(sch)
        self.b_avvia = bottone("Avvia la verifica", self._avvia, ARANCIO)
        c.add_widget(self.b_avvia)
        self.barra = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(18), opacity=0)
        c.add_widget(self.barra)
        self.l_stato = Testo("", (1, 1, 1, 1))
        c.add_widget(self.l_stato)
        self.esito = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.esito.bind(minimum_height=self.esito.setter("height"))
        c.add_widget(self.esito)
        if self.risultato and self.risultato[0] is self.g:
            self._mostra_esito(*self.risultato[1:])

    def _etichetta(self):
        self.l_n.text = f"Concorsi da verificare: [b]{int(self.slider.value)}[/b]  (10 – 1000)"

    def _avvia(self):
        if self.app.occupato:
            self.stop = True
            self.b_avvia.text = "Interruzione..."
            return
        self.stop = False
        n, impara, g = int(self.slider.value), self.cb.active, self.g
        self.b_avvia.text = "Ferma"
        self.barra.opacity, self.barra.value = 1, 0
        self.l_stato.text = "Verifica in corso... (con 1000 concorsi può volerci qualche minuto)"

        @mainthread
        def avanza(i, tot):
            self.barra.max, self.barra.value = tot, i
            self.l_stato.text = f"Concorso {i} di {tot}"

        def lavoro():
            return self.s.verifica(n, impara, avanza, lambda: self.stop)

        def fatto(ris):
            es, nota = ris
            self.risultato = (g, es, nota)
            self.b_avvia.text = "Avvia la verifica"
            self.barra.opacity = 0
            self.l_stato.text = "Interrotta: risultato parziale." if self.stop else ""
            self._mostra_esito(es, nota)

        def errore(_msg):
            self.b_avvia.text = "Avvia la verifica"
            self.barra.opacity = 0
        self.app.in_background(None, lavoro, fatto, errore)

    def _mostra_esito(self, es, nota):
        self.esito.clear_widgets()
        sch = Scheda()
        sch.add_widget(Testo(es.testo().replace("[", "(").replace("]", ")"), font_size=sp(13),
                             font_name="RobotoMono-Regular"))
        if nota:
            sch.add_widget(Testo(f"[b]{nota}[/b]", font_size=sp(13)))
        self.esito.add_widget(sch)
        g = self.g
        det = Scheda()
        det.add_widget(Testo(f"[b]Ultimi concorsi[/b] (in [color={EVIDENZIA}][b]rosso[/b][/color] i numeri "
                             "indovinati)"))
        for d, combs, estratti, punti, prev_sp, estr_sp in list(reversed(es.dettagli))[:40]:
            presi = set(estratti)
            righe = [f"[b]{d:%d/%m/%Y}[/b]  estratti: {' '.join(map(str, estratti))}"]
            for i, (s, p) in enumerate(zip(combs, punti), 1):
                righe.append(f"  {g.C()} {i}: {evidenzia(s, presi)}  → [b]{p}[/b]")
            if g.is_ej:
                righe.append(f"  Euro: {evidenzia(list(prev_sp), set(estr_sp))}  (usciti {estr_sp[0]} {estr_sp[1]})")
            else:
                righe.append(f"  Jolly {evidenzia([prev_sp[0]], presi)}  SuperStar "
                             f"{evidenzia([prev_sp[1]], {estr_sp[1]}) if prev_sp[1] else '-'}  "
                             f"(SuperStar uscito {estr_sp[1] or '-'})")
            det.add_widget(Testo("\n".join(righe), font_size=sp(13)))
        self.esito.add_widget(det)


class PaginaAI(Pagina):
    titolo = "Intelligenza artificiale"

    def __init__(self, app, **kw):
        super().__init__(app, name="ai", **kw)
        self.risposta = None

    def mostra(self):
        c = self.corpo
        c.clear_widgets()
        s = self.s
        self.fornitore = s.fornitore()
        sch = Scheda()
        sch.add_widget(Testo("[b]Servizio[/b]"))
        self.sp_forn = Spinner(text=servizi.FORNITORI[self.fornitore], values=list(servizi.FORNITORI.values()),
                               size_hint_y=None, height=dp(46), font_size=sp(16))
        self.sp_forn.bind(text=lambda *_: self._cambia_fornitore())
        sch.add_widget(self.sp_forn)
        sch.add_widget(Testo("[b]Chiave API[/b] (resta solo su questo telefono)"))
        self.e_chiave = TextInput(password=True, multiline=False, size_hint_y=None, height=dp(46),
                                  font_size=sp(15), write_tab=False)
        sch.add_widget(self.e_chiave)
        sch.add_widget(Testo("[b]Modello[/b]"))
        self.sp_mod = Spinner(size_hint_y=None, height=dp(46), font_size=sp(13))
        sch.add_widget(self.sp_mod)
        self._carica_fornitore()
        r = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        r.add_widget(bottone("Prova chiave", self._prova, VERDE, alto=dp(50)))
        r.add_widget(bottone("Chiedi all'AI", self._chiedi, ARANCIO, alto=dp(50)))
        sch.add_widget(r)
        c.add_widget(sch)
        self.esito = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.esito.bind(minimum_height=self.esito.setter("height"))
        c.add_widget(self.esito)
        if self.risposta and self.risposta[0] is self.g:
            self._mostra_risposta(*self.risposta[1:])
        else:
            self.risposta = None
            c.add_widget(Testo("L'AI riceve i dati dell'archivio, la proposta di Magico Pensiero, l'esito "
                               "dell'ultima verifica storica e quanto l'algoritmo ha imparato, poi sceglie "
                               f"{'la cinquina e gli Euronumeri' if self.g.is_ej else 'le 3 sestine, Jolly e SuperStar'}"
                               " rispettando le stesse regole. La chiave di Gemini si crea gratis su "
                               "aistudio.google.com (anche con un account Google diverso).",
                               (1, 1, 1, 0.85), font_size=sp(13)))

    def _codice_fornitore(self):
        return next(k for k, v in servizi.FORNITORI.items() if v == self.sp_forn.text)

    def _carica_fornitore(self):
        f = self.fornitore
        self.e_chiave.text = self.s.chiave(f)
        self.modelli = self.s.modelli(f)
        self.sp_mod.values = [d for _, d in self.modelli]
        attuale = self.s.modello(f)
        self.sp_mod.text = next((d for m, d in self.modelli if m == attuale), self.modelli[0][1])

    def _cambia_fornitore(self):
        self.fornitore = self._codice_fornitore()
        self._carica_fornitore()

    def _dati(self):
        chiave = self.e_chiave.text.strip()
        modello = next((m for m, d in self.modelli if d == self.sp_mod.text), self.modelli[0][0])
        return self.fornitore, chiave, modello

    def _prova(self):
        f, chiave, modello = self._dati()
        if not chiave:
            avviso("Chiave API", "Inserisci prima la chiave.")
            return
        self.s.salva_ai(f, chiave, modello)
        self.app.in_background("Provo la chiave...", lambda: self.s.prova_chiave(f, chiave, modello),
                               lambda esito: avviso("Prova della chiave", "La chiave funziona.\n\n" + str(esito)))

    def _chiedi(self):
        f, chiave, modello = self._dati()
        if not chiave:
            avviso("Chiave API", "Inserisci prima la chiave.")
            return
        self.s.salva_ai(f, chiave, modello)
        g = self.g
        nome = "Gemini" if f == "gemini" else "Claude"

        def fatto(ris):
            rc, base = ris
            self.risposta = (g, rc, base, f)
            self._mostra_risposta(rc, base, f)
            self.sv.scroll_y = 0.6
        self.app.in_background(f"{nome} sta studiando l'archivio...\n(di solito meno di un minuto)",
                               lambda: self.s.chiedi_ai(f, chiave, modello), fatto)

    def _mostra_risposta(self, rc, base, f, applicata=False):
        self.esito.clear_widgets()
        sch = Scheda()
        nome = "Gemini" if f == "gemini" else "Claude"
        sch.add_widget(Testo(f"[b]La scelta di {nome}[/b]"))
        for w in palle_previsione(self.g, rc.sestine, rc.jolly, rc.superstar):
            sch.add_widget(w)
        self.esito.add_widget(sch)
        if not applicata:
            self.esito.add_widget(bottone("Usa questa scelta (salva tra le previsioni)",
                                          lambda: self._applica(rc, base, f), VERDE))
        sch2 = Scheda()
        sch2.add_widget(Testo(servizi.descrivi_risposta(rc, base, self.g).replace("[", "(").replace("]", ")"),
                              font_size=sp(13)))
        self.esito.add_widget(sch2)

    def _applica(self, rc, base, f):
        self.s.applica_ai(rc, base, f)
        self._mostra_risposta(rc, base, f, applicata=True)
        avviso("Previsione salvata", "La scelta è salvata: la trovi in Magico Pensiero e verrà confrontata "
                                     "con l'estrazione quando aggiornerai l'archivio.")


# ------------------------------------------------------------------ applicazione
class PensieroMagicoApp(App):
    title = "Pensiero Magico"

    def build(self):
        servizi.prepara_certificati()
        Window.softinput_mode = "below_target"
        Window.clearcolor = hexc(VERDE_SCURO)
        self.occupato = False
        self.cartella = os.environ.get("PMSE_DATI") or self.user_data_dir
        self.serv = servizi.Servizio(self.cartella, servizi.ultimo_gioco(self.cartella))
        self.sm = ScreenManager(transition=SlideTransition(duration=0.18))
        self.pagine = {}
        for cls in (Home, PaginaArchivio, PaginaMagico, PaginaVerifica, PaginaAI):
            p = cls(self)
            self.pagine[p.name] = p
            self.sm.add_widget(p)
        Window.bind(on_keyboard=self._tasto)
        return self.sm

    def on_stop(self):
        try:
            self.serv.chiudi()
        except Exception:
            pass

    def _tasto(self, _w, tasto, *_):
        if tasto == 27 and self.sm.current != "home":       # tasto "indietro" di Android
            self.vai("home")
            return True
        return False

    def vai(self, nome):
        self.sm.transition.direction = "right" if nome == "home" else "left"
        if self.sm.current == nome:
            self.pagine[nome].on_pre_enter()
        self.sm.current = nome

    def cambia_gioco(self, g):
        if g is self.serv.g:
            return
        if self.occupato:
            avviso("Attendi", "C'è un lavoro in corso: cambia gioco quando è finito.")
            self.pagine["home"].mostra()
            return
        self.serv.chiudi()
        self.serv = servizi.Servizio(self.cartella, g)
        servizi.ricorda_gioco(self.cartella, g)
        self.pagine["home"].on_pre_enter()

    def in_background(self, messaggio, lavoro, fatto=None, errore=None):
        """Esegue un lavoro lungo senza bloccare lo schermo (un solo lavoro alla volta)."""
        if self.occupato:
            avviso("Attendi", "C'è già un lavoro in corso.")
            return
        self.occupato = True
        attesa = None
        if messaggio:
            corpo = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
            corpo.add_widget(Testo(messaggio, (1, 1, 1, 1)))
            pb = ProgressBar(max=100, size_hint_y=None, height=dp(20))
            corpo.add_widget(pb)
            attesa = Popup(title="Pensiero Magico", content=corpo, size_hint=(0.88, None), height=dp(220),
                           auto_dismiss=False)
            attesa.barra = pb
            attesa.open()
            self._giro = Clock.schedule_interval(lambda dt: setattr(pb, "value", (pb.value + 4) % 100), 0.1)

        @mainthread
        def fine(ok, valore):
            self.occupato = False
            if attesa:
                self._giro.cancel()
                attesa.dismiss()
            if ok:
                if fatto:
                    fatto(valore)
            else:
                if errore:
                    errore(valore)
                avviso("Errore", valore)

        def esegui():
            try:
                fine(True, lavoro())
            except Exception as ex:                    # noqa: BLE001 – mostrato all'utente
                traceback.print_exc()
                fine(False, str(ex) or ex.__class__.__name__)
        threading.Thread(target=esegui, daemon=True).start()
        return attesa

    def aggiorna(self):
        def fatto(esito):
            self.pagine["home"].mostra()
            avviso("Aggiornamento", esito.testo())
        self.in_background(f"Scarico le estrazioni {self.serv.g.nome} da Internet...",
                           lambda: self.serv.aggiorna(), fatto)


if __name__ == "__main__":
    PensieroMagicoApp().run()
