"""Test della logica dell'app Android (mobile/servizi.py), senza grafica e senza rete."""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mobile"))

import servizi  # noqa: E402
from pmse.core import claude_ai, internet, magico  # noqa: E402
from pmse.core.db import Archivio  # noqa: E402
from pmse.core.gioco import EJ, SE  # noqa: E402
from pmse.core.modello import Estrazione  # noqa: E402


def estrazioni(g, n, seme=3, inizio=date(2020, 1, 2)):
    rnd = random.Random(seme)
    out, d = [], inizio
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


@pytest.fixture
def finto_internet(monkeypatch):
    """scarica_anni restituisce estrazioni sintetiche fino a una certa quantità (impostabile)."""
    stato = {"n": {"SE": 300, "EJ": 200}, "anni": []}

    def scarica(anni, avanzamento=None, interrompi=None, gioco=SE):
        stato["anni"].append((gioco.codice, list(anni)))
        if avanzamento:
            avanzamento("prova", 1, 1)
        return estrazioni(gioco, stato["n"][gioco.codice])
    monkeypatch.setattr(internet, "scarica_anni", scarica)
    from pmse.core import vincite
    monkeypatch.setattr(vincite, "scarica", lambda date_c, *a, **k: {})      # niente rete nei test
    return stato


def test_giochi_separati(tmp_path, finto_internet):
    se = servizi.Servizio(tmp_path, SE)
    ej = servizi.Servizio(tmp_path, EJ)
    assert se.percorso.parent.name == "PensieroMagicoSE" and ej.percorso.parent.name == "PensieroMagicoEJ"
    se.aggiorna()
    assert se.conta() == 300 and ej.conta() == 0
    se.salva_ai("gemini", " chiave-se ", "gemini-3.8-flash")
    assert se.chiave("gemini") == "chiave-se" and ej.chiave("gemini") == ""
    assert ej.fornitore() == "gemini" and ej.modello("claude") == claude_ai.MODELLI[0][0]
    se.chiudi()
    ej.chiudi()
    with pytest.raises(Exception):          # l'archivio SE non si apre come EJ
        Archivio(tmp_path / "PensieroMagicoSE" / "archivio.db", gioco=EJ)
    servizi.ricorda_gioco(tmp_path, EJ)
    assert servizi.ultimo_gioco(tmp_path) is EJ
    assert servizi.ultimo_gioco(tmp_path / "nessuna") is SE


def test_aggiorna_genera_e_apprende(tmp_path, finto_internet):
    s = servizi.Servizio(tmp_path, SE)
    esito = s.aggiorna()
    assert esito.unione.nuove == 300 and finto_internet["anni"][0][1][0] == 1997
    assert s.aggiorna().unione.nuove == 0                     # nessun doppione
    r = s.genera()
    assert len(r.sestine) == 3 and all(len(x.numeri) == 6 for x in r.sestine)
    prev = s.previsioni_attuali()
    assert prev and prev[0]["sestine"] == [x.numeri for x in r.sestine]
    finto_internet["n"]["SE"] = 304                           # escono 4 nuove estrazioni
    esito = s.aggiorna()
    assert esito.unione.nuove == 4
    assert len(esito.valutazioni) == 4 and "Estrazione del" in esito.testo()
    assert s.previsioni_attuali() == []                       # serve una nuova previsione
    assert [e.data for e in s.elenco()][:2] == sorted([e.data for e in s.elenco()], reverse=True)[:2]
    s.chiudi()


def test_verifica_e_ai_ej(tmp_path, finto_internet, monkeypatch):
    s = servizi.Servizio(tmp_path, EJ)
    s.aggiorna()
    with pytest.raises(ValueError):
        servizi.Servizio(tmp_path / "vuoto", EJ).verifica(10)
    es, nota = s.verifica(20, apprendi=True)
    assert es.prove == 20 and "Apprendimento" in nota
    assert s.arch.leggi_impostazione(claude_ai.CHIAVE_VERIFICA)
    es2, nota2 = s.verifica(20, apprendi=True)
    assert "già stati studiati" in nota2

    visti = {}

    def finta_gemini(chiave, modello, dossier, gia_uscite, m, limiti, timeout=300, g=SE):
        visti.update(chiave=chiave, modello=modello, dossier=dossier, g=g)
        return claude_ai.RispostaClaude([[3, 11, 24, 38, 45]], 2, 9, ["perché sì"], "euro", "analisi", "",
                                        "bassa", modello)
    monkeypatch.setattr(claude_ai, "chiedi_a_gemini", finta_gemini)
    rc, base = s.chiedi_ai("gemini", " k ", "gemini-3.8-flash")
    assert visti["chiave"] == "k" and visti["g"] is EJ and visti["dossier"]
    testo = servizi.descrivi_risposta(rc, base, EJ)
    assert "Cinquina 1: 3 11 24 38 45" in testo and "Euronumeri 2 e 9" in testo
    r = s.applica_ai(rc, base, "gemini")
    assert r.sestine[0].numeri == [3, 11, 24, 38, 45]
    assert s.previsioni_attuali()[0]["origine"].startswith("Gemini")
    s.chiudi()


def test_lavoro_in_background(tmp_path, finto_internet):
    """Sul telefono aggiornamento e verifica girano in un thread separato."""
    import threading
    s = servizi.Servizio(tmp_path, SE)
    esiti = []
    t = threading.Thread(target=lambda: esiti.append(s.aggiorna()))
    t.start()
    t.join()
    assert esiti[0].unione.nuove == 300 and s.conta() == 300
    s.chiudi()


