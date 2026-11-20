"""Colonne diverse per ogni utente: codice personale, livelli di variazione, opzione «poco giocate»."""
from pmse.core import magico, personale
from pmse.core.db import Archivio
from pmse.core.gioco import EJ, SE
from tests.test_sistemi import archivio_finto


def _imp(tmp_path, g, nome, livello):
    a = Archivio(tmp_path / f"{nome}_{g.codice}.db", g)
    a.unisci(archivio_finto(g, 300))
    imp = personale.applica(a, magico.Impostazioni.predefinite(g))
    imp.variazione = livello
    return a, imp


def _colonne(a, imp):
    return [s.numeri for s in magico.genera(a.sestine(), imp).sestine]


def test_codice_stabile_e_rigenerabile(tmp_path):
    a, _ = _imp(tmp_path, SE, "u", "moderata")
    c1 = personale.codice(a)
    assert c1 and personale.codice(a) == c1
    assert personale.rigenera(a) != c1 and personale.codice(a) != c1
    assert len(personale.mostra(c1).split("-")) == 2


def test_utenti_diversi_colonne_diverse_stesso_utente_stesse(tmp_path):
    for g in (SE, EJ):
        for livello in ("moderata", "media", "forte"):
            risultati = []
            for i, codice in enumerate(("0a1b2c3d4e5f6071", "99aa88bb77cc66dd", "1234567890abcdef",
                                        "fedcba0987654321")):
                a, imp = _imp(tmp_path, g, f"u{i}", livello)
                imp.codice_personale = codice
                col = _colonne(a, imp)
                assert col == _colonne(a, imp)                      # stesso utente: stesse colonne
                for c in col:                                       # sempre colonne valide
                    assert len(set(c)) == g.k and all(1 <= n <= g.n for n in c)
                risultati.append(tuple(map(tuple, col)))
            assert len(set(risultati)) >= 3, (g.codice, livello)    # utenti diversi: colonne quasi sempre diverse


def test_nessuna_variazione_uguale_per_tutti(tmp_path):
    a1, i1 = _imp(tmp_path, SE, "u1", "nessuna")
    a2, i2 = _imp(tmp_path, SE, "u2", "nessuna")
    assert _colonne(a1, i1) == _colonne(a2, i2)


def test_variazione_non_modifica_le_impostazioni_salvate(tmp_path):
    a, imp = _imp(tmp_path, SE, "u", "forte")
    pesi, nit = dict(imp.pesi), imp.nitidezza
    magico.genera(a.sestine(), imp)
    assert imp.pesi == pesi and imp.nitidezza == nit
    v = personale.variato(imp)
    assert v.pesi != pesi and abs(sum(v.pesi.values()) - sum(pesi.values())) < 1e-9


def test_popolari_attivo_per_impostazioni_vecchie():
    assert magico.Impostazioni.predefinite(SE).evita_popolari is True
    vecchio = magico.Impostazioni.da_json('{"evita_popolari": false, "nitidezza": 3.0}', SE)
    assert vecchio.evita_popolari is True and vecchio.variazione == "moderata"
    nuovo = magico.Impostazioni.da_json('{"evita_popolari": false, "variazione": "media"}', SE)
    assert nuovo.evita_popolari is False and nuovo.variazione == "media"
