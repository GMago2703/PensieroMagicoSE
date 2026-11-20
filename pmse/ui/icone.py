"""Icone colorate per i pulsanti: ogni funzione ha sempre la stessa icona in tutto il programma (SE ed EJ).

Il riconoscimento è dal testo del pulsante (Salva → 💾, Elimina → 🗑 ...). Un filtro installato sull'applicazione
decora ogni pulsante la prima volta che compare, quindi vale anche per le finestre future senza altro lavoro."""
from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QPushButton

# (espressione sul testo senza simboli iniziali e in minuscolo, icona). Vince la prima che corrisponde.
REGOLE: list[tuple[str, str]] = [
    (r"^(taglia)\b", "✂️"),
    (r"^(copia|duplica)\b", "📑"),
    (r"^(incolla)\b", "📋"),
    (r"^(elimina|cancella|rimuovi|scarta|svuota archivio)\b", "🗑️"),
    (r"^(svuota|pulisci|azzera)\b", "🧹"),
    (r"^(salva|memorizza|ok \(salva\))\b", "💾"),
    (r"^(carica|apri|scegli file|leggi da|sfoglia)\b", "📂"),
    (r"^(annulla|chiudi la sezione)\b", "↩️"),
    (r"^(chiudi|esci)\b", "🚪"),
    (r"^(sì|si|yes|ok|usa|conferma|applica il suggerimento)\b", "✅"),
    (r"^(no)\b", "❌"),
    (r"^(applica|importa nell'archivio|mostra in home|registra e|registra$)", "✅"),
    (r"^(aggiungi|nuovo|nuova|crea)\b", "➕"),
    (r"^(modifica|rinomina)\b", "✏️"),
    (r"^(stampa|tabulato)\b", "🖨️"),
    (r"^(esporta)\b", "📤"),
    (r"^(importa)\b", "📥"),
    (r"^(scarica)\b", "🌐"),
    (r"^(aggiorna)\b", "🔄"),
    (r"^(cerca|trova)\b", "🔎"),
    (r"^(genera casuali|usa le combinazioni della macchina)\b", "🎲"),
    (r"^(genera|chiedi)\b", "✨"),
    (r"^(registra)\b", "📝"),
    (r"^(mostra l'analisi)", "📊"),
    (r"^(analizza|analisi|rendimento|esegui analisi|statistic)", "📊"),
    (r"^(verifica|prova|avvia il laboratorio)\b", "🧪"),
    (r"^(avvia|esegui|sviluppa|simula|allena)\b", "▶️"),
    (r"^(ferma|stop|interrompi)\b", "⏹️"),
    (r"^(salta)\b", "⏭️"),
    (r"^(ripristina|ricarica)\b", "♻️"),
    (r"^(nascondi)\b", "🙈"),
    (r"^(note)\b", "🗒️"),
    (r"^(tutti|seleziona tutti)\b", "☑️"),
    (r"^(sposta su)\b", "⬆️"),
    (r"^(sposta giù|sposta giu)\b", "⬇️"),
    (r"^(vedi|mostra)\b", "👁️"),
    (r"^(aiuto|guida)\b", "❓"),
    (r"^(archivio)\b", "🗃️"),
    (r"^(controllo)\b", "🩺"),
    (r"^(ricalcola)\b", "🔄"),
    (r"^sposta ▶", "➡️"),
    (r"^sposta$", "⬅️"),
]
_COMPILATE = [(re.compile(r), e) for r, e in REGOLE]
_INIZIO = re.compile(r"^[^\w«\"'(]+", re.UNICODE)
_CACHE: dict[str, QIcon] = {}
LATO = 24


def pulisci(testo: str) -> str:
    """Il testo senza mnemonici (&) né simboli o emoji iniziali."""
    return _INIZIO.sub("", testo.replace("&", "")).strip()


def emoji_per(testo: str) -> str | None:
    t = pulisci(testo).lower()
    if not t or t.isdigit():
        return None
    for r, e in _COMPILATE:
        if r.search(t):
            return e
    return None


def icona(emoji: str) -> QIcon:
    """L'icona colorata (emoji disegnata a colori) di dimensione fissa, con cache."""
    if emoji not in _CACHE:
        scala = 2
        pm = QPixmap(LATO * scala, LATO * scala)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.TextAntialiasing)
        f = QFont("Segoe UI Emoji")
        f.setPixelSize(int(LATO * scala * 0.78))
        p.setFont(f)
        p.drawText(QRectF(0, 0, LATO * scala, LATO * scala), Qt.AlignCenter, emoji)
        p.end()
        pm.setDevicePixelRatio(scala)
        _CACHE[emoji] = QIcon(pm)
    return _CACHE[emoji]


def decora(b: QPushButton) -> bool:
    """Mette l'icona al pulsante secondo la sua funzione. Restituisce True se l'ha messa."""
    if not isinstance(b, QPushButton) or b.property("senza_icona") or b.property("class") == "lato":
        return False
    if not b.icon().isNull():
        return False
    e = emoji_per(b.text())
    if not e:
        return False
    nuovo = pulisci(b.text())
    if nuovo and nuovo != b.text():
        b.setText(nuovo)
    b.setIcon(icona(e))
    b.setIconSize(QSize(LATO - 4, LATO - 4))
    b.setProperty("_icona", e)
    return True


class Decoratore(QObject):
    """Filtro sull'applicazione: decora ogni pulsante la prima volta che viene mostrato."""

    def eventFilter(self, obj, ev):          # noqa: N802 – nome imposto da Qt
        if ev.type() == QEvent.Show and isinstance(obj, QPushButton) and not obj.property("_decorato"):
            obj.setProperty("_decorato", True)
            try:
                decora(obj)
            except RuntimeError:
                pass
        return False


_FILTRO: Decoratore | None = None


def installa(app) -> None:
    global _FILTRO
    if _FILTRO is None:
        _FILTRO = Decoratore(app)
        app.installEventFilter(_FILTRO)
