# Pensiero Magico SE

Applicazione per Windows che gestisce l'archivio delle estrazioni del SuperEnalotto, esegue analisi sullo storico e, nelle prossime fasi, produrrà con l'algoritmo **Magico Pensiero** 3 sestine con Jolly e SuperStar.

## Scaricare il programma
Ogni modifica caricata su GitHub genera automaticamente l'eseguibile:
**Releases → l'ultima "Pensiero Magico SE (build N)" → `PensieroMagicoSE.exe`**.
Non serve installare niente: basta avviare il file. Al primo avvio Windows potrebbe mostrare l'avviso SmartScreen ("App non riconosciuta"): clicca *Ulteriori informazioni → Esegui comunque*.

L'archivio viene salvato in `%APPDATA%\PensieroMagicoSE\archivio.db`.

## Fase 1 (questa versione)
- **Home**: a sinistra la tabella dei 90 numeri selezionabili, a destra la tabella "Magico Pensiero".
- **Archivio**
  - consultazione con ordine crescente/decrescente, filtro per anno, ricerca di un numero;
  - *Aggiornamento archivio*: scheda per scorrere, inserire, modificare ed eliminare le estrazioni (montepremi e quote facoltativi);
  - *Importa da file* CSV/TXT/Excel con riconoscimento automatico del formato, anteprima, eliminazione dei duplicati e segnalazione dei conflitti;
  - esportazione CSV, verifica integrità, backup e ripristino.
- **Internet**: scaricamento completo dell'archivio dal 03/12/1997 e aggiornamento delle sole estrazioni mancanti (anche automatico all'avvio). Fonte: archivio pubblico annuale di superenalotto.com.
- **Analisi**: frequenze e ritardi, ritardatari, numeri successivi (nesso tra un'estrazione e le seguenti), numeri ripetuti, struttura delle sestine. Ogni analisi assegna un *punteggio* ai 90 numeri, che Magico Pensiero potrà combinare.
- **Magico Pensiero**: menu predisposto; l'algoritmo verrà sviluppato nelle prossime fasi.

## Formati di file riconosciuti in importazione
Una estrazione per riga, con data e almeno 7 numeri (sestina + Jolly, l'eventuale ottavo è il SuperStar). Esempi validi:
```
115;18/07/2026;1;28;52;62;79;86;61;31
18/07/2026,1,28,52,62,79,86,61,31
sabato 18 luglio 2026 1 28 52 62 79 86 61 31
2026-07-18 1 28 52 62 79 86 61 31
```
Le righe di intestazione e quelle non riconosciute vengono ignorate e mostrate nell'anteprima.

## Struttura del codice
- `pmse/core` – dati e logica, senza interfaccia (archivio SQLite, importatore, Internet, analisi)
- `pmse/ui` – finestre PySide6
- `tests` – test automatici, eseguiti a ogni build

Gioca responsabilmente: le estrazioni sono casuali e nessun programma può garantire vincite.
