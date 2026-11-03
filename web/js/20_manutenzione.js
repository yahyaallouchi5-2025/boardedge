/* ---------- avviso di MANUTENZIONE (comune a tutte le schede), v6.85 ----------
   ebManutenzione({scheda, codice, quando, dal}): stessa chiamata di prima, ma NIENTE piu' popup che blocca la pagina.
   Al suo posto una STRISCIA SOTTILE in cima alla scheda, con linguaggio da "sito in manutenzione" (niente "errore
   server 503", niente allarmi):  ● In manutenzione · dati aggiornati al 02/11/2026   (i)   ×
   - la spiegazione breve sta nel fumetto (i), come nel resto del sito;
   - la scheda resta usabile con gli ultimi dati validi; la × chiude la striscia per la sessione
     (sessionStorage "ebAvv:<scheda>:<quando>"), lo stesso criterio del vecchio popup;
   - se la scheda si ridisegna (filtri, ordinamenti) la striscia viene rimessa in cima da sola;
   - il codice tecnico (503, 504...) e i dettagli restano solo nel registro admin e nella mail di GitHub.
   Nelle statistiche anonime conta come evento "avviso" (una volta per sessione). */
window.ebManutenzione=function(o){try{
 if(!o)return;const el=document.getElementById(o.scheda);if(!el)return;
 const gg=d=>d?d.slice(8,10)+"/"+d.slice(5,7)+"/"+d.slice(0,4):"";
 const chiave="ebAvv:"+o.scheda+":"+(o.quando||o.dal||"1");
 try{if(sessionStorage.getItem(chiave))return;}catch(e){}           // chiusa con la x in questa sessione
 const dati=o.dal?`dati aggiornati al <b>${gg(o.dal)}</b>`:"dati dell'ultimo aggiornamento valido";
 const box=document.createElement("div");box.className="avman";box.setAttribute("role","status");
 box.innerHTML=`<i class="avman-p" aria-hidden="true"></i><span class="avman-t"><b>In manutenzione</b><span class="avman-s"> &middot; </span><span class="avman-d">${dati}</span></span>
  <details class="info avman-i"><summary title="Cosa succede" aria-label="Informazioni">i</summary><div>Stiamo aggiornando i dati di questa sezione. Nel frattempo vedi quelli dell'<b>ultimo aggiornamento valido</b>: puoi usare la pagina normalmente. Torna tutto regolare da solo, non devi fare nulla.</div></details>
  <button type="button" class="avman-x" aria-label="Chiudi avviso" title="Chiudi">&times;</button>`;
 let chiuso=false;
 box.querySelector(".avman-x").onclick=()=>{chiuso=true;try{sessionStorage.setItem(chiave,"1");}catch(e){}
  box.classList.add("via");setTimeout(()=>box.remove(),200);};
 // in cima alla scheda, sotto il titolo h2 se c'e'; rimessa al suo posto se la scheda ridisegna il contenuto
 const metti=()=>{if(chiuso||el.contains(box))return;const h=el.querySelector(":scope > h2");
  h?h.after(box):el.prepend(box);};
 metti();new MutationObserver(metti).observe(el,{childList:true});
 if(!window.__ebAvvStat){window.__ebAvvStat=1;try{window.ebStat&&ebStat.ev("avviso",{scheda:o.scheda});}catch(e){}}
}catch(e){console.error("[BoardEdge] avviso di manutenzione:",e);}};
