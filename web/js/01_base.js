/* ==========================================================================
   01_base.js - PRIMO dei file della pagina (web/js/, uniti in ordine di nome da pagina.py in un solo script)
   --------------------------------------------------------------------------
   Qui: aiuti comuni, protezione anti-crollo, etichette (i). Ogni altro file disegna UNA scheda:
     02_stato  03_navigazione  04_dashboard  05_forex  06_strumenti  07_macro  09_correlazioni
     10_stagionalita  11_guida  12_grafico  13_verifica  14_registro  20_manutenzione  21_portafogli
     22_azioni  23_vetrina_top5  24_pattern  (+ consenso legale e feedback: vedi i file 25_ e 26_)
   Un errore in una scheda resta chiuso nel suo try/catch: le altre schede continuano a funzionare.
   I dati arrivano da Python nella costante D (vedi index.html):
     D.meta      impostazioni e ora di aggiornamento      D.sources   stato di ogni fonte
     D.assets    ogni strumento (punteggi, COT, mercato)   D.pairs     coppie di valute
     D.market    driver di mercato                         D.corr_px   correlazioni dei prezzi
     D.fed       liquidita' Fed                            D.corr      matrice delle correlazioni
   Ogni sezione qui sotto riempie un pezzo di pagina (gli id corrispondono a quelli di index.html).
   Si usano "template literal" `...${valore}...` per costruire l'HTML.
   DEBUG: F12 -> Console. Scrivi D per vedere i dati, D.assets.EUR per un singolo strumento.
          Un errore in rosso nella Console indica file e riga del problema.
   ========================================================================== */
// v7.59 NOME DEL SITO AUTOMATICO: sul sito vero e' la prima cartella dell'indirizzo (utente.github.io/<nome>/...),
//   cosi' rinominare il repository non rompe i dati in tempo reale. In locale (prove) si usa il nome attuale.
const EB_REPO=(()=>{try{return location.hostname.endsWith("github.io")&&location.pathname.split("/")[1]||"cot-radar";}catch(e){return "cot-radar";}})();
const EB_RAW="https://raw.githubusercontent.com/yahyaallouchi5-2025/"+EB_REPO+"/";   // file dei rami live e pattern
const EB_SITO="https://yahyaallouchi5-2025.github.io/"+EB_REPO+"/";                 // pagina di presentazione

const M=D.meta;            // impostazioni (pesi, soglie, ora di aggiornamento)

