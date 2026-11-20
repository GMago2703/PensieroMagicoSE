"""Quadri e condizioni personalizzate: regole, analisi, raccolta «Le mie condizioni»."""
import numpy as np

from pmse.core import condizioni as cnd
from pmse.core import condizioni_utente as cu
from pmse.core import sistemi as sis
from pmse.core.db import Archivio
from pmse.core.gioco import EJ, SE
from tests.test_sistemi import archivio_finto

G3 = [{"numeri": [1, 2, 3], "minimo": 1, "massimo": 3}, {"numeri": [11, 12], "minimo": 1, "massimo": 2},
      {"numeri": [21], "minimo": 1, "massimo": 1}]
C = np.array([[1, 2, 3, 11, 12, 21],       # A, B, C verificati  -> 3
              [1, 11, 40, 50, 60, 70],      # A, B               -> 2
              [1, 40, 50, 60, 70, 80],      # A                  -> 1
              [40, 50, 60, 70, 80, 90]])    # nessuno            -> 0


def _arch(tmp_path, g, n=200):
    a = Archivio(tmp_path / f"cu_{g.codice}.db", g)
    a.unisci(archivio_finto(g, n))
    return a


def test_regole_dei_quadri():
    ctx = cnd.Contesto(SE)
    atteso = {"tutte": [1, 0, 0, 0], "almeno_una": [1, 1, 1, 0], "una_sola": [0, 0, 1, 0],
              "nessuna": [0, 0, 0, 1], "tutte_tranne_una": [0, 1, 0, 0], "pari": [0, 1, 0, 1],
              "dispari": [1, 0, 1, 0]}
    for regola, v in atteso.items():
        assert cnd.quadri(G3, regola).rispetta(C, ctx).astype(int).tolist() == v, regola
    assert cnd.quadri(G3, "almeno_n", 2).rispetta(C, ctx).astype(int).tolist() == [1, 1, 0, 0]
    assert cnd.quadri(G3, "esattamente_n", 2).rispetta(C, ctx).astype(int).tolist() == [0, 1, 0, 0]
    assert cnd.quadri(G3, "al_massimo_n", 1).rispetta(C, ctx).astype(int).tolist() == [0, 0, 1, 1]


def test_descrizione_e_json_dei_quadri():
    q = cnd.quadri(cnd.decine(SE), "almeno_n", 3, "Le mie decine")
    assert q.descrivi().startswith("«Le mie decine»: Quadri (9 gruppi)") and "almeno 3" in q.descrivi()
    q2 = cnd.da_json(cnd.a_json([q]))[0]
    assert q2.regola == "almeno_n" and q2.nome == "Le mie decine" and len(q2.gruppi) == 9
    assert (q2.minimo, q2.massimo) == (3, 9)


def test_gruppi_comuni():
    for g in (SE, EJ):
        ins = cnd.insiemi_comuni(g)
        assert ins["Finale 1"] == [x for x in range(1, g.n + 1) if x % 10 == 1]
        assert ins["Decina 1-10"] == list(range(1, 11)) and len(ins["Tutti i numeri"]) == g.n
        assert len(cnd.decine(g)) == (g.n + 9) // 10 and len(cnd.finali(g)) == 10
        assert sorted(sum((x["numeri"] for x in cnd.decine(g)), [])) == list(range(1, g.n + 1))


def test_analisi_dei_quadri(tmp_path):
    for g in (SE, EJ):
        a = _arch(tmp_path, g)
        ctx = sis.contesto_da_archivio(a)
        an = cnd.analizza_quadri(cnd.decine(g), ctx)
        assert an.estrazioni == a.conta() and sum(r[1] for r in an.righe) == a.conta()
        assert abs(sum(r[3] for r in an.righe) - 100) < 1e-6
        assert an.copertura[0] <= an.piu_frequente <= an.copertura[1]
        a.chiudi()


def test_raccolta_le_mie_condizioni(tmp_path):
    a = _arch(tmp_path, SE)
    assert cu.carica(a) == []
    q = cnd.quadri(G3, "almeno_una")
    v = cu.aggiungi(a, "I miei tre", q)
    ins = cnd.gruppo([7, 17, 27], 1, 2)
    cu.aggiungi(a, "Fortunati", ins)
    assert [x["nome"] for x in cu.carica(a)] == ["I miei tre", "Fortunati"]
    assert [x["nome"] for x in cu.carica(a, ("quadri",))] == ["I miei tre"]
    c = cu.condizione(v)
    assert c.nome == "I miei tre" and c.regola == "almeno_una" and c.attiva
    cu.aggiungi(a, "i miei tre", cnd.quadri(G3, "tutte"))              # stesso nome e tipo: sostituisce
    assert len(cu.carica(a)) == 2 and cu.condizione(cu.carica(a)[0]).regola == "tutte"
    d = cu.duplica(a, v["id"])
    assert d["nome"].endswith("(copia)") and len(cu.carica(a)) == 3
    cu.rinomina(a, v["id"], "Nuovo nome")
    assert cu.carica(a)[0]["nome"] == "Nuovo nome"
    cu.elimina(a, v["id"])
    assert len(cu.carica(a)) == 2
    a.chiudi()


