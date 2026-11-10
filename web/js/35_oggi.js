/* ---------- v7.29 "COSA FARE OGGI" (Dashboard, in cima) ----------
   Tre promemoria ricavati SOLO dai dati del giorno, con regole fisse (nessuna opinione):
     1) PORTAFOGLI  (D.port: rotazione, prossima, az_fino)
        - entro 3 giorni dalla rotazione del mese      -> "Portafogli aggiornati il ...": confronta le tue quote
        - mancano 3 giorni o meno alla prossima         -> "Rotazione tra N giorni"
        - altrimenti                                    -> "Nessuna operazione fino al ..."
        + se la prossima rotazione e' quella in cui la quota delle 5 azioni passa all'S&P 500 (az_fino), lo dice.
     2) MERCATI     (window.ebMercati, orari e festivita' di 02b_mercati.js): solo Europa e USA (dove compri su Scalable)
     3) DA SAPERE   in ordine di priorita':
        a) evento ad alto impatto OGGI nell'agenda (D.agenda) -> nome e ora
        b) nuovi dati COT oggi (D.sources[0].next_ms)          -> i segnali cambiano in serata
        c) azioni forti acquistabili (window.__top, vetrina)    -> quante, una per settore
   Si ridisegna quando arriva il calendario delle borse ("eb-mercati"), la vetrina ("eb-top") e ogni minuto.
   DEBUG: F12 -> Console -> ebOggi() restituisce le tre righe calcolate. */
