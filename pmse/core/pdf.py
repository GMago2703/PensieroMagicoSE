"""PDF di solo testo, scritto a mano (nessuna libreria): carattere Courier, A4, pagine numerate.

Serve all'app Android per salvare il tabulato dei sistemi senza dipendenze in più. Il carattere si
rimpicciolisce da solo perché la riga più lunga entri nella pagina.
"""
from __future__ import annotations

A4 = (595.0, 842.0)          # punti
MARGINE = 36.0


SOSTITUZIONI = str.maketrans({"→": "->", "←": "<-", "≥": ">=", "≤": "<=", "✔": "v", "★": "*", "★": "*"})


def _esc(t: str) -> bytes:
    b = t.translate(SOSTITUZIONI).encode("cp1252", errors="replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def crea(titolo: str, testo: str) -> bytes:
    righe = testo.replace("\t", "    ").splitlines() or [""]
    larga = max(len(r) for r in righe)
    utile_x = A4[0] - 2 * MARGINE
    corpo = min(10.0, max(5.0, utile_x / (max(larga, 60) * 0.6)))        # Courier: larghezza 0,6 em
    interl = corpo * 1.18
    alto = A4[1] - 2 * MARGINE - 40
    per_pagina = max(1, int(alto // interl))
    pagine = [righe[i:i + per_pagina] for i in range(0, len(righe), per_pagina)] or [[]]

    oggetti: list[bytes] = []

    def nuovo(b: bytes) -> int:
        oggetti.append(b)
        return len(oggetti)

    catalogo = nuovo(b"")                 # 1, riempito alla fine
    radice_pagine = nuovo(b"")            # 2
    f_normale = nuovo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    f_grassetto = nuovo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>")
    figli = []
    for n, pag in enumerate(pagine, 1):
        y0 = A4[1] - MARGINE
        flusso = [b"BT", b"/F2 12 Tf", f"{MARGINE:.1f} {y0 - 12:.1f} Td".encode(), b"(" + _esc(titolo) + b") Tj",
                  b"ET", b"BT", f"/F1 {corpo:.2f} Tf".encode(), f"{interl:.2f} TL".encode(),
                  f"{MARGINE:.1f} {y0 - 36:.1f} Td".encode()]
        for r in pag:
            flusso.append(b"(" + _esc(r) + b") '")
        flusso += [b"ET", b"BT", b"/F1 8 Tf", f"{A4[0] / 2 - 30:.1f} {MARGINE / 2:.1f} Td".encode(),
                   b"(" + _esc(f"Pagina {n} di {len(pagine)}") + b") Tj", b"ET"]
        dati = b"\n".join(flusso)
        contenuto = nuovo(b"<< /Length %d >>\nstream\n" % len(dati) + dati + b"\nendstream")
        figli.append(nuovo(
            f"<< /Type /Page /Parent {radice_pagine} 0 R /MediaBox [0 0 {A4[0]:.0f} {A4[1]:.0f}] "
            f"/Resources << /Font << /F1 {f_normale} 0 R /F2 {f_grassetto} 0 R >> >> "
            f"/Contents {contenuto} 0 R >>".encode()))
    oggetti[catalogo - 1] = f"<< /Type /Catalog /Pages {radice_pagine} 0 R >>".encode()
    oggetti[radice_pagine - 1] = (f"<< /Type /Pages /Count {len(figli)} /Kids [" +
                                  " ".join(f"{k} 0 R" for k in figli) + "] >>").encode()
    info = nuovo(b"<< /Title (" + _esc(titolo) + b") /Producer (Pensiero Magico) >>")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    pos = []
    for i, o in enumerate(oggetti, 1):
        pos.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(oggetti) + 1}\n0000000000 65535 f \n".encode()
    for p in pos:
        out += f"{p:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(oggetti) + 1} /Root {catalogo} 0 R /Info {info} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)
