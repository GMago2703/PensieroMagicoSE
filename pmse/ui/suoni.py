"""Suoni della macchina dell'estrazione, generati dal programma (nessun file esterno, nessun diritto altrui).

Rotolamento delle palline sullo scivolo, aria e palline che si urtano nella sfera, risucchio nel tubo,
"toc" contro l'arresto, campanella dell'annuncio, "plink" nelle caselle, piccolo arpeggio finale.
I file WAV vengono creati una volta nella cartella temporanea; se l'audio non è disponibile tutto tace.
"""
from __future__ import annotations

import os
import tempfile
import wave

import numpy as np

try:
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QSoundEffect
except Exception:          # QtMultimedia assente: niente suoni
    QSoundEffect = None

FREQ = 44100
VERSIONE = 2


def _rng(seme):
    return np.random.default_rng(seme)


def _pb(x: np.ndarray, taglio: float) -> np.ndarray:
    """Passa basso del primo ordine applicato nel dominio delle frequenze (veloce, senza scipy)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / FREQ)
    return np.fft.irfft(X / (1 + 1j * f / taglio), len(x))


def _tempo(sec):
    return np.arange(int(sec * FREQ)) / FREQ


def _normalizza(x, picco=0.8):
    m = np.max(np.abs(x)) or 1.0
    return x / m * picco


def _ciclo(x, dissolvenza=0.25):
    """Rende un suono ripetibile senza scatti (dissolvenza incrociata tra fine e inizio)."""
    n = int(dissolvenza * FREQ)
    a = x[:n] * np.linspace(0, 1, n) + x[-n:] * np.linspace(1, 0, n)
    return np.concatenate([a, x[n:-n]])


def _campanella(f, durata, t0=0.0, tot=None, vol=1.0):
    t = _tempo(tot or durata)
    x = np.zeros_like(t)
    s = t >= t0
    tt = t[s] - t0
    env = np.exp(-tt * 3.2) * np.minimum(1, tt * 400)
    x[s] = vol * env * (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2.01 * f * tt) * np.exp(-tt * 3)
                        + 0.18 * np.sin(2 * np.pi * 3.02 * f * tt) * np.exp(-tt * 5))
    return x


def _clic(f, dec, n, amp=1.0, rng=None):
    t = np.arange(n) / FREQ
    rumore = (rng.standard_normal(n) if rng is not None else 0) * np.exp(-t * 900) * 0.4
    return amp * (np.sin(2 * np.pi * f * t) * np.exp(-t / dec) + rumore)


def genera() -> dict[str, np.ndarray]:
    r = _rng(11)
    s = {}
    # aria: soffio morbido con lieve ondeggiare
    t = _tempo(4.0)
    rum = r.standard_normal(len(t))
    soffio = _pb(rum, 900) - 0.6 * _pb(rum, 120)
    soffio *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.5 * t)
    s["aria"] = _normalizza(_ciclo(soffio), 0.35)
    # palline che si urtano nella sfera
    x = np.zeros(len(t))
    for _ in range(int(4.0 * 34)):
        i = int(r.uniform(0, len(t) - 2000))
        c = _clic(r.uniform(2300, 4300), r.uniform(0.004, 0.012), 1500, r.uniform(0.15, 1.0), r)
        x[i:i + len(c)] += c
    s["palline"] = _normalizza(_ciclo(x, 0.1), 0.5)
    # risucchio nel tubo: soffio che sale + piccoli tocchi della pallina
    t = _tempo(1.5)
    rum = r.standard_normal(len(t))
    sweep = _pb(rum, 2500) - _pb(rum, 400)
    env = np.sin(np.pi * np.clip(t / 1.5, 0, 1)) ** 1.5
    x = sweep * env * (0.4 + 0.6 * t / 1.5)
    for k, tt in enumerate((0.35, 0.6, 0.82, 1.0, 1.15)):
        c = _clic(1800 + 250 * k, 0.006, 900, 0.5, r)
        i = int(tt * FREQ)
        x[i:i + len(c)] += c[: len(x) - i]
    s["tubo"] = _normalizza(x, 0.5)
    # rotolamento sullo scivolo: rombo con il ritmo della rotazione che accelera
    t = _tempo(4.0)
    rum = r.standard_normal(len(t))
    rombo = _pb(rum, 380) * 1.6 + 0.25 * (_pb(rum, 1800) - _pb(rum, 700))
    fase = 2 * np.pi * (5 * t + 1.4 * t ** 2)                     # giri al secondo in aumento
    ritmo = 0.62 + 0.38 * np.abs(np.sin(fase / 2))
    vib = np.sin(2 * np.pi * (95 + 18 * t) * t) * 0.18
    env = np.minimum(1, t / 0.15) * np.minimum(1, (4.0 - t) / 0.3)
    s["rotola"] = _normalizza((rombo * ritmo + vib) * env, 0.6)
    # toc contro l'arresto
    t = _tempo(0.35)
    x = (np.sin(2 * np.pi * 820 * t) * np.exp(-t * 38) + 0.6 * np.sin(2 * np.pi * 1530 * t) * np.exp(-t * 55)
         + 0.4 * r.standard_normal(len(t)) * np.exp(-t * 400))
    s["toc"] = _normalizza(x, 0.7)
    # campanella dell'annuncio: due note dolci (mi - si)
    s["annuncio"] = _normalizza(_campanella(1318.5, 1.8, 0, 2.2, 0.8) + _campanella(1975.5, 1.6, 0.16, 2.2, 0.7),
                                0.55)
    # plink nella casella
    t = _tempo(0.4)
    f = 1760 * (1 + 0.04 * np.exp(-t * 30))
    s["casella"] = _normalizza(np.sin(2 * np.pi * np.cumsum(f) / FREQ) * np.exp(-t * 14)
                               + 0.3 * np.sin(2 * np.pi * 3520 * t) * np.exp(-t * 25), 0.4)
    # accensione: ronzio che sale
    t = _tempo(1.6)
    f = 70 + 60 * (t / 1.6) ** 0.6
    ph = 2 * np.pi * np.cumsum(f) / FREQ
    x = (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph)) * np.minimum(1, t / 0.4) * np.minimum(1, (1.6 - t) / 0.5)
    s["avvio"] = _normalizza(x, 0.4)
    # finale: arpeggio do-mi-sol-do
    tot = 2.6
    x = sum(_campanella(fq, 1.6, i * 0.17, tot, 0.8) for i, fq in enumerate((1046.5, 1318.5, 1568.0, 2093.0)))
    s["fine"] = _normalizza(x, 0.5)
    return s


def scrivi(cartella: str) -> dict[str, str]:
    os.makedirs(cartella, exist_ok=True)
    percorsi = {}
    nomi = ["aria", "palline", "tubo", "rotola", "toc", "annuncio", "casella", "avvio", "fine"]
    if all(os.path.exists(os.path.join(cartella, n + ".wav")) for n in nomi):
        return {n: os.path.join(cartella, n + ".wav") for n in nomi}
    for nome, x in genera().items():
        p = os.path.join(cartella, nome + ".wav")
        dati = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
        with wave.open(p, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(FREQ)
            w.writeframes(dati)
        percorsi[nome] = p
    return percorsi


class Suoni:
    """Riproduce i suoni; tace se l'audio non è disponibile o se è spento."""
    CICLI = ("aria", "palline")

    def __init__(self, parent=None):
        self.attivo = True
        self.volume = 0.8
        self.effetti: dict[str, list] = {}
        self.turno: dict[str, int] = {}
        if QSoundEffect is None:
            return
        try:
            cartella = os.path.join(tempfile.gettempdir(), f"pensieromagico_suoni_{VERSIONE}")
            for nome, p in scrivi(cartella).items():
                copie = 3 if nome in ("casella", "toc") else 1
                lista = []
                for _ in range(copie):
                    e = QSoundEffect(parent)
                    e.setSource(QUrl.fromLocalFile(p))
                    if nome in self.CICLI:
                        e.setLoopCount(QSoundEffect.Infinite)
                    lista.append(e)
                self.effetti[nome] = lista
        except Exception:
            self.effetti = {}

    def suona(self, nome: str, volume: float = 1.0):
        if not self.attivo or nome not in self.effetti:
            return
        try:
            lista = self.effetti[nome]
            i = self.turno.get(nome, 0) % len(lista)
            self.turno[nome] = i + 1
            e = lista[i]
            e.setVolume(max(0.0, min(1.0, volume * self.volume)))
            e.play()
        except Exception:
            pass

    def ferma(self, nome: str):
        for e in self.effetti.get(nome, []):
            try:
                e.stop()
            except Exception:
                pass

    def ciclo(self, nome: str, volume: float):
        """Suoni continui (aria, palline): partono, cambiano volume, si fermano."""
        lista = self.effetti.get(nome)
        if not lista:
            return
        e = lista[0]
        try:
            if not self.attivo or volume < 0.02:
                if e.isPlaying():
                    e.stop()
                return
            e.setVolume(max(0.0, min(1.0, volume * self.volume)))
            if not e.isPlaying():
                e.play()
        except Exception:
            pass

    def zitto(self):
        for nome in self.effetti:
            self.ferma(nome)


_CONDIVISI: Suoni | None = None


def condivisi() -> Suoni:
    """Un solo insieme di suoni per tutto il programma, legato all'applicazione (si chiude con lei)."""
    global _CONDIVISI
    if _CONDIVISI is None:
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
        except Exception:
            app = None
        _CONDIVISI = Suoni(app)
    return _CONDIVISI