try{(function(){const el=$("oggi");if(!el)return;
 const GGL=["domenica","lunedì","martedì","mercoledì","giovedì","venerdì","sabato"],
  MM=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];
 // data di Roma "AAAA-MM-GG" di un istante (il sito ragiona in ora italiana, anche se chi guarda e' in un altro fuso)
 const fRoma=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Rome",year:"numeric",month:"2-digit",day:"2-digit"});
 const ymdRoma=d=>fRoma.format(d);
 const oraRoma=d=>d.toLocaleTimeString("it-IT",{timeZone:"Europe/Rome",hour:"2-digit",minute:"2-digit"});
 const giorni=(a,b)=>Math.round((Date.parse(b)-Date.parse(a))/864e5);            // giorni tra due date "AAAA-MM-GG"
 const dataTxt=ymd=>{const x=new Date(ymd+"T12:00:00Z");return `${GGL[x.getUTCDay()]} ${x.getUTCDate()} ${MM[x.getUTCMonth()]}`;};

 // 1) PORTAFOGLI
 function rigaPort(oggi){const p=D.port;if(!p||!p.prossima)return null;
  const rot=p.rotazione,pro=p.prossima,dopo=rot?giorni(rot,oggi):99,manca=giorni(oggi,pro);
  const az=p.az_fino&&pro>=p.az_fino&&(rot||"")<p.az_fino?` Dal ${dataTxt(p.az_fino).replace(/^\S+ /,"").replace(/^1 /,"1&deg; ")} la quota delle 5 azioni passa all'S&amp;P 500.`:"";
  if(rot&&dopo>=0&&dopo<=3)return {k:"port",liv:"att",cat:"Portafogli",tit:dopo==0?"Oggi i portafogli cambiano":`Portafogli aggiornati ${dopo==1?"ieri":"il "+dataTxt(rot)}`,
   txt:`Confronta le tue quote con quelle nuove in Acquisto diretto.${p.az_fino&&rot==p.az_fino?" Da questo mese la quota delle 5 azioni &egrave; passata all'S&amp;P 500.":""}`,vai:"port",cta:"Apri"};
  if(manca<0)return {k:"port",liv:"att",cat:"Portafogli",tit:`Rotazione del ${dataTxt(pro).replace(/^\S+ /,"")} in aggiornamento`,   // dati in ritardo: lo diciamo
   txt:"Le nuove quote compaiono qui appena il calcolo del mese &egrave; pronto.",vai:"port",cta:"Apri"};
  if(manca>=0&&manca<=3)return {k:"port",liv:"att",cat:"Portafogli",tit:manca==0?"Oggi i portafogli cambiano":`Rotazione tra ${manca} ${manca==1?"giorno":"giorni"}`,
   txt:`${dataTxt(pro)[0].toUpperCase()+dataTxt(pro).slice(1)}, ore 9:00. Fino ad allora nessuna operazione.${az}`,vai:"port",cta:"Apri"};
  return {k:"port",liv:"ok",cat:"Portafogli",tit:"Nessuna operazione da fare",txt:`Prossima rotazione ${dataTxt(pro)}.${az}`,vai:"port",cta:"Apri"};}

 // 2) MERCATI (Europa e USA)
 function rigaMerc(){const M=window.ebMercati;if(!M)return null;
  const eu=M.stato("Europa"),us=M.stato("USA"),aperti=[eu.aperto&&"Europa",us.aperto&&"USA"].filter(Boolean);
  const fest=[eu.festivo&&`Europa (${eu.festivo})`,us.festivo&&`USA (${us.festivo})`].filter(Boolean);
  const festTxt=fest.length?` Chiuse per festivit&agrave;: ${fest.map(esc).join(", ")}.`:"";
  if(aperti.length==2)return {k:"merc",liv:"ok",cat:"Mercati",tit:"Borse aperte: Europa e USA",txt:"Un ordine viene eseguito subito, al prezzo del momento."};
  if(aperti.length==1){const altro=aperti[0]=="USA"?["Europa",eu]:["USA",us];
   return {k:"merc",liv:"ok",cat:"Mercati",tit:`Aperta ${aperti[0]=="USA"?"Wall Street":"l'Europa"}`,
    txt:`${altro[0]} ${altro[1].prossima?"riapre "+esc(M.oraIt(altro[1].prossima)):"chiusa"}.${festTxt}`};}
  const pr=[["Europa",eu],["USA",us]].filter(x=>x[1].prossima).sort((a,b)=>a[1].prossima-b[1].prossima)[0];
  return {k:"merc",liv:"chiuso",cat:"Mercati",tit:"Borse chiuse",
   txt:`${pr?`Riapre prima ${pr[0]=="USA"?"Wall Street":"l'Europa"}: ${esc(M.oraIt(pr[1].prossima))}. `:""}Un ordine inviato ora parte all'apertura, al prezzo di quel momento.${festTxt}`};}

 // 3) DA SAPERE
 function rigaSapere(oggi,ora){
  const ag=((D.agenda&&D.agenda.eventi)||[]).filter(e=>e.utc&&!e.uscito&&(e.impatto||"high")=="high")
   .map(e=>({t:new Date(e.utc.replace("Z",":00Z")),n:String(e.nome||"").replace(/\s*\(.*\)$/,""),v:e.valuta}))
   .filter(e=>!isNaN(e.t)&&ymdRoma(e.t)==oggi&&e.t>ora).sort((a,b)=>a.t-b.t);
  if(ag.length){const e=ag[0];
   return {k:"sap",liv:"att",cat:"Da sapere",tit:`Oggi alle ${oraRoma(e.t)}: ${esc(e.n)}${e.v?" ("+esc(e.v)+")":""}`,
    txt:`Dato ad alto impatto${ag.length>1?` (oggi altri ${ag.length-1})`:""}: di solito i prezzi si muovono pi&ugrave; del normale.`,scorri:"eventi",cta:"Agenda"};}
  const cot=(D.sources||[])[0]||{},cn=cot.next_ms?new Date(cot.next_ms):null;
  if(cn&&ymdRoma(cn)==oggi&&cn>ora)return {k:"cot",liv:"neu",cat:"Da sapere",tit:`Alle ${oraRoma(cn)} arrivano i nuovi dati COT`,
   txt:"I segnali di valute, materie prime e indici si aggiornano in serata.",vai:"assets",cta:"Segnali"};
  const T=window.__top;
  if(T&&T.titoli){const n=T.titoli.length;
   return n?{k:"az",liv:"neu",cat:"Azioni",tit:`${n} ${n==1?"azione forte":"azioni forti"} comprabili su Scalable`,
     txt:`Una per settore, con tutti i filtri favorevoli. Dati al ${gg(T.aggiornato)}.`,scorri:"topaz",cta:"Vedi"}
    :{k:"az",liv:"neu",cat:"Azioni",tit:"Nessuna azione supera tutti i filtri oggi",txt:"La selezione resta vuota finch&eacute; un titolo non li supera tutti.",scorri:"topaz",cta:"Vedi"};}
  return null;}
 const gg=d=>d?String(d).slice(8,10)+"/"+String(d).slice(5,7):"";

 function righe(){const ora=new Date(),oggi=ymdRoma(ora);
  return [rigaPort(oggi),rigaMerc(),rigaSapere(oggi,ora)].filter(Boolean);}
 window.ebOggi=righe;

 const ICO={port:'<path d="M3 7h18v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  az:'<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',cot:'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
 merc:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',sap:'<path d="M12 8v5"/><circle cx="12" cy="16.5" r=".6" fill="currentColor"/><path d="M10.3 3.9L2.5 17.5A2 2 0 0 0 4.2 20.5h15.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>'};
 let ultimo="";
 function disegna(){let R;try{R=righe();}catch(e){console.warn("oggi",e);return;}
  if(!R.length){el.innerHTML="";return;}
  const ora=new Date();
  const giorno=ora.toLocaleDateString("it-IT",{timeZone:"Europe/Rome",weekday:"long",day:"numeric",month:"long"});
  const html=`<div class="cfo"><div class="cfot"><h3>Cosa fare oggi</h3><span class="cfod">${esc(giorno)}</span>
   <details class="info"><summary title="Da dove vengono" aria-label="Da dove vengono">i</summary><div>Tre promemoria calcolati dai dati di oggi, con regole fisse: <b>calendario dei portafogli</b> (rotazione il primo giorno feriale del mese), <b>orari e festivit&agrave; ufficiali</b> delle borse europee e americane, <b>agenda</b> degli eventi ad alto impatto, uscita dei <b>dati COT</b> e <b>selezione delle azioni</b>. Non sono consigli personalizzati: cosa fare dipende dal tuo piano e dal profilo che hai scelto.</div></details></div>
   <div class="cfog">${R.map(r=>{const tag=r.vai||r.scorri?"a":"div",att=r.vai?` href="#${r.vai}" data-vai="${r.vai}"`:r.scorri?` href="#${r.scorri}" data-scorri-oggi="${r.scorri}"`:"";
    return `<${tag} class="cfor ${r.liv}"${att}><span class="cfoi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICO[r.k]}</svg></span>
     <span class="cfox"><span class="cfoc">${r.cat}</span><b>${r.tit}</b><span class="cfotx">${r.txt}</span></span>${r.cta?`<span class="cfova">${r.cta}<span aria-hidden="true">&rsaquo;</span></span>`:""}</${tag}>`;}).join("")}</div></div>`;
  if(html==ultimo)return;ultimo=html;el.innerHTML=html;
  el.querySelectorAll("[data-scorri-oggi]").forEach(a=>a.onclick=e=>{e.preventDefault();const t=$(a.dataset.scorriOggi);if(t)t.scrollIntoView({behavior:"smooth",block:"start"});});}
 disegna();
 window.addEventListener("eb-mercati",disegna);window.addEventListener("eb-top",disegna);
 setInterval(()=>{if(el.isConnected)disegna();},60000);
})();}catch(e){console.warn("oggi",e);}
