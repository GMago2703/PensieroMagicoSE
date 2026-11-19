"""Disegna le icone dell'app Android (bianche su fondo trasparente, colorabili da Kivy).
Uso: python strumenti/disegna_icone.py  -> mobile/icone/*.png"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 768                      # si disegna grande e si riduce: bordi morbidi
OUT = 192
CARTELLA = os.path.join(os.path.dirname(__file__), "..", "mobile", "icone")
FONT = "/usr/share/fonts/opentype/inter/Inter-BlackItalic.otf"
B = (255, 255, 255, 255)
T = (0, 0, 0, 0)


def nuova():
    im = Image.new("RGBA", (S, S), T)
    return im, ImageDraw.Draw(im)


def salva(im, nome):
    im.resize((OUT, OUT), Image.LANCZOS).save(os.path.join(CARTELLA, nome + ".png"))


def stella(d, cx, cy, r, punte=4, interno=0.28, colore=B, rot=0):
    pts = []
    for i in range(punte * 2):
        a = rot + math.pi * i / punte - math.pi / 2
        rr = r if i % 2 == 0 else r * interno
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=colore)


def casa():
    im, d = nuova()
    d.polygon([(384, 90), (90, 360), (170, 360), (170, 670), (598, 670), (598, 360), (678, 360)], fill=B)
    d.rounded_rectangle((320, 450, 448, 670), 20, fill=T)          # porta
    d.rectangle((520, 130, 590, 290), fill=B)                      # camino
    salva(im, "home")


def archivio():
    im, d = nuova()
    for i, y in enumerate((110, 330, 550)):
        d.rounded_rectangle((120, y, 648, y + 190), 36, fill=B)
        d.rounded_rectangle((300, y + 70, 468, y + 110), 20, fill=T)  # maniglia
    salva(im, "archivio")


def magico():
    """MP scritto in modo "magico": lettere corsive con una scia di stelle (bacchetta)."""
    im, d = nuova()
    f = ImageFont.truetype(FONT, 420)
    d.text((395, 430), "MP", font=f, fill=B, anchor="mm")
    # scia curva sopra le lettere, che finisce in una stella
    for i in range(40):
        t = i / 39
        x = 70 + t * 560
        y = 250 - math.sin(t * math.pi) * 170 + t * 10
        r = 6 + 12 * t
        d.ellipse((x - r, y - r, x + r, y + r), fill=B)
    stella(d, 655, 240, 105, 4, 0.25)
    stella(d, 140, 640, 55, 4, 0.25)
    stella(d, 640, 655, 70, 4, 0.25)
    stella(d, 560, 90, 40, 4, 0.25)
    salva(im, "magico")


def sistemi():
    im, d = nuova()
    pieni = {0, 2, 4, 5, 7}
    for r in range(3):
        for c in range(3):
            x, y = 110 + c * 192, 110 + r * 192
            if r * 3 + c in pieni:
                d.rounded_rectangle((x, y, x + 160, y + 160), 34, fill=B)
            else:
                d.rounded_rectangle((x, y, x + 160, y + 160), 34, outline=B, width=26)
    salva(im, "sistemi")


def dado():
    im, d = nuova()
    dado_ = Image.new("RGBA", (S, S), T)
    dd = ImageDraw.Draw(dado_)
    dd.rounded_rectangle((150, 150, 618, 618), 90, fill=B)
    for x, y in ((260, 260), (508, 260), (384, 384), (260, 508), (508, 508)):
        dd.ellipse((x - 48, y - 48, x + 48, y + 48), fill=T)
    dado_ = dado_.rotate(14, resample=Image.BICUBIC)
    im.alpha_composite(dado_)
    stella(d, 640, 130, 70, 4, 0.25)
    stella(d, 120, 650, 45, 4, 0.25)
    salva(im, "casualita")


def aggiorna():
    im, d = nuova()
    for a0 in (20, 200):
        d.arc((130, 130, 638, 638), a0, a0 + 140, fill=B, width=72)
        a = math.radians(a0 + 140)
        cx, cy = 384 + 254 * math.cos(a), 384 + 254 * math.sin(a)
        tx, ty = -math.sin(a), math.cos(a)                     # direzione della freccia
        nx, ny = math.cos(a), math.sin(a)
        d.polygon([(cx + tx * 110, cy + ty * 110), (cx + nx * 105, cy + ny * 105),
                   (cx - nx * 105, cy - ny * 105)], fill=B)
    salva(im, "aggiorna")


def verifica():
    im, d = nuova()
    d.ellipse((90, 90, 520, 520), outline=B, width=64)
    d.line((470, 470, 680, 680), fill=B, width=110)
    d.ellipse((625, 625, 735, 735), fill=B)
    d.line((205, 310, 280, 390, 410, 230), fill=B, width=52, joint="curve")
    salva(im, "verifica")


def ai():
    im, d = nuova()
    d.rounded_rectangle((170, 170, 598, 598), 70, fill=B)
    for i in range(4):
        p = 240 + i * 96
        for (x0, y0, x1, y1) in ((p - 18, 80, p + 18, 170), (p - 18, 598, p + 18, 688),
                                 (80, p - 18, 170, p + 18), (598, p - 18, 688, p + 18)):
            d.rounded_rectangle((x0, y0, x1, y1), 14, fill=B)
    f = ImageFont.truetype(FONT, 230)
    d.text((384, 392), "AI", font=f, fill=T, anchor="mm")
    salva(im, "ai")


def laboratorio():
    im, d = nuova()
    d.polygon([(300, 100), (468, 100), (468, 330), (650, 640), (118, 640), (300, 330)], fill=B)
    d.rounded_rectangle((260, 80, 508, 140), 26, fill=B)
    d.polygon([(330, 160), (438, 160), (438, 340), (500, 450), (268, 450), (330, 340)], fill=T)
    for x, y, r in ((300, 540, 34), (420, 580, 26), (500, 530, 20)):
        d.ellipse((x - r, y - r, x + r, y + r), fill=T)
    salva(im, "laboratorio")


if __name__ == "__main__":
    os.makedirs(CARTELLA, exist_ok=True)
    for f in (casa, archivio, magico, sistemi, dado, aggiorna, verifica, ai, laboratorio):
        f()
    print("icone in", os.path.abspath(CARTELLA), file=sys.stderr)
