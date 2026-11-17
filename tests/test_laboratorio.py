"""Laboratorio sulla casualità: niente falsi allarmi su archivi casuali, difetti inseriti scoperti."""
import random
from datetime import date, timedelta

from pmse.core import laboratorio as L
from pmse.core.gioco import EJ, SE
from pmse.core.modello import Estrazione


def archivio(n, difetto=None, seme=1):
    rnd, out, d, prec = random.Random(seme), [], date(1998, 1, 3), None
    while len(out) < n:
        if d.weekday() in (1, 3, 5):
            pesi = [0.0] + [1.0] * 90
            if difetto == "ordinati" and rnd.random() < 0.4:   # archivio pubblicato in parte già ordinato
                nums_ord = True
            else:
                nums_ord = False
            if difetto == "peso":
                pesi[7] = 1.6
            if difetto == "memoria" and prec:
                for x in prec:
                    pesi[x] = 2.0
            nums = []
            while len(nums) < 6:
                x = rnd.choices(range(91), weights=pesi)[0]
                if x not in nums:
                    nums.append(x)
            if nums_ord:          # quasi ordinati: crescenti con una sola coppia scambiata
                nums = sorted(nums)
                i = rnd.randrange(5)
                nums[i], nums[i + 1] = nums[i + 1], nums[i]
            resto = [x for x in range(1, 91) if x not in nums]
            out.append(Estrazione(d, nums, rnd.choice(resto), rnd.randint(1, 90)))
            prec = nums
        d += timedelta(days=1)
    return out


def test_statistica_di_base():
    assert abs(L.chi2_p(89, 89) - 0.48) < 0.03
    assert abs(L.chi2_p(3.84, 1) - 0.05) < 0.002
    assert abs(L.norm_p2(1.96) - 0.05) < 0.001
    assert L.holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]


def test_archivio_casuale_nessuna_anomalia():
    r = L.esegui(archivio(2500), SE, simulazioni=40)
    assert len(r.epoche) == 2 and not r.anomalie
    assert {p.gruppo for p in r.prove} == {"Dati", "Macchina", "Memoria", "Previsione"}
    assert "VERDETTO" in r.testo() and "Nessuna anomalia" in r.testo()
    assert "nessuna anomalia" in L.riassunto_per_ai(r)


def test_difetti_scoperti():
    r = L.esegui(archivio(2500, "peso"), SE, simulazioni=40)
    assert any(p.nome == "Il numero più anomalo" and "il 7 " in p.risultato for p in r.anomalie)
    r = L.esegui(archivio(2500, "memoria"), SE, simulazioni=40)
    nomi = {p.nome for p in r.anomalie}
    assert "Numeri ripetuti dal concorso precedente" in nomi
    assert "Ripetere i numeri appena usciti" in nomi            # la regola giusta batte il caso


def test_archivio_in_parte_ordinato():
    """Se l'archivio pubblica parte delle sestine già ordinate, le 'anomalie di posizione' sono dei dati."""
    r = L.esegui(archivio(2500, "ordinati"), SE, simulazioni=40)
    assert r.epoche_ordine_inaffidabile
    assert any(p.nome.startswith("Posizione di uscita") for p in r.anomalie)      # il test le vede...
    assert not any(p.nome.startswith(("Posizione di uscita", "Palline vicine")) or p.gruppo == "Dati"
                   for p in r.anomalie_vere)                                    # ...ma non sono della macchina
    assert "non è credibile" in r.testo()


def test_eurojackpot():
    rnd, ej, d = random.Random(3), [], date(2012, 3, 23)
    while len(ej) < 700:
        if d.weekday() in (1, 4):
            n = rnd.sample(range(1, 51), 5)
            e = rnd.sample(range(1, EJ.euro_max(d) + 1), 2)
            ej.append(Estrazione(d, n, e[0], e[1], gioco=EJ))
        d += timedelta(days=1)
    r = L.esegui(ej, EJ, simulazioni=30)
    assert r.gioco == "Eurojackpot" and len(r.epoche) == 1 and not r.anomalie