def test_raccolte_separate_per_gioco(tmp_path):
    a, b = _arch(tmp_path, SE), _arch(tmp_path, EJ)
    cu.aggiungi(a, "Solo SE", cnd.gruppo([1, 2, 3], 1, 3))
    assert len(cu.carica(a)) == 1 and cu.carica(b) == []
    a.chiudi()
    b.chiudi()


def test_condizione_personale_nei_sistemi(tmp_path):
    """Una condizione personale si comporta come le altre nel filtro dei sistemi e si salva con il sistema."""
    a = _arch(tmp_path, SE)
    ctx = sis.contesto_da_archivio(a)
    q = cnd.quadri(cnd.finali(SE), "almeno_n", 3, "Finali")
    ok = cnd.filtra(C, [q], ctx)
    assert ok.dtype == bool and len(ok) == len(C)
    s = sis.Sistema(tipo="condizionato", gioco="SE", numeri=list(range(1, 21)), garanzia=0)
    s.condizioni = cnd.a_json([q])
    assert s.lista_condizioni()[0].nome == "Finali" and s.lista_condizioni()[0].regola == "almeno_n"
    a.chiudi()


def test_quadri_speciali(tmp_path):
    for g in (SE, EJ):
        a = _arch(tmp_path, g)
        ctx = sis.contesto_da_archivio(a)
        ctx.vincenti = {e.data for e in ctx.estrazioni[::10]}          # finte vincenti: una ogni dieci
        for quale in cnd.ARCHIVI_SPECIALI:
            an = cnd.analizza_speciale(ctx, quale)
            assert an.estrazioni == len(ctx.estrazioni) and sum(r[1] for r in an.righe) == an.estrazioni
        assert len(ctx.righe_archivio("vincenti")) + len(ctx.righe_archivio("senza_vincenti")) == len(ctx.estrazioni)
        # una colonna identica a un'estrazione ha tutti i numeri in comune con l'archivio completo
        C = np.array([ctx.ultime[5], ctx.ultime[0]], dtype=np.int64)
        assert cnd.massimo_in_comune(C, ctx, "completo").tolist() == [g.k, g.k]
        voci = cnd.voci_speciali_vuote()
        assert cnd.quadri_speciali(voci).rispetta(C, ctx).all()             # nessun quadro attivo: accetta tutto
        voci[0].update(attivo=True, modo="non_ammessi", valori=[g.k])       # niente colonne già uscite
        c = cnd.quadri_speciali(voci)
        assert not c.rispetta(C, ctx).any() and "NON ammessi" in c.descrivi()
        voci[0].update(modo="ammessi", valori=[g.k])
        assert cnd.quadri_speciali(voci).rispetta(C, ctx).all()
        c2 = cnd.da_json(cnd.a_json([cnd.quadri_speciali(voci, "x")]))[0]
        assert c2.codice == "quadri_speciali" and c2.gruppi[0]["valori"] == [g.k]
        a.chiudi()


def test_controllo_condizioni(tmp_path):
    a = _arch(tmp_path, SE)
    ctx = sis.contesto_da_archivio(a)
    rng = np.random.default_rng(3)
    C = np.sort(np.argsort(rng.random((5000, 90)), axis=1)[:, :6] + 1, axis=1)
    larga = cnd.gruppo(list(range(1, 91)), 0, 6)                   # sempre rispettata -> inoperante
    forte = cnd.gruppo(list(range(1, 31)), 3, 6)                   # scarta molte colonne
    inclusa = cnd.gruppo(list(range(1, 31)), 2, 6)                 # scarta un sottoinsieme di quelle di 'forte'
    spenta = cnd.gruppo([1, 2, 3], 3, 3)
    spenta.attiva = False
    r = cnd.controllo(C, [larga, forte, inclusa, spenta], ctx)
    st = {x.indice: x for x in r.righe}
    assert st[0].stato == "inoperante" and st[0].escluse == 0
    assert st[1].stato == "operante" and st[1].uniche > 0
    assert st[2].stato == "assorbita" and st[2].assorbita_da and st[2].uniche == 0
    assert st[3].stato == "disattivata"
    assert r.ammesse == int(cnd.filtra(C, [larga, forte, inclusa], ctx).sum())
    assert st[2].nuove_in_sequenza == 0 and st[1].nuove_in_sequenza == st[1].escluse
    assert "ASSORBITA" in cnd.testo_controllo(r)
    a.chiudi()
