"""Prova automatica dell'app Android su PC (GitHub Actions, schermo virtuale).

Avvia l'app vera con un archivio sintetico (niente rete, AI simulata), percorre tutte le pagine
per entrambi i giochi e salva le schermate in FOTO_DIR. Esce con errore se qualcosa si rompe.
Uso:  xvfb-run python mobile/prova_grafica.py   (dalla cartella principale del progetto)
"""
import os
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path[:0] = [str(QUI), str(QUI.parent)]
os.environ["PMSE_DATI"] = tempfile.mkdtemp()
FOTO = Path(os.environ.get("FOTO_DIR", "foto_android"))
FOTO.mkdir(parents=True, exist_ok=True)

TELEFONO = bool(os.environ.get("PMSE_TELEFONO"))
DENSITA = 2.625 if TELEFONO else 1.0
if TELEFONO:          # come un telefono vero: alta densità e caratteri di sistema ingranditi
    os.environ["KIVY_METRICS_DENSITY"] = str(DENSITA)
    os.environ["KIVY_METRICS_FONTSCALE"] = "1.3"

from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", str(int(400 * DENSITA) // 8 * 8))      # multiplo di 8: catture diritte
Config.set("graphics", "height", str(int(820 * DENSITA) // 8 * 8))
Config.set("kivy", "exit_on_escape", "0")

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.uix.modalview import ModalView  # noqa: E402

import main  # noqa: E402
from pmse.core import claude_ai, internet  # noqa: E402
from pmse.core.gioco import EJ, SE  # noqa: E402
from pmse.core.modello import Estrazione  # noqa: E402


def sintetiche(g, n, seme=5):
    rnd, out, d = random.Random(seme), [], date(2021, 1, 2)
    while len(out) < n:
        if d.weekday() in g.giorni_estrazione:
            nums = rnd.sample(range(1, g.n + 1), g.k)
            if g.is_ej:
                e = rnd.sample(range(1, g.euro_max(d) + 1), 2)
                out.append(Estrazione(d, nums, e[0], e[1], gioco=EJ))
            else:
                resto = [x for x in range(1, 91) if x not in nums]
                out.append(Estrazione(d, nums, rnd.choice(resto), rnd.randint(1, 90)))
        d += timedelta(days=1)
    return out


internet.scarica_anni = lambda anni, avanzamento=None, interrompi=None, gioco=SE: sintetiche(
    gioco, 400 if gioco is SE else 250)


def finta_ai(chiave, modello, dossier, gia_uscite, m, limiti, timeout=300, g=SE):
    if g.is_ej:
        return claude_ai.RispostaClaude([[4, 17, 22, 35, 48]], 3, 9, ["Equilibrio tra ritardatari e frequenti."],
                                        "Euronumeri con buona tendenza.", "Analisi di prova.", "",
                                        "Bassa: il gioco è casuale.", modello)
    return claude_ai.RispostaClaude([[3, 18, 27, 44, 61, 85], [7, 21, 33, 50, 68, 79], [12, 26, 39, 55, 72, 88]],
                                    44, 17, ["Prima motivazione.", "Seconda.", "Terza."], "Jolly e SuperStar.",
                                    "Analisi di prova.", "Scartati 90 e 1.", "Bassa.", modello)


claude_ai.chiedi_a_gemini = finta_ai
ERRORI = []
_avviso = main.avviso


def avviso_registrato(titolo, testo):
    if titolo == "Errore":
        ERRORI.append(testo)
    return _avviso(titolo, testo)


main.avviso = avviso_registrato


class Prova(main.PensieroMagicoApp):
    def on_start(self):
        self.passi = self.copione()
        Clock.schedule_interval(self.avanti, 0.4)

    def avanti(self, _dt):
        if self.occupato:
            return
        try:
            next(self.passi)
        except StopIteration:
            self.stop()
            return False

    def chiudi_popup(self):
        for w in list(Window.children):
            if isinstance(w, ModalView):
                w.dismiss(animation=False)

    def foto(self, nome):
        Window.screenshot(name=str(FOTO / f"{nome}.png"))
        self.controlla(nome)

    def controlla(self, nome):
        """Nessuna scritta deve uscire dal suo spazio; nessun testo può essere troppo alto da disegnare
        (oltre circa 4000 pixel il telefono lo mostra nero)."""
        from kivy.uix.label import Label
        for radice in list(Window.children):
            for w in radice.walk(restrict=True):
                if not isinstance(w, Label) or not w.text or w.width <= 1:
                    continue
                if w.texture_size[1] > 4000:
                    ERRORI.append(f"{nome}: testo troppo alto ({w.texture_size[1]} px): {w.text[:40]!r}")
                if w.text_size[0] is None and w.texture_size[0] > w.width + 2:
                    ERRORI.append(f"{nome}: scritta fuori dallo spazio ({w.texture_size[0]:.0f} > "
                                  f"{w.width:.0f}): {w.text[:40]!r}")

    def copione(self):
        yield
        assert self.serv.g is SE
        self.foto("a01_home_vuota_se")
        yield
        self.aggiorna()
        yield
        yield
        self.foto("a02_aggiornamento_se")
        self.chiudi_popup()
        assert self.serv.conta() == 400, self.serv.conta()
        yield
        self.foto("a03_home_se")
        self.vai("archivio")
        yield
        yield
        self.foto("a04_archivio_se")
        self.pagine["archivio"]._altre()
        self.pagine["archivio"]._inverti()
        yield
        self.foto("a04b_archivio_crescente_se")
        self.vai("magico")
        yield
        yield
        self.pagine["magico"]._genera()
        yield
        yield
        self.foto("a05_magico_se")
        self.vai("verifica")
        yield
        yield
        v = self.pagine["verifica"]
        v.slider.value = 40
        v._avvia()
        yield
        yield
        assert v.risultato and v.risultato[1].prove == 40
        self.foto("a06_verifica_se")
        v.sv.scroll_y = 0.45
        yield
        self.foto("a07_verifica_dettaglio_se")
        self.vai("laboratorio")
        yield
        yield
        lab = self.pagine["laboratorio"]
        lab._avvia()
        yield
        yield
        assert "VERDETTO" in self.serv.ultimo_laboratorio()
        lab.sv.scroll_y = 0.5
        yield
        self.foto("a075_laboratorio_se")
        self.vai("ai")
        yield
        yield
        a = self.pagine["ai"]
        a.e_chiave.text = "chiave-di-prova"
        a._chiedi()
        yield
        yield
        assert a.risposta
        a.sv.scroll_y = 1
        yield
        self.foto("a08_ai_se")
        a._applica(*a.risposta[1:])
        yield
        self.chiudi_popup()
        self.vai("magico")
        yield
        yield
        self.foto("a09_magico_con_ai_se")
        self.vai("home")
        yield
        yield
        # ---- Eurojackpot: archivio completamente separato
        self.cambia_gioco(EJ)
        yield
        assert self.serv.g is EJ and self.serv.conta() == 0
        assert self.serv.chiave("gemini") == ""          # la chiave del SuperEnalotto non passa all'EJ
        self.foto("b01_home_vuota_ej")
        self.aggiorna()
        yield
        yield
        self.chiudi_popup()
        yield
        self.foto("b02_home_ej")
        self.vai("magico")
        yield
        yield
        self.pagine["magico"]._genera()
        yield
        yield
        self.foto("b03_magico_ej")
        self.vai("verifica")
        yield
        yield
        v = self.pagine["verifica"]
        v.slider.value = 20
        v._avvia()
        yield
        yield
        v.sv.scroll_y = 0.4
        yield
        self.foto("b04_verifica_ej")
        self.vai("archivio")
        yield
        yield
        self.foto("b05_archivio_ej")
        self.vai("home")
        yield
        self.cambia_gioco(SE)
        yield
        assert self.serv.conta() == 400
        self.foto("b06_ritorno_se")
        # telefono stretto (320 dp): le palline devono restare dentro i riquadri
        Window.size = (int(320 * DENSITA), int(640 * DENSITA))
        yield
        self.vai("magico")
        yield
        yield
        self.foto("c01_magico_stretto_se")
        self.vai("home")
        yield
        yield
        self.foto("c02_home_stretta_se")


if __name__ == "__main__":
    Prova().run()
    if ERRORI:
        print("ERRORI:", ERRORI)
        sys.exit(1)
    print("Prova grafica completata, schermate in", FOTO)
