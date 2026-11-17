# Pensiero Magico SE / Pensiero Magico EJ

Un unico eseguibile con due programmi, scelti dal menu in alto a sinistra:
- **Pensiero Magico SE** – SuperEnalotto (6 numeri su 90, Jolly, SuperStar): Magico Pensiero propone 3 sestine + Jolly + SuperStar;
- **Pensiero Magico EJ** – Eurojackpot (5 numeri su 50 + 2 Euronumeri da 1 a 12): Magico Pensiero propone 1 cinquina + 2 Euronumeri.

I due programmi hanno menu, analisi e algoritmi identici (adattati al gioco) ma sono **rigidamente separati**: cartelle dati distinte (`%APPDATA%\PensieroMagicoSE` e `%APPDATA%\PensieroMagicoEJ`), archivi, impostazioni, analisi personalizzate, previsioni, apprendimento e chiave di Claude indipendenti. Un archivio è legato al suo gioco e non può essere aperto dall'altro.
Fonte Internet EJ: archivio annuale di euro-jackpot.net (dal 23/03/2012; Euronumeri da 1 a 8 fino al 3/10/2014, da 1 a 10 fino al 18/3/2022, poi da 1 a 12).


Applicazione per Windows che gestisce l'archivio delle estrazioni del SuperEnalotto, esegue analisi sullo storico e, nelle prossime fasi, produrrà con l'algoritmo **Magico Pensiero** 3 sestine con Jolly e SuperStar.

## Scaricare il programma
Ogni modifica caricata su GitHub genera automaticamente l'eseguibile:
**Releases → l'ultima "Pensiero Magico SE (build N)" → `PensieroMagicoSE.exe`**.
Non serve installare niente: basta avviare il file. Al primo avvio Windows potrebbe mostrare l'avviso SmartScreen ("App non riconosciuta"): clicca *Ulteriori informazioni → Esegui comunque*.

L'archivio viene salvato in `%APPDATA%\PensieroMagicoSE\archivio.db`.

## Versione 0.4 – Analisi delle previsioni e apprendimento
Da quando si installa questa versione, ogni nuova estrazione che entra in archivio viene analizzata automaticamente: il programma rifà il calcolo di Magico Pensiero "com'era prima", guarda in che posizione ogni voce aveva messo i numeri usciti, controlla se i filtri avrebbero scartato la combinazione vincente e confronta le sestine salvate (dell'algoritmo e di Claude) con quella uscita. Il risultato è un elenco di **positivi** e **mancanze** (menu Magico Pensiero → Analisi delle previsioni e apprendimento).
L'algoritmo si corregge da solo: i pesi effettivi delle voci si spostano verso quelle che, sommando tutte le estrazioni valutate, hanno visto i numeri usciti meglio del caso (conta solo lo scarto oltre ±1,5 deviazioni standard, così le oscillazioni casuali non lo sbilanciano) e i filtri che scartano troppo spesso le vere vincenti vengono allentati. Si può allenare subito sul passato e azzerare. Le lezioni vengono passate anche a Claude.
Nella finestra di Claude: pulsante **Prova la chiave** e campo facoltativo **ID workspace**.

## Versione 0.3.1 – Somiglianza con l'archivio
Nuova analisi *Somiglianza con l'archivio*: per ogni combinazione vincente calcola il massimo di numeri in comune con una qualsiasi estrazione precedente e ricava l'intervallo consigliato (di solito 3-4). Magico Pensiero scarta le sestine fuori da questo intervallo (automatico o fissato a 3/4/5 nelle impostazioni), Claude riceve la regola come obbligatoria e, se non la rispetta, gli viene chiesto di correggere la risposta. Nella ricerca di sestine un pulsante applica i limiti consigliati.

## Versione 0.3 – Magico Pensiero + Claude
Menu Magico Pensiero → *Magico Pensiero + Claude* (o pulsante 🤖 Claude in home). Il programma calcola la proposta dell'algoritmo, prepara un dossier statistico dell'archivio (ultime estrazioni, statistiche per numero, forma delle sestine, coppie forti, candidate dell'algoritmo, SuperStar, esito della verifica storica) e lo invia a Claude tramite la Claude API. Claude valuta, scarta ciò che ritiene meno plausibile e sceglie le 3 sestine, il Jolly e il SuperStar con le motivazioni. La scelta si può mostrare in home e viene salvata nello storico delle previsioni accanto a quella dell'algoritmo, così nel tempo si confrontano i risultati reali.

Serve una chiave API personale della Claude Console (platform.claude.com): l'uso dell'API è a pagamento e separato dall'abbonamento a claude.ai. La chiave resta salvata solo sul computer dell'utente. Con "Mostra i dati che verranno inviati" si vede esattamente cosa riceve Claude.

## Fase 2 (versione 0.2)
- **Nuove analisi**: Consecutività numerica, Somme, Sequenze, Pari e dispari, Posizioni. In ogni tabella un clic su una riga evidenzia sulla griglia i numeri interessati.
- **Costruttore di analisi personalizzate** (Analisi → Costruttore): ricette fatte di misure pesate (frequenza, ritardo, tendenza, numeri successivi, posizione, numeri amici, giorno della settimana, Jolly, SuperStar…) e filtri (parità, intervallo, decine, finali, numeri usciti di recente). Le ricette salvate compaiono nel menu Analisi e si possono usare in Magico Pensiero.
- **Le mie sestine** (Analisi → Le mie sestine): confronto di sestine dell'utente con tutto l'archivio (punti massimi, quante volte avrebbero fatto 2-3-4-5, ultima volta con almeno 3 numeri, caratteristiche) e ricerca di sestine con caratteristiche date (mai uscite, al massimo N numeri in comune con qualsiasi estrazione, somma, pari, alti, consecutivi, decine, numeri obbligatori/esclusi, probabilità pesata con un'analisi).
- **Magico Pensiero 0.1** (bozza): punteggio dei numeri da cinque voci (eco delle estrazioni precedenti, affinità con l'ultima estrazione, tendenza, maturità del ritardo, frequenza storica) più le analisi personalizzate; generazione delle 3 sestine con controllo della forma; Jolly e SuperStar; spiegazione, impostazioni, verifica storica contro sestine casuali, storico delle previsioni.

## Fase 1
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
