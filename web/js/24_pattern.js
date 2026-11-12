
/* ---------- PATTERN DETECTOR: inversione a 3 candele con assorbimento (forex e materie prime) ----------
   Dati: pattern.json scritto ogni 4 ore da cot_radar/pattern.py nel ramo git "pattern" e letto DIRETTAMENTE da
   raw.githubusercontent.com (cosi' non serve ripubblicare il sito a ogni candela H4); se non risponde si usa la
   copia nel sito (../pattern/pattern.json).
   BUY  = candela 1 SELL, candele 2 e 3 BUY, chiusura della 3 sopra l'apertura della 1 (assorbimento).
   SELL = candela 1 BUY, candele 2 e 3 SELL, chiusura della 3 sotto l'apertura della 1.
   - si scarica solo all'apertura della scheda (scheletro di attesa) e si riaggiorna ogni 10 minuti finche' e' aperta;
   - timeframe H4 / Daily, filtro Forex / Materie prime, segnali freschi in evidenza;
   - clic su uno strumento: grafico a candele delle ultime 60 con i pattern evidenziati e le due linee
     (apertura della candela 1 e chiusura della candela 3), come nelle immagini di riferimento;
   - anomalia (Yahoo fermo) o file assente: popup comune di manutenzione con giorno e ora.
   DEBUG: F12 -> Console -> window.__pattern */