def test_contesto_ssl():
    import ssl
    from pmse.core.rete import contesto_ssl
    c = contesto_ssl()
    assert c.verify_mode == ssl.CERT_REQUIRED and c.check_hostname       # la verifica resta attiva
    try:
        import certifi  # noqa: F401
        assert c.cert_store_stats()["x509_ca"] > 50                       # certificati caricati
    except ImportError:
        pass


def test_laboratorio_servizio(tmp_path, finto_internet, monkeypatch):
    from pmse.core import laboratorio
    s = servizi.Servizio(tmp_path, SE)
    s.aggiorna()
    r = s.laboratorio(simulazioni=20)
    assert r.prove and "VERDETTO" in s.ultimo_laboratorio()
    visti = {}

    def finta(chiave, modello, dossier, *a, **k):
        visti["dossier"] = dossier
        return claude_ai.RispostaClaude([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12], [13, 14, 15, 16, 17, 18]],
                                        19, 20, [], "", "", "", "", modello)
    monkeypatch.setattr(claude_ai, "chiedi_a_gemini", finta)
    s.chiedi_ai("gemini", "k", "gemini-3.8-flash")
    assert "Laboratorio sulla casualità" in visti["dossier"]
    assert s.arch.leggi_impostazione(laboratorio.CHIAVE_LAB) in visti["dossier"]
    s.chiudi()


def test_sistemi_ridotti_servizio():
    import servizi
    from pmse.core.gioco import EJ, SE
    assert servizi.ridotti_disponibili(SE, 10, 0)[0] == (5, 15)
    s = servizi.sviluppa_ridotto(SE, [3, 7, 12, 18, 21, 33, 45, 56, 67, 78], [7], 1, True)
    assert s.colonne and all(7 in c for c in s.colonne)
    s2 = servizi.sviluppa_ridotto(EJ, range(1, 10), [], 2, False)
    assert s2.colonne and len(s2.colonne[0]) == 5
    nome, dati = servizi.documento(s, "pdf")
    assert nome.endswith(".pdf") and dati.startswith(b"%PDF-1.4") and dati.rstrip().endswith(b"%%EOF")
    nome, dati = servizi.documento(s2, "txt")
    assert nome.endswith(".txt") and "TABULATO DEL SISTEMA" in dati.decode("utf-8")
    import pytest
    with pytest.raises(ValueError):
        servizi.sviluppa_ridotto(SE, range(1, 31), [], 1, False)


def test_condizionati_e_casuali_servizio(tmp_path):
    from pmse.core import condizioni as cnd
    from tests.test_sistemi import archivio_finto
    for g in (SE, EJ):
        s = servizi.Servizio(tmp_path, g)
        s.arch.unisci(archivio_finto(g, 300))
        tipi = [t.codice for t in s.tipi_condizioni()]
        assert "pari" in tipi and not ("popolarita" in tipi and g is EJ)
        a = s.analizza("pari", 0)
        assert a.valori_80 and a.estrazioni > 200
        conds = [cnd.Condizione("pari", valori=a.valori_80), cnd.gruppo([1, 2, 3, 4], 0, 1)]
        x = s.sviluppa_condizionato(range(1, 16), [], conds, 0, 0)
        assert x.colonne and all(len(set(c) & {1, 2, 3, 4}) <= 1 for c in x.colonne)
        y = s.sviluppa_condizionato(range(1, 16), [], conds, 0, 1)
        assert 0 < len(y.colonne) < len(x.colonne) and y.tipo == "condizionato_ridotto"
        cs = servizi.combinazioni_casuali(g, 4)
        assert len(cs) == 4 and all(len(set(c)) == g.k and max(c) <= g.n for c in cs)
        ns = servizi.numeri_casuali(g, 12)
        assert len(set(ns)) == 12
        with pytest.raises(ValueError):
            s.sviluppa_condizionato(range(1, 41), [], conds, 0, 0)
        s.chiudi()


def test_guida_testo():
    from pmse.core import guida
    from pmse.core.gioco import EJ, SE
    for g in (SE, EJ):
        c = guida.capitoli(g)
        assert len(c) == 14 and len({i for i, _, _ in c}) == 14
        tutto = guida.pagina(g)
        assert "Colonna magica" in tutto and "Magico Pensiero" in tutto
        assert ("Jolly" in tutto) != g.is_ej or "SuperStar" in tutto
        assert "cinquina" in tutto.lower() if g.is_ej else "sestina" in tutto.lower()
        corpo = tutto.split("</style>")[1]
        assert "{" not in corpo and "}" not in corpo


def test_guida_android():
    """La guida per il telefono: markup Kivy bilanciato, senza emoji né HTML, introduzione presente."""
    import re

    from pmse.core import guida
    from pmse.core.gioco import EJ, SE
    for g in (SE, EJ):
        intro = guida.intro_android(g)
        assert "Archivio" in intro and "Impostazioni" in intro and g.codice in intro
        for cod, titolo, html in guida.capitoli(g):
            k = guida.a_kivy(html)
            assert k and "<" not in k and "{" not in k, cod
            for tag in ("b", "i", "color"):
                assert len(re.findall(rf"\[{tag}[=\]]", k)) == len(re.findall(rf"\[/{tag}\]", k)), (cod, tag)
            assert not re.search("[\U0001F000-\U0001FFFF☀-➿️]", k), cod
            assert not re.search("[\U0001F000-\U0001FFFF☀-➿️]", guida._pulisci_simboli(titolo))
    assert guida.a_kivy("<h2>Titolo</h2><p>Uno [x] &amp; due</p><ul><li>a</li><li>b</li></ul>") == \
        "[b][color=#00653B]Titolo[/color][/b]\n\nUno &bl;x&br; &amp; due\n• a\n• b"
