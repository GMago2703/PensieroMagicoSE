"""Combinazioni casuali: la macchina dell'estrazione.

Una sfera di cristallo con le palline mescolate dall'aria; a ogni estrazione una pallina viene aspirata
nella fessura in alto, sale nel tubo, scende lungo lo scivolo in leggera pendenza e si ferma; quando la
combinazione è completa le palline volano nelle caselle del tabellone. SuperEnalotto: una macchina (90
palline; la SuperStar, se richiesta, viene estratta dopo aver rimesso tutte le palline). Eurojackpot: due
macchine, 50 numeri e 12 Euronumeri.

I numeri sono scelti con random.SystemRandom (generatore del sistema operativo): l'animazione mostra
l'estrazione di numeri veramente casuali, la fisica serve solo allo spettacolo.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPainterPathStroker, QPen,
                           QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

from ..core import ridotti_pronti
from ..core import sistemi as sis
from ..core.db import Archivio
from ..core.gioco import Gioco
from .schermo import adatta_schermo

# Ultime combinazioni estratte con la macchina, per gioco: restano SOLO in memoria finché il programma è
# aperto (si cancellano cambiando programma SE/EJ o chiudendo), così si usano altrove senza copia-incolla.
CASUALI: dict[str, dict] = {}


def combinazioni_casuali(g) -> list[list[int]]:
    """Colonne dell'ultima estrazione con la macchina (Eurojackpot: 5 numeri + 2 Euronumeri)."""
    d = CASUALI.get(g.codice)
    if not d:
        return []
    return [r["numeri"] + (r["extra"] if g.is_ej else []) for r in d["risultati"]]


def numeri_casuali(g) -> list[int]:
    """Tutti i numeri principali dell'ultima estrazione con la macchina (per un sistema)."""
    d = CASUALI.get(g.codice)
    return sorted({x for r in d["risultati"] for x in r["numeri"]}) if d else []


def superstar_casuali(g) -> list[int | None]:
    d = CASUALI.get(g.codice)
    if not d or g.is_ej:
        return []
    return [(r["extra"][0] if r["extra"] else None) for r in d["risultati"]]


def dimentica():
    CASUALI.clear()


W, H = 1280, 760                       # coordinate della scena (poi scalate alla finestra)
CASO = random.SystemRandom()
VELOCITA = [("Tranquilla (con suspense)", 1.0), ("Normale", 0.65), ("Veloce", 0.35)]

COLORI_DECINE = ["#e53935", "#fb8c00", "#fdd835", "#43a047", "#00acc1", "#1e88e5", "#5e35b1", "#8e24aa",
                 "#d81b60", "#6d4c41"]
ORO = "#f9a825"