const COL={"STRONG BUY":"var(--sb)","BUY":"var(--b)","NEUTRO":"var(--n)","SELL":"var(--s)","STRONG SELL":"var(--ss)"};
const fmt=n=>{if(n==null||isNaN(n))return"n/d";const r=Math.round(n);return(r>0?"+":"")+(r==0?0:r).toLocaleString("it-IT");};
const fx=(n,d=2)=>n==null||isNaN(n)?"n/d":n.toLocaleString("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d});
const sg=(n,d=2)=>n==null||isNaN(n)?"n/d":(n>0?"+":"")+fx(n,d);
const c2=v=>{const t=v.toFixed(2);return t=="-0.00"?"0.00":t;};const c1=v=>{const t=v.toFixed(1);return t=="-0.0"?"0.0":t;};
const verb=s=>s>=20?["COMPRANO","up","▲"]:s<=-20?["VENDONO","down","▼"]:["neutri","flat","■"];
// v7.42 ETICHETTE DI POSIZIONAMENTO: nei dati restano BUY/SELL (cosi' regole e registro non cambiano), in pagina si
//   legge il POSIZIONAMENTO degli speculatori. Motivo (scheda Verifica): dal 1987 questi segnali non hanno mostrato
//   un vantaggio misurabile (48% di esiti giusti a 4 settimane), quindi sono contesto e non un'indicazione operativa.
const ETI={"STRONG BUY":"FORTE RIALZO","BUY":"RIALZO","NEUTRO":"NEUTRO","SELL":"RIBASSO","STRONG SELL":"FORTE RIBASSO"};
const eti=l=>ETI[l]||l;
const ETI_NOTA="Posizionamento degli speculatori (dati COT): contesto, non un'indicazione operativa";
// v7.43 AVVISO EDUCATIVO: una riga breve nelle schede con importi, quote o selezioni (Portafogli, Azionario, test del
//   profilo). Il testo completo sta nelle Note legali; qui solo l'essenziale, sempre visibile.
const avvisoEdu=()=>`<p class="avedu"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.01"/></svg><span><b>Solo a scopo educativo</b>, non &egrave; consulenza finanziaria. Puoi perdere il capitale, anche comprando a contanti senza leva.</span><a href="../legale/#rischi" target="_blank" rel="noopener">Rischi</a></p>`;
const badge=l=>`<span class="badge" style="--bc:${COL[l]}" title="${ETI_NOTA}">${eti(l)}</span>`;   // pillola: bordo e testo nel colore del segnale
const pos=s=>Math.max(0,Math.min(100,(s+100)/2));
const nm=k=>(D.assets[k]||{}).name||k;
const esc=t=>String(t).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const lab=s=>Math.abs(s)>=M.strong?(s>0?"STRONG BUY":"STRONG SELL"):Math.abs(s)>=M.normal?(s>0?"BUY":"SELL"):"NEUTRO";
const $=id=>document.getElementById(id);


/* ---------- aiuti comuni a piu' sezioni ---------- */
const SEC=D.sectors,byS={};Object.values(D.assets).forEach(a=>{if(a.key!="USD")(byS[a.group]=byS[a.group]||[]).push(a);});
const NOTE={"Tassi USA":"Futures sui titoli di Stato: COMPRARE = scommettere su tassi in calo.","VIX":"Sul VIX comprare = aspettarsi piu' volatilita'."};
function mtag(cot,mac){if(mac==null)return`<span class="tag">mercato: n/d</span>`;if(Math.abs(mac)<25)return`<span class="tag">mercato: gia' scontato</span>`;
 if(Math.abs(cot)<10)return`<span class="tag">mercato ${mac>0?'rialzista':'ribassista'}</span>`;
 return (mac>0)==(cot>0)?`<span class="tag ok">Mercato conferma</span>`:`<span class="tag ko">Mercato contro</span>`;}
const split=(cot,mac)=>`<div class="split"><div>COT (${Math.round((1-M.mw)*100)}%)<b>${fmt(cot)}</b></div><div>Mercato (${Math.round(M.mw*100)}%)<b>${mac==null?'n/d':fmt(mac)}</b></div></div>`;
/* v7.28 SCALA UNICA 0-100 della forza (punteggio dell'Azionario, vetrina, PDF): stesse soglie e stessi colori ovunque.
   Forte da 65 in su, Debole sotto 35, Neutro in mezzo (soglie simmetriche attorno a 50 = titolo nella media).
   Restituisce [classe CSS, etichetta] oppure null se il dato manca. DEBUG: forzaLiv(70) -> ["f","Forte"] */
const FORZA_SOGLIE=[65,35];
const forzaLiv=v=>v==null||isNaN(v)?null:v>=FORZA_SOGLIE[0]?["f","Forte"]:v>=FORZA_SOGLIE[1]?["n","Neutro"]:["d","Debole"];
/* ANELLO del punteggio: il numero e' l'intensita' (0-100, senza segno), il colore la direzione
   (verde = acquisto, rosso = vendita, grigio = neutro). L'arco pieno = punteggio 100. */
const anello=s=>{const v=Math.min(100,Math.abs(Math.round(s||0))),r=24,c=2*Math.PI*r,
 col=s>=M.normal?"var(--b)":s<=-M.normal?"var(--s)":"var(--n)";
 return `<div class="anello" title="Punteggio finale ${fmt(s)} (intensita' ${v}/100)"><svg viewBox="0 0 60 60"><circle cx="30" cy="30" r="${r}" class="fondo"/>`+
  `<circle cx="30" cy="30" r="${r}" class="arco" style="stroke:${col}" stroke-dasharray="${(c*v/100).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 30 30)"/></svg><b>${v}</b><small>/100</small></div>`;};
const meter=s=>`<div class="meter"><i style="left:${pos(s)}%"></i></div><div class="scale"><span>-100 vendi</span><span>finale <b style="color:var(--ink)">${fmt(s)}</b></span><span>compra +100</span></div>`;
function fd(s){if(!s)return"";const m=["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"];if(s.length==7)return m[+s.slice(5,7)-1]+" "+s.slice(0,4);return s.slice(8,10)+"/"+s.slice(5,7)+"/"+s.slice(0,4);}

/* ---------- PROTEZIONE ANTI-CROLLO ----------
   Ogni sezione qui sotto e' racchiusa in try { ... } catch: se una sezione ha un errore (bug o dati strani)
   al suo posto compare un riquadro "Sezione non disponibile" e TUTTE le altre continuano a funzionare.
   Gli errori imprevisti (anche dentro i clic) mostrano un avviso rosso in alto invece di una pagina bianca.
   DEBUG: F12 -> Console: ogni errore e' stampato con il nome della sezione. window.__errori li elenca tutti. */
window.__errori=[];
function fail(sezione,contenitore,e){
 window.__errori.push({sezione,errore:String(e&&e.stack||e)});
 try{window.ebStat&&ebStat.ev("errore",{sezione:sezione});}catch(_){}   // statistiche: quali sezioni si rompono ai visitatori
 console.error("[BoardEdge] sezione '"+sezione+"' non disponibile:",e);
 const box=`<div class="alert red"><b>Sezione "${sezione}" non disponibile.</b> Errore: ${esc(e&&e.message||e)}. Le altre sezioni funzionano normalmente.</div>`;
 const el=contenitore&&document.getElementById(contenitore);
 if(el)el.insertAdjacentHTML("afterbegin",box);else{const a=document.getElementById("alerts");if(a)a.insertAdjacentHTML("beforeend",box);}
}
function bannerErrore(msg){const a=document.getElementById("alerts");if(a&&!a.querySelector(".js-err"))a.insertAdjacentHTML("afterbegin",`<div class="alert red js-err"><b>Errore imprevisto nella pagina:</b> ${esc(msg)}. Ricarica la pagina.</div>`);}
/* "ResizeObserver loop..." e' un avviso innocuo del browser (zoom, rotazione dello schermo): non e' un errore della pagina */
window.addEventListener("error",ev=>{if(/ResizeObserver loop/i.test(ev.message||""))return;
 window.__errori.push({sezione:"pagina",errore:String(ev.message)});bannerErrore(ev.message);});
/* ---------- ETICHETTE INFORMATIVE (i) ----------
   Le spiegazioni lunghe (<p class="sub"> subito dopo un titolo <h2>, e le note tra parentesi dei sottotitoli
   <h3 class="vft"> della Verifica) restano nascoste: accanto al titolo compare
   un pulsante "i" che le apre e chiude. La pagina resta pulita e i comandi si notano subito.
   Vale per tutte le schede, anche per quelle ridisegnate dopo un clic (MutationObserver). Una spiegazione aperta
   resta aperta quando la sua sezione si ridisegna (es. cambio di strumento): la ricordiamo per titolo in infoAperte.
   DEBUG: se un titolo non ha la "i", controlla che il paragrafo abbia class="sub" e venga SUBITO dopo l'<h2>. */
const infoAperte=new Set();
function etichetteInfo(root){
 // sottotitoli delle schede di Verifica: "Titolo <span class=small>(spiegazione)</span>" -> titolo pulito + paragrafo
 root.querySelectorAll("h3.vft>span.small").forEach(sp=>{const h=sp.parentNode,t=sp.textContent.trim().replace(/^\(|\)$/g,"");
  sp.remove();const p=document.createElement("p");p.className="sub";p.textContent=t.charAt(0).toUpperCase()+t.slice(1)+".";
  h.after(p);});
 root.querySelectorAll("p.sub:not(.infotesto)").forEach(p=>{const h=p.previousElementSibling;
  if(!h||!(h.tagName=="H2"||h.matches("h3.vft")))return;
  const k=h.textContent.trim(),ap=infoAperte.has(k);
  p.classList.add("infotesto");p.classList.toggle("aperta",ap);
  const b=document.createElement("button");
  Object.assign(b,{type:"button",className:"info",textContent:"i",title:"Spiegazione"});
  b.dataset.k=k;b.setAttribute("aria-label","Mostra o nascondi la spiegazione");b.setAttribute("aria-expanded",ap);
  h.appendChild(b);});}
document.addEventListener("click",e=>{const b=e.target.closest&&e.target.closest("button.info");if(!b)return;
 const p=b.dataset.apri?document.getElementById(b.dataset.apri):b.closest("h2,h3")&&b.closest("h2,h3").nextElementSibling;if(!p||!p.classList.contains("infotesto"))return;
 const ap=p.classList.toggle("aperta");b.setAttribute("aria-expanded",ap);
 if(ap)infoAperte.add(b.dataset.k);else infoAperte.delete(b.dataset.k);});
(()=>{const w=document.querySelector(".wrap");if(!w)return;etichetteInfo(w);
 new MutationObserver(()=>etichetteInfo(w)).observe(w,{childList:true,subtree:true});})();
/* VERSIONE NUOVA? Il browser (o GitHub Pages, ~10 minuti) puo' tenere in memoria la pagina vecchia.
   Ogni 10 minuti leggiamo stato.json "fresco": se e' piu' recente dei dati di questa pagina, compare
   un avviso con il pulsante per ricaricare. Solo sul sito (http/https), non sul file aperto dal PC. */
function controllaVersione(){if(!/^https?:/.test(location.protocol)||!D.stato||!D.stato.creato)return;
 fetch("stato.json?v="+Date.now(),{cache:"no-store"}).then(r=>r.ok?r.json():null).then(s=>{
  if(!s||!s.creato||s.creato<=D.stato.creato||s.esito=="scartato"||document.getElementById("nuovaversione"))return;
  const d=document.createElement("div");d.id="nuovaversione";d.className="alert";
  d.style.cssText="position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:60;display:flex;gap:12px;align-items:center;box-shadow:0 6px 24px rgba(0,0,0,.18)";
  d.innerHTML=`<span>&Egrave; disponibile una versione pi&ugrave; recente della dashboard.</span><button class="tvbtn" onclick="location.reload()">Aggiorna</button>`;
  document.body.appendChild(d);}).catch(()=>{});}   // senza rete: nessun avviso, nessun errore
controllaVersione();setInterval(controllaVersione,10*60*1000);
window.addEventListener("unhandledrejection",ev=>{window.__errori.push({sezione:"pagina",errore:String(ev.reason)});bannerErrore(ev.reason);});


/* v7.30 FUMETTI (i) SUL TELEFONO: posizione corretta anche a pagina scorsa.
   PROBLEMA: sul telefono molti fumetti usano "position:fixed" (larghi quanto lo schermo, regole @media in stile.css)
   ma senza "top": il browser li mette dove starebbero nel flusso della pagina SENZA tenere conto dello scorrimento,
   quindi, piu' in basso si e' scesi, piu' il fumetto finisce fuori dallo schermo (es. "Il mio conto" nei Portafogli:
   tocchi la (i) e non compare niente).
   SOLUZIONE: quando una (i) si apre e il suo fumetto e' "fixed", lo mettiamo noi sotto la (i) (o sopra, se sotto non
   c'e' spazio), sempre dentro lo schermo
   (se il testo e' lungo scorre dentro il fumetto); mentre si scorre lo segue, e se la (i) esce dallo schermo si chiude.
   I fumetti "absolute" (PC) non vengono toccati. DEBUG: F12 -> Console -> document.querySelectorAll("details.info[open]") */
(function(){
 const M=8;                                               // margine dai bordi dello schermo (px)
 function piazza(d){const box=d.querySelector(":scope>div"),s=d.querySelector(":scope>summary");if(!box||!s)return;
  if(getComputedStyle(box).position!=="fixed"){box.style.top="";return;}
  const r=s.getBoundingClientRect(),h=box.offsetHeight,H=window.innerHeight;
  if(r.bottom<0||r.top>H){d.open=false;box.style.top="";return;}          // la (i) e' uscita dallo schermo: chiudi
  // sotto la (i) se ci sta (o se sotto c'e' piu' spazio che sopra), altrimenti sopra; mai sopra la (i) stessa,
  // cosi' si puo' sempre ritoccare per chiudere. Se il testo e' piu' alto dello spazio, il fumetto scorre al suo interno.
  const sotto=H-r.bottom-2*M,sopra=r.top-2*M,giu=h<=sotto||sotto>=sopra,spazio=Math.max(60,giu?sotto:sopra);
  box.style.maxHeight=spazio+"px";box.style.overflowY=h>spazio?"auto":"";box.style.marginTop="0";
  box.style.top=Math.round(giu?r.bottom+M:r.top-M-Math.min(h,spazio))+"px";}
 document.addEventListener("toggle",ev=>{const d=ev.target;                // "toggle" non risale: si ascolta in cattura
  if(d&&d.matches&&d.matches("details.info")&&d.open)requestAnimationFrame(()=>piazza(d));},true);
 const tutti=()=>document.querySelectorAll("details.info[open]").forEach(piazza);
 window.addEventListener("scroll",tutti,{passive:true});window.addEventListener("resize",tutti);
})();