try{(function(){const el=$("pattern");if(!el)return;
 const RAW=EB_RAW+"pattern/pattern.json",LOC="../pattern/pattern.json";
 const ST={d:null,tf:"h4",g:"tutti"};
 try{const s=JSON.parse(localStorage.getItem("ebPattern")||"{}");if(s.tf)ST.tf=s.tf;if(s.g)ST.g=s.g;}catch(e){}
 const salva=()=>{try{localStorage.setItem("ebPattern",JSON.stringify({tf:ST.tf,g:ST.g}));}catch(e){}};
 const z=x=>String(x).padStart(2,"0");
 // orario della CHIUSURA della candela, in ora italiana (H4: inizio + 4 ore; daily: solo la data)
 const quando=(t,tf)=>{const d=new Date((t+(tf=="h4"?4*3600:0))*1000);return tf=="h4"?`${z(d.getDate())}/${z(d.getMonth()+1)} ore ${z(d.getHours())}:${z(d.getMinutes())}`:`${z(d.getDate())}/${z(d.getMonth()+1)}/${d.getFullYear()}`;};
 const num=(v,c)=>v==null?"n/d":Number(v).toLocaleString("it-IT",{minimumFractionDigits:Math.min(c,5),maximumFractionDigits:c});
 const cifre=v=>{const s=String(v);return s.includes(".")?s.split(".")[1].length:0;};
 // variazione %: sotto lo 0,005% e' zero (evita il "-0,00%" quando il prezzo e' fermo)
 const pc=v=>{if(v==null)return "n/d";if(Math.abs(v)<0.005)v=0;return `<span class="${v>0?"up":v<0?"down":"flat"}">${v>0?"+":""}${fx(v,2)}%</span>`;};
 // "1 candela fa" al singolare, "N candele fa" al plurale
 const fa=n=>n==0?"ultima candela":n==1?"1 candela fa":n+" candele fa";
 const badge=l=>`<span class="ptb ${l=="BUY"?"buy":"sell"}">${l}</span>`;
 const sk=(w,h)=>`<i class="sk" style="width:${w};height:${h}px"></i>`;

 // mini schema del pattern (spiegazione visiva, sempre uguale)
 const schema=lato=>{const B=lato=="BUY",c=[[B?20:70,B?70:20],[B?70:20,B?50:45],[B?50:45,B?12:82]];
  const y=v=>8+v*0.9;return `<svg viewBox="0 0 120 96" class="ptschema" aria-hidden="true">
   <line x1="8" x2="112" y1="${y(c[0][0])}" y2="${y(c[0][0])}" class="lv"/>${c.map((k,i)=>{const s=k[1]<k[0];const top=Math.min(y(k[0]),y(k[1])),h=Math.abs(y(k[0])-y(k[1]));
   return `<rect x="${22+i*28}" y="${top}" width="16" height="${Math.max(2,h)}" rx="2" class="${(B?(i?"su":"giu"):(i?"giu":"su"))}"/>`;}).join("")}
   <circle cx="${22+2*28+8}" cy="${y(c[2][1])}" r="3.5" class="pt"/></svg>`;};

 function scheletro(){el.innerHTML=`<h2>Pattern Detector</h2><p class="sub">Caricamento dei segnali&hellip;</p>
  <div class="azbar">${sk("220px",38)}${sk("260px",38)}</div><div class="ptfresh">${Array(3).fill(`<div class="card">${sk("40%",14)}${sk("70%",24)}${sk("100%",60)}</div>`).join("")}</div>
  <div class="tablewrap" style="padding:14px">${Array(8).fill(`<div class="azskr">${sk("22%",14)}${sk("12%",14)}${sk("14%",14)}${sk("12%",14)}</div>`).join("")}</div>`;}

 let carico=null,timer=null;
 function scarica(){const v=Math.floor(Date.now()/300000);   // cambia ogni 5 minuti: niente copie vecchie in cache
  return fetch(RAW+"?v="+v,{cache:"no-cache"}).then(r=>{if(!r.ok)throw 0;return r.json();})
   .catch(()=>fetch(LOC,{cache:"no-cache"}).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();}));}
 function carica(){if(carico)return carico;scheletro();
  return carico=scarica().then(d=>{ST.d=d;window.__pattern=d;disegna();
    if(d.anomalia)ebManutenzione({scheda:"pattern",codice:d.anomalia.codice,quando:d.anomalia.quando});
    clearInterval(timer);timer=setInterval(()=>{if(el.classList.contains("on")&&!document.hidden)scarica().then(n=>{if(n.generato_utc!=(ST.d||{}).generato_utc){ST.d=n;disegna();}}).catch(()=>{});},600000);})
   .catch(e=>{console.error("[BoardEdge] pattern non caricati:",e);carico=null;
    el.innerHTML=`<h2>Pattern Detector</h2><div class="card azvuoto"><span class="pav-i grande" aria-hidden="true">!</span><h3>Segnali momentaneamente non disponibili</h3><p class="small">La scheda torna appena il servizio &egrave; di nuovo regolare.</p></div>`;
    const n=new Date();ebManutenzione({scheda:"pattern",codice:"503",quando:`${n.getFullYear()}-${z(n.getMonth()+1)}-${z(n.getDate())} ${z(n.getHours())}:${z(n.getMinutes())}`});});}
 const nb=document.querySelector('#nav button[data-t=pattern]');if(nb)nb.addEventListener("click",()=>setTimeout(carica,0));
 setTimeout(()=>{if(el.classList.contains("on"))carica();},0);

 // --- STUDIO STORICO (v6.59, cot_radar/pattern.py studio()): tutti i pattern daily degli ultimi 25 anni operati
 //     con stop all'estremo, target 1R/2R, costi e filtro trend; VERDETTO automatico in cima, senza giri di parole.
 // v6.59b: testo breve in pagina, spiegazione completa nella (i). Verdetto: "peggio" se il risultato e' SICURAMENTE
 //   sotto zero (anche il limite alto dell'intervallo al 95% e' negativo), "si" se sicuramente sopra, altrimenti "no".
 /* v6.76 STUDIO STORICO in italiano semplice (prima: "DA SOLO, PEGGIO DEL CASO" e colonne in "R").
    Il risultato si mostra in % del RISCHIO: 100% = quanto si perde se scatta lo stop (1 R). -4% = in media si perde
    il 4% di quanto si rischia a ogni operazione, costi inclusi. Esito: "in perdita" se e' sotto zero anche nel caso
    migliore (limite alto dell'intervallo al 95% negativo), "utile" se sopra zero anche nel caso peggiore, altrimenti
    "nessun vantaggio". Numeri da cot_radar/pattern.py studio(); la riga "a cicli" e' lo studio offline
    tools/studio_pattern_cicli.py del 02/11/2026 (ingresso con il COT, uscita al pattern opposto). */
 function studio(st){if(!st||!st.varianti)return "";
  const pr=v=>v==null?"n/d":(v>0?"+":"\u2212")+fx(Math.abs(v*100),0)+"%",V=st.varianti;
  const ETV={si:"utile",no:"nessun vantaggio",peggio:"in perdita"},ETC={si:"utile",no:"no",peggio:"perdita"},ETS={si:"Vantaggio in almeno una variante",no:"Nessun vantaggio dimostrato",ko:"Da solo non conviene"};
  const esito=x=>!x||!x.ic?"no":x.ic[0]>0?"si":x.ic[1]<0?"peggio":"no";
  const tutte=[V["1R"].tutti,V["2R"].tutti,V["1R"].trend,V["2R"].trend,V["1R"].contro_trend,V["2R"].contro_trend];
  const stato=tutte.some(x=>esito(x)=="si")?"si":tutte.some(x=>esito(x)=="peggio")?"ko":"no";
  const riga=(nome,x)=>x?`<tr><td>${nome}</td><td class="num ptmob">${x.n.toLocaleString("it-IT")}</td><td class="num ptmob">${x.vinte}%</td>
   <td class="num ${x.r_medio>=0?"up":"down"}"><b>${pr(x.r_medio)}</b></td><td class="num ptmob">${x.ic?`da ${pr(x.ic[0])} a ${pr(x.ic[1])}`:"n/d"}</td>
   <td class="num"><span class="ptv ${esito(x)}"><span class="ptlg">${ETV[esito(x)]}</span><span class="ptsh">${ETC[esito(x)]}</span></span></td></tr>`:"";
  const t1=V["1R"].tutti,anno=esc((t1&&t1.dal||"").slice(0,4));
  const frase=t1?`Operando <b>ogni</b> pattern dal ${anno} (${t1.n.toLocaleString("it-IT")} operazioni), con stop all'estremo e obiettivo pari al rischio, in media ${t1.r_medio<0?"si perde":"si guadagna"} il <b>${fx(Math.abs(t1.r_medio*100),0)}% di quanto si rischia</b> a operazione, costi inclusi.`:"";
  return `<div class="card ptstudio ${stato}"><div class="ptsth"><span class="ptverd">${ETS[stato]}</span>
    <span class="small">Studio Daily dal ${anno} &middot; ${ST.d.strumenti.length} strumenti</span>
    <button type="button" class="info" data-apri="ptinfo" data-k="ptstudio" aria-label="Mostra o nascondi la spiegazione">i</button></div>
   <p class="ptfrase">${frase} Usalo per leggere il grafico, non come segnale da solo.</p>
   <p id="ptinfo" class="sub infotesto${infoAperte.has("ptstudio")?" aperta":""}">Ogni pattern operato come un trade vero: ingresso alla chiusura della candela 3, stop all'estremo del pattern, obiettivo a 1 o 2 volte il rischio, uscita dopo ${st.regole.uscita_max} candele al massimo, costi inclusi; stop e obiettivo nella stessa candela = stop. <b>Risultato medio</b> in % del rischio: 100% = quanto perdi se scatta lo stop. <b>Range probabile</b>: dove sta davvero la media con il 95% di sicurezza (corretto per 10 confronti, operazioni delle stesse 2 settimane contate insieme). <b>In perdita</b> = sotto zero anche nel caso migliore. Trend = media a 200 candele. <b>A cicli con il COT</b> (studio del 02/11/2026): ingresso solo nel verso del segnale COT, uscita al pattern opposto, rientro finch&eacute; il COT resta attivo: dal 2001 fa peggio che tenere il segnale COT per tutta la sua durata. Statistica del passato, non un consiglio.</p>
   <div class="tablewrap"><table class="compatta"><tr><th>Come si opera</th><th class="num ptmob">Operazioni</th><th class="num ptmob">Vincenti</th><th class="num"><span class="ptlg">Risultato medio</span><span class="ptsh">Medio</span></th><th class="num ptmob">Range probabile</th><th class="num">Esito</th></tr>
    ${riga("<span class=\"ptob\">Obiettivo </span>1&times; rischio &middot; tutti",V["1R"].tutti)}${riga("<span class=\"ptob\">Obiettivo </span>1&times; rischio &middot; a favore del trend",V["1R"].trend)}${riga("<span class=\"ptob\">Obiettivo </span>1&times; rischio &middot; contro il trend",V["1R"].contro_trend)}
    ${riga("<span class=\"ptob\">Obiettivo </span>2&times; rischio &middot; tutti",V["2R"].tutti)}${riga("<span class=\"ptob\">Obiettivo </span>2&times; rischio &middot; a favore del trend",V["2R"].trend)}${riga("<span class=\"ptob\">Obiettivo </span>2&times; rischio &middot; contro il trend",V["2R"].contro_trend)}</table></div>
   <p class="small ptcicli">Provato anche <b>a cicli con il COT</b> (entri con il segnale COT, esci al pattern opposto, rientri finch&eacute; il COT &egrave; attivo): peggio che tenere il segnale COT.</p></div>`;}

 function disegna(){const d=ST.d,tf=ST.tf;
  const S=d.strumenti.filter(s=>ST.g=="tutti"||s.g==ST.g);
  const freschi=S.filter(s=>s[tf].ultimo&&s[tf].ultimo.fa==0);
  // statistica complessiva del timeframe (tutti gli strumenti filtrati)
  let n=0,v=0,m=0;S.forEach(s=>{const st=s[tf].stat;if(st&&st.n){n+=st.n;v+=st.vinti*st.n/100;m+=st.media*st.n;}});
  const tot=n?{v:Math.round(100*v/n),m:m/n}:null;
  el.innerHTML=`<h2>Pattern Detector</h2><p class="sub">Inversione a 3 candele con assorbimento: la candela 1 va in una direzione, le candele 2 e 3 nella direzione opposta e la candela 3 chiude oltre l'apertura della candela 1, &laquo;assorbendola&raquo; del tutto. Solo candele chiuse, ${S.length} strumenti tra forex e materie prime, aggiornamento ogni 4 ore.</p>
   <div class="ptspiega"><div>${schema("BUY")}<span>${badge("BUY")} candela 1 SELL, poi 2 candele BUY: la 3 chiude sopra l'apertura della 1</span></div>
    <div>${schema("SELL")}<span>${badge("SELL")} candela 1 BUY, poi 2 candele SELL: la 3 chiude sotto l'apertura della 1</span></div></div>
   ${studio(d.studio)}
   <div class="azbar"><span class="azdata"><i></i>Aggiornato <b>${esc((d.generato||"").slice(8,10)+"/"+(d.generato||"").slice(5,7)+" ore "+(d.generato||"").slice(11,16))}</b></span>
    <div class="vfswitch pttf">${[["h4","H4"],["d1","Daily"]].map(x=>`<button data-tf="${x[0]}" class="${tf==x[0]?"on":""}">${x[1]}</button>`).join("")}</div>
    <div class="filters ptg">${[["tutti","Tutti"],["forex","Forex"],["materie","Materie prime"]].map(x=>`<button data-g="${x[0]}" class="${ST.g==x[0]?"on":""}">${x[1]}</button>`).join("")}</div></div>
   <h3 class="vft">Segnali freschi <span class="small">(pattern completato sull'ultima candela ${tf=="h4"?"H4":"giornaliera"} chiusa: ${freschi.length} su ${S.length} strumenti)</span></h3>
   ${freschi.length?`<div class="ptfresh">${freschi.map(s=>{const u=s[tf].ultimo,st=s[tf].stat;return `<button class="card ptc ${u.lato=="BUY"?"buy":"sell"}" data-id="${s.id}">
     <div class="ptct">${badge(u.lato)}<span class="small">chiusa ${quando(u.t,tf)}</span></div>
     <b class="ptn">${esc(s.n)}</b>
     <div class="ptlv"><span><em>Ingresso</em><b>${num(u.ingresso,cifre(u.ingresso))}</b></span><span><em>Apertura cand. 1</em><b>${num(u.livello,cifre(u.livello))}</b></span><span><em>${u.lato=="BUY"?"Minimo":"Massimo"} pattern</em><b>${num(u.estremo,cifre(u.estremo))}</b></span></div>
     <span class="small">Storico su ${esc(s.n)}: ${st.n?`${st.vinti}% nella direzione del segnale dopo ${st.dopo} candele (${st.n} casi, media ${st.media>0?"+":""}${fx(st.media,2)}%)`:"casi insufficienti"}</span></button>`;}).join("")}</div>`
    :`<div class="card small" style="padding:18px 20px">Nessun pattern sull'ultima candela ${tf=="h4"?"H4":"giornaliera"} chiusa. La tabella sotto mostra l'ultimo segnale di ogni strumento.</div>`}
   <h3 class="vft">Tutti gli strumenti <span class="small">(ultimo pattern di ciascuno &middot; clic per il grafico${tot?` &middot; storico complessivo ${tf=="h4"?"H4":"daily"}: ${tot.v}% nella direzione del segnale dopo ${d.dopo} candele, ${n} casi`:""})</span></h3>
   <div class="tablewrap"><table class="pttab"><tr><th>Strumento</th><th>Ultimo segnale</th><th>Chiusura candela 3</th><th class="num">Ingresso</th><th class="num">Ultimo prezzo</th><th class="num">Da ingresso</th><th class="num azh">Storico</th></tr>
    ${S.map(s=>{const u=s[tf].ultimo,st=s[tf].stat;return `<tr class="clic" data-id="${s.id}" tabindex="0"><td class="aznome"><b>${esc(s.n)}</b><span>${s.g=="forex"?"Forex":"Materie prime"}${s.copia?" &middot; dati del giro precedente":""}</span></td>
     <td>${u?`${badge(u.lato)} <span class="small">${fa(u.fa)}</span>`:'<span class="small">nessuno di recente</span>'}</td>
     <td>${u?quando(u.t,tf):""}</td><td class="num">${u?num(u.ingresso,cifre(u.ingresso)):""}</td><td class="num">${u?num(u.ora,cifre(u.ora)):""}</td><td class="num">${u?pc(u.mossa):""}</td>
     <td class="num azh">${st.n?`${st.vinti}% <span class="small">su ${st.n}</span>`:'<span class="small">n/d</span>'}</td></tr>`;}).join("")}</table></div>`;
  el.querySelectorAll(".pttf button").forEach(b=>b.onclick=()=>{ST.tf=b.dataset.tf;salva();disegna();});
  el.querySelectorAll(".ptg button").forEach(b=>b.onclick=()=>{ST.g=b.dataset.g;salva();disegna();});
  el.querySelectorAll("[data-id]").forEach(r=>{r.onclick=()=>apri(r.dataset.id);r.onkeydown=e=>{if(e.key=="Enter")apri(r.dataset.id);};});}

 // --- grafico a candele con i pattern evidenziati (pannello laterale, stesso stile del dettaglio Azionario)
 /* DETTAGLIO di uno strumento (v6.80): PAGINA INTERA come l'Azionario, con barra "Indietro" in alto (anche il tasto
    indietro del telefono/browser e Esc chiudono). Contenuto centrato con margini (.azwrap). Il grafico NON si deforma
    piu': il viewBox ha la stessa larghezza del riquadro (prima era 680 px "stirato" su tutto lo schermo e le scritte
    BUY/SELL e i prezzi uscivano schiacciati); se cambia la larghezza della finestra si ridisegna. */
 function grafico(a,u,tf,W){const C=a.candele,H=W<520?260:340,L=8,R=W<520?58:70,T=14,B=26;
  const lo=Math.min(...C.map(c=>c[3])),hi=Math.max(...C.map(c=>c[2])),Y=v=>T+(hi-v)/(hi-lo||1)*(H-T-B),bw=(W-L-R)/C.length,X=i=>L+i*bw+bw/2;
  const idx=new Map(C.map((c,i)=>[c[0],i]));
  // etichette BUY/SELL: almeno 38 px tra una e l'altra; si parte dalla piu' recente (quella del segnale attuale
  // resta sempre), andando indietro si salta chi si sovrapporrebbe
  const sg=a.segnali.filter(p=>idx.has(p.t)&&idx.get(p.t)>=2),conEt=new Set();let ultX=1e9;
  [...sg].reverse().forEach(p=>{const x=X(idx.get(p.t)-1);if(ultX-x>=38){conEt.add(p.t);ultX=x;}});
  const bande=sg.map(p=>{const i=idx.get(p.t),ult=u&&p.t==u.t,et=conEt.has(p.t);
   return `<rect x="${(L+(i-2)*bw).toFixed(1)}" y="${T}" width="${(3*bw).toFixed(1)}" height="${H-T-B}" class="ptband ${p.lato=="BUY"?"buy":"sell"}${ult?" ult":""}"/>${et?`<text x="${X(i-1).toFixed(1)}" y="${H-B-6}" text-anchor="middle" class="ptbl ${p.lato=="BUY"?"buy":"sell"}">${p.lato}</text>`:""}`;}).join("");
  const cand=C.map((c,i)=>{const su=c[4]>=c[1],top=Y(Math.max(c[1],c[4])),h=Math.max(1,Math.abs(Y(c[1])-Y(c[4])));
   return `<line x1="${X(i).toFixed(1)}" x2="${X(i).toFixed(1)}" y1="${Y(c[2]).toFixed(1)}" y2="${Y(c[3]).toFixed(1)}" class="ptw ${su?"su":"giu"}"/><rect x="${(X(i)-bw*0.36).toFixed(1)}" y="${top.toFixed(1)}" width="${Math.max(1,bw*0.72).toFixed(1)}" height="${h.toFixed(1)}" class="ptk ${su?"su":"giu"}"><title>${quando(c[0],tf)} · A ${c[1]} · M ${c[2]} · m ${c[3]} · C ${c[4]}</title></rect>`;}).join("");
  let linee="";if(u&&idx.has(u.t)){const i=idx.get(u.t);
   linee=`<line x1="${X(i-2)}" x2="${W-R}" y1="${Y(u.livello)}" y2="${Y(u.livello)}" class="ptl lv"/><text x="${W-R+6}" y="${Y(u.livello)+4}" class="ptlt lv">${num(u.livello,cifre(u.livello))}</text>
    <line x1="${X(i)}" x2="${W-R}" y1="${Y(u.ingresso)}" y2="${Y(u.ingresso)}" class="ptl in"/><text x="${W-R+6}" y="${Y(u.ingresso)+4}" class="ptlt in">${num(u.ingresso,cifre(u.ingresso))}</text>`;}
  const tick=[0,.25,.5,.75,1].map(k=>lo+(hi-lo)*k).map(v=>`<line x1="${L}" x2="${W-R}" y1="${Y(v)}" y2="${Y(v)}" class="pgr"/>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" class="ptsvg">${tick}${bande}${cand}${linee}</svg>`;}
 function apri(id){const s=ST.d.strumenti.find(x=>x.id==id);if(!s)return;const tf=ST.tf,a=s[tf],u=a.ultimo;
  // riquadro proprio (.ptdett): non si mescola con quello dell'Azionario
  let ov=document.querySelector(".ptdett");if(!ov){ov=document.createElement("div");ov.className="azdett ptdett";document.body.appendChild(ov);
   ov.addEventListener("click",e=>{if(e.target.closest(".azx"))ov._chiudi&&ov._chiudi();});
   window.addEventListener("popstate",()=>{if(ov.classList.contains("on"))ov._chiudi&&ov._chiudi(true);});}
  if(!ov.classList.contains("on")){try{history.pushState({ptStrumento:id},"");}catch(e){}}
  const largo=()=>{const g=ov.querySelector(".azgraf");return Math.max(300,Math.round(g?g.clientWidth:Math.min(980,innerWidth)-56));};
  const ridisegna=()=>{const g=ov.querySelector(".azgraf");if(g)g.innerHTML=grafico(a,u,tf,largo());};
  const chiudi=daCronologia=>{if(!ov.classList.contains("on"))return;
   if(!daCronologia){try{if(history.state&&history.state.ptStrumento){history.back();return;}}catch(e){}}   // il popstate richiama chiudi(true)
   ov.classList.remove("on");document.documentElement.classList.remove("azaperto");document.removeEventListener("keydown",tasto);
   removeEventListener("resize",ridisegna);setTimeout(()=>{if(!ov.classList.contains("on"))ov.innerHTML="";},250);};
  ov._chiudi=chiudi;
  const tasto=e=>{if(e.key=="Escape")chiudi();};document.removeEventListener("keydown",ov._tasto||(()=>{}));ov._tasto=tasto;document.addEventListener("keydown",tasto);
  removeEventListener("resize",ov._rid||(()=>{}));ov._rid=ridisegna;addEventListener("resize",ridisegna);
  document.documentElement.classList.add("azaperto");                                  // blocca lo scorrimento della pagina sotto
  const C=a.candele;
  ov.innerHTML=`<div class="azpan" role="dialog" aria-modal="true" aria-label="${esc(s.n)}">
   <div class="azbarra"><button class="azx" aria-label="Torna al Pattern Detector"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>Indietro</button>
    <span class="azbt"><b>${esc(s.n)}</b><small>${tf=="h4"?"H4":"Daily"}</small></span></div>
   <div class="azwrap">
   <div class="aztesta"><span class="small">${s.g=="forex"?"Forex":"Materie prime"} &middot; ${tf=="h4"?"H4":"Daily"} &middot; ultime ${C.length} candele chiuse</span><h3>${esc(s.n)}</h3>
    ${u?`<div class="azprz">${badge(u.lato)}<span class="small">pattern chiuso il ${quando(u.t,tf)} &middot; ${fa(u.fa)}</span></div>`:""}</div>
   <div class="azgraf ptgraf"></div>
   ${u?`<div class="pleg ptleg"><span><i class="lv"></i>Apertura candela 1 (${num(u.livello,cifre(u.livello))})</span><span><i class="in"></i>Chiusura candela 3 = ingresso (${num(u.ingresso,cifre(u.ingresso))})</span></div>
   <div class="azmini"><div><span>Ingresso</span><b>${num(u.ingresso,cifre(u.ingresso))}</b></div><div><span>${u.lato=="BUY"?"Minimo":"Massimo"} del pattern</span><b>${num(u.estremo,cifre(u.estremo))}</b></div><div><span>Da ingresso</span>${pc(u.mossa)}</div></div>`:""}
   <h4 class="aztit">Pattern passati <span class="small">(esito dopo ${ST.d.dopo} candele nella direzione del segnale)</span></h4>
   <div class="tablewrap"><table class="compatta"><tr><th><span class="ptlg">Chiusura candela 3</span><span class="ptsh">Candela 3</span></th><th>Segnale</th><th class="num">Ingresso</th><th class="num">Esito</th></tr>
    ${[...a.segnali].reverse().map(p=>`<tr><td class="ptdata">${quando(p.t,tf)}</td><td>${badge(p.lato)}</td><td class="num">${num(p.ingresso,cifre(p.ingresso))}</td><td class="num">${p.esito==null?'<span class="small">aperto</span>':pc(p.esito)}</td></tr>`).join("")||'<tr><td colspan="4" class="small">Nessun pattern nel periodo.</td></tr>'}</table></div>
   <p class="small azfonte">${s.fonte&&s.fonte.endsWith("=F")?"Prezzi del future (approssimazione dello spot). ":""}Le candele H4 sono allineate alla chiusura di New York (17:00, come MT4/MT5) e possono differire di poco da quelle del proprio broker.</p></div></div>`;
  ridisegna();                                               // dopo l'inserimento: ora si conosce la larghezza vera
  requestAnimationFrame(()=>{ov.classList.add("on");ridisegna();});ov.querySelector(".azx").focus({preventScroll:true});
  try{window.ebStat&&ebStat.ev("pattern",{strumento:id,tf:tf});}catch(e){}}
})();}catch(e){fail('Pattern Detector','pattern',e);}