def colore_pallina(n: int, euro: bool = False) -> QColor:
    return QColor(ORO if euro else COLORI_DECINE[min((n - 1) // 10, 9)])


def _ease(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


# ------------------------------------------------------------------ immagini delle palline
class Pennelli:
    """Immagini delle palline già disegnate alla dimensione giusta (nitide e veloci)."""

    def __init__(self):
        self.cache: dict[tuple, QPixmap] = {}
        self.scala = 1.0

    def imposta_scala(self, s: float):
        if abs(s - self.scala) > 1e-3:
            self.scala = s
            self.cache.clear()

    def pallina(self, n: int, r: float, euro: bool = False) -> QPixmap:
        rp = max(4, int(round(r * self.scala * 2)))       # diametro in pixel
        chiave = (n, rp, euro)
        pm = self.cache.get(chiave)
        if pm is not None:
            return pm
        pm = QPixmap(rp, rp)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        c = colore_pallina(n, euro)
        g = QRadialGradient(rp * 0.36, rp * 0.32, rp * 0.75)
        g.setColorAt(0.0, c.lighter(175))
        g.setColorAt(0.45, c)
        g.setColorAt(1.0, c.darker(230))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QRectF(0.5, 0.5, rp - 1, rp - 1))
        # disco bianco con il numero
        d = rp * 0.62
        gb = QRadialGradient(rp * 0.45, rp * 0.42, d * 0.8)
        gb.setColorAt(0, QColor("#ffffff"))
        gb.setColorAt(1, QColor("#dcdcdc"))
        p.setBrush(gb)
        p.drawEllipse(QRectF((rp - d) / 2, (rp - d) / 2, d, d))
        f = QFont("Segoe UI")
        f.setBold(True)
        f.setPixelSize(max(5, int(d * (0.62 if n < 10 else 0.54))))
        p.setFont(f)
        p.setPen(QColor("#111111"))
        p.drawText(QRectF(0, 0, rp, rp * 1.02), Qt.AlignCenter, str(n))
        # riflesso
        gr = QRadialGradient(rp * 0.32, rp * 0.26, rp * 0.28)
        gr.setColorAt(0, QColor(255, 255, 255, 190))
        gr.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(gr)
        p.drawEllipse(QRectF(rp * 0.08, rp * 0.05, rp * 0.5, rp * 0.4))
        p.end()
        self.cache[chiave] = pm
        return pm


def disegna_pallina(p: QPainter, pen: Pennelli, n: int, x: float, y: float, r: float, ang: float = 0.0,
                    euro: bool = False, ombra: bool = False):
    if ombra:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawEllipse(QRectF(x - r * 0.9, y + r * 0.75, r * 1.8, r * 0.45))
    pm = pen.pallina(n, r, euro)
    p.save()
    p.translate(x, y)
    if ang:
        p.rotate(math.degrees(ang))
    p.drawPixmap(QRectF(-r, -r, 2 * r, 2 * r), pm, QRectF(pm.rect()))
    p.restore()


# ------------------------------------------------------------------ una macchina
@dataclass
class Viaggio:
    """Una pallina fuori dalla sfera: tubo → scivolo → ferma → (volo verso il tabellone)."""
    numero: int
    euro: bool
    r: float
    x: float = 0.0
    y: float = 0.0
    ang: float = 0.0
    stato: str = "tubo"          # tubo, scivolo, ferma, volo, arrivata
    t: float = 0.0
    durata: float = 1.0
    da: tuple = (0.0, 0.0)
    a: tuple = (0.0, 0.0)
    r_arrivo: float = 0.0
    s_stop: float = 0.0          # distanza di arresto sullo scivolo


@dataclass
class Macchina:
    nome: str
    numeri: int
    cx: float
    cy: float
    R: float
    r: float
    euro: bool = False
    fine_scivolo: float = 840.0
    pendenza: float = 0.07
    P: np.ndarray = field(default=None)
    V: np.ndarray = field(default=None)
    ANG: np.ndarray = field(default=None)
    dentro: np.ndarray = field(default=None)
    aria: bool = False
    potenza: float = 0.0              # cresce e cala dolcemente
    aspirata: int = -1                # indice della pallina guidata verso la fessura
    in_viaggio: list = field(default_factory=list)
    sullo_scivolo: int = 0            # palline ferme sullo scivolo
    particelle: list = field(default_factory=list)
    eventi: list = field(default_factory=list)       # suoni da riprodurre: "tubo", "rotola", "toc", "casella"

    def __post_init__(self):
        self.rng = np.random.default_rng()
        n = self.numeri
        self.P = np.zeros((n, 2))
        self.V = np.zeros((n, 2))
        self.ANG = np.array([CASO.uniform(0, 6.28) for _ in range(n)])
        self.dentro = np.ones(n, dtype=bool)
        # disposizione iniziale: palline ammucchiate sul fondo
        k = 0
        passo = self.r * 2.05
        y = self.cy + self.R - self.r - 2
        while k < n:
            meta = math.sqrt(max(0.0, (self.R - self.r - 2) ** 2 - (y - self.cy) ** 2))
            x = self.cx - meta + self.r
            while x <= self.cx + meta - self.r and k < n:
                self.P[k] = (x + CASO.uniform(-1, 1), y)
                k += 1
                x += passo
            y -= passo * 0.88
        self._tubo()

    # geometria del tubo e dello scivolo
    def _tubo(self):
        top = self.cy - self.R
        self.uscita = (self.cx, top + self.r + 1)
        alto = top - 70
        ra = 45
        punti = [(self.cx, top + self.r)]
        y = top + self.r
        while y > alto:
            y -= 4
            punti.append((self.cx, max(y, alto)))
        for i in range(1, 21):
            a = math.pi - i * (math.pi / 2) / 20          # quarto di cerchio verso destra
            punti.append((self.cx + ra + ra * math.cos(a), alto - ra * math.sin(a) + 0))
        self.punti_tubo = punti
        lun = [0.0]
        for (x1, y1), (x2, y2) in zip(punti, punti[1:]):
            lun.append(lun[-1] + math.hypot(x2 - x1, y2 - y1))
        self.lun_tubo = lun
        self.inizio_scivolo = punti[-1]
        dx = self.fine_scivolo - self.inizio_scivolo[0]
        self.lun_scivolo = math.hypot(dx, dx * self.pendenza)
        self.dir_scivolo = (dx / self.lun_scivolo, dx * self.pendenza / self.lun_scivolo)

    def punto_tubo(self, s: float) -> tuple[float, float]:
        lun = self.lun_tubo
        s = max(0.0, min(s, lun[-1]))
        i = min(int(np.searchsorted(lun, s)), len(lun) - 1)
        if i == 0:
            return self.punti_tubo[0]
        a, b = self.punti_tubo[i - 1], self.punti_tubo[i]
        f = (s - lun[i - 1]) / max(1e-6, lun[i] - lun[i - 1])
        return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f

    def punto_scivolo(self, s: float) -> tuple[float, float]:
        x0, y0 = self.inizio_scivolo
        return x0 + self.dir_scivolo[0] * s, y0 + self.dir_scivolo[1] * s

    # ---------------------------------------------------------------- fisica
    def passo(self, dt: float, lento: float):
        target = 1.0 if self.aria else 0.0
        self.potenza += (target - self.potenza) * min(1.0, dt * 1.6)
        idx = np.flatnonzero(self.dentro)
        if len(idx):
            self._fisica(idx, dt)
        self._particelle(dt)
        for v in list(self.in_viaggio):
            self._viaggio(v, dt, lento)

    def _fisica(self, idx, dt):
        P, V, r, R = self.P, self.V, self.r, self.R
        c = np.array([self.cx, self.cy])
        acc = np.zeros((len(idx), 2))
        acc[:, 1] = 980.0
        q = P[idx]
        if self.potenza > 0.01:
            pw = self.potenza
            alt = np.clip((q[:, 1] - (self.cy - 0.1 * R)) / (1.1 * R), 0, 1)       # più forte in basso
            ug = self.rng.random(len(idx))
            acc[:, 1] -= pw * 2300 * alt * (0.55 + 0.9 * ug)
            acc[:, 0] += pw * self.rng.uniform(-1, 1, len(idx)) * 1000
            rel = q - c
            tang = np.stack([-rel[:, 1], rel[:, 0]], axis=1) / R
            acc += pw * 380 * tang
            acc[:, 1] -= pw * 420 * np.clip((q[:, 1] - self.cy) / R, 0, 1)
        guida = self.aspirata
        pesi = np.ones(len(idx))
        if guida >= 0 and self.dentro[guida]:
            k = int(np.flatnonzero(idx == guida)[0])
            e = np.array(self.uscita)
            acc[k] = (e - q[k]) * 16 - V[guida] * 4.5
            pesi[k] = 0.0
        sub = 3
        h = dt / sub
        for _ in range(sub):
            V[idx] += acc * h
            V[idx] *= (1 - 0.35 * h)
            sp = np.linalg.norm(V[idx], axis=1)
            troppo = sp > 1100
            if troppo.any():
                V[idx[troppo]] *= (1100 / sp[troppo])[:, None]
            P[idx] += V[idx] * h
            # urti tra palline
            q = P[idx]
            diff = q[:, None, :] - q[None, :, :]
            d2 = (diff ** 2).sum(-1)
            m = np.triu(d2 < (2 * r) ** 2, 1) & (d2 > 1e-9)
            i, j = np.nonzero(m)
            if len(i):
                d = np.sqrt(d2[i, j])
                nrm = diff[i, j] / d[:, None]
                wi, wj = pesi[i], pesi[j]
                ws = wi + wj
                ok = ws > 0
                i, j, d, nrm, wi, wj, ws = i[ok], j[ok], d[ok], nrm[ok], wi[ok], wj[ok], ws[ok]
                corr = ((2 * r - d) / ws)[:, None] * nrm
                np.add.at(P, idx[i], corr * wi[:, None])
                np.add.at(P, idx[j], -corr * wj[:, None])
                vrel = ((V[idx[i]] - V[idx[j]]) * nrm).sum(1)
                neg = vrel < 0
                if neg.any():
                    J = (-(1.88) * vrel[neg] / ws[neg])[:, None] * nrm[neg]
                    np.add.at(V, idx[i[neg]], J * wi[neg][:, None])
                    np.add.at(V, idx[j[neg]], -J * wj[neg][:, None])
            # pareti della sfera
            rel = P[idx] - c
            dist = np.linalg.norm(rel, axis=1)
            fuori = dist > (R - r - 1)
            if fuori.any():
                n = rel[fuori] / dist[fuori][:, None]
                P[idx[fuori]] = c + n * (R - r - 1)
                vn = (V[idx[fuori]] * n).sum(1)
                urta = vn > 0
                V[idx[fuori][urta]] -= (1.8 * vn[urta])[:, None] * n[urta]
        self.ANG[idx] += V[idx, 0] / r * dt * 0.8
        if guida >= 0 and self.dentro[guida]:
            if math.dist(P[guida], self.uscita) < r * 0.7:
                self.dentro[guida] = False
                self.aspirata = -1
                v = Viaggio(guida + 1, self.euro, r, *self.uscita, ang=float(self.ANG[guida]))
                self.in_viaggio.append(v)
                self.eventi.append("tubo")

    def _particelle(self, dt):
        if self.potenza > 0.05 and len(self.particelle) < int(26 * self.potenza):
            self.particelle.append([self.cx + CASO.uniform(-0.25, 0.25) * self.R, self.cy + self.R - 8,
                                    CASO.uniform(-40, 40), -CASO.uniform(260, 520), 1.0])
        for pa in self.particelle:
            pa[0] += pa[2] * dt
            pa[1] += pa[3] * dt
            pa[4] -= dt * 0.9
        self.particelle = [pa for pa in self.particelle
                           if pa[4] > 0 and math.dist((pa[0], pa[1]), (self.cx, self.cy)) < self.R - 6]

    def _viaggio(self, v: Viaggio, dt: float, lento: float):
        v.t += dt
        if v.stato == "tubo":
            durata = 1.5 * lento
            s = self.lun_tubo[-1] * _ease(v.t / durata)
            nx, ny = self.punto_tubo(s)
            v.ang += math.hypot(nx - v.x, ny - v.y) / v.r
            v.x, v.y = nx, ny
            if v.t >= durata:
                v.stato, v.t = "scivolo", 0.0
                v.s_stop = self.lun_scivolo - v.r - 6 - self.sullo_scivolo * (2 * v.r + 1)
                self.sullo_scivolo += 1
                v.durata = (1.2 + v.s_stop / 420) * lento
                self.eventi.append("rotola")
        elif v.stato == "scivolo":
            u = min(1.0, v.t / v.durata)
            if u < 1:
                s = v.s_stop * (u ** 1.7)
            else:                                   # piccolo rimbalzo contro l'arresto o la pallina davanti
                if not v.r_arrivo:
                    v.r_arrivo = 1.0
                    self.eventi.append("toc")
                b = min(1.0, (v.t - v.durata) / (0.45 * lento))
                s = v.s_stop - 9 * math.sin(math.pi * b) * (1 - b)
                if b >= 1:
                    v.stato = "ferma"
            nx, ny = self.punto_scivolo(s)
            ny -= 0
            v.ang += (nx - v.x) / v.r
            v.x, v.y = nx, ny
        elif v.stato == "volo":
            u = min(1.0, v.t / v.durata)
            e = _ease(u)
            (x0, y0), (x1, y1) = v.da, v.a
            v.x = x0 + (x1 - x0) * e
            v.y = y0 + (y1 - y0) * e - math.sin(math.pi * e) * 90
            v.ang *= (1 - min(1.0, dt * 4))
            if u >= 1:
                v.stato = "arrivata"
                self.eventi.append("casella")

    def scegli(self) -> int:
        """Indice della pallina estratta: scelta con il generatore casuale del sistema operativo."""
        return int(CASO.choice([int(x) for x in np.flatnonzero(self.dentro)]))

    def rimetti(self, numeri: list[int]):
        """Le palline estratte tornano nella sfera, cadendo dall'alto."""
        for n in numeri:
            i = n - 1
            if self.dentro[i]:
                continue
            self.dentro[i] = True
            self.P[i] = (self.cx + CASO.uniform(-0.3, 0.3) * self.R, self.cy - self.R * 0.6 + CASO.uniform(0, 20))
            self.V[i] = (CASO.uniform(-60, 60), 80)
        self.in_viaggio = [v for v in self.in_viaggio if v.numero not in numeri]
        self.sullo_scivolo = sum(1 for v in self.in_viaggio if v.stato in ("scivolo", "ferma"))

    # ---------------------------------------------------------------- disegno
    def disegna(self, p: QPainter, pen: Pennelli):
        cx, cy, R = self.cx, self.cy, self.R
        # basamento
        alto_collo = cy + R - 12
        collo = QRectF(cx - R * 0.26, alto_collo, R * 0.52, R * 0.32)
        g = QLinearGradient(collo.left(), 0, collo.right(), 0)
        for t, c in ((0, "#30343c"), (0.35, "#c9ced6"), (0.55, "#f4f6f8"), (1, "#3a3e46")):
            g.setColorAt(t, QColor(c))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRect(collo)
        base = QRectF(cx - R * 0.72, collo.bottom() - 4, R * 1.44, R * 0.24)
        g2 = QLinearGradient(base.left(), 0, base.right(), 0)
        for t, c in ((0, "#1d2026"), (0.3, "#8c939e"), (0.5, "#dfe3e8"), (0.7, "#8c939e"), (1, "#1d2026")):
            g2.setColorAt(t, QColor(c))
        p.setBrush(g2)
        p.drawRoundedRect(base, 10, 10)
        p.setBrush(QColor(255, 255, 255, 25))
        p.drawEllipse(QRectF(base.left() + 10, base.bottom() - 6, base.width() - 20, 18))
        f = QFont("Segoe UI")
        f.setPixelSize(max(9, int(R * 0.075)))
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        p.setFont(f)
        p.setPen(QColor(40, 44, 52, 220))
        p.drawText(base, Qt.AlignCenter, "PENSIERO MAGICO" if not self.euro else "EURONUMERI")
        # anello alla base della sfera
        anello = QRectF(cx - R * 0.42, cy + R - 28, R * 0.84, 34)
        g3 = QLinearGradient(0, anello.top(), 0, anello.bottom())
        g3.setColorAt(0, QColor("#eef1f4"))
        g3.setColorAt(1, QColor("#5b6270"))
        p.setBrush(g3)
        p.drawEllipse(anello)
        # interno della sfera (vetro, parte posteriore)
        gi = QRadialGradient(cx - R * 0.25, cy - R * 0.3, R * 1.25)
        gi.setColorAt(0, QColor(190, 225, 255, 45))
        gi.setColorAt(0.7, QColor(60, 110, 170, 55))
        gi.setColorAt(1, QColor(20, 40, 80, 120))
        p.setBrush(gi)
        p.drawEllipse(QPointF(cx, cy), R, R)
        # ugello dell'aria
        p.setBrush(QColor(30, 34, 40, 200))
        p.drawEllipse(QRectF(cx - 16, cy + R - 14, 32, 10))
        # getti d'aria
        for x, y, _, _, vita in self.particelle:
            p.setPen(QPen(QColor(220, 240, 255, int(70 * vita)), 2))
            p.drawLine(QPointF(x, y), QPointF(x, y + 16))
        # palline (prima quelle più lontane: in alto)
        idx = np.flatnonzero(self.dentro)
        for i in idx[np.argsort(self.P[idx, 1])]:
            disegna_pallina(p, pen, int(i) + 1, self.P[i, 0], self.P[i, 1], self.r, float(self.ANG[i]), self.euro)
        # vetro, parte anteriore
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(225, 240, 255, 170), 3))
        p.drawEllipse(QPointF(cx, cy), R, R)
        p.setPen(QPen(QColor(255, 255, 255, 40), 10))
        p.drawArc(QRectF(cx - R + 8, cy - R + 8, 2 * R - 16, 2 * R - 16), 200 * 16, 120 * 16)
        gr = QRadialGradient(cx - R * 0.42, cy - R * 0.5, R * 0.45)
        gr.setColorAt(0, QColor(255, 255, 255, 150))
        gr.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(gr)
        p.save()
        p.translate(cx - R * 0.42, cy - R * 0.52)
        p.rotate(-35)
        p.drawEllipse(QRectF(-R * 0.36, -R * 0.18, R * 0.72, R * 0.36))
        p.restore()
        gr2 = QRadialGradient(cx + R * 0.5, cy + R * 0.45, R * 0.25)
        gr2.setColorAt(0, QColor(255, 255, 255, 55))
        gr2.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(gr2)
        p.drawEllipse(QPointF(cx + R * 0.5, cy + R * 0.45), R * 0.25, R * 0.15)
        # collare della fessura in alto
        col = QRectF(cx - self.r * 1.6, cy - R - 10, self.r * 3.2, 20)
        g4 = QLinearGradient(col.left(), 0, col.right(), 0)
        for t, c in ((0, "#4a505a"), (0.5, "#f0f2f5"), (1, "#4a505a")):
            g4.setColorAt(t, QColor(c))
        p.setBrush(g4)
        p.drawRoundedRect(col, 5, 5)

    def disegna_tubo(self, p: QPainter):
        path = QPainterPath(QPointF(*self.punti_tubo[0]))
        for x, y in self.punti_tubo[1:]:
            path.lineTo(x, y)
        largo = self.r * 2 + 8
        p.setPen(QPen(QColor(190, 225, 255, 38), largo, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        st = QPainterPathStroker()
        st.setWidth(largo)
        st.setCapStyle(Qt.FlatCap)
        p.setPen(QPen(QColor(225, 240, 255, 140), 1.6))
        p.drawPath(st.createStroke(path))
        # scivolo: guida posteriore trasparente e rotaia metallica sotto le palline
        x0, y0 = self.inizio_scivolo
        x1, y1 = self.punto_scivolo(self.lun_scivolo)
        off = self.r + 3
        p.setPen(QPen(QColor(200, 230, 255, 70), 2))
        p.drawLine(QPointF(x0, y0 - off - 3), QPointF(x1, y1 - off - 3))
        g = QLinearGradient(0, y0 + off - 4, 0, y0 + off + 6)
        g.setColorAt(0, QColor("#f2f4f7"))
        g.setColorAt(1, QColor("#5d6470"))
        p.setPen(QPen(QBrush(g), 6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x0 - 4, y0 + off), QPointF(x1 + 6, y1 + off))
        p.setPen(QPen(QColor(120, 128, 140), 3))
        p.drawLine(QPointF(x0 + 30, y0 + off + 3), QPointF(x0 + 30, y0 + off + 26))
        p.drawLine(QPointF(x1 - 20, y1 + off + 3), QPointF(x1 - 20, y1 + off + 26))
        # arresto
        p.setPen(QPen(QColor("#c62828"), 6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x1 + 4, y1 + off), QPointF(x1 + 4, y1 - off + 2))

    def disegna_viaggi(self, p: QPainter, pen: Pennelli):
        for v in self.in_viaggio:
            if v.stato != "volo":
                disegna_pallina(p, pen, v.numero, v.x, v.y, v.r, v.ang, v.euro)


# ------------------------------------------------------------------ la scena
@dataclass
class Casella:
    x: float
    y: float
    r: float
    euro: bool = False
    numero: int = 0              # 0 = vuota


class Scena(QWidget):
    """La macchina (o le due macchine), lo scivolo e il tabellone, animati."""

    def __init__(self, g: Gioco, parent=None):
        super().__init__(parent)
        self.g = g
        self.setMinimumSize(640, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.pen = Pennelli()
        if g.is_ej:
            self.macchine = [Macchina("principale", g.n, 250, 420, 188, 17, fine_scivolo=830),
                             Macchina("euro", 12, 650, 500, 112, 16, euro=True, fine_scivolo=835)]
        else:
            self.macchine = [Macchina("principale", g.n, 335, 405, 232, 16.5, fine_scivolo=845)]
        self.caselle: list[Casella] = []
        self.etichette: list[tuple[float, float, str]] = []
        self.titolo_tab = ""
        self.voli: list[tuple[Viaggio, Casella]] = []
        self.testo = "Scegli e premi «Avvia l'estrazione»"
        self.annuncio: tuple | None = None          # (numero, euro, testo, inizio)
        self.t = 0.0
        self.lento = 1.0
        self.copione = None
        self.istantaneo = False
        self.alla_fine = None
        from .suoni import Suoni
        self.suoni = Suoni(None)
        self.orologio = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tic)
        self.timer.start()
        self.orologio.start()

    # ---------------------------------------------------------------- tempo
    def _tic(self):
        dt = min(0.05, self.orologio.restart() / 1000.0)
        self.avanza(dt)
        self.update()

    def avanza(self, dt: float):
        self.t += dt
        for m in self.macchine:
            m.passo(dt, self.lento)
        self._suoni()
        if self.copione is not None:
            try:
                next(self.copione)
            except StopIteration:
                self.copione = None
                if self.alla_fine:
                    self.alla_fine()

    def _suoni(self):
        su = self.suoni
        pot = max(m.potenza for m in self.macchine)
        su.ciclo("aria", 0.55 * pot)
        su.ciclo("palline", 0.6 * pot)
        for m in self.macchine:
            for e in m.eventi:
                if self.istantaneo:
                    continue
                if e == "toc":
                    su.ferma("rotola")
                    su.suona("toc", 0.8)
                elif e == "rotola":
                    su.suona("rotola", 0.9 if not m.euro else 0.75)
                elif e == "tubo":
                    su.suona("tubo", 0.7)
                elif e == "casella":
                    su.suona("casella", 0.6)
            m.eventi.clear()

    def simula(self, secondi: float, dt: float = 1 / 60):
        """Per le prove: fa avanzare la scena senza aspettare il tempo reale."""
        for _ in range(int(secondi / dt)):
            self.avanza(dt)

    def attendi(self, secondi: float):
        if self.istantaneo:
            return
        fine = self.t + secondi * self.lento
        while self.t < fine and not self.istantaneo:
            yield

    def finche(self, cond):
        while not cond() and not self.istantaneo:
            yield

    # ---------------------------------------------------------------- azioni del copione
    def estrai(self, m: Macchina, ordine: int, nome: str):
        """Generatore: una pallina dalla macchina m fino allo scivolo; restituisce il Viaggio."""
        i = m.scegli()
        if self.istantaneo:
            m.dentro[i] = False
            v = Viaggio(i + 1, m.euro, m.r)
            v.stato = "ferma"
            v.x, v.y = m.punto_scivolo(m.lun_scivolo - m.r - 6 - m.sullo_scivolo * (2 * m.r + 1))
            m.sullo_scivolo += 1
            m.in_viaggio.append(v)
            return v
        self.testo = f"Estrazione del {ordine}° {nome}..."
        yield from self.attendi(0.9)
        if self.istantaneo:
            return self._completa_viaggio(m, i)
        m.aspirata = i
        yield from self.finche(lambda: not m.dentro[i])
        if self.istantaneo:
            return self._completa_viaggio(m, i)
        v = next(x for x in m.in_viaggio if x.numero == i + 1)
        self.testo = f"Il {ordine}° {nome} sta scendendo..."
        yield from self.finche(lambda: v.stato == "ferma")
        if self.istantaneo:
            return self._completa_viaggio(m, i)
        self.annuncio = (v.numero, m.euro, f"{ordine}° {nome}: {v.numero}", self.t)
        self.suoni.suona("annuncio", 0.7)
        self.testo = f"Uscito il {v.numero}!"
        return v

    def _completa_viaggio(self, m, i):
        m.aspirata = -1
        m.dentro[i] = False
        v = next((x for x in m.in_viaggio if x.numero == i + 1), None)
        if v is None:
            v = Viaggio(i + 1, m.euro, m.r)
            m.in_viaggio.append(v)
            m.sullo_scivolo += 1
        v.stato = "ferma"
        return v

    def colloca(self, coppie: list[tuple[Viaggio, Casella]]):
        """Le palline dello scivolo volano nelle caselle del tabellone."""
        for k, (v, c) in enumerate(coppie):
            v.stato, v.t = "volo", -0.18 * k * self.lento
            v.da, v.a = (v.x, v.y), (c.x, c.y)
            v.durata = 1.3 * self.lento
            self.voli.append((v, c))
        if self.istantaneo:
            for v, c in coppie:
                v.stato = "arrivata"
        while any(v.stato != "arrivata" for v, _ in coppie) and not self.istantaneo:
            yield
        for v, c in coppie:
            c.numero = v.numero
            v.stato = "arrivata"
        self.voli = [(v, c) for v, c in self.voli if v.stato != "arrivata"]
        for m in self.macchine:
            m.in_viaggio = [v for v in m.in_viaggio if v.stato != "arrivata"]
            m.sullo_scivolo = sum(1 for v in m.in_viaggio if v.stato in ("scivolo", "ferma"))

    def aria(self, accesa: bool, macchine=None):
        for m in (macchine or self.macchine):
            m.aria = accesa
            if self.istantaneo:
                m.potenza = 1.0 if accesa else 0.0

    # ---------------------------------------------------------------- disegno
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = min(self.width() / W, self.height() / H)
        self.pen.imposta_scala(s * self.devicePixelRatioF())
        p.fillRect(self.rect(), QColor("#03060f"))
        p.translate((self.width() - W * s) / 2, (self.height() - H * s) / 2)
        p.scale(s, s)
        self._sfondo(p)
        for m in self.macchine:
            m.disegna_tubo(p)
        for m in self.macchine:
            m.disegna(p, self.pen)
        for m in self.macchine:
            m.disegna_viaggi(p, self.pen)
        self._tabellone(p)
        for v, _ in self.voli:
            if v.stato == "volo":
                disegna_pallina(p, self.pen, v.numero, v.x, v.y, v.r, v.ang, v.euro, ombra=True)
        self._scritte(p)
        p.end()

    def _sfondo(self, p: QPainter):
        g = QLinearGradient(0, 0, 0, H)
        g.setColorAt(0, QColor("#0d1d44"))
        g.setColorAt(0.6, QColor("#060b1d"))
        g.setColorAt(1, QColor("#020309"))
        p.fillRect(QRectF(0, 0, W, H), g)
        for m in self.macchine:
            luce = QRadialGradient(m.cx, m.cy - m.R * 0.2, m.R * 2.0)
            luce.setColorAt(0, QColor(90, 150, 255, 80))
            luce.setColorAt(1, QColor(90, 150, 255, 0))
            p.fillRect(QRectF(0, 0, W, H), luce)
            pav = QRadialGradient(m.cx, m.cy + m.R * 1.42, m.R * 1.1)
            pav.setColorAt(0, QColor(140, 180, 255, 55))
            pav.setColorAt(1, QColor(140, 180, 255, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(pav)
            p.drawEllipse(QPointF(m.cx, m.cy + m.R * 1.42), m.R * 1.1, m.R * 0.22)
        # stelline
        rnd = random.Random(7)
        p.setPen(Qt.NoPen)
        for _ in range(70):
            x, y = rnd.uniform(0, W), rnd.uniform(0, H * 0.55)
            a = int(60 + 120 * (0.5 + 0.5 * math.sin(self.t * rnd.uniform(0.5, 2) + rnd.uniform(0, 6))))
            p.setBrush(QColor(255, 255, 255, a // 3))
            p.drawEllipse(QPointF(x, y), 1.1, 1.1)

    def _tabellone(self, p: QPainter):
        x0 = 870
        box = QRectF(x0, 18, W - x0 - 14, H - 36)
        g = QLinearGradient(0, box.top(), 0, box.bottom())
        g.setColorAt(0, QColor(28, 44, 92, 235))
        g.setColorAt(1, QColor(10, 16, 38, 235))
        p.setBrush(g)
        p.setPen(QPen(QColor(120, 160, 255, 140), 1.5))
        p.drawRoundedRect(box, 16, 16)
        f = QFont("Segoe UI")
        f.setPixelSize(22)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffe082"))
        p.drawText(QRectF(box.left(), box.top() + 8, box.width(), 34), Qt.AlignCenter, self.titolo_tab)
        f.setPixelSize(14)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor("#c5cae9"))
        for x, y, t in self.etichette:
            p.drawText(QRectF(x - 60, y - 12, 120, 24), Qt.AlignCenter, t)
        for c in self.caselle:
            if c.numero:
                disegna_pallina(p, self.pen, c.numero, c.x, c.y, c.r, 0, c.euro)
            else:
                gv = QRadialGradient(c.x, c.y - c.r * 0.3, c.r * 1.2)
                gv.setColorAt(0, QColor(0, 0, 0, 160))
                gv.setColorAt(1, QColor(40, 60, 110, 120))
                p.setBrush(gv)
                p.setPen(QPen(QColor(255, 213, 79, 140) if c.euro else QColor(140, 170, 255, 120), 1.4))
                p.drawEllipse(QPointF(c.x, c.y), c.r, c.r)

    def _scritte(self, p: QPainter):
        f = QFont("Segoe UI")
        f.setPixelSize(26)
        f.setBold(True)
        p.setFont(f)
        r = QRectF(0, 4, 860, 44)
        p.setPen(QColor(0, 0, 0, 180))
        p.drawText(r.translated(2, 2), Qt.AlignCenter, self.testo)
        p.setPen(QColor("#ffffff"))
        p.drawText(r, Qt.AlignCenter, self.testo)
        if self.annuncio:
            n, euro, testo, t0 = self.annuncio
            dt = (self.t - t0) / max(0.3, self.lento)
            if dt > 2.6:
                self.annuncio = None
                return
            a = min(1.0, dt * 3) * (1.0 if dt < 2.0 else max(0.0, (2.6 - dt) / 0.6))
            m = self.macchine[1] if euro and len(self.macchine) > 1 else self.macchine[0]
            cx, cy = (600, 250) if not self.g.is_ej else (520, 262)
            rr = m.r * (1.0 + 2.6 * min(1.0, dt * 2.2))
            p.setOpacity(a)
            alone = QRadialGradient(cx, cy, rr * 2.2)
            alone.setColorAt(0, QColor(255, 236, 140, 120))
            alone.setColorAt(1, QColor(255, 236, 140, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(alone)
            p.drawEllipse(QPointF(cx, cy), rr * 2.2, rr * 2.2)
            disegna_pallina(p, self.pen, n, cx, cy, rr, 0, euro)
            f.setPixelSize(30)
            p.setFont(f)
            p.setPen(QColor(0, 0, 0, 200))
            p.drawText(QRectF(cx - 260, cy + rr + 8, 520, 44).translated(2, 2), Qt.AlignCenter, testo)
            p.setPen(QColor("#ffe082"))
            p.drawText(QRectF(cx - 260, cy + rr + 8, 520, 44), Qt.AlignCenter, testo)
            p.setOpacity(1.0)


# ------------------------------------------------------------------ la finestra
class FinestraMacchina(QDialog):
    """modo "sestine": combinazioni casuali singole e separate; modo "sistema": i numeri di un sistema."""

    def __init__(self, arch: Archivio, modo: str = "sestine", parent=None, apri_editor=None):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.modo = modo
        self.apri_editor = apri_editor
        self.risultati: list[dict] = []
        g = self.g
        nome = "Sestine" if not g.is_ej else "Cinquine ed Euronumeri"
        self.setWindowTitle(f"🎱 {'Sistema casuale' if modo == 'sistema' else nome + ' casuali'} – "
                            f"la macchina dell'estrazione – {g.nome}")
        adatta_schermo(self, 1280, 840)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.scena = Scena(g, self)
        v.addWidget(self.scena, 1)
        h = QHBoxLayout()
        if modo == "sistema":
            h.addWidget(QLabel("Numeri del sistema"))
            self.sp_n = QSpinBox()
            self.sp_n.setRange(g.k + 1, 20)
            self.sp_n.setValue(10 if not g.is_ej else 9)
        else:
            h.addWidget(QLabel("Quante " + ("sestine" if not g.is_ej else "combinazioni")))
            self.sp_n = QSpinBox()
            self.sp_n.setRange(1, 10)
            self.sp_n.setValue(3 if not g.is_ej else 2)
        h.addWidget(self.sp_n)
        self.cb_ss = QCheckBox("con SuperStar")
        if not g.is_ej and modo == "sestine":
            h.addWidget(self.cb_ss)
        h.addSpacing(10)
        h.addWidget(QLabel("Ritmo"))
        self.c_vel = QComboBox()
        for t, _ in VELOCITA:
            self.c_vel.addItem(t)
        self.c_vel.currentIndexChanged.connect(lambda i: setattr(self.scena, "lento", VELOCITA[i][1]))
        h.addWidget(self.c_vel)
        self.b_avvia = QPushButton("▶ Avvia l'estrazione")
        f = self.b_avvia.font()
        f.setBold(True)
        f.setPointSize(11)
        self.b_avvia.setFont(f)
        self.b_avvia.setMinimumHeight(34)
        self.b_avvia.clicked.connect(self.avvia)
        h.addWidget(self.b_avvia)
        self.cb_suoni = QCheckBox("🔊 Suoni")
        self.cb_suoni.setChecked((arch.leggi_impostazione("macchina_suoni") or "1") == "1")
        self.scena.suoni.attivo = self.cb_suoni.isChecked()
        self.cb_suoni.toggled.connect(self._suoni)
        if not self.scena.suoni.disponibile:
            self.cb_suoni.setToolTip("Nessuna uscita audio trovata su questo computer")
        h.addWidget(self.cb_suoni)
        self.b_salta = QPushButton("⏭ Salta l'animazione")
        self.b_salta.setEnabled(False)
        self.b_salta.clicked.connect(self.salta)
        h.addWidget(self.b_salta)
        h.addStretch()
        v.addLayout(h)
        h2 = QHBoxLayout()
        self.dopo: list[QPushButton] = []
        if modo == "sistema":
            h2.addWidget(QLabel("Sviluppo"))
            self.c_tipo = QComboBox()
            h2.addWidget(self.c_tipo, 1)
            self._aggiungi(h2, "▶ Sviluppa il sistema", self.sviluppa)
            self._aggiungi(h2, "✏ Apri nell'editor (condizioni)", self.editor)
            self.sp_n.valueChanged.connect(self._tipi)
            self._tipi()
        else:
            self.sp_n.valueChanged.connect(self._ridisegna)
            self.cb_ss.toggled.connect(self._ridisegna)
            self._aggiungi(h2, "🔍 Verifica sull'archivio", self.verifica)
            self._aggiungi(h2, "📝 Registra come giocata", self.registra)
        self._aggiungi(h2, "📋 Copia", self.copia)
        self._aggiungi(h2, "🖨 Stampa / PDF / TXT", self.stampa)
        h2.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.reject)
        h2.addWidget(b)
        v.addLayout(h2)
        self._prepara_tabellone()

    def _suoni(self, on):
        self.scena.suoni.attivo = on
        self.arch.scrivi_impostazione("macchina_suoni", "1" if on else "0")
        if on:
            self.scena.suoni.suona("annuncio", 0.6)          # prova: si sente subito la campanella
        else:
            self.scena.suoni.zitto()

    def _aggiungi(self, lay, testo, fun):
        b = QPushButton(testo)
        b.clicked.connect(fun)
        b.setEnabled(False)
        lay.addWidget(b)
        self.dopo.append(b)

    def _ridisegna(self, *_):
        if self.scena.copione is None:
            self.risultati = []
            self._prepara_tabellone()
            self.scena.update()

    def _tipi(self, *_):
        n = self.sp_n.value()
        k = self.g.k
        self.c_tipo.clear()
        self.c_tipo.addItem(f"Integrale ({sis.numero_integrale(n, k, 0):,} colonne)".replace(",", "."), 0)
        for nn, f, punti, colonne in sorted(ridotti_pronti.disponibili(k), key=lambda x: -x[2]):
            if nn == n and f == 0:
                self.c_tipo.addItem(f"Ridotto immediato – garanzia n-{k - punti}: almeno {punti} punti se {k} "
                                    f"({colonne} colonne)", k - punti)
        if self.c_tipo.count() > 1:
            self.c_tipo.setCurrentIndex(1)
        if not self.risultati:
            self._prepara_tabellone()

    # ---------------------------------------------------------------- tabellone
    def _prepara_tabellone(self):
        sc = self.scena
        g = self.g
        sc.caselle, sc.etichette = [], []
        x0, x1 = 880, W - 24
        if self.modo == "sistema":
            n = self.sp_n.value()
            sc.titolo_tab = f"Sistema di {n} numeri"
            r = 22
            col = 5
            dx = (x1 - x0 - 40) / col
            for i in range(n):
                sc.caselle.append(Casella(x0 + 20 + dx * (i % col) + dx / 2, 110 + (i // col) * 62, r))
            if g.is_ej:
                y = 110 + ((n - 1) // col + 1) * 62 + 40
                sc.etichette.append(((x0 + x1) / 2, y - 34, "Euronumeri"))
                for j in range(2):
                    sc.caselle.append(Casella((x0 + x1) / 2 + (j - 0.5) * 60, y, r, euro=True))
            return
        n = self.sp_n.value()
        sc.titolo_tab = ("Sestine estratte" if not g.is_ej else "Combinazioni estratte")
        alt = min(66.0, (H - 150) / n)
        r = min(19.0, alt * 0.36)
        extra = (1 if self.cb_ss.isChecked() else 0) if not g.is_ej else 2
        tot = g.k + extra
        larg = x1 - x0 - 56
        dx = min(2 * r + 9, larg / (tot + (0.6 if extra else 0)))
        for i in range(n):
            y = 112 + i * alt
            sc.etichette.append((x0 + 22, y, f"{i + 1}"))
            for j in range(g.k):
                sc.caselle.append(Casella(x0 + 52 + j * dx, y, r))
            for j in range(extra):
                sc.caselle.append(Casella(x0 + 52 + (g.k + 0.6 + j) * dx, y, r, euro=g.is_ej))
        if extra:
            xs = x0 + 52 + (g.k + 0.6 + (extra - 1) / 2) * dx
            sc.etichette.append((xs, 112 - alt / 2 - 6, "SuperStar" if not g.is_ej else "Euro"))

    # ---------------------------------------------------------------- estrazione
    def avvia(self):
        self.risultati = []
        self._prepara_tabellone()
        sc = self.scena
        sc.lento = VELOCITA[self.c_vel.currentIndex()][1]
        sc.istantaneo = False
        for m in sc.macchine:
            m.rimetti(list(range(1, m.numeri + 1)))
            m.in_viaggio, m.sullo_scivolo = [], 0
        sc.voli = []
        for w in (self.b_avvia, self.sp_n, self.cb_ss, *self.dopo):
            w.setEnabled(False)
        self.b_salta.setEnabled(True)
        sc.alla_fine = self._finito
        sc.copione = self._copione_sistema() if self.modo == "sistema" else self._copione_sestine()

    def _caselle_riga(self, i: int) -> list[Casella]:
        g = self.g
        extra = (1 if self.cb_ss.isChecked() else 0) if not g.is_ej else 2
        tot = g.k + extra
        return self.scena.caselle[i * tot:(i + 1) * tot]

    def _copione_sestine(self):
        sc, g = self.scena, self.g
        principale = sc.macchine[0]
        sc.testo = "Accensione della macchina..."
        sc.suoni.suona("avvio", 0.6)
        yield from sc.attendi(1.2)
        sc.testo = "Le palline vengono mescolate dall'aria..."
        sc.aria(True)
        yield from sc.attendi(4.5)
        nome = "numero"
        for i in range(self.sp_n.value()):
            righe = self._caselle_riga(i)
            usciti = []
            for j in range(g.k):
                if j:
                    sc.testo = "Mescolamento..."
                    yield from sc.attendi(1.6)
                v = yield from sc.estrai(principale, j + 1, nome)
                usciti.append(v)
                yield from sc.attendi(2.2)
            extra = []
            if g.is_ej:
                euro = sc.macchine[1]
                for j in range(2):
                    sc.testo = "Ora gli Euronumeri..." if j == 0 else "Mescolamento..."
                    yield from sc.attendi(1.6)
                    v = yield from sc.estrai(euro, j + 1, "Euronumero")
                    extra.append(v)
                    yield from sc.attendi(2.0)
            sc.testo = f"{'Sestina' if not g.is_ej else 'Combinazione'} {i + 1} completa: nelle caselle!"
            ordinati = sorted(usciti, key=lambda x: x.numero) + sorted(extra, key=lambda x: x.numero)
            yield from sc.colloca(list(zip(ordinati, righe)))
            principale.rimetti([v.numero for v in usciti])
            if g.is_ej:
                sc.macchine[1].rimetti([v.numero for v in extra])
            ss = None
            if not g.is_ej and self.cb_ss.isChecked():
                sc.testo = "Tutte le palline tornano nella sfera: estrazione della SuperStar..."
                yield from sc.attendi(2.5)
                v = yield from sc.estrai(principale, 1, "numero SuperStar")
                yield from sc.attendi(2.0)
                yield from sc.colloca([(v, righe[g.k])])
                principale.rimetti([v.numero])
                ss = v.numero
            self.risultati.append({"numeri": sorted(x.numero for x in usciti),
                                   "extra": [ss] if ss else sorted(x.numero for x in extra)})
            if i + 1 < self.sp_n.value():
                sc.testo = "Le palline tornano nella sfera..."
                yield from sc.attendi(1.8)
        sc.aria(False)
        sc.testo = "Estrazione terminata. Buona fortuna!"
        if not sc.istantaneo:
            sc.suoni.suona("fine", 0.6)

    def _copione_sistema(self):
        sc, g = self.scena, self.g
        principale = sc.macchine[0]
        n = self.sp_n.value()
        sc.testo = "Accensione della macchina..."
        sc.suoni.suona("avvio", 0.6)
        yield from sc.attendi(1.2)
        sc.testo = "Le palline vengono mescolate dall'aria..."
        sc.aria(True)
        yield from sc.attendi(4.5)
        numeri = []
        for j in range(n):
            if j:
                sc.testo = "Mescolamento..."
                yield from sc.attendi(1.3)
            v = yield from sc.estrai(principale, j + 1, "numero")
            yield from sc.attendi(1.8)
            numeri.append(v.numero)
            yield from sc.colloca([(v, sc.caselle[j])])
        extra = []
        if g.is_ej:
            euro = sc.macchine[1]
            for j in range(2):
                sc.testo = "Ora gli Euronumeri..."
                yield from sc.attendi(1.6)
                v = yield from sc.estrai(euro, j + 1, "Euronumero")
                yield from sc.attendi(1.8)
                extra.append(v.numero)
                yield from sc.colloca([(v, sc.caselle[n + j])])
        self.risultati = [{"numeri": sorted(numeri), "extra": sorted(extra)}]
        sc.aria(False)
        sc.testo = "I numeri del sistema sono pronti: scegli lo sviluppo."
        if not sc.istantaneo:
            sc.suoni.suona("fine", 0.6)

    def salta(self):
        sc = self.scena
        if sc.copione is None:
            return
        sc.istantaneo = True
        sc.annuncio = None
        sc.suoni.zitto()
        cop = sc.copione
        sc.copione = None
        try:
            for _ in cop:
                pass
        except StopIteration:
            pass
        sc.istantaneo = False
        for m in sc.macchine:
            m.aspirata = -1
            m.rimetti([x + 1 for x in range(m.numeri) if not m.dentro[x]])
            m.in_viaggio, m.sullo_scivolo = [], 0
        sc.voli = []
        self._finito()

    def _finito(self):
        if self.risultati:
            CASUALI[self.g.codice] = {"modo": self.modo, "risultati": [dict(r) for r in self.risultati]}
        self.b_salta.setEnabled(False)
        for w in (self.b_avvia, self.sp_n, self.cb_ss, *self.dopo):
            w.setEnabled(True)
        self.b_avvia.setText("▶ Nuova estrazione")

    # ---------------------------------------------------------------- dopo l'estrazione
    def _testo(self) -> str:
        g = self.g
        righe = []
        for i, r in enumerate(self.risultati, 1):
            num = " ".join(f"{x:2d}" for x in r["numeri"])
            if g.is_ej:
                extra = f"   Euronumeri {' '.join(map(str, r['extra']))}" if r["extra"] else ""
            else:
                extra = f"   SuperStar {r['extra'][0]}" if r["extra"] else ""
            pref = "Sistema" if self.modo == "sistema" else f"{i:2d})"
            righe.append(f"{pref} {num}{extra}")
        return "\n".join(righe)

    def copia(self):
        QApplication.clipboard().setText(self._testo())
        self.scena.testo = "Copiate negli appunti."

    def stampa(self):
        from .stampa import stampa
        titolo = ("Sistema casuale" if self.modo == "sistema" else "Combinazioni casuali") + f" – {self.g.nome}"
        stampa(self, titolo, "Estratte con la macchina di Pensiero Magico\n\n" + self._testo(), titolo)

    def verifica(self):
        from .statistiche import FinestraVerificaColonne
        cols = [r["numeri"] + (r["extra"] if self.g.is_ej else []) for r in self.risultati]
        FinestraVerificaColonne(self.arch, self, cols).exec()

    def registra(self):
        from .giocate import registra
        if self.risultati:
            registra(self.arch, self, [r["numeri"] for r in self.risultati], [r["extra"] for r in self.risultati],
                     "Macchina dell'estrazione")

    def _sistema(self, tipo: str, garanzia: int) -> sis.Sistema:
        r = self.risultati[0]
        nota = "Numeri estratti con la macchina di Pensiero Magico"
        if self.g.is_ej and r["extra"]:
            nota += f"; Euronumeri estratti: {r['extra'][0]} e {r['extra'][1]}"
        return sis.Sistema(nome="", tipo=tipo, gioco=self.g.codice, numeri=list(r["numeri"]), garanzia=garanzia,
                           note=nota)

    def sviluppa(self):
        if not self.risultati:
            return
        from .sistemi import ULTIMO, FinestraSviluppo
        gar = self.c_tipo.currentData() or 0
        s = self._sistema("immediato" if gar else "ridotto", gar)
        if not gar:
            s.tipo = "condizionato"                       # senza condizioni = integrale
        try:
            sv = sis.sviluppa(s)
        except Exception as ex:
            QMessageBox.warning(self, "Sviluppo", str(ex))
            return
        s.colonne = sv.colonne.tolist()
        s.info = {"integrale": sv.integrale, "possibili": sv.possibili}
        ULTIMO[self.g.codice] = (s, sv.possibili_colonne)
        FinestraSviluppo(self.arch, s, sv.possibili_colonne, self).exec()

    def editor(self):
        if self.risultati and self.apri_editor:
            s = self._sistema("condizionato", 0)
            self.accept()
            self.apri_editor("condizionato", s)

    def closeEvent(self, ev):
        self.scena.timer.stop()
        self.scena.suoni.chiudi()
        super().closeEvent(ev)

    def reject(self):
        self.scena.timer.stop()
        self.scena.suoni.chiudi()
        super().reject()

    def accept(self):
        self.scena.timer.stop()
        self.scena.suoni.chiudi()
        super().accept()
