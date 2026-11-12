
/* ---------- CONSENSO LEGALE prima di usare la dashboard ----------
   Al primo accesso (e a ogni nuova versione del testo) un popup a tutto schermo mostra le condizioni d'uso.
   - Il pulsante "Accetto" si attiva solo dopo aver fatto scorrere il testo FINO IN FONDO (barra di avanzamento).
   - "Accetto": si salva nel browser (localStorage "eb_consenso" + cookie tecnico di 1 anno + sessione) e il popup
     non torna piu' a ogni accesso,
     finche' non cambia CONSENSO_VERSIONE (cambiando il testo, alzare la versione: tutti devono riaccettare).
   - "Non accetto": la dashboard resta coperta con un messaggio e il pulsante "Rileggi le condizioni".
   - Se il browser non permette di salvare (navigazione privata) il consenso vale per la sessione aperta.
   Il testo completo sta nelle Note legali (/legale/), qui c'e' la sintesi che l'utente deve accettare.
   Nelle statistiche anonime conta come evento "consenso" (accettato / rifiutato). */
(function(){try{
 const CONSENSO_VERSIONE="2026-11-12b";            // v7.45: condizioni d'uso complete (10 punti): tutti riaccettano
 const DATA_TESTO="12 novembre 2026";                // data mostrata nel testo (separata dalla versione tecnica)
 // Il consenso si ricorda in TRE posti (come fanno i grandi siti), cosi' non viene richiesto a ogni accesso anche
 // se un browser ne cancella uno: archiviazione locale (principale), cookie tecnico di 1 anno (alcuni browser e le
 // app tipo Telegram/Instagram svuotano l'archiviazione locale ma tengono i cookie) e archiviazione di sessione
 // (navigazione privata: vale finche' la finestra resta aperta). Basta che UNO dei tre abbia la versione giusta.
 const COOKIE="eb_consenso",GIORNI=365;
 const leggiCookie=()=>{try{const m=document.cookie.match(/(?:^|;\s*)eb_consenso=([^;]+)/);return m?decodeURIComponent(m[1]):null;}catch(e){return null;}};
 function ricorda(){const ora=new Date().toISOString();
  try{localStorage.setItem("eb_consenso",JSON.stringify({versione:CONSENSO_VERSIONE,data:ora}));}catch(e){}
  try{document.cookie=`${COOKIE}=${encodeURIComponent(CONSENSO_VERSIONE)}; Max-Age=${GIORNI*86400}; Path=/; SameSite=Lax; Secure`;}catch(e){}
  try{sessionStorage.setItem("eb_consenso",CONSENSO_VERSIONE);}catch(e){}
  window.__ebConsenso=true;}
 const salvato=()=>{
  try{const v=JSON.parse(localStorage.getItem("eb_consenso")||"null");if(v&&v.versione==CONSENSO_VERSIONE){
   if(leggiCookie()!=CONSENSO_VERSIONE)ricorda();          // chi ha accettato prima di v6.37: aggiunge il cookie di riserva
   return true;}}catch(e){}
  if(leggiCookie()==CONSENSO_VERSIONE){try{localStorage.setItem("eb_consenso",JSON.stringify({versione:CONSENSO_VERSIONE,data:new Date().toISOString()}));}catch(e){}return true;}
  try{if(sessionStorage.getItem("eb_consenso")==CONSENSO_VERSIONE)return true;}catch(e){}
  return window.__ebConsenso===true;};
 if(salvato())return;
 // v7.45 testo completo delle condizioni (versione di Ya, 11/11/2026) con piccole integrazioni: maggiore eta',
 // cookie tecnico del consenso, canale Telegram, nuova accettazione a ogni modifica. Elenco puntato = classe "cl".
 const TESTO=`
  <p class="cint">Ultimo aggiornamento: ${DATA_TESTO}. Prima di accedere leggi con attenzione le condizioni: l'utilizzo della piattaforma comporta la presa visione delle avvertenze e delle limitazioni qui descritte.</p>
  <h4>1. Natura e finalità di BoardEdge</h4>
  <p>BoardEdge è un progetto indipendente sviluppato a scopo personale, <b>educativo, didattico e di ricerca quantitativa</b> sui mercati finanziari: uno strumento di studio e sperimentazione statistica che permette di osservare, analizzare e confrontare dati finanziari con modelli matematici, indicatori quantitativi e metodologie statistiche.</p>
  <p>Tra i contenuti possono figurare:</p>
  <ul class="cl"><li>posizionamento degli operatori sui mercati (COT);</li><li>indicatori macroeconomici e monetari;</li><li>punteggi quantitativi e classifiche azionarie;</li><li>analisi di stagionalità e correlazioni;</li><li>portafogli teorici e modelli di allocazione del capitale;</li><li>simulazioni, backtest e analisi del rischio;</li><li>selezioni di strumenti finanziari elaborate automaticamente.</li></ul>
  <p><b>BoardEdge non è una banca, un intermediario finanziario, una società di gestione del risparmio né un soggetto autorizzato alla prestazione di servizi di investimento.</b> Non custodisce denaro, non gestisce patrimoni di terzi, non riceve né trasmette ordini e non esegue operazioni sui mercati.</p>
  <h4>2. Assenza di consulenza finanziaria</h4>
  <p>I contenuti hanno finalità esclusivamente informative, didattiche e analitiche. Non costituiscono:</p>
  <ul class="cl"><li>consulenza personalizzata in materia di investimenti;</li><li>raccomandazioni individuali di acquisto, vendita o mantenimento di strumenti finanziari;</li><li>sollecitazioni all'investimento o offerte al pubblico di prodotti finanziari;</li><li>indicazioni sull'adeguatezza di un investimento rispetto alla situazione economica o patrimoniale dell'utente.</li></ul>
  <p>Ai sensi del D.Lgs. 58/1998 (TUF) e della direttiva MiFID II, la consulenza in materia di investimenti consiste in raccomandazioni personalizzate su strumenti finanziari. BoardEdge non svolge tale attività e non valuta profilo finanziario, obiettivi, orizzonte temporale, situazione patrimoniale o tolleranza al rischio degli utilizzatori.</p>
  <p>Espressioni come «rialzista», «ribassista», «forte», «debole», «migliori azioni», «portafoglio conservativo», «moderato» o «aggressivo» identificano solo classificazioni interne ai modelli quantitativi. Importi, percentuali e quantità calcolati sul capitale inserito dall'utente sono <b>simulazioni matematiche</b>, non proposte di allocazione personalizzate. Nessun risultato va interpretato come indicazione a effettuare un'operazione finanziaria.</p>
  <h4>3. Rischi degli investimenti</h4>
  <p>Investire comporta rischi economici significativi e la possibilità di <b>perdere in parte o interamente il capitale investito</b>, <b>anche senza leva finanziaria</b>. Azioni, ETF, obbligazioni, materie prime, oro, valute e criptovalute sono soggetti a rischi di mercato, liquidità, volatilità, cambio, credito e ad altri fattori che possono ridurne in modo significativo il valore.</p>
  <p>A titolo di esempio, storicamente:</p>
  <ul class="cl"><li>S&amp;P 500: ribasso di circa il 57% nella crisi finanziaria 2007-2009;</li><li>Nasdaq Composite: ribasso di circa il 78% nella crisi del 2000-2002;</li><li>Bitcoin: ribassi superiori al 75% in alcuni cicli.</li></ul>
  <p>Le singole società possono subire perdite permanenti, fino alla perdita totale del capitale investito. Leva finanziaria, futures, opzioni, CFD, forex e altri derivati comportano rischi ulteriori: in determinate circostanze <b>le perdite possono superare il capitale versato</b>. Gli investimenti in valute diverse dalla propria sono soggetti anche al rischio di cambio. Volatilità, drawdown e rischio mostrati da BoardEdge <b>non sono limiti massimi alle perdite future</b>.</p>
  <h4>4. Backtest, simulazioni e risultati storici</h4>
  <p>Performance storiche, simulazioni, backtest e statistiche hanno solo finalità di studio e di valutazione metodologica. <b>I risultati passati non garantiscono né prevedono i rendimenti futuri.</b> I modelli quantitativi possono essere soggetti, tra gli altri, a questi limiti:</p>
  <ul class="cl"><li>overfitting e ottimizzazione eccessiva sui dati storici;</li><li>look-ahead bias, cioè uso involontario di informazioni non disponibili al momento della simulazione;</li><li>survivorship bias, dovuto all'uso di società oggi esistenti o presenti negli indici, con possibile esclusione di società fallite, delistate o uscite dagli indici;</li><li>costi di transazione, commissioni, spread, slippage e imposte non sempre rappresentati per intero;</li><li>cambiamenti strutturali dei mercati e delle condizioni macroeconomiche.</li></ul>
  <p>Le performance teoriche possono quindi differire sensibilmente da quelle ottenibili con operazioni reali. I registri live, dove presenti, documentano solo le attività effettivamente registrate e non sono una promessa di risultati futuri.</p>
  <h4>5. Modelli quantitativi e strumenti automatizzati</h4>
  <p>I risultati derivano da algoritmi, regole statistiche e metodologie sviluppate a fini sperimentali. I modelli non sono infallibili e possono produrre classificazioni errate, segnali contraddittori, risultati distorti o informazioni non più attuali. Un punteggio elevato, una posizione in classifica o la presenza in un portafoglio teorico non significano che uno strumento sia sicuro, sottovalutato, adatto all'acquisto o destinato a rendimenti positivi. I modelli possono essere modificati, aggiornati, sospesi o sostituiti senza alcuna garanzia sulla validità dei risultati pubblicati in precedenza.</p>
  <h4>6. Fonti dei dati e disponibilità del servizio</h4>
  <p>BoardEdge usa informazioni da fonti esterne, pubbliche o commerciali, tra cui CFTC, FRED, Banca Centrale Europea (BCE), Yahoo Finance, U.S. Securities and Exchange Commission (SEC) e altri fornitori di dati finanziari e macroeconomici. I dati possono presentare ritardi, imprecisioni, revisioni, indisponibilità temporanee o differenze di metodo tra le fonti. Pur con controlli e procedure di verifica, BoardEdge non garantisce completezza, esattezza, aggiornamento o continuità delle informazioni ricevute da terzi. La piattaforma può essere temporaneamente indisponibile per manutenzione, aggiornamenti, problemi tecnici o interruzioni dei servizi esterni.</p>
  <h4>7. Limitazione di responsabilità</h4>
  <p>Ogni decisione di acquisto, vendita, detenzione o allocazione di strumenti finanziari è presa <b>dall'utilizzatore, in autonomia e sotto la propria responsabilità</b>. BoardEdge, i suoi sviluppatori e i soggetti coinvolti nel progetto non rispondono delle decisioni operative prese sulla base di informazioni, statistiche, simulazioni o risultati pubblicati. Nei limiti consentiti dalla normativa applicabile, non è fornita alcuna garanzia sull'accuratezza dei risultati, sull'idoneità dei modelli a specifici obiettivi finanziari o sul conseguimento di determinati rendimenti, e non potranno essere richiesti risarcimenti per perdite derivanti dall'uso delle informazioni pubblicate, salvo i casi in cui la responsabilità non possa essere esclusa o limitata per legge.</p>
  <p>Prima di decidere un investimento rivolgiti a un <b>professionista abilitato e indipendente</b>, valutando con attenzione la tua situazione finanziaria e i rischi degli strumenti considerati, e investi solo denaro che puoi permetterti di perdere.</p>
  <h4>8. Proprietà intellettuale e uso dei contenuti</h4>
  <p>Software, interfaccia, modelli quantitativi, elaborazioni originali, struttura della piattaforma e contenuti di BoardEdge sono tutelati, nei limiti previsti dalla normativa, dalle norme su proprietà intellettuale e diritto d'autore, inclusa la L. 633/1941. Senza autorizzazione scritta è vietato:</p>
  <ul class="cl"><li>riprodurre o distribuire i contenuti originali della piattaforma;</li><li>copiare o commercializzare i modelli quantitativi e le elaborazioni proprietarie;</li><li>ripubblicare o rivendere i dati e le analisi prodotti da BoardEdge;</li><li>usare il servizio per finalità commerciali non autorizzate.</li></ul>
  <p>Restano esclusi dalla titolarità di BoardEdge i dati, i marchi, i contenuti e i diritti dei rispettivi fornitori e titolari.</p>
  <h4>9. Privacy e trattamento dei dati</h4>
  <p>BoardEdge raccoglie il minimo indispensabile di dati personali. Non usa cookie pubblicitari o di profilazione. Le statistiche di utilizzo sono raccolte con Umami Analytics in forma aggregata e senza cookie. Il browser conserva nell'archiviazione locale preferenze tecniche, stato di accesso e presa visione delle condizioni d'uso; la presa visione è ricordata anche da un <b>cookie tecnico</b> di durata annuale, necessario al funzionamento e privo di finalità di tracciamento. I messaggi inviati con «Feedback» arrivano ai responsabili del progetto via email e non vengono pubblicati. L'iscrizione al canale Telegram è regolata dall'informativa di Telegram. Titolare, finalità, basi giuridiche, tempi di conservazione e diritti degli interessati sono descritti nella sezione <a href="../legale/#privacy" target="_blank" rel="noopener">Privacy delle Note legali</a>.</p>
  <h4>10. Accettazione delle condizioni</h4>
  <p>Premendo «Accetto» dichiari di essere <b>maggiorenne</b>, di aver letto e compreso le presenti condizioni d'uso e le avvertenze sui rischi, e di riconoscere la natura educativa, informativa e sperimentale della piattaforma: i contenuti non sostituiscono una valutazione professionale indipendente. Le condizioni possono essere aggiornate per adeguamenti normativi, modifiche tecniche o nuove funzionalità; a ogni aggiornamento la nuova versione ti verrà mostrata e <b>dovrà essere accettata di nuovo</b>.</p>
  <p class="small">BoardEdge — strumento indipendente di studio e ricerca quantitativa sui mercati finanziari. Testo completo: <a href="../legale/" target="_blank" rel="noopener">Note legali</a>. Versione del ${DATA_TESTO}.</p>`;
 const box=document.createElement("div");box.className="cmodal";
 box.innerHTML=`<div class="cmodal-box" role="dialog" aria-modal="true" aria-labelledby="cmt">
   <div class="cmodal-testa"><span class="cmodal-ico" aria-hidden="true">&sect;</span><div><h3 id="cmt">Prima di entrare</h3><p>Leggi le condizioni d'uso fino in fondo per continuare.</p></div></div>
   <div class="cmodal-avanz" aria-hidden="true"><i></i></div>
   <div class="cmodal-testo" tabindex="0">${TESTO}</div>
   <div class="cmodal-piede"><span class="cmodal-hint">Scorri fino in fondo per attivare &laquo;Accetto&raquo;</span>
    <div class="cmodal-btn"><button class="cno">Non accetto</button><button class="csi" disabled>Accetto</button></div></div></div>`;
 const blocco=document.createElement("div");blocco.className="cmodal cblocco";blocco.hidden=true;
 blocco.innerHTML=`<div class="cmodal-box cmodal-picc" role="alertdialog" aria-modal="true"><span class="cmodal-ico" aria-hidden="true">&sect;</span>
   <h3>Accesso non disponibile</h3><p>Per usare la dashboard &egrave; necessario accettare le condizioni d'uso.</p>
   <div class="cmodal-btn"><a class="cno" href="../">Torna alla home</a><button class="csi crileggi">Rileggi le condizioni</button></div></div>`;
 document.documentElement.classList.add("cbloccato");                    // niente scorrimento della pagina sotto
 document.body.appendChild(box);document.body.appendChild(blocco);
 requestAnimationFrame(()=>box.classList.add("on"));
 const testo=box.querySelector(".cmodal-testo"),si=box.querySelector(".csi"),barra=box.querySelector(".cmodal-avanz i"),hint=box.querySelector(".cmodal-hint");
 // avanzamento della lettura: "Accetto" si attiva arrivati in fondo (con 8px di tolleranza)
 function controlla(){const max=testo.scrollHeight-testo.clientHeight,p=max<=0?1:Math.min(1,testo.scrollTop/max);
  barra.style.width=(p*100).toFixed(1)+"%";
  if(p>=0.995||max-testo.scrollTop<=8){si.disabled=false;hint.textContent="Grazie per aver letto. Puoi accettare.";hint.classList.add("ok");}}
 testo.addEventListener("scroll",controlla,{passive:true});setTimeout(controlla,50);
 const stat=(esito)=>{try{window.ebStat&&ebStat.ev("consenso",{esito});}catch(e){}};
 si.onclick=()=>{ricorda();
  stat("accettato");box.classList.remove("on");setTimeout(()=>box.remove(),220);blocco.remove();document.documentElement.classList.remove("cbloccato");};
 box.querySelector(".cno").onclick=()=>{stat("rifiutato");box.classList.remove("on");setTimeout(()=>{box.hidden=true;blocco.hidden=false;requestAnimationFrame(()=>blocco.classList.add("on"));},200);};
 blocco.querySelector(".crileggi").onclick=()=>{blocco.classList.remove("on");blocco.hidden=true;box.hidden=false;requestAnimationFrame(()=>box.classList.add("on"));testo.focus({preventScroll:true});};
}catch(e){console.error("[BoardEdge] consenso:",e);}})();
