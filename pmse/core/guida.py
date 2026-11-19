"""Guida all'uso del programma (testo del menu Help → Guida). Un capitolo = (identificativo, titolo, HTML).
Il testo si adatta al gioco: SuperEnalotto (sestine) o Eurojackpot (cinquine + Euronumeri)."""
from __future__ import annotations

from .gioco import Gioco


def capitoli(g: Gioco) -> list[tuple[str, str, str]]:
    ej = g.is_ej
    C, CP = g.nome_comb, g.nome_comb_pl
    k, n = g.k, g.n
    app = g.nome_app
    nome = g.nome
    extra = ("i 2 Euronumeri (da 1 a 12)" if ej else "il Jolly e il SuperStar")
    prop = ("1 cinquina + 2 Euronumeri" if ej else "3 sestine + Jolly + SuperStar")
    c = []

    c.append(("inizio", "1. Per cominciare", f"""
<h2>Per cominciare</h2>
<p><b>{app}</b> è un programma che conserva l'archivio di tutte le estrazioni del {nome}, le studia con molte
analisi statistiche e, con l'algoritmo <b>Magico Pensiero</b>, propone {prop}. Serve anche a costruire
<b>sistemi</b>, a conservare e controllare le tue giocate e a vedere «come sarebbe andata» sul passato.</p>
<div class='av'><b>Una verità da tenere a mente.</b> Le estrazioni del lotto sono casuali: nessun programma può
prevedere i numeri e nessuna colonna ha più probabilità di un'altra di essere estratta. Il programma ti aiuta a
<i>scegliere con criterio</i>, a <i>non sprecare soldi</i> in colonne molto improbabili per la loro forma e a
<i>tenere ordine</i> in quello che giochi. Gioca solo ciò che puoi permetterti di perdere.</div>
<h3>I primi passi (5 minuti)</h3>
<ol>
<li><b>Scarica l'archivio.</b> Al primo avvio il programma chiede se scaricare da Internet tutte le estrazioni dal
{g.prima_estrazione.year}: rispondi <i>Sì</i> e attendi. Poi si aggiorna da solo a ogni avvio (si può disattivare dal
menu <i>Internet</i>).</li>
<li><b>Premi «✨ Genera»</b> nella parte destra della schermata principale: compaiono la proposta di Magico
Pensiero.</li>
<li><b>Premi «❓ Perché»</b> per leggere come sono nate: ogni numero ha il suo motivo.</li>
<li>Se ti piace una proposta, registrala come giocata (menu <i>Stampe</i> → «Combinazioni di Magico Pensiero» o
<i>Le mie giocate</i>) così potrai verificarla con le estrazioni successive.</li>
</ol>
<h3>Due programmi in uno</h3>
<p>In alto a sinistra il pulsante con il nome del programma permette di passare da <b>Pensiero Magico SE</b>
(SuperEnalotto) a <b>Pensiero Magico EJ</b> (Eurojackpot). I due sono <b>completamente separati</b>: archivio,
impostazioni, giocate e apprendimento non si mescolano mai.</p>
<h3>Dove sono i miei dati?</h3>
<p>In una cartella del tuo utente (la vedi in <i>Help → Informazioni</i>). Per sicurezza fai ogni tanto un backup
da <i>Impostazioni → Salva una copia dei dati</i>, oppure attiva le <i>Copie automatiche</i>.</p>
"""))

    c.append(("home", "2. La schermata principale", f"""
<h2>La schermata principale</h2>
<p>È divisa in due metà.</p>
<ul>
<li><b>A sinistra, la tabella dei {n} numeri:</b> cliccando i numeri li selezioni (diventano colorati). Con i numeri
selezionati puoi aprire <i>Analisi</i> o confrontare la tua {C} con tutto l'archivio (pulsante «📋 {g.C(plurale=True)}»).
«Tutti» seleziona tutti i numeri, «Azzera» toglie la selezione.</li>
<li><b>A destra, la tabella «Magico Pensiero»:</b> mostra la proposta dell'algoritmo con colori diversi per ogni
{C}. Pulsanti: «✨ Genera» (calcola), «❓ Perché» (spiegazione), «🤖 AI» (la stessa proposta rivista
dall'intelligenza artificiale).</li>
</ul>
<p>In alto compare l'ultima estrazione{'' if ej else ' e, se disponibile, il jackpot'}. Il menu in alto raccoglie tutte
le funzioni: questa guida le spiega una per una.</p>
"""))

    c.append(("archivio", "3. Archivio ed Internet", f"""
<h2>L'archivio delle estrazioni</h2>
<p>È la base di tutto: più è completo e aggiornato, più le analisi sono affidabili.</p>
<h3>Menu Internet</h3>
<ul>
<li><b>Aggiorna ora:</b> scarica solo le estrazioni che mancano. Usalo dopo ogni estrazione.</li>
<li><b>Scarica archivio completo:</b> riparte da zero dal {g.prima_estrazione.year}. Serve solo la prima volta o se
l'archivio è danneggiato.</li>
<li><b>Aggiorna automaticamente all'avvio:</b> spunta per non pensarci più.</li>
{'' if ej else "<li><b>★ Aggiorna i vincitori del 6:</b> completa i dati dei concorsi in cui qualcuno ha fatto 6.</li>"}
</ul>
<h3>Menu Archivio</h3>
<ul>
<li><b>Consulta archivio:</b> scorri le estrazioni, ordina dalla più recente o dalla più vecchia, filtra per anno,
cerca un numero.</li>
<li><b>Aggiornamento archivio (inserisci / modifica):</b> inserisci a mano un'estrazione, correggi o elimina.</li>
<li><b>Importa da file (CSV, TXT, Excel):</b> il programma riconosce da solo il formato, mostra un'anteprima, scarta
i duplicati e segnala i conflitti.</li>
<li><b>Esporta in CSV, Verifica integrità, Backup, Ripristina, Svuota:</b> manutenzione dell'archivio.
<i>Svuota</i> cancella tutto: usalo solo se sai cosa fai (fai prima un backup).</li>
</ul>
"""))

    c.append(("analisi", "4. Analisi e Statistiche", f"""
<h2>Analisi</h2>
<p>Ogni analisi studia l'archivio da un punto di vista e dà un <b>punteggio ai {n} numeri</b>: Magico Pensiero
combina questi punteggi. Apri il menu <i>Analisi</i> e scegli:</p>
<ul>
<li><b>Frequenze e ritardi:</b> quante volte è uscito ogni numero e da quanto manca.</li>
<li><b>Numeri ritardatari:</b> i più in ritardo.</li>
<li><b>Numeri successivi:</b> se dopo certi numeri tendono a uscirne altri.</li>
<li><b>Numeri ripetuti:</b> quanti numeri si ripetono da un'estrazione alla successiva.</li>
<li><b>Consecutività, Somme, Sequenze, Pari e dispari, Posizioni, Struttura:</b> la «forma» delle {CP} uscite.</li>
<li><b>Somiglianza con l'archivio:</b> quanti numeri in comune ha ogni {C} vincente con una qualsiasi estrazione
precedente (di solito pochi: le {CP} troppo simili al passato sono poco plausibili).</li>
<li><b>{'Euronumeri' if ej else 'Jolly e SuperStar'}:</b> studio dei numeri speciali.</li>
</ul>
<p>In ogni tabella <b>un clic su una riga</b> evidenzia i numeri interessati sulla griglia.</p>
<h3>Costruttore di analisi personalizzate</h3>
<p>Crea una tua «ricetta»: scegli misure (frequenza, ritardo, tendenza, numeri amici, giorno della settimana...) e
filtri (pari/dispari, intervalli, decine, finali...). La ricetta salvata compare nel menu Analisi e può essere
usata da Magico Pensiero.</p>
<h3>Le mie {CP} (menu Analisi)</h3>
<p>Scrivi o seleziona le tue {CP} e il programma le confronta con <b>tutto l'archivio</b>: punti massimi, quante volte
avrebbero fatto 2, 3, 4... , l'ultima volta che hanno fatto almeno 3, le caratteristiche. C'è anche la <b>ricerca</b>:
chiedi {CP} con caratteristiche precise (mai uscite, somma in un intervallo, quanti pari, numeri obbligatori o
esclusi...).</p>
{'' if ej else "<h3>★ I concorsi con il 6</h3><p>Confronta le combinazioni vincenti del 6 con l'archivio.</p>"}
<h2>Statistiche</h2>
<p>Il menu <i>Statistiche</i> offre tabelle pronte da consultare e stampare (pulsante «Stampa» nella finestra):
<b>Tutti i numeri</b>, <b>{'Euronumeri' if ej else 'SuperStar e Jolly'}</b>, <b>Tabellone dei ritardi</b>, <b>Numeri caldi e
freddi</b>, <b>Ritardo di posizione</b>, <b>Classifica delle condizioni</b>, <b>Riepilogo per anno</b> e, nel
sottomenu <i>Combinazioni</i>, ambi e terni più frequenti o più ritardatari.</p>
"""))

    c.append(("magico", "5. Magico Pensiero", f"""
<h2>Magico Pensiero</h2>
<p>È l'algoritmo del programma. Per ogni numero calcola un punteggio da cinque «voci»: <b>eco</b> delle estrazioni
precedenti, <b>affinità</b> con l'ultima estrazione, <b>tendenza</b> recente, <b>maturità del ritardo</b> e
<b>frequenza storica</b> (più le tue analisi personalizzate). Poi costruisce {prop} controllando che abbiano una forma
«normale» (somma, pari/dispari, consecutivi, decine, somiglianza con l'archivio...).</p>
<h3>Come usarlo</h3>
<ul>
<li><b>✨ Genera</b> (anche dal menu): serve almeno un archivio di 30 estrazioni. La proposta si salva nello
<i>Storico delle previsioni</i>.</li>
<li><b>Come sono nate (spiegazione):</b> per ogni numero scelto spiega quali voci l'hanno premiato.</li>
<li><b>Impostazioni dell'algoritmo:</b> peso delle voci e filtri. Se non sai cosa toccare, lascia i valori
predefiniti: l'apprendimento li corregge da solo.</li>
<li><b>Verifica storica:</b> rifà le previsioni su concorsi già passati (usando solo i dati precedenti) e le confronta
con i numeri usciti e con il caso. È il test onesto: dice se l'algoritmo, nel passato, ha fatto meglio di scelte
a caso. Scegli quanti concorsi verificare (più sono, più è attendibile e più ci vuole).</li>
<li><b>Storico delle previsioni:</b> tutte le proposte fatte, con l'esito rispetto alle estrazioni successive.</li>
<li><b>📈 Analisi delle previsioni e apprendimento:</b> dopo ogni nuova estrazione il programma studia dove aveva
messo i numeri usciti e corregge i pesi delle voci (solo scarti significativi, per non inseguire il caso). Puoi
allenarlo sul passato o azzerarlo.</li>
<li><b>🧪 Laboratorio:</b> mette alla prova la casualità: cerca regolarità vere nelle estrazioni. Aspettati,
giustamente, che quasi sempre non ne trovi.</li>
</ul>
<div class='av'>Come leggere la verifica storica: un piccolo vantaggio sul caso può essere pura fortuna. Fidati
di scarti che restano su centinaia di concorsi, non di una serie fortunata.</div>
"""))

    c.append(("ai", "6. Intelligenza artificiale e Colonna magica", f"""
<h2>Magico Pensiero + intelligenza artificiale</h2>
<p>Il programma prepara un <b>dossier</b> (ultime estrazioni, statistiche per numero, candidati dell'algoritmo,
esito della verifica storica, lezioni apprese) e lo invia a un'intelligenza artificiale, che valuta, scarta ciò che
le pare meno plausibile e sceglie le {CP} con le motivazioni. Servono almeno 100 estrazioni.</p>
<h3>Cosa serve: una chiave personale</h3>
<ul>
<li><b>Gemini</b> (Google): c'è un livello gratuito con un limite giornaliero di richieste. Il modello leggero
(Flash-Lite) permette molte più richieste al giorno.</li>
<li><b>Claude</b> (Anthropic): uso a pagamento tramite la Claude API, separato dall'abbonamento a claude.ai.</li>
</ul>
<p>La chiave si inserisce nella finestra dell'intelligenza artificiale (menu <i>Magico Pensiero</i> → «Magico Pensiero +
intelligenza artificiale») e <b>resta solo sul tuo computer</b>. Il pulsante <i>Prova la chiave</i> verifica che funzioni;
<i>Mostra i dati che verranno inviati</i> ti fa vedere esattamente cosa riceve l'AI. Se un modello è sovraccarico o
ha esaurito il limite, il programma prova da solo con un altro.</p>
<h3>💡 Suggerimenti AI</h3>
<p>Chiede all'AI un piccolo <b>sistema per intuizione</b>: un gruppo di numeri su cui costruire più colonne.</p>
<h2>🎩 Colonna magica</h2>
<p>Menu <i>Magico Pensiero → Colonna magica → Genera</i>. Una colonna di {k} numeri in cui <b>ogni numero ha una
provenienza diversa</b>, indicata nella scheda:</p>
<ul>
<li>🎲 un numero <b>casuale</b>;</li>
<li>✨ un numero scelto da <b>Magico Pensiero</b>;</li>
<li>🤖✨ un numero scelto dall'<b>AI</b> che ha anche il dossier di Magico Pensiero;</li>
{'' if ej else "<li>🤖 un numero scelto dall'<b>AI da sola</b>, guardando solo l'archivio;</li>"}
<li>📈 il numero che rende la colonna <b>più tipica</b> secondo tutte le condizioni;</li>
<li>📉 il numero che la rende <b>meno tipica</b> (la più insolita).</li>
</ul>
{"<p>Nell'Eurojackpot i numeri sono 5, quindi manca «l'AI da sola»; gli Euronumeri sono quelli di Magico Pensiero.</p>" if ej else ''}
<p>Se l'AI non è disponibile (chiave mancante, limite raggiunto) il numero viene <b>sostituito</b> e la scheda lo dice.
Ogni colonna magica si salva da sola in <i>Le mie giocate → Colonna magica</i>.</p>
"""))

    c.append(("sistemi", "7. Sistemi e Condizioni", f"""
<h2>Sistemi</h2>
<p>Un <b>sistema</b> è un modo per giocare molti numeri insieme con più colonne. Il menu <i>Sistemi → Nuovo</i>
offre:</p>
<ul>
<li><b>Ridotti immediati:</b> riduzioni già pronte e verificate: scegli quanti numeri giocare e che garanzia vuoi.</li>
<li><b>Ridotti (integrali a garanzia):</b> sviluppo con una garanzia di vincita minima se escono certi numeri.</li>
<li><b>Condizionati:</b> sviluppo integrale di tutte le colonne dei tuoi numeri, ma tenendo <b>solo quelle che
rispettano le condizioni</b> che imposti (vedi sotto).</li>
<li><b>Condizionati ridotti:</b> come i condizionati, ma ridotti per spendere meno.</li>
</ul>
<h3>Come si fa</h3>
<ol>
<li>Scegli il tipo e i numeri del sistema.</li>
<li>Per i condizionati aggiungi le condizioni.</li>
<li><b>Sviluppo (F5):</b> il programma costruisce le colonne e ti dice quante sono e quanto costano
(<i>Sviluppo → Impostazioni (prezzi)</i>).</li>
<li>Controlla le <b>garanzie</b> (<i>Calcolo garanzie</i>): con quali risultati il sistema paga.</li>
<li><b>Salva (F2)</b> per ritrovarlo con <b>Carica (F3)</b>; usa <i>Tabulato</i> (Ctrl+T) per stampare.</li>
</ol>
<h3>Spoglio</h3>
<p>Dal menu <i>Combinazioni di sistema</i>: <b>spoglio sull'ultima estrazione</b> (cosa avresti vinto),
<b>su una combinazione</b> (inserita da te) e <b>storico</b> (cosa avresti vinto su tutto il passato).</p>
<h2>Condizioni</h2>
<p>Una condizione descrive una caratteristica della colonna: <b>somma</b> dei numeri, <b>pari e dispari</b>,
<b>consecutivi</b>, <b>sequenze</b>, <b>cifre</b>, <b>distanze</b> tra i numeri, <b>posizione</b> (il 1° o l'ultimo numero),
<b>decine occupate</b>, <b>simmetrie</b>, <b>ripetizioni</b> rispetto all'archivio o all'ultima estrazione,
<b>ritardatari</b>, <b>numeri alti</b>, <b>numeri primi</b>{'' if ej else ''} e <b>popolarità</b> (quanto la colonna è
«comune» tra i giocatori).</p>
<p>Per ognuna il programma mostra, sull'archivio, <b>quante volte è uscito ogni valore</b> e confronta con quanto
accadrebbe col caso. Il consiglio è chiedere i valori che coprono la maggior parte delle estrazioni reali (di solito
l'80%): così scarti le colonne dalla forma insolita senza perdere quasi nessuna estrazione plausibile.</p>
<ul>
<li><b>📊 Analisi di tutte le condizioni sull'archivio:</b> la panoramica completa.</li>
<li><b>Rendimento delle condizioni:</b> quanto ogni condizione riduce le colonne e quanto «costa» in estrazioni
perse.</li>
</ul>
<div class='av'>Le condizioni non aumentano la probabilità di vincere: tolgono colonne <i>statisticamente rare</i>, quindi
ti fanno spendere meno per coprire quasi gli stessi scenari.</div>
"""))

    c.append(("casuali", "8. Combinazioni casuali", f"""
<h2>Combinazioni casuali</h2>
<ul>
<li><b>🎱 {'Cinquine ed Euronumeri' if ej else 'Sestine'} casuali – la macchina dell'estrazione (Ctrl+E):</b> la
macchina estrae come in televisione. Scegli quante colonne vuoi, premi, e puoi ripetere. I risultati si salvano in
<i>Le mie giocate</i>.</li>
<li><b>🎱 Sistema casuale – i numeri dalla macchina:</b> la macchina estrae i numeri di un sistema (per esempio 10
numeri) da sviluppare poi come ridotto o integrale.</li>
<li><b>🎲 Verifica colonne casuali (Ctrl+K):</b> mostra come si comportano colonne casuali rispetto all'archivio:
utile per capire che cosa ci si deve aspettare dal solo caso.</li>
</ul>
<p>Giocare a caso è una scelta valida quanto le altre: la macchina serve anche per evitare le combinazioni «da
tutti giocate» (date, sequenze regolari) che, in caso di vincita, si dividono in molti.</p>
"""))

    c.append(("giocate", "9. Le mie giocate", f"""
<h2>Le mie giocate</h2>
<p>È l'archivio personale di tutto ciò che generi e giochi. Ogni voce ha una <b>categoria</b> (sottomenu):</p>
<ul>
<li><b>Le mie colonne:</b> colonne scritte da te (<i>✍ Aggiungi le mie colonne</i>): le incolli o le scrivi, le analizzi,
le salvi e le giochi.</li>
<li><b>Colonne casuali, Sistemi casuali:</b> quelle uscite dalla macchina.</li>
<li><b>Magico Pensiero</b> e <b>Magico Pensiero + AI</b>: le proposte dell'algoritmo.</li>
<li><b>Colonna magica:</b> le colonne con la provenienza dei numeri.</li>
<li><b>Sistemi ridotti/condizionati/integrali:</b> i sistemi che sviluppi.</li>
</ul>
<h3>Cosa puoi farci</h3>
<ul>
<li><b>Riconoscere cosa hai giocato:</b> le righe <span style='background:#c8e6c9'>verdi</span> sono giocate, le
<span style='background:#fff9c4'>gialle</span> solo generate, le <i style='color:#777'>grigie in corsivo</i> nascoste.</li>
<li><b>Analizza:</b> tutte le caratteristiche della colonna e il confronto con l'archivio.</li>
<li><b>Verifica con l'archivio:</b> quante volte la colonna avrebbe fatto 2, 3, 4... e quando.</li>
<li><b>Dopo:</b> cosa è successo dopo l'ultima volta che la colonna è stata «viva».</li>
<li><b>Registra come giocata / Simula:</b> la porta nel Registro (spesa e vincite) o prova «e se l'avessi
giocata?».</li>
<li><b>Nascondi</b> (per toglierla dalla vista senza perderla; si rivede con «Le nascoste») e <b>Ricarica</b>
(riporta una voce vecchia nella schermata principale); <b>Note</b> per annotare; <b>Elimina</b> per cancellare
definitivamente.</li>
</ul>
"""))

    c.append(("ricevitoria", "10. Ricevitoria e Stampe", f"""
<h2>Ricevitoria</h2>
<ul>
<li><b>📝 Registro delle giocate (Ctrl+R):</b> annota cosa giochi, per quale concorso e quanto spendi. Dopo
l'estrazione il programma controlla da solo le vincite e ti mostra il bilancio.</li>
<li><b>📈 E se avessi giocato… (simulatore):</b> prende le tue colonne e calcola quanto avresti speso e vinto
giocandole in tutti i concorsi passati. È il modo più onesto per vedere che cosa rende (di solito, in perdita).</li>
</ul>
<h2>Stampe</h2>
<ul>
<li><b>🖨 Tabulato di un sistema (Ctrl+T):</b> le colonne pronte per la ricevitoria, su stampante, PDF o TXT.</li>
<li><b>Estrazioni dell'archivio:</b> le ultime N o tutto.</li>
<li><b>Combinazioni di Magico Pensiero:</b> stampa o registra la proposta.</li>
<li><b>📋 Scegli cosa stampare (Ctrl+Shift+P):</b> un riepilogo di tutte le sezioni attive.</li>
</ul>
<p>Le statistiche e molte altre finestre hanno un loro pulsante <b>Stampa</b>.</p>
"""))

    c.append(("impostazioni", "11. Impostazioni e copie dei dati", f"""
<h2>Impostazioni</h2>
<ul>
<li><b>📋 Riepilogo delle sezioni attive:</b> cosa è in corso (proposte, sistemi, giocate).</li>
<li><b>💾 Salva una copia dei dati / ♻ Ripristina:</b> backup completo e ritorno a una copia precedente. Fai una
copia prima di aggiornamenti importanti o di <i>Svuota archivio</i>.</li>
<li><b>🗂 Copie automatiche:</b> il programma salva da solo copie periodiche.</li>
</ul>
<p>Per spostare tutto su un altro computer: salva una copia, copia il file sul nuovo PC, ripristina.</p>
"""))

    c.append(("android", "12. La versione Android", f"""
<h2>Pensiero Magico per Android</h2>
<p>È una versione ridotta per il telefono, con SuperEnalotto ed Eurojackpot separati. In basso la barra sempre
visibile: <b>Home, Archivio, Magico Pensiero, Sistemi, Casualità</b>.</p>
<ul>
<li><b>Archivio:</b> aggiornamento da Internet e consultazione.</li>
<li><b>Magico Pensiero:</b> genera le proposte, con l'intelligenza artificiale e la verifica storica (scrivi o scegli il
numero di concorsi, da 10 a 1000).</li>
<li><b>Sistemi:</b> condizioni, condizionati, condizionati ridotti, ridotti.</li>
<li><b>Casualità:</b> {CP} casuali e sistema casuale (per l'Eurojackpot solo le cinquine, non gli Euronumeri).</li>
</ul>
<p>Si installa scaricando il file <i>.apk</i> dalla pagina delle release del progetto (consenti l'installazione da fonti
sconosciute). Le versioni firmate si installano sopra la precedente senza perdere i dati.</p>
"""))

    c.append(("consigli", "13. Come usarlo in modo proficuo", f"""
<h2>Come usarlo in modo proficuo</h2>
<ol>
<li><b>Tieni l'archivio aggiornato</b> (ti basta l'aggiornamento automatico all'avvio).</li>
<li><b>Parti da Magico Pensiero</b> e leggi sempre il «Perché»: capire le scelte aiuta a decidere.</li>
<li><b>Controlla la verifica storica</b> ogni tanto e lascia lavorare l'apprendimento: i pesi si adattano.</li>
<li><b>Usa i sistemi condizionati</b> se vuoi giocare tanti numeri spendendo meno: le condizioni al 80% tolgono molte
colonne improbabili per forma.</li>
<li><b>Prima di giocare, simula:</b> «E se avessi giocato…» mostra il bilancio vero nel passato.</li>
<li><b>Registra ogni giocata</b> nel Registro: vedere la spesa reale aiuta a restare in equilibrio.</li>
<li><b>Fissa un budget</b> e rispettalo. Il gioco deve restare un passatempo.</li>
</ol>
<h3>Cosa il programma non può fare</h3>
<ul>
<li>Non può prevedere l'estrazione né aumentare la probabilità di una singola colonna.</li>
<li>Non garantisce vincite: le garanzie dei sistemi riguardano solo gli scenari indicati.</li>
</ul>
<p>Se il gioco ti sembra sfuggire di mano, parla con qualcuno di fiducia o rivolgiti ai servizi di aiuto.</p>
"""))

    c.append(("faq", "14. Domande frequenti e scorciatoie", f"""
<h2>Domande frequenti</h2>
<dl>
<dt><b>«Servono almeno 30 estrazioni»</b></dt><dd>L'archivio è troppo piccolo: scarica dall'<i>Internet</i>.</dd>
<dt><b>L'AI dice che il limite è esaurito</b></dt><dd>Con Gemini, aspetta il giorno dopo o usa il modello leggero;
il programma prova anche altri modelli da solo.</dd>
<dt><b>La verifica storica è lenta</b></dt><dd>Scegli meno concorsi (100 bastano per un primo giudizio).</dd>
<dt><b>Ho cambiato gioco e non vedo più i miei dati</b></dt><dd>SE ed EJ sono separati: torna dal pulsante in alto
a sinistra.</dd>
<dt><b>Ho cancellato per errore</b></dt><dd><i>Impostazioni → Ripristina i dati da una copia</i>.</dd>
<dt><b>Windows segnala «App non riconosciuta»</b></dt><dd>Clicca <i>Ulteriori informazioni → Esegui comunque</i>.</dd>
</dl>
<h2>Scorciatoie da tastiera</h2>
<table border='1' cellpadding='4' style='border-collapse:collapse'>
<tr><td><b>F2</b></td><td>Salva il sistema</td><td><b>F3</b></td><td>Carica un sistema</td></tr>
<tr><td><b>F5</b></td><td>Sviluppo del sistema</td><td><b>Ctrl+T</b></td><td>Tabulato</td></tr>
<tr><td><b>Ctrl+E</b></td><td>Macchina dell'estrazione</td><td><b>Ctrl+K</b></td><td>Verifica colonne casuali</td></tr>
<tr><td><b>Ctrl+R</b></td><td>Registro delle giocate</td><td><b>Ctrl+Shift+P</b></td><td>Scegli cosa stampare</td></tr>
<tr><td><b>F1</b></td><td>Questa guida</td><td></td><td></td></tr>
</table>
"""))
    return c


STILE = ("body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; } h2 { color: #1b5e20; } "
         "h3 { color: #1565c0; } .av { background: #fff8e1; border: 1px solid #ffb300; padding: 6px; }")


def pagina(g: Gioco, quali: list[str] | None = None) -> str:
    """Tutta la guida (o i capitoli indicati) in un unico HTML, per la stampa."""
    parti = [h for i, _, h in capitoli(g) if quali is None or i in quali]
    return f"<html><head><style>{STILE}</style></head><body>{''.join(parti)}</body></html>"
