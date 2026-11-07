
/* ---------- portafogli modello ----------
   Dati da D.port (vedi cot_radar/portafogli.py): tre profili (conservativo, moderato, aggressivo), solo acquisti,
   rotazione il primo giorno di borsa di ogni mese. In alto un selettore a segmenti (Conservativo / Moderato /
   Aggressivo: "stesso motore, rischio diverso") e la CARD PRINCIPALE del profilo: rischio, descrizione, rendimento
   annuo, max drawdown, 10.000 euro dall'inizio dello storico, composizione per classe, le 5 azioni scelte del mese
   e la spiegazione apribile della rotazione. Sotto, per il profilo scelto:
     1. "Portafoglio di <mese>" del profilo scelto: righe raggruppate per classe (Azionario, Obbligazionario,
        Materie prime, Cripto, Liquidita'), per ogni mercato lo strumento UCITS/ETC/ETP da comprare in Europa con
        ISIN copiabile, peso e importo in euro sul capitale scritto dall'utente; le 5 azioni scelte elencate una per
        una (o l'ANTEPRIMA provvisoria del mese prossimo); esposizione al dollaro stimata;
        in alto il CONTO ALLA ROVESCIA al prossimo ribilanciamento (giorno di rotazione, 09:00 ora italiana);
     2. il rischio del MESE della rotazione (es. ottobre): la composizione di oggi tenuta in ogni ottobre dello
        storico, con rendimento e max drawdown dentro il mese anno per anno, esempio su 10.000 euro e
        stagionalita' del mese per ogni mercato (nessuna statistica per anno solare);
     3. la curva del capitale: storico, fuori campione (dal 2016) e live (dalla prima rotazione pubblicata),
        con il confronto 60/40; passando il mouse si leggono data e valore;
     4. tabella dei periodi, ultime rotazioni (entrati / usciti / tenuti) e mercati esclusi con il motivo.
   Il profilo scelto resta salvato nel browser (localStorage "ebProfilo"). */
try{(function(){const P=D.port,el=$("port");if(!el)return;
 if(!P||!P.profili||!P.profili.length){el.innerHTML=`<h2>Portafogli modello</h2><div class="sub psub">Tre profili di rischio in euro: solo acquisti, ribilanciamento una volta al mese.
   <details class="info"><summary title="Come funziona" aria-label="Come funziona">i</summary><div><b>Come funziona.</b> Ogni profilo ha una base fissa di mercati e pesi. Un mercato azionario resta finch&eacute; il prezzo &egrave; sopra la media a 200 giorni, altrimenti il suo peso va in liquidit&agrave; fino a quando torna sopra; Treasury e oro restano sempre come difesa. Il COT &egrave; mostrato solo come informazione: nei test non migliorava i risultati.<br><br><b>Come si misura.</b> Regole decise sullo storico fino al 2015 e verificate dal 2016; la prova davvero pulita &egrave; la linea live dal 2 novembre 2026. Numeri in euro senza copertura del cambio, costi 0,10% a ogni rotazione. Informazione, non consulenza.</div></details></div>`;return;}
 const CL={azioni:"var(--c1)","azioni singole":"var(--acc)",obbligazioni:"var(--c4)",metalli:"var(--warn)","materie prime":"var(--c2)",crypto:"var(--c5)",liquidita:"var(--c3)"};
 // nomi delle classi per la "composizione per classe" della card principale (ordine fisso di lettura)
 const CLN=[["azioni","Azionario (ETF)"],["azioni singole","Azioni singole"],["obbligazioni","Obbligazionario"],["metalli","Metalli preziosi"],["materie prime","Materie prime"],["crypto","Cripto"],["liquidita","Liquidità"]];
 // macro-classi per raggruppare le righe del portafoglio (azioni singole stanno nell'Azionario)
 const MACRO=[["Azionario",["azioni","azioni singole"]],["Obbligazionario",["obbligazioni"]],["Materie prime",["metalli","materie prime"]],["Cripto",["crypto"]],["Liquidità",["liquidita"]]];
 // borsa dal suffisso del ticker Yahoo; "ue:false" = di solito NON acquistabile dai broker europei per privati
 const BORSE={T:["Tokyo",1],NS:["India (NSE)",0],BO:["India (BSE)",0],SS:["Shanghai",0],SZ:["Shenzhen",0],HK:["Hong Kong",1],MI:["Milano",1],DE:["Xetra",1],PA:["Parigi",1],AS:["Amsterdam",1],L:["Londra",1],SW:["Svizzera",1],MC:["Madrid",1],BR:["Bruxelles",1],KS:["Corea",0],TW:["Taiwan",0],AX:["Australia",1],TO:["Toronto",1]};
 const borsa=t=>{const m=/\.([A-Z]+)$/.exec(t);return m?(BORSE[m[1]]||[m[1],1]):["USA",1];};
 const MESI=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];
 const SETT={tech:["Tecnologia"],tlc:["Comunicazione"],cdis:["Beni voluttuari"],cstap:["Prima necessità"],salute:["Salute"],fin:["Finanza"],ind:["Industria"],mat:["Materiali"],ener:["Energia"],util:["Servizi pubblici"],imm:["Immobiliare"]};
 // capitale per calcolare gli importi in euro di ogni riga (salvato nel browser)
 let capitale=10000;try{const c=+localStorage.getItem("ebCapitale");if(c>0)capitale=c;}catch(e){}
 // v6.100 SIMULATORE: capitale, orizzonte e leva scelti dall'utente (ricordati nel browser)
 let simCap=100000,simOrz="5",simLeva="1.0";
 try{const c=+localStorage.getItem("ebSimCap");if(c>0)simCap=c;simOrz=localStorage.getItem("ebSimOrz")||simOrz;simLeva=localStorage.getItem("ebSimLeva")||simLeva;}catch(e){}
 const RISK={conservativo:["Basso","r1"],moderato:["Medio","r2"],aggressivo:["Alto","r3"]};
 const pc=(v,d=1)=>v==null?"n/d":(v>0?"+":"")+fx(v,d)+"%";
 const eur=v=>v==null?"n/d":Math.round(v).toLocaleString("it-IT")+" €";
 const gg=d=>d?d.slice(8,10)+"/"+d.slice(5,7)+"/"+d.slice(0,4):"";
 const nomeK=k=>{for(const p of P.profili){const c=p.composizione.find(x=>x.k==k);if(c)return c.nome;const a=p.ammessi.find(x=>x.k==k);if(a)return a.nome;}return k;};
 let sel=P.profili[1].id,per="tutto",tutteRot=false;
 try{const s=localStorage.getItem("ebProfilo");if(s&&P.profili.some(p=>p.id==s))sel=s;}catch(e){}

 // --- ciambella dei pesi (SVG): un arco per mercato, colore = classe
 function ciambella(comp){const R=62,C=2*Math.PI*R;let off=0;
  const archi=comp.map(c=>{const l=C*c.peso/100,s=`<circle r="${R}" cx="80" cy="80" fill="none" stroke="${CL[c.classe]||"var(--c3)"}" stroke-width="22" stroke-dasharray="${Math.max(0,l-2)} ${C}" stroke-dashoffset="${-off}" transform="rotate(-90 80 80)"><title>${esc(c.nome)}: ${fx(c.peso,1)}%</title></circle>`;off+=l;return s;}).join("");
  const n=comp.filter(c=>c.k!="CASH").length;
  return `<svg viewBox="0 0 160 160" class="ptorta" role="img" aria-label="Composizione del portafoglio">${archi}<text x="80" y="76" text-anchor="middle" class="ptn">${n}</text><text x="80" y="96" text-anchor="middle" class="ptl">${n==1?"mercato":"mercati"}</text></svg>`;}

 // --- curva del capitale (SVG, scala logaritmica: le percentuali hanno la stessa altezza in ogni epoca)
 function curva(p){const W=900,H=300,L=52,Rm=14,T=16,B=30;
  let pts=p.curva,bench=(P.bench||{}).curva||[];
  const dal=per=="oos"?P.oos_dal:per=="live"?(p.live_dal||P.oos_dal):null;
  if(dal){pts=pts.filter(x=>x[0]>=dal);bench=bench.filter(x=>x[0]>=dal);}
  if(pts.length<2)return `<div class="small" style="padding:30px;text-align:center">Dati non ancora sufficienti per questo periodo.</div>`;
  const b0=pts[0][1],bb0=(bench[0]||[0,1])[1];
  const s=pts.map(x=>[x[0],x[1]/b0*100]),sb=bench.map(x=>[x[0],x[1]/bb0*100]);
  const t0=+new Date(s[0][0]),t1=+new Date(s[s.length-1][0]);
  const tutti=s.concat(sb).map(x=>x[1]),lo=Math.log(Math.min(...tutti)*.97),hi=Math.log(Math.max(...tutti)*1.03);
  const X=d=>L+(+new Date(d)-t0)/(t1-t0||1)*(W-L-Rm),Y=v=>T+(hi-Math.log(v))/(hi-lo||1)*(H-T-B);
  const path=a=>a.map((x,i)=>(i?"L":"M")+X(x[0]).toFixed(1)+" "+Y(x[1]).toFixed(1)).join("");
  // griglia orizzontale: valori "tondi" del capitale (base 100)
  const passi=[25,50,75,100,150,200,300,400,600,800,1000,1500,2000,3000,5000];
  const righe=passi.filter(v=>Math.log(v)>lo&&Math.log(v)<hi).map(v=>`<line x1="${L}" x2="${W-Rm}" y1="${Y(v)}" y2="${Y(v)}" class="pgr"/><text x="${L-8}" y="${Y(v)+4}" text-anchor="end" class="pax">${v}</text>`).join("");
  const anni=[];for(let a=+s[0][0].slice(0,4)+1;a<=+s[s.length-1][0].slice(0,4);a++){const d=a+"-01-01";anni.push(a);}
  const passoA=Math.ceil(anni.length/10)||1;
  const etA=anni.filter((a,i)=>i%passoA==0).map(a=>`<text x="${X(a+"-01-01")}" y="${H-8}" text-anchor="middle" class="pax">${a}</text>`).join("");
  // fasce: fuori campione e live
  const fascia=(d,cls,et)=>d&&d>s[0][0]?`<rect x="${X(d)}" y="${T}" width="${W-Rm-X(d)}" height="${H-T-B}" class="${cls}"/><text x="${X(d)+8}" y="${T+14}" class="pfet">${et}</text>`:"";
  const live=p.live_dal?s.filter(x=>x[0]>=p.live_dal):[];
  return `<svg viewBox="0 0 ${W} ${H}" class="pcurva" data-t0="${t0}" data-t1="${t1}" preserveAspectRatio="none">
   ${righe}${fascia(P.oos_dal,"pfoos","VERIFICA")}${p.live_dal?fascia(p.live_dal,"pflive","LIVE"):""}${etA}
   ${sb.length?`<path d="${path(sb)}" class="pbench"/>`:""}<path d="${path(s)}" class="plinea"/>${live.length>1?`<path d="${path(live)}" class="plive"/>`:""}
   <line class="pcur" x1="0" x2="0" y1="${T}" y2="${H-B}" style="display:none"/><circle class="pcurp" r="4.5" style="display:none"/></svg>
   <div class="ptip" hidden></div>
   <div class="pleg"><span><i class="lp"></i>Portafoglio ${esc(p.nome.toLowerCase())}</span><span><i class="lb"></i>${esc((P.bench||{}).nome||"60/40")}</span>${p.live_dal?'<span><i class="ll"></i>Live</span>':""}</div>`;}

 // --- una riga del portafoglio: nome, strumento UCITS da comprare (ISIN copiabile), motivo, peso, importo in euro.
 //     Per "Azioni scelte": elenco dei 5 titoli (registrati, oppure ANTEPRIMA provvisoria del mese prossimo).
 function riga(c,p){const col=CL[c.classe]||"var(--c3)";
  const mot=c.k=="CASH"?"Liquidit&agrave; fissa del profilo + pesi dei mercati in pausa."
   :c.k=="AZ"?`filtro di mercato: S&amp;P 500 ${pc(c.trend)} sopra la media a 200 giorni`
   :`trend ${pc(c.trend)} sopra la media a 200 giorni · volatilit&agrave; ${fx(c.vol,0)}% · COT ${c.score!=null?sg(c.score,0):"n/d"} (informativo)`;
  const ue=c.ue?`<div class="pue"><span class="pue-n">${esc(c.ue.nome)}</span><button class="pisin" data-isin="${esc(c.ue.isin)}" title="Copia l'ISIN da cercare nell'app del broker"><code>${esc(c.ue.isin)}</code><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg></button></div>`
   :`<span>${esc(c.strumento)}</span>`;
  let tit="";
  if(c.k=="AZ"){const reg=c.titoli&&c.titoli.length,an=c.anteprima,lista=reg?c.titoli:(an&&an.titoli)||[];
   const quota=lista.length?c.peso/lista.length:0;
   if(lista.length)tit=`<div class="paz">${reg?"":`<div class="paz-ante"><b>Anteprima per ${MESI[+an.mese.slice(5,7)-1]}</b> &middot; calcolata il ${gg(an.al)} con i prezzi di oggi. La lista definitiva si fissa l'ultimo giorno di borsa dopo la chiusura ed entra il ${gg(P.prossima)}.</div>`}
    ${lista.map(x=>{const b=borsa(x.t),sett=(SETT[x.s]||[x.s||""])[0];return `<button class="paz-r clic" data-az="${esc(x.t)}" title="Apri nell'Azionario">
     <span class="paz-id"><b>${esc(x.t)}</b><span class="paz-n">${esc(x.n)}</span>${x.sost?`<span class="paz-sost" title="${esc(x.sost_n||x.sost)} (${esc(x.sost)}) non si compra su Scalable: sostituito dal candidato acquistabile successivo, stessi filtri">al posto di ${esc(x.sost_n||x.sost)}</span>`:""}<span class="paz-isin" data-isinaz="${esc(x.t)}" hidden></span></span><span class="paz-s">${esc(sett)}</span><span class="paz-b${b[1]?"":" no"}" title="${b[1]?"Borsa di quotazione":"Di solito non acquistabile dai broker europei per privati"}">${b[0]}</span><span class="paz-p"><b>${fx(quota,1)}%</b><em data-peso="${quota}">${eur(capitale*quota/100)}</em></span></button>`;}).join("")}</div>`;
   else tit=`<div class="small paz-vuoto">I 5 titoli si scelgono l'ultimo giorno di borsa del mese, dopo la chiusura, ed entrano con la rotazione del ${gg(P.prossima)}.</div>`;}
  // l'elenco dei titoli sta su una riga a parte della griglia, a tutta larghezza (leggibile anche su telefono)
  return `<div class="prow${c.k=="AZ"?" prow-az":""}"><i style="background:${col}"></i><div class="pnome"><b>${esc(c.nome)}<details class="info pmot"><summary title="Perch&eacute; &egrave; in portafoglio" aria-label="Perch&eacute; &egrave; in portafoglio">i</summary><div>${mot}${c.ue&&c.ue.nota?`<br>${esc(c.ue.nota)}`:""}</div></details></b>${ue}</div>
   <div class="ppeso"><b>${fx(c.peso,1)}%</b><span class="peur">${eur(capitale*c.peso/100)}</span><span class="pbar"><i style="width:${Math.min(100,c.peso*2.5)}%;background:${col}"></i></span></div>${tit}</div>`;}

 // --- composizione del mese raggruppata per macro-classe (Azionario, Obbligazionario, Materie prime, Cripto, Liquidita')
 function composizione(p){const mesi=MESI[+P.rotazione.slice(5,7)-1];
  const gruppi=MACRO.map(g=>({n:g[0],r:p.composizione.filter(c=>g[1].includes(c.classe))})).filter(g=>g.r.length);
  // esposizione al dollaro: mercati quotati in USD (indici USA, Treasury, oro, Bitcoin) + azioni USA tra le scelte
  const USD=["SP500","NASDAQ","DOW","RUSSELL","US10Y","USBOND","GOLD","SILVER","PLATINUM","BTC","ETH"];
  let usd=p.composizione.filter(c=>USD.includes(c.k)).reduce((a,c)=>a+c.peso,0);
  const az=p.composizione.find(c=>c.k=="AZ");if(az){const l=(az.titoli&&az.titoli.length?az.titoli:(az.anteprima||{}).titoli)||[];if(l.length)usd+=az.peso*l.filter(x=>borsa(x.t)[0]=="USA").length/l.length;}
  return `<div class="card pcomp"><div class="ptesta"><div><h3>Portafoglio di ${mesi} <span class="pbprof">${esc(p.nome)}</span></h3>
    <span class="small">${p.composizione.filter(c=>c.k!="CASH").length} mercati &middot; prossimo controllo ${gg(P.prossima)}</span>
    </div>${ciambella(p.composizione)}</div>
   ${gruppi.map(g=>`<div class="pgrp"><div class="pgrp-t"><span>${g.n}</span><b>${fx(g.r.reduce((a,c)=>a+c.peso,0),1)}%</b></div>${g.r.map(c=>riga(c,p)).join("")}</div>`).join("")}
   <div class="pfx"><span>Esposizione al dollaro stimata <b>${fx(usd,0)}%</b></span><details class="info"><summary title="Valute e strumenti" aria-label="Valute e strumenti">i</summary><div><b>Valute.</b> Nessuna posizione diretta in valuta, ma gli strumenti in euro che seguono mercati USA (S&amp;P 500, Treasury, oro, Bitcoin) si muovono anche con il cambio EUR/USD.<br><br><b>Strumenti.</b> UCITS / ETC / ETP acquistabili da un conto europeo: cerca l'ISIN nell'app del tuo broker. Gli ETF USA usati nei calcoli (SPY, QQQ&hellip;) non sono acquistabili dai privati in Europa.</div></details></div></div>`;}

 // --- v6.91 ACQUISTO DIRETTO A QUOTE INTERE (Scalable e gli altri broker: con l'ordine normale si comprano solo quote
 //     intere). Per ogni strumento: quote = parte intera di (obiettivo / prezzo di 1 quota, con 0,5% di margine perche'
 //     il prezzo e' quello di chiusura e durante il giorno si muove). Le 5 azioni: se 1 azione costa piu' della sua
 //     quota, al suo posto la prima RISERVA (stessa regola, punteggio successivo) che ci sta, max 1 titolo per settore.
 //     Quello che avanza resta sul conto. Il modello e il registro live non cambiano: e' solo come lo realizzi tu.
 const MARG=1.005;
 function piano(p){const righe=[];let spesa=0;
  const ordine=[];MACRO.forEach(g=>p.composizione.filter(c=>g[1].includes(c.classe)).forEach(c=>ordine.push(c)));
  ordine.forEach(c=>{const obi=capitale*c.peso/100;
   if(c.k=="AZ"){const lista=c.titoli||[];if(!lista.length)return;const per=obi/lista.length,ris=(c.riserve||[]).slice(),settori=new Set(lista.map(x=>x.s));
    lista.forEach(x=>{let t=x,nota=null;
     if(!x.eur||x.eur*MARG>per){                                // 1 azione costa piu' della quota (o prezzo mancante)
      settori.delete(x.s);const i=ris.findIndex(r=>r.eur*MARG<=per&&!settori.has(r.s)&&!lista.some(y=>y.t==r.t));
      if(i>=0){t=ris.splice(i,1)[0];nota=`al posto di ${x.n}${x.eur?` (1 azione &asymp; ${eur(x.eur)})`:""}`;}else{t=null;nota=`${x.n}: 1 azione costa pi&ugrave; della quota e nessuna riserva ci sta, resta sul conto`;}
      if(t)settori.add(t.s);}
     if(!t){righe.push({az:true,nome:x.n,tk:x.t,q:0,prezzo:x.eur,obi:per,nota});return;}
     const q=Math.floor(per/(t.eur*MARG));spesa+=q*t.eur;righe.push({az:true,nome:t.n,tk:t.t,q,prezzo:t.eur,obi:per,nota});});
    return;}
   // v7.1 LIQUIDITA' SUL CONTO: niente ETF overnight da comprare, la quota resta sul conto del broker (interessi)
   // v7.5 regola BCE: tasso sui depositi sotto zero = niente XEON (perde ogni giorno), si resta sul conto a 0%
   if(c.k=="CASH"){const t=P.tasso_bce,neg=t!=null&&t<=0;
    righe.push({cash:true,neg,nome:"Liquidità sul conto",obi,real:obi,q:null,prezzo:null,
     nota:t==null?null:neg?`tasso BCE ${fx(t,2)}%: niente XEON`:`oppure XEON (LU0290358497) &middot; tasso BCE ${fx(t,2)}%`});return;}
   const lv=window.ebLive&&ebLive.ue&&ebLive.ue[c.k],pr=(lv&&lv.p)||(c.ue&&c.ue.prezzo);   // v7.1: intraday se c'e'
   if(!pr){righe.push({nome:c.ue?c.ue.nome:c.nome,isin:c.ue&&c.ue.isin,q:null,prezzo:null,obi});return;}
   const q=Math.floor(obi/(pr*MARG));spesa+=q*pr;
   righe.push({nome:c.ue.nome,isin:c.ue.isin,q,prezzo:pr,obi,nota:q?null:`1 quota costa di pi&ugrave;: resta sul conto`});});
  const scost=righe.reduce((a,r)=>a+Math.abs((r.real??(r.q||0)*(r.prezzo||0))-r.obi),0)/2/(capitale||1)*100;
  return {righe,spesa,resto:capitale-spesa,scost};}
 function acquistoHTML(p){const pi=piano(p);if(!pi.righe.length)return "";
  // orario dei PREZZI (non della corsa): a borse chiuse e' l'ultima seduta, quindi si mostra anche la data
  const L=window.ebLive,tt=L&&L.ue?Math.max(0,...Object.values(L.ue).map(v=>v.t||0)):0,dt=tt?new Date(tt*1000):null,
   oggi=dt&&dt.toDateString()==new Date().toDateString(),
   ora=dt?(oggi?"":dt.toLocaleDateString("it-IT",{day:"2-digit",month:"2-digit"})+" ")+dt.toLocaleTimeString("it-IT",{hour:"2-digit",minute:"2-digit"}):null;
  return `<div class="pacq-t"><h3>Acquisto diretto <span class="small">quote intere su ${eur(capitale)}</span></h3>
    <span class="plive${ora&&oggi?" on":""}" title="${ora?"Prezzi intraday con il ritardo di borsa (circa 15-20 minuti)":"Prezzi di chiusura dell'ultima seduta"}"><i></i>${ora?(oggi?`prezzi delle ${ora} &middot; ritardo ~15 min`:`ultimi prezzi: ${ora}`):"prezzi di chiusura"}</span>
    <details class="info pacq-i"><summary title="Come si calcola" aria-label="Informazioni">i</summary><div>Con l'ordine normale il broker compra solo <b>quote intere</b>: per ogni strumento il numero di quote &egrave; la parte intera di importo del modello &divide; prezzo di 1 quota (prezzo di chiusura, con 0,5% di margine). Quello che avanza resta sul conto. Le <b>5 azioni</b>: se 1 azione costa pi&ugrave; della sua quota, al suo posto c'&egrave; il candidato successivo della stessa regola che ci sta (massimo 1 per settore). Con capitali piccoli lo <b>scostamento dal modello</b> &egrave; normale; il modello e i risultati pubblicati non cambiano. Prezzi indicativi: controllali sul broker prima di confermare.</div></details></div>
   <div class="pacq-l">${pi.righe.map(r=>`<div class="pacq-r${r.q===0?" zero":""}"><div class="pacq-n"><b>${esc(r.nome)}</b><span>${r.cash&&!r.nota?"nessun acquisto":r.cash?"":r.isin?`ISIN ${esc(r.isin)}`:esc(r.tk||"")}${r.nota?(r.cash&&!r.neg?r.nota:`${r.cash?"":" &middot; "}<em>${r.nota}</em>`):""}</span></div>
    <div class="pacq-q">${r.cash?`<b>${eur(r.obi)}</b><span>resta sul conto</span>`:r.q==null?`<span class="small">prezzo n/d &middot; ${eur(r.obi)}</span>`:`<b>${r.q} ${r.q==1?"quota":"quote"}</b><span>${r.prezzo?"&times; "+fx(r.prezzo,2)+" € = "+eur(r.q*r.prezzo):""}</span>`}</div></div>`).join("")}</div>
   <div class="pacq-tot"><span>Investito <b>${eur(pi.spesa)}</b></span><span>Resta sul conto <b>${eur(pi.resto)}</b></span></div>
   <details class="pacq-come"><summary>Come comprare su Scalable</summary><ol>
    <li>Copia l'<b>ISIN</b> (o il ticker per le azioni) e cercalo nella barra di ricerca.</li>
    <li>Premi <b>Acquista</b>: la borsa proposta (es. European Investor Exchange) va bene.</li>
    <li>Passa da <b>Importo target</b> alla scheda <b>Numero di titoli</b> e scrivi le quote indicate qui sopra (con l'importo Scalable arrotonda per difetto alle quote intere).</li>
    <li><b>Prepara ordine</b>, controlla il totale e conferma, in orario di borsa (09:00-17:30).</li>
    <li>Niente <b>piano di accumulo</b>: si ripete ogni mese, mentre il portafoglio ruota.</li></ol></details>`;}

 // --- RISCHIO DEL MESE della rotazione (v6.41): la composizione di oggi tenuta nello stesso mese di ogni anno dello storico.
 //     1) TERMOMETRO: drawdown peggiore del mese contro il limite del profilo (tacca bianca), verdetto in parole;
 //     2) HEAT MAP: una casella per anno con la %, verde = guadagno, rosso = perdita (piu' intenso = piu' grande);
 //        interruttore "Risultato del mese" / "Scenario peggiore" (drawdown dentro il mese); fumetto con i dettagli;
 //     3) quattro numeri chiave allineati (titoli su piu' righe non spostano i valori: CSS subgrid).
 let hmModo="r";                                         // modo della heat map, ricordato cambiando profilo
 function hmCelle(m,modo){const peg=m.anni.reduce((a,x)=>x.dd<a.dd?x:a,m.anni[0]),per={};m.anni.forEach(x=>per[x.a]=x);
  const d0=Math.floor(m.anni[0].a/10)*10,d1=Math.floor(m.anni[m.anni.length-1].a/10)*10;
  const col=x=>{const t=Math.min(1,Math.abs(x)/(modo=="dd"?6:5));return modo=="dd"||x<0?`rgba(242,113,107,${(.12+.78*t).toFixed(2)})`:`rgba(79,214,163,${(.12+.78*t).toFixed(2)})`;};
  let h="";
  for(let d=d0;d<=d1;d+=10){h+=`<div class="phmdec">${d==1990?"anni '90":"anni "+d}</div>`;
   for(let y=d;y<d+10;y++){const x=per[y];
    if(!x){h+=`<div class="phmc vuota" aria-hidden="true"></div>`;continue;}
    const v=modo=="r"?x.r:x.dd;
    h+=`<div class="phmc${x.a==peg.a?" peg":""}" tabindex="0" data-a="${y}" style="background:${col(v)}"><span>${y}</span><b>${pc(v)}</b></div>`;}}
  return h;}
 function hmLeg(modo){return modo=="r"
  ?`<span>perdita</span><i style="background:linear-gradient(90deg,rgba(242,113,107,.9),rgba(242,113,107,.12) 48%,rgba(79,214,163,.12) 52%,rgba(79,214,163,.9))"></i><span>guadagno</span>`
  :`<span>drawdown piccolo</span><i style="background:linear-gradient(90deg,rgba(242,113,107,.12),rgba(242,113,107,.9))"></i><span>drawdown grande</span>`;}
 function contro(p){const m=p.mese,s=p.stat.totale||{},o=p.stat.oos||{},ddTot=Math.min(s.maxdd??0,o.maxdd??0);
  if(!m)return `<div class="card pcontro"><h3>Rischio del mese</h3><div class="small">Storico non ancora sufficiente.</div></div>`;
  const peg=m.anni.reduce((a,x)=>x.dd<a.dd?x:a,m.anni[0]),lim=-p.dd_rif,oltre=m.dd_max<lim,wr=Math.round(100*m.positivi/m.n);
  const altri=Math.min(...m.anni.filter(x=>x!==peg).map(x=>x.dd));
  // termometro: 0% a sinistra, fondo scala poco oltre il peggiore tra drawdown e limite
  const fondo=Math.min(m.dd_max,lim)*1.18,pos=v=>(v/fondo*100).toFixed(1);
  const k=(t,v,sub,cls="")=>`<div><span>${t}</span><b class="${cls}">${v}</b><em>${sub}</em></div>`;
  return `<div class="card pcontro"><div class="pctesta"><h3>Rischio di ${m.mese}</h3><span class="pbprof">${esc(p.nome)}</span><details class="info pci"><summary title="Come si legge" aria-label="Come si legge">i</summary><div>Questo portafoglio tenuto in ogni ${m.mese} dal ${m.anni[0].a} (${m.n} anni). Peggior caso: ${m.mese} ${peg.a}, con 10.000 &euro; il conto sarebbe sceso fino a ${eur(10000*(1+m.dd_max/100))} durante il mese. Negli altri anni il drawdown non ha superato il ${pc(altri)}.</div></details></div>
   <div class="ptermo-t"><span>Drawdown peggiore di ${m.mese}</span><em class="${oltre?"pko":"pok"}">${oltre?`Oltre il limite di ${fx(Math.abs(m.dd_max-lim),1)} punti`:"Dentro il limite del profilo"}</em></div>
   <div class="ptermo"><div class="ptermo-r" style="width:${pos(m.dd_max)}%"></div><span class="ptermo-l" style="left:${pos(lim)}%"></span>
    <span class="ptermo-e su" style="left:${pos(lim)}%">limite ${pc(lim,0)}</span><span class="ptermo-e giu" style="left:0;transform:none">0%</span>
    <span class="ptermo-e giu" style="left:${pos(m.dd_max)}%">${pc(m.dd_max)}</span></div>
   <div class="phmtesta"><span>${m.mese[0].toUpperCase()+m.mese.slice(1)} anno per anno</span>
    <div class="phmsw" role="tablist"><button type="button" data-m="r" class="${hmModo=="r"?"on":""}" role="tab" aria-selected="${hmModo=="r"}">Risultato del mese</button><button type="button" data-m="dd" class="${hmModo=="dd"?"on":""}" role="tab" aria-selected="${hmModo=="dd"}">Scenario peggiore</button></div></div>
   <div class="phmbox"><div class="phm">${hmCelle(m,hmModo)}</div><div class="phmtip" hidden></div></div>
   <div class="phmleg">${hmLeg(hmModo)}</div>
   <div class="pmini">${k("Peggior "+m.mese,pc(m.peggiore[1]),String(m.peggiore[0]),"down")}${k(m.mese[0].toUpperCase()+m.mese.slice(1)+" medio",pc(m.media),`su ${m.n} anni`,m.media>=0?"up":"down")}
    ${k("Anni positivi",`${m.positivi} su ${m.n}`,`${wr}% degli anni`)}${k("Max drawdown",pc(ddTot),"di sempre","down")}</div>
   ${m.mercati.length?`<div class="pstag"><div class="pstag-t">${m.mese[0].toUpperCase()+m.mese.slice(1)} per mercato</div>${m.mercati.map(x=>`<div class="pstag-r"><span>${esc(nomeK(x.k))}</span><i><s class="${x.media>=0?"su":"giu"}" style="width:${Math.min(100,Math.abs(x.media)*8)}%"></s></i><b class="${x.media>=0?"up":"down"}">${pc(x.media)}</b><em><span>${x.pos}% positivi</span><span>${x.n} anni</span></em></div>`).join("")}</div>`:""}</div>`;}


 // --- MESE IN CORSO (v6.43): come sta andando adesso il portafoglio del profilo scelto, dalla rotazione a oggi.
 //     Prezzi a fine giornata (EOD), ingresso alla chiusura del giorno di rotazione (come nello storico e nel registro).
 //     Il risultato e' provvisorio fino a fine mese; i mesi chiusi dal live restano nel registro (chiusure_v3.json).
 // v6.98: prezzi "fermi" = l'ultima chiusura usata e' indietro di piu' di una seduta (giorni feriali, ora italiana)
 function fermi(al){if(!al)return false;const d=new Date(al+"T12:00:00"),o=new Date();let n=0;
  for(const x=new Date(d);x<o;x.setDate(x.getDate()+1)){const w=x.getDay();if(x>d&&w>0&&w<6)n++;}
  return n>2;}                                                          // oggi + ieri ancora "normali"
 function corso(p){const c=p.corrente;if(!c)return "";
  const z=v=>v==null?v:(Math.abs(v)<0.05?0:v);                       // niente "-0,0%": sotto 0,05 punti e' zero
  const r=z(c.r),rr=z(c.rr),m=p.mese,cl=r>0?"up":r<0?"down":"flat",MES=x=>x[0].toUpperCase()+x.slice(1);
  const chiusi=(P.chiusure||[]).filter(x=>x.profili&&x.profili[p.id]).slice(-6).reverse();
  let termo="";
  if(m&&m.anni&&m.anni.length){const rs=m.anni.map(x=>x.r),lo=Math.min(...rs,c.r),hi=Math.max(...rs,c.r),sp=(hi-lo)||1,pos=v=>Math.max(3,Math.min(97,(v-lo)/sp*100)).toFixed(1);
   termo=`<div class="pmc-f"><span class="pmc-pt" style="left:${pos(c.r)}%"></span><span class="pmc-e" style="left:3%;transform:none">${pc(lo)}</span><span class="pmc-e" style="left:${pos(m.media)}%">media ${pc(m.media)}</span><span class="pmc-e" style="left:97%;transform:translateX(-100%)">${pc(hi)}</span></div>
`;}
  const wr=m&&m.n?Math.round(100*m.positivi/m.n):null;
  const k=(t,v,cls="")=>`<div><small>${t}</small><b class="${cls}">${v}</b></div>`;
  if(c.attesa)return `<div class="card pmc"><div class="pmc-t"><h3>${MES(c.mese)} in partenza <span class="pbprof">${esc(p.nome)}</span></h3>
    <span class="pmc-b">Composizione decisa &middot; si entra il ${gg(c.dal)}</span></div>
   <div class="pmc-k">${k("Giorni di borsa nel mese",c.tot)}${k("Mesi storici in positivo",wr==null?"n/d":wr+"%")}${k("Media storica del mese",m&&m.media!=null?pc(m.media):"n/d",m&&m.media>=0?"up":"down")}</div>
   ${chiusi.length?`<div class="pmc-h"><div class="pmc-ht">Mesi chiusi (live)</div>${chiusi.map(x=>{const r=x.profili[p.id];return `<div class="pmc-hr"><span>${MES(MESI[+x.mese.slice(5)-1])} ${x.mese.slice(0,4)}</span><b class="${r.r>=0?"up":"down"}">${pc(r.r)}</b><em>drawdown ${pc(r.dd)}</em></div>`;}).join("")}</div>`:""}</div>`;
  return `<div class="card pmc"><div class="pmc-t"><h3>${MES(c.mese)} in corso <span class="pbprof">${esc(p.nome)}</span><details class="info pmci"><summary title="Come si legge" aria-label="Come si legge">i</summary><div>Risultato del mese dalla chiusura del giorno di rotazione all'ultima chiusura. La barra sotto confronta il mese con gli stessi mesi degli anni passati (minimo, media, massimo). Il risultato &egrave; provvisorio fino a fine mese.</div></details></h3>
    <span class="pmc-b${c.live?"":" sim"}">${c.live?"Provvisorio &middot; si chiude a fine mese":"Simulazione &middot; il live parte il "+gg(P.prossima)}</span></div>
   <div class="pmc-g"><b class="${cl}">${pc(r)}</b><span>da inizio mese &middot; ingresso alla chiusura del ${gg(c.dal)} &middot; <em class="pmc-al${fermi(c.al)?" fermo":""}" title="${fermi(c.al)?"Prezzi non aggiornati: il risultato non include le ultime sedute":"Ultima chiusura usata"}">prezzi al ${gg(c.al)}${fermi(c.al)?" (in aggiornamento)":""}</em></span></div>
   <div class="pmc-oggi" hidden></div>
   <div><div class="pmc-bar"><i style="width:${Math.min(100,c.gg/c.tot*100).toFixed(0)}%"></i></div><div class="pmc-bl"><span>Giorno ${c.gg} di ${c.tot} di borsa</span><span>fine mese</span></div></div>
   <div class="pmc-k">${k("Drawdown peggiore",pc(c.dd),"down")}${k("Mesi storici in positivo",wr==null?"n/d":wr+"%")}</div>
   ${termo}
   ${chiusi.length?`<div class="pmc-h"><div class="pmc-ht">Mesi chiusi (live)</div>${chiusi.map(x=>{const r=x.profili[p.id];return `<div class="pmc-hr"><span>${MES(MESI[+x.mese.slice(5)-1])} ${x.mese.slice(0,4)}</span><b class="${r.r>=0?"up":"down"}">${pc(r.r)}</b><em>drawdown ${pc(r.dd)}</em></div>`;}).join("")}</div>`:""}
</div>`;}

 function tabella(p){const st=p.stat,b=(P.bench||{}).stat||{};
  // v6.52: la colonna Live compare solo quando ci sono dati live (prima era una colonna di "in arrivo")
  const col=[["Storico",st.storico,`fino al 2015`],["Verifica",st.oos,`dal 2016`]].concat(st.live?[["Live",st.live,p.live_dal?`dal ${gg(p.live_dal)}`:"dall'avvio"]]:[]).concat([["60/40",b.oos,"dal 2016"]]);
  const r=(t,f)=>`<tr><th>${t}</th>${col.map(c=>`<td>${c[1]?f(c[1]):'<span class="small">n/d</span>'}</td>`).join("")}</tr>`;
  return `<div class="tablewrap ptab"><table><tr><th class="ptab0">Risultati<span>per periodo <details class="info pti"><summary title="Periodi" aria-label="Periodi">i</summary><div>Regole decise sui dati fino al 2015 e verificate dal 2016 in poi. 60/40 = 60% azioni USA e 40% Treasury, per confronto.${st.live?"":` La colonna Live compare dopo la prima rotazione con le regole attuali.`}</div></details></span></th>${col.map(c=>`<th>${c[0]}<span>${c[2]}</span></th>`).join("")}</tr>
   ${r("Rendimento annuo",x=>x.cagr==null?pc(x.totale)+" tot.":pc(x.cagr))}
   ${r("Max drawdown",x=>`<b class="down">${pc(x.maxdd)}</b>`)}${r("Peggior mese",x=>x.peggior_mese?pc(x.peggior_mese[1]):"n/d")}${r("Mesi positivi",x=>(x.mesi_pos??"n/d")+"%")}</table></div>
`;}

 /* v6.52: ogni rotazione mostra com'e' andato il mese (netto e drawdown) e, aprendo "Dettaglio", ogni mercato con
    peso, rendimento, contributo al totale (punti %) e drawdown; per le Azioni scelte anche i singoli titoli. */
 function dettMese(m){if(!m)return `<div class="prisul small">mese in corso</div>`;
  const riga=a=>`<tr><td>${esc(a.nome)}${a.titoli&&a.titoli.length?`<div class="ptit">${a.titoli.map(t=>`<span>${esc(t.n)} <em class="${t.r==null?"":t.r>=0?"up":"down"}">${t.r==null?"in corso":pc(t.r)}</em></span>`).join("")}</div>`:""}</td>
   <td class="num">${fx(a.w,0)}%</td>${a.attesa?`<td class="num small" colspan="3" title="I rendimenti delle 5 azioni di questo mese arrivano con il prossimo aggiornamento dell'Azionario">dati in arrivo</td>`:`<td class="num ${a.r>=0?"up":"down"}">${pc(a.r)}</td><td class="num ${a.c>=0?"up":"down"}">${a.c>0?"+":""}${fx(a.c,2)}</td><td class="num down">${pc(a.dd)}</td>`}</tr>`;
  const peg=m.asset.filter(x=>x.c!=null).sort((x,y)=>x.c-y.c)[0];
  return `<div class="prisul"><span>Risultato <b class="${m.r>=0?"up":"down"}">${pc(m.r)}</b></span><span>drawdown <b class="down">${pc(m.dd)}</b></span></div>
   <details class="pdet"><summary>Dettaglio del mese</summary>
    ${peg&&peg.c<0?`<p class="small">Ha pesato di pi&ugrave;: <b>${esc(peg.nome)}</b> (${fx(peg.c,2)} punti sul totale).</p>`:""}
    <div class="tablewrap"><table class="compatta pdett"><tr><th>Mercato</th><th class="num">Peso</th><th class="num">Rend.</th><th class="num">Contributo</th><th class="num">Drawdown</th></tr>${m.asset.map(riga).join("")}</table></div>
    <p class="small">Contributo = peso &times; rendimento, in punti percentuali: la somma (meno i costi) d&agrave; il risultato del mese.</p></details>`;}
 // --- v6.100 SIMULATORE: cosa sarebbe successo al capitale partendo in OGNI mese dello storico (finestre mobili),
 //     sulla curva onesta del sito (euro, acquisto prudente, costi). Leva moderata con il costo del prestito.
 //     Dati da p.sim (cot_radar/portafogli.py, simulatore()). Testo breve in pagina, metodo nel fumetto (i).
 function simCorpo(p){const S=p.sim;if(!S)return "";const o=((S.leve||{})[simLeva]||{})[simOrz];
  if(!o)return `<div class="small">Storico troppo corto per questo orizzonte.</div>`;
  const anni=+simOrz,annuo=m=>pc((Math.pow(m,1/anni)-1)*100),v=m=>eur(simCap*m);
  const lo=o.p5,hi=o.p95,sp=(hi-lo)||1,x=m=>Math.max(0,Math.min(100,(m-lo)/sp*100)).toFixed(1);
  const pr=(S.prelievo||{})[simLeva];
  return `<div class="psim-g"><span class="small">In met&agrave; dei casi, dopo ${anni} ${anni==1?"anno":"anni"}</span>
    <b class="${o.p50>=1?"up":"down"}">${v(o.p50)}</b><span class="small">${annuo(o.p50)} l'anno</span></div>
   <div class="psim-bar"><i style="left:${x(o.p25)}%;width:${(x(o.p75)-x(o.p25)).toFixed(1)}%"></i><s style="left:${x(o.p50)}%"></s>
    ${lo<1&&hi>1?`<u style="left:${x(1)}%" title="capitale iniziale"></u>`:""}</div>
   <div class="psim-bl"><span>${v(lo)}</span><span>9 casi su 10 tra questi valori</span><span>${v(hi)}</span></div>
   <div class="pmc-k psim-k"><div><small>Partenze in perdita</small><b class="${o.perdita>0?"down":"up"}">${fx(o.perdita,0)}%</b></div>
    <div><small>Drawdown tipico</small><b class="down">${pc(o.dd)}</b></div><div><small>Drawdown peggiore</small><b class="down">${pc(o.dd_peggiore)}</b></div></div>
   ${pr?`<div class="psim-r"><span>Rendita annua sostenibile</span><b>${fx(pr.p50,1)}% l'anno &middot; ${eur(simCap*pr.p50/100)}</b><em>minimo ${fx(pr.p10,1)}% in 9 casi su 10</em></div>`:""}
`;}
 function simulatoreHTML(p){if(!p.sim)return "";
  const b=(arr,cur,attr,lab)=>`<div class="vfswitch psim-s">${arr.map(x=>`<button data-${attr}="${x}" class="${x==cur?"on":""}">${lab(x)}</button>`).join("")}</div>`;
  return `<div class="card psim" id="psim"><div class="psim-t"><h3>Simulatore <span class="pbprof">${esc(p.nome)}</span></h3>
    <details class="info"><summary title="Come funziona" aria-label="Come funziona">i</summary><div><b>Cosa mostra.</b> Il capitale investito in questo profilo partendo in ogni mese dello storico (dal ${gg(p.sim.dal)}): il valore a fine periodo nel caso medio (mediana) e la fascia che contiene 9 casi su 10. Stessa misura del sito: euro, acquisto prudente, costi inclusi.<br><br><b>Leva.</b> 1,3&times; e 1,5&times; = investire anche denaro preso a prestito, con un costo stimato di tasso BCE + ${fx(p.sim.spread,1)} punti l'anno. Guadagni e drawdown crescono insieme; costi e condizioni reali dipendono dal broker.<br><br><b>Rendita.</b> Prelievo annuo massimo che, in 10 anni, avrebbe lasciato il capitale finale almeno uguale a quello iniziale.<br><br><b>Attenzione.</b> Le regole del portafoglio sono state riviste guardando anche questi anni: i numeri futuri possono essere peggiori. Informazione, non consulenza.</div></details></div>
   <div class="psim-c"><label class="pcap">Capitale <input type="text" inputmode="numeric" value="${simCap.toLocaleString("it-IT")}" aria-label="Capitale del simulatore in euro"> &euro;</label>
    ${b(["1","3","5","10"],simOrz,"orz",x=>x+(x=="1"?" anno":" anni"))}${b(["1.0","1.3","1.5"],simLeva,"leva",x=>x=="1.0"?"Senza leva":"Leva "+x.replace(".",",")+"&times;")}</div>
   <div class="psim-b">${simCorpo(p)}</div></div>`;}
 function simEventi(p){const c=el.querySelector("#psim");if(!c)return;const corpo=()=>{c.querySelector(".psim-b").innerHTML=simCorpo(p);};
  const salva=(k,v)=>{try{localStorage.setItem(k,v);}catch(e){}};
  c.querySelectorAll("[data-orz]").forEach(x=>x.onclick=()=>{simOrz=x.dataset.orz;salva("ebSimOrz",simOrz);c.querySelectorAll("[data-orz]").forEach(y=>y.classList.toggle("on",y==x));corpo();});
  c.querySelectorAll("[data-leva]").forEach(x=>x.onclick=()=>{simLeva=x.dataset.leva;salva("ebSimLeva",simLeva);c.querySelectorAll("[data-leva]").forEach(y=>y.classList.toggle("on",y==x));corpo();});
  const ci=c.querySelector("input");ci.oninput=()=>{simCap=+ci.value.replace(/\D/g,"")||0;corpo();};
  ci.onblur=()=>{ci.value=simCap.toLocaleString("it-IT");salva("ebSimCap",simCap);};}


 // --- v7.4 CRISI STORICHE (cot_radar/portafogli.py: crisi_profilo + crisi_mercati): per ogni grande crisi dal 2006
 //     il drawdown del profilo contro l'S&P 500 (in euro), chi ha difeso il portafoglio e quali mercati sono saliti.
 //     Una riga per crisi (la piu' recente in alto); il tocco apre il dettaglio sotto la riga (una alla volta).
 let crSel=null;
 function crDett(p,c){const x=(p.crisi||[]).find(y=>y.id==c.id);if(!x)return "";
  const ct=Object.entries(x.contrib||{}).filter(e=>Math.abs(e[1])>=0.1).sort((a,b)=>b[1]-a[1]),mx=Math.max(1,...ct.map(e=>Math.abs(e[1])));
  const mesi=n=>n==null?"non ancora":n+(n==1?" mese":" mesi");
  const m=c.mappa||[],su=m.slice(0,3),giu=m.slice(-3).reverse();
  const chip=y=>`<span class="pcr-ch ${y.r>=0?"up":"down"}">${esc(y.n)} <b>${pc(y.r,0)}</b></span>`;
  return `<div class="pcr-d">
   <div class="pcr-sz"><span class="pcr-lab">Contributo al risultato</span>${ct.map(e=>`<div class="pcr-c"><span>${esc(e[0])}</span>
     <i><em class="${e[1]>=0?"su":"giu"}" style="width:${(Math.abs(e[1])/mx*100).toFixed(0)}%"></em></i><b class="${e[1]>=0?"up":"down"}">${e[1]>0?"+":""}${fx(e[1],1)}</b></div>`).join("")}</div>
   <div class="pcr-sz"><span class="pcr-lab">Ritorno al valore di prima</span><div class="pcr-rec"><b>${mesi(x.rec)}</b><span>S&amp;P 500: ${mesi(c.sp.rec)}</span></div></div>
   <div class="pcr-sz"><span class="pcr-lab">Mercati in quella crisi</span><div class="pcr-chs">${su.map(chip).join("")}</div><div class="pcr-chs">${giu.map(chip).join("")}</div></div></div>`;}
 function crisiHTML(p){const C=(P.crisi||[]).slice().reverse();if(!C.length||!p.crisi)return "";
  if(!crSel||!C.some(c=>c.id==crSel))crSel=C[0].id;
  const mx=Math.max(1,...C.map(c=>Math.abs(c.sp.dd)));
  return `<div class="card pcr" id="pcr"><div class="psim-t"><h3>Crisi storiche <span class="pbprof">${esc(p.nome)}</span></h3>
    <details class="info"><summary title="Come leggerlo" aria-label="Come leggerlo">i</summary><div><b>Cosa mostra.</b> Le grandi crisi da quando esiste il modello: dal massimo dell'S&amp;P 500 al suo minimo (date fisse, scelte prima di guardare i risultati). Numero grande = drawdown massimo del portafoglio in quei giorni, accanto quello dell'S&amp;P 500. Tutto in euro, come la curva della pagina.<br><br><b>Contributo al risultato.</b> Guadagno o perdita di ogni parte del portafoglio, in punti percentuali del capitale a inizio crisi: la somma &egrave; il risultato della crisi.<br><br><b>Ogni crisi ha un motore diverso</b>: nelle crisi di crescita difendono Treasury e oro, in quelle di inflazione materie prime e oro, nei crolli improvvisi la liquidit&agrave; del filtro di trend. Nessuno le prevede: la diversificazione serve ad avere gi&agrave; in portafoglio l'ingrediente giusto. Statistica del passato, non un consiglio.</div></details></div>
   <div class="pcr-l">${C.map(c=>{const x=(p.crisi||[]).find(y=>y.id==c.id)||{};
    return `<button type="button" class="pcr-r${c.id==crSel?" on":""}" data-cr="${c.id}" aria-expanded="${c.id==crSel}"><span class="pcr-n"><b>${esc(c.nome)}</b><small>${esc(c.id)} &middot; ${esc(c.motore)}</small></span>
     <span class="pcr-v"><small>Portafoglio</small><b class="${(x.dd||0)<0?"down":"up"}">${pc(x.dd)}</b><i><em style="width:${(Math.abs(x.dd||0)/mx*100).toFixed(1)}%"></em></i></span>
     <span class="pcr-v pcr-sp"><small>S&amp;P 500</small><b class="down">${pc(c.sp.dd)}</b><i><em style="width:${(Math.abs(c.sp.dd)/mx*100).toFixed(1)}%"></em></i></span></button>
     ${c.id==crSel?crDett(p,c):""}`;}).join("")}</div></div>`;}
 function crEventi(p){const c=el.querySelector("#pcr");if(!c)return;
  c.querySelectorAll("[data-cr]").forEach(b=>b.onclick=()=>{crSel=b.dataset.cr;const n=document.createElement("div");n.innerHTML=crisiHTML(p);
   c.querySelector(".pcr-l").replaceWith(n.querySelector(".pcr-l"));crEventi(p);});}

 function rotazioni(p){const ch=k=>`<span class="pchip" title="${esc(nomeK(k))}">${esc(nomeK(k))}</span>`;
  const perMese={};(p.mesi_chiusi||[]).forEach(m=>perMese[m.mese]=m);
  return `<div class="prot${tutteRot?" aperta":""}">${p.rotazioni.map((r,i)=>`<div class="protr${i>=3?" pextra":""}"><b>${gg(r.data)}</b><div>
   ${r.entrati.length?`<div class="pin">+ ${r.entrati.map(ch).join("")}</div>`:""}${r.usciti.length?`<div class="pout">&minus; ${r.usciti.map(ch).join("")}</div>`:""}
   ${r.tenuti.length?`<div class="pten">= ${r.tenuti.map(ch).join("")}</div>`:""}${!r.entrati.length&&!r.usciti.length&&!r.tenuti.length?'<div class="small">tutto in liquidit&agrave;</div>':""}</div>
   <span class="small">${r.liquidita?`liquidit&agrave; ${r.liquidita}%`:""}</span>${r.attesa?`<div class="prisul small"><span class="pmc-b">si esegue all'apertura del ${gg(r.data)}</span></div>`:dettMese(perMese[r.data.slice(0,7)])}</div>`).join("")}
   ${p.rotazioni.length>3?`<button class="ptutte">${tutteRot?"Mostra meno":`Mostra tutte (${p.rotazioni.length})`}</button>`:""}</div>`;}

 // --- CONFRONTO DEI 3 PROFILI mese per mese (v6.56): stessi mesi chiusi delle rotazioni, i tre profili affiancati,
 //     con rischio (volatilita' annua e drawdown sul periodo), mesi negativi, peggior mese, correlazione e la spiegazione
 //     automatica di ogni mese negativo (il mercato che ha pesato di piu'). Interruttore: profilo in evidenza.
 let cfrSel=null;
 function confronto(){const PR=P.profili,mesi=[...new Set(PR.flatMap(p=>(p.mesi_chiusi||[]).map(m=>m.mese)))].sort().reverse();
  if(!mesi.length)return "";
  const evid=cfrSel||sel,M=MESI.map(x=>x.slice(0,3));
  const serie=p=>mesi.map(k=>((p.mesi_chiusi||[]).find(m=>m.mese==k)||{}).r).reverse();   // dal piu' vecchio
  const st=p=>{const v=serie(p).filter(x=>x!=null);if(!v.length)return null;
   let cap=1,max=1,dd=0;v.forEach(r=>{cap*=1+r/100;max=Math.max(max,cap);dd=Math.min(dd,cap/max-1);});
   const med=v.reduce((a,b)=>a+b,0)/v.length,sd=Math.sqrt(v.reduce((a,b)=>a+(b-med)**2,0)/Math.max(1,v.length-1));
   return {tot:(cap-1)*100,neg:v.filter(r=>r<0).length,n:v.length,peg:Math.min(...v),vol:sd*Math.sqrt(12),dd:dd*100};};
  const corr=(a,b)=>{const x=serie(a),y=serie(b),c=x.map((v,i)=>[v,y[i]]).filter(q=>q[0]!=null&&q[1]!=null);if(c.length<4)return null;
   const ma=c.reduce((s,q)=>s+q[0],0)/c.length,mb=c.reduce((s,q)=>s+q[1],0)/c.length;let sab=0,sa=0,sb=0;
   c.forEach(q=>{sab+=(q[0]-ma)*(q[1]-mb);sa+=(q[0]-ma)**2;sb+=(q[1]-mb)**2;});return sa&&sb?sab/Math.sqrt(sa*sb):null;};
  const S=PR.map(st),pe=PR.find(p=>p.id==evid)||PR[0];
  const perche=k=>{const m=(pe.mesi_chiusi||[]).find(z=>z.mese==k);if(!m||m.r>=0)return "";
   const neg=[...m.asset].filter(a=>a.c<0).sort((a,b)=>a.c-b.c).slice(0,2);
   return neg.map(a=>`${esc(a.nome)} ${pc(a.r)}`).join(" &middot; ");};
  const cel=v=>(v=v==null?null:(Math.round(v*10)/10||0),v==null)?'<td class="num">&ndash;</td>':`<td class="num"><span class="pcf ${v>=0?"su":"giu"}" style="--a:${Math.min(1,Math.abs(v)/6)}">${pc(v)}</span></td>`;
  const ym=k=>M[+k.slice(5)-1]+" "+k.slice(0,4);
  return `<h3 class="vft">Confronto dei 3 profili <span class="small">(ultimi ${mesi.length} mesi chiusi, stesso periodo per tutti)</span></h3>
   <div class="card pcfr">
    <div class="vfswitch pcfsw" role="tablist" aria-label="Profilo in evidenza">${PR.map(x=>`<button data-c="${x.id}" class="${x.id==evid?"on":""}">${x.nome}</button>`).join("")}</div>
    <div class="tablewrap"><table class="compatta pcft"><tr><th>Mese</th>${PR.map(x=>`<th class="num${x.id==evid?" ev":""}"><span class="pcl">${x.nome}</span><span class="pcs">${x.nome.slice(0,4)}.</span></th>`).join("")}<th class="pcfw">Perch&eacute; negativo <span class="small">(${esc(pe.nome)})</span></th></tr>
     ${mesi.map(k=>`<tr><td>${ym(k)}</td>${PR.map(x=>cel(((x.mesi_chiusi||[]).find(m=>m.mese==k)||{}).r).replace('class="num"',`class="num${x.id==evid?" ev":""}"`)).join("")}<td class="pcfw small">${perche(k)}</td></tr>`).join("")}
     <tr class="pcftot"><td>Totale periodo</td>${S.map((v,i)=>`<td class="num${PR[i].id==evid?" ev":""} ${v&&v.tot>=0?"up":"down"}"><b>${v?pc(v.tot):"n/d"}</b></td>`).join("")}<td class="pcfw"></td></tr>
     <tr><td>Mesi negativi</td>${S.map((v,i)=>`<td class="num${PR[i].id==evid?" ev":""}">${v?v.neg+" su "+v.n:"n/d"}</td>`).join("")}<td class="pcfw"></td></tr>
     <tr><td>Peggior mese</td>${S.map((v,i)=>`<td class="num down${PR[i].id==evid?" ev":""}">${v?pc(v.peg):"n/d"}</td>`).join("")}<td class="pcfw"></td></tr>
     <tr><td>Volatilit&agrave; annua</td>${S.map((v,i)=>`<td class="num${PR[i].id==evid?" ev":""}">${v?fx(v.vol,1)+"%":"n/d"}</td>`).join("")}<td class="pcfw small">quanto oscilla in un anno (da mesi)</td></tr>
     <tr><td>Drawdown del periodo</td>${S.map((v,i)=>`<td class="num down${PR[i].id==evid?" ev":""}">${v?pc(v.dd):"n/d"}</td>`).join("")}<td class="pcfw small">dal picco al minimo, a fine mese</td></tr>
     <tr><td>Correlazione con ${esc(pe.nome)}</td>${PR.map(x=>{const c=x.id==pe.id?1:corr(x,pe);return `<td class="num${x.id==evid?" ev":""}">${c==null?"n/d":fx(c,2)}</td>`;}).join("")}<td class="pcfw small">1 = si muovono uguale</td></tr>
     <tr class="pcfsto"><td>Storico dal ${esc((PR[0].stat.totale.dal||"").slice(0,4))}: mesi positivi</td>${PR.map(x=>`<td class="num${x.id==evid?" ev":""}">${x.stat.totale.mesi_pos??"n/d"}%</td>`).join("")}<td class="pcfw small">la regola, su tutta la storia</td></tr>
     <tr><td>Storico: max drawdown</td>${PR.map(x=>`<td class="num down${x.id==evid?" ev":""}">${pc(x.stat.totale.maxdd)}</td>`).join("")}<td class="pcfw"></td></tr>
     <tr><td>Storico: rendimento annuo</td>${PR.map(x=>`<td class="num up${x.id==evid?" ev":""}">${pc(x.stat.totale.cagr)}</td>`).join("")}<td class="pcfw"></td></tr>
     <tr><td>Storico: oltre la liquidit&agrave;</td>${PR.map(x=>`<td class="num${x.id==evid?" ev":""}">${x.stat.totale.oltre_liq!=null?pc(x.stat.totale.oltre_liq):"n/d"}</td>`).join("")}<td class="pcfw small">rendimento annuo meno la liquidit&agrave; in euro</td></tr>
     <tr><td>Storico: mesi per recuperare</td>${PR.map(x=>`<td class="num${x.id==evid?" ev":""}">${x.stat.totale.recupero_mesi??"in corso"}</td>`).join("")}<td class="pcfw small">dal drawdown peggiore</td></tr>
     ${PR.some(x=>x.stat_sel)?`<tr class="pcfsto"><td>Con la selezione dei 5 titoli</td>${PR.map(x=>`<td class="num${x.id==evid?" ev":""}">${x.stat_sel?pc(x.stat_sel.totale.cagr):"n/d"}</td>`).join("")}<td class="pcfw small">rendimento annuo, ottimista (titoli di oggi)</td></tr>
     <tr><td>In dollari</td>${PR.map(x=>`<td class="num${x.id==evid?" ev":""}">${x.stat_usd?pc(x.stat_usd.totale.cagr):"n/d"}</td>`).join("")}<td class="pcfw small">rendimento annuo per chi investe in USD</td></tr>`:""}</table></div>
    <p class="small pcfnota">Un mese negativo su tre &egrave; normale per un portafoglio diversificato: nello storico i mesi positivi sono circa due su tre. Il risultato si misura sull'anno, non sul singolo mese. ${pe.live_dal?`Prima del ${gg(pe.live_dal)} i mesi sono calcolati applicando le regole attuali al passato (simulazione), non operazioni reali.`:""} Non &egrave; un consiglio di investimento.</p></div>`;}

 // --- AVVISO DATI NON AGGIORNATI (P.avviso dal backend): solo il popup comune di manutenzione (manutenzione.js),
 //     nessuna barra fissa. Data e ora dell'anomalia arrivano dal backend (P.avviso.quando).
 if(P.avviso)ebManutenzione({scheda:"port",codice:P.avviso.codice,quando:P.avviso.quando,dal:P.avviso.dal});

 // --- CARD PRINCIPALE del profilo scelto: rischio, descrizione, numeri chiave, composizione per classe, 5 azioni
 // v7.2 un solo fumetto (i) accanto al nome: descrizione, come si misura, numeri secondari (niente righe tecniche fisse)
 function infoProfilo(p,t){const usd=p.stat_usd&&p.stat_usd.totale;
  return `<details class="info phi"><summary title="Il profilo" aria-label="Il profilo">i</summary><div>${esc(p.descr)}<br><br><b>Come si misura.</b> Numeri in euro senza copertura del cambio, liquidit&agrave; al tasso BCE, acquisto alla chiusura del giorno di rotazione, costi 0,10% inclusi.${t.oltre_liq!=null?` Oltre la liquidit&agrave;: <b>${pc(t.oltre_liq)}</b> l'anno.`:""}${t.recupero_mesi!=null?` Recupero dal drawdown peggiore: <b>${t.recupero_mesi} mesi</b>.`:""}${usd?` In dollari: ${pc(usd.cagr)} l'anno.`:""}</div></details>`;}
 function hero(p){const t=p.stat.totale||{},rk=RISK[p.id]||["",""];
  const cl={};p.composizione.forEach(c=>{cl[c.classe]=(cl[c.classe]||0)+c.peso;});
  const te=p.stat_eur&&p.stat_eur.totale,finale=te&&te.totale!=null?10000*(1+te.totale/100):t.totale!=null?10000*(1+t.totale/100):null   /* v6.57: 10.000 EURO -> si usa la curva in euro */,anno=(t.dal||"").slice(0,4);
  const az=p.composizione.find(c=>c.k=="AZ"),pausa=p.esclusi.find(x=>x.k=="AZ");
  return `<div class="card phero"><div class="phtesta"><h3>${esc(p.nome)}${infoProfilo(p,t)}</h3><div class="phazioni"><span class="prisk ${rk[1]}">Rischio ${rk[0].toLowerCase()}</span>${window.ebPdf?ebPdf.bottone():""}</div></div>
   <div class="phnum"><div><em>Rendimento annuo</em><b class="up">${pc(t.cagr)}</b><span>media dal ${anno}</span></div>
    <div><em>Max drawdown</em><b class="down">${pc(t.maxdd)}</b><span>dal picco al minimo</span></div>
    <div><em>10.000 € nel ${anno}</em><b>${eur(finale)}</b><span>valore di oggi${p.stat_eur&&p.stat_eur.totale?" (in euro)":""}</span></div>
    <div><em>Mesi positivi</em><b>${t.mesi_pos??"n/d"}%</b><span>su tutti i mesi</span></div></div>
   <div class="phcomp"><h4>Composizione del mese <details class="info"><summary title="Come funziona" aria-label="Come funziona">i</summary><div><b>Ogni primo giorno di borsa del mese</b> si controlla il trend: un mercato azionario sotto la media a 200 giorni va in pausa nella liquidit&agrave;. Treasury e oro restano sempre come difesa. Si scambia solo se un mercato entra o esce, e a inizio trimestre per riportare i pesi. Durante il mese non si tocca nulla. Dettagli nella <b>Guida</b>.</div></details></h4>${CLN.filter(x=>cl[x[0]]).map(x=>`<div class="phbar"><span>${x[1]}</span><b>${fx(cl[x[0]],1)}%</b><i><s style="width:${Math.min(100,cl[x[0]])}%;--cb:${CL[x[0]]}"></s></i></div>`).join("")}</div>
   <div class="phaz"${p.az?"":" hidden"}><h4>Le 5 azioni del mese <span class="small">(${p.az}% del portafoglio${az&&az.titoli&&az.titoli.length?`, ${fx(az.peso_titolo,1)}% ciascuna`:""})</span></h4>
    ${pausa?`<div class="small">${esc(pausa.motivo)}.</div>`:az&&az.titoli&&az.titoli.length?`<div class="ptit">${az.titoli.map(x=>`<button class="pchip clic" data-az="${esc(x.t)}" title="Apri nell'Azionario">${esc(x.t)} <small>${esc(x.n)}</small></button>`).join("")}</div>`
     :`<div class="small">I titoli vengono scelti l'ultimo giorno di borsa del mese, dopo la chiusura, e entrano con la rotazione del ${gg(P.prossima)}.</div>`}</div>
</div>`;}

 // --- v6.78 PDF DEL PORTAFOGLIO (generatore in 01b_pdf.js): gli stessi dati della pagina su un foglio chiaro, pensato
 //     per la stampa. Pagina 1: rischio, numeri chiave, composizione (ciambella + classi) e righe del portafoglio con
 //     strumento, ISIN, peso e importo sul capitale scritto dall'utente (5 azioni comprese, con ISIN). Poi: curva del
 //     capitale (periodo scelto nella pagina), risultati per periodo, rischio del mese, ultime rotazioni.
 const COLP={azioni:"#3b7de0","azioni singole":"#1a9e93",obbligazioni:"#12a874",metalli:"#c98a14","materie prime":"#e0820f",crypto:"#9b59d0",liquidita:"#8793a6"};
 const txt=s=>String(s==null?"":s).replace(/&middot;/g,"·").replace(/&amp;/g,"&").replace(/&[a-z]+;/g,"").replace(/<[^>]+>/g,"");
 const motivo=c=>c.k=="CASH"?"Liquidità fissa del profilo + pesi dei mercati in pausa."
  :c.k=="AZ"?`Filtro di mercato: S&P 500 ${pc(c.trend)} sopra la media a 200 giorni.`
  :`Trend ${pc(c.trend)} sopra la media a 200 giorni · volatilità ${fx(c.vol,0)}% · COT ${c.score!=null?sg(c.score,0):"n/d"} (informativo)`;
 async function pdfPort(){const E=window.ebPdf;if(!E)return;const p=P.profili.find(x=>x.id==sel),C=E.C;
  const az=p.composizione.find(c=>c.k=="AZ"),reg=!!(az&&az.titoli&&az.titoli.length),lista=az?((reg?az.titoli:(az.anteprima||{}).titoli)||[]):[];
  // ISIN delle 5 azioni: stessi file della pagina; massimo 5 secondi di attesa, poi il PDF esce comunque
  const isin={};await Promise.race([Promise.all(lista.map(x=>isinDi(x.t).then(v=>{isin[x.t]=v;}))),new Promise(r=>setTimeout(r,5000))]);
  const d=E.Doc();d.pagina();const {M,PW}=d,LW=PW-2*M,T="Portafoglio "+p.nome,mese=MESI[+P.rotazione.slice(5,7)-1];
  const t=p.stat.totale||{},rk=RISK[p.id]||["",""],anno=(t.dal||"").slice(0,4),nM=p.composizione.filter(c=>c.k!="CASH").length;
  let y=E.testata(d,T,`Rotazione del ${gg(P.rotazione)} · prossimo ribilanciamento ${gg(P.prossima)} · importi calcolati su ${eur(capitale)}`);
  // rischio del profilo (etichetta colorata) e descrizione
  const rc={r1:C.up,r2:C.warn,r3:C.down}[rk[1]]||C.mute,rt="Rischio "+rk[0].toLowerCase(),rw=d.larghezza(rt,9,true)+22;
  d.rett(M,y-12,rw,18,{f:E.chiaro(rc,.12),s:rc,r:9});d.testo(M+rw/2,y+1,rt,{s:9,b:true,c:rc,a:"c"});
  y+=22;y+=d.paragrafo(M,y,txt(p.descr),LW,{s:9.5})+6;
  // quattro numeri chiave (come la card principale della pagina)
  const te=p.stat_eur&&p.stat_eur.totale,fin=te&&te.totale!=null?10000*(1+te.totale/100):t.totale!=null?10000*(1+t.totale/100):null;
  const K=[["Rendimento annuo",pc(t.cagr),"media dal "+anno,C.up],["Max drawdown",pc(t.maxdd),"dal picco al minimo",C.down],
   ["10.000 € nel "+anno,eur(fin),"valore di oggi"+(te?" (in euro)":""),C.ink],["Mesi positivi",(t.mesi_pos??"n/d")+"%","su tutti i mesi",C.ink]];
  const bw=(LW-24)/4;K.forEach((k,i)=>{const x=M+i*(bw+8);d.rett(x,y,bw,56,{f:C.soft,r:7});
   d.testo(x+11,y+16,k[0],{s:7.8,c:C.mute});d.testo(x+11,y+36,k[1],{s:15,b:true,c:k[3]});d.testo(x+11,y+48,k[2],{s:7.2,c:C.mute});});
  y+=56;
  // v6.87: stessa misura prudente della pagina (euro, acquisto alla chiusura del giorno di rotazione, 5 azioni = S&P 500)
  {const sel=p.stat_sel&&p.stat_sel.totale,usd=p.stat_usd&&p.stat_usd.totale;y+=16;
   d.testo(M,y,`${p.valuta=="EUR"?"In euro":"In dollari"} · oltre la liquidità ${t.oltre_liq!=null?pc(t.oltre_liq):"n/d"} l'anno · Calmar ${t.calmar!=null?fx(t.calmar,2):"n/d"} · recupero ${t.recupero_mesi!=null?t.recupero_mesi+" mesi":"in corso"}`,{s:8.5,c:C.mute});
   y+=12;y+=d.paragrafo(M,y,`Numeri prudenti: acquisto alla chiusura del giorno di rotazione, costi inclusi, 5 azioni contate come l'S&P 500 (lo storico usa i titoli di oggi).${sel?` Con la selezione vera: ${pc(sel.cagr)} l'anno.`:""}${usd?` In dollari: ${pc(usd.cagr)} l'anno.`:""}`,LW,{s:7.8,c:C.mute});}
  // composizione: ciambella dei pesi (colore = classe) e barre per classe
  y=E.sezione(d,y+30,"Composizione del mese",`${nM} ${nM==1?"mercato":"mercati"}`);
  const cx=M+62,cy=y+60;let a=0;
  p.composizione.forEach(c=>{const g=c.peso*3.6;if(g>0.5)d.anello(cx,cy,34,56,a,a+g-1,COLP[c.classe]||C.mute);a+=g;});
  d.testo(cx,cy+4,String(nM),{s:19,b:true,a:"c"});d.testo(cx,cy+16,nM==1?"mercato":"mercati",{s:7.5,c:C.mute,a:"c"});
  const cl={};p.composizione.forEach(c=>{cl[c.classe]=(cl[c.classe]||0)+c.peso;});
  const x0=M+150,bw2=LW-150;let yy=y+14;
  CLN.filter(x=>cl[x[0]]).forEach(x=>{d.testo(x0,yy,x[1],{s:9});d.testo(x0+bw2,yy,fx(cl[x[0]],1)+"%",{s:9,b:true,a:"r"});
   d.rett(x0,yy+5,bw2,4,{f:C.soft,r:2});d.rett(x0,yy+5,Math.max(2,bw2*Math.min(100,cl[x[0]])/100),4,{f:COLP[x[0]]||C.mute,r:2});yy+=21;});
  y=Math.max(cy+64,yy+4);
  // righe del portafoglio per classe: strumento UCITS da comprare con ISIN, peso e importo
  const xP=PW-M-92,xI=PW-M-8,wN=xP-60-(M+20);
  const testaTab=()=>{d.rett(M,y,LW,19,{f:C.navy,r:4});d.testo(M+10,y+12.5,"Mercato e strumento da comprare",{s:8,b:true,c:C.bianco});
   d.testo(xP,y+12.5,"Peso",{s:8,b:true,c:C.bianco,a:"r"});d.testo(xI,y+12.5,"Importo",{s:8,b:true,c:C.bianco,a:"r"});y+=23;};
  const spazio=h=>{const y0=y;y=d.serve(y,h,T);if(y<y0)testaTab();};
  y=d.serve(y,90,T);y=E.sezione(d,y+22,`Portafoglio di ${mese}`,`importi su ${eur(capitale)}`);testaTab();
  MACRO.map(g=>({n:g[0],r:p.composizione.filter(c=>g[1].includes(c.classe))})).filter(g=>g.r.length).forEach(g=>{
   spazio(60);d.rett(M,y,LW,18,{f:C.soft,r:3});d.testo(M+10,y+12.5,g.n,{s:8.5,b:true});
   d.testo(xP,y+12.5,fx(g.r.reduce((s,c)=>s+c.peso,0),1)+"%",{s:8.5,b:true,a:"r"});y+=22;
   g.r.forEach(c=>{const nota=c.ue&&c.ue.nota,h=40+(nota?10:0);spazio(h);
    d.cerchio(M+10,y+8.5,3.2,COLP[c.classe]||C.mute);d.testo(M+20,y+12,d.taglia(c.nome,wN,9.5,true),{s:9.5,b:true});
    d.testo(xP,y+12,fx(c.peso,1)+"%",{s:9.5,b:true,a:"r"});d.testo(xI,y+12,eur(capitale*c.peso/100),{s:9.5,a:"r"});
    const str=c.ue?`${c.ue.nome}  ·  ISIN ${c.ue.isin}`:txt(c.strumento);
    d.testo(M+20,y+24,d.taglia(str,xP-M-30,8,!!c.ue),{s:8,b:!!c.ue,c:c.ue?C.acc:C.ink});let yr=y+24;
    if(nota){yr+=10;d.testo(M+20,yr,d.taglia(txt(nota),xP-M-30,7.2),{s:7.2,c:C.mute});}
    d.testo(M+20,yr+11,d.taglia(motivo(c),xP-M-30,7.2),{s:7.2,c:C.mute});y=yr+18;
    // le 5 azioni scelte, una per riga, con ISIN, borsa, quota e importo
    if(c.k=="AZ"){const q=lista.length?c.peso/lista.length:0;
     if(!lista.length){spazio(16);y+=d.paragrafo(M+20,y+2,`I 5 titoli si scelgono l'ultimo giorno di borsa del mese, dopo la chiusura, ed entrano con la rotazione del ${gg(P.prossima)}.`,xP-M-30,{s:7.8,c:C.mute})+4;}
     else{if(!reg){spazio(28);y+=d.paragrafo(M+20,y+2,`Anteprima per ${MESI[+az.anteprima.mese.slice(5,7)-1]}, calcolata il ${gg(az.anteprima.al)} con i prezzi di quel giorno: la lista definitiva si fissa l'ultimo giorno di borsa ed entra il ${gg(P.prossima)}.`,xP-M-30,{s:7.8,c:C.warn})+4;}
      lista.forEach(x=>{spazio(26);const b=borsa(x.t),st=(SETT[x.s]||[x.s||""])[0];
       d.rett(M+20,y,LW-28,22,{f:"#fafbfd",s:C.line,lw:.4,r:4});
       d.testo(M+28,y+9.5,x.t,{s:8.2,b:true});d.testo(M+28+d.larghezza(x.t,8.2,true)+6,y+9.5,d.taglia(x.n+(x.sost?" (al posto di "+(x.sost_n||x.sost)+")":""),xP-M-110,8.2),{s:8.2});
       d.testo(M+28,y+18.5,[st,b[0]+(b[1]?"":" (di solito non acquistabile in Europa)"),isin[x.t]?"ISIN "+isin[x.t]:""].filter(Boolean).join("  ·  "),{s:7,c:isin[x.t]?C.acc:C.mute});
       d.testo(xP,y+14,fx(q,1)+"%",{s:8.5,b:true,a:"r"});d.testo(xI,y+14,eur(capitale*q/100),{s:8.5,a:"r"});y+=26;});}}
    d.linea(M+20,y-3,PW-M,y-3,{c:C.line,lw:.4});});});
  // esposizione al dollaro e nota sugli strumenti
  const USD=["SP500","NASDAQ","DOW","RUSSELL","US10Y","USBOND","GOLD","SILVER","PLATINUM","BTC","ETH"];
  let usd=p.composizione.filter(c=>USD.includes(c.k)).reduce((s,c)=>s+c.peso,0);if(az&&lista.length)usd+=az.peso*lista.filter(x=>borsa(x.t)[0]=="USA").length/lista.length;
  y=d.serve(y,40,T);y+=8;
  y+=d.paragrafo(M,y,`Valute: nessuna posizione diretta. Esposizione al dollaro stimata ${fx(usd,0)}% (gli strumenti UCITS in euro seguono comunque il cambio EUR/USD).`,LW,{s:8,c:C.mute});
  y+=d.paragrafo(M,y,"Strumenti UCITS / ETC / ETP acquistabili da un conto europeo: cerca l'ISIN nell'app del tuo broker.",LW,{s:8,c:C.mute});

  // curva del capitale (stesso periodo scelto nella pagina), scala logaritmica, base 100
  let pts=p.curva,bench=(P.bench||{}).curva||[];const dal=per=="oos"?P.oos_dal:per=="live"?(p.live_dal||P.oos_dal):null;
  if(dal){pts=pts.filter(x=>x[0]>=dal);bench=bench.filter(x=>x[0]>=dal);}
  if(pts.length>1){y=d.serve(y,280,T);y=E.sezione(d,y+26,"Andamento del capitale",per=="oos"?"dal 2016 · base 100, scala logaritmica":"base 100, scala logaritmica");
   const gx=M+34,gw=LW-42,gy=y+4,gh=190,passo=a=>a.filter((_,i)=>i%Math.max(1,Math.ceil(a.length/700))==0||i==a.length-1);
   const b0=pts[0][1],bb0=(bench[0]||[0,1])[1],s=passo(pts).map(x=>[x[0],x[1]/b0*100]),sb=passo(bench).map(x=>[x[0],x[1]/bb0*100]);
   const t0=+new Date(s[0][0]),t1=+new Date(s[s.length-1][0]),tutti=s.concat(sb).map(x=>x[1]);
   const lo=Math.log(Math.min(...tutti)*.97),hi=Math.log(Math.max(...tutti)*1.03);
   const X=q=>gx+(+new Date(q)-t0)/(t1-t0||1)*gw,Y=v=>gy+(hi-Math.log(v))/(hi-lo||1)*gh;
   // fasce fuori campione e live, griglia con valori "tondi", anni sull'asse
   const fascia=(q,col,et)=>{if(q&&q>s[0][0]){d.rett(X(q),gy,gx+gw-X(q),gh,{f:col});d.testo(X(q)+6,gy+11,et,{s:6.8,b:true,c:C.mute});}};
   fascia(P.oos_dal,"#f1f6fb","VERIFICA");if(p.live_dal)fascia(p.live_dal,"#e4f5f2","LIVE");
   [25,50,75,100,150,200,300,400,600,800,1000,1500,2000,3000,5000].filter(v=>Math.log(v)>lo&&Math.log(v)<hi).forEach(v=>{d.linea(gx,Y(v),gx+gw,Y(v),{c:"#e6ebf2",lw:.5});d.testo(gx-6,Y(v)+2.5,String(v),{s:6.8,c:C.mute,a:"r"});});
   const a0=+s[0][0].slice(0,4)+1,a1=+s[s.length-1][0].slice(0,4),pa=Math.ceil((a1-a0+1)/10)||1;
   for(let an=a0;an<=a1;an++)if((an-a0)%pa==0)d.testo(X(an+"-01-01"),gy+gh+11,String(an),{s:6.8,c:C.mute,a:"c"});
   d.linea(gx,gy+gh,gx+gw,gy+gh,{c:"#c3ccd8",lw:.6});
   if(sb.length>1)d.poli(sb.map(x=>[X(x[0]),Y(x[1])]),{s:"#8793a6",lw:1,tratt:[3,2]});
   d.poli(s.map(x=>[X(x[0]),Y(x[1])]),{s:C.acc,lw:1.4});
   const live=p.live_dal?s.filter(x=>x[0]>=p.live_dal):[];if(live.length>1)d.poli(live.map(x=>[X(x[0]),Y(x[1])]),{s:"#0b6b63",lw:2.2});
   y=gy+gh+26;let lx=M;const leg=(col,et,tr)=>{d.linea(lx,y-3,lx+18,y-3,{c:col,lw:tr?1:2,tratt:tr?[3,2]:null});lx+=24;lx+=d.testo(lx,y,et,{s:8,c:C.mute})+18;};
   leg(C.acc,"Portafoglio "+p.nome.toLowerCase());leg("#8793a6",(P.bench||{}).nome||"60/40",true);if(p.live_dal)leg("#0b6b63","Live");y+=6;}

  // risultati per periodo (come la tabella della pagina)
  const st=p.stat,bs=(P.bench||{}).stat||{};
  const col=[["Storico",st.storico,"fino al 2015"],["Verifica",st.oos,"dal 2016"]].concat(st.live?[["Live",st.live,p.live_dal?"dal "+gg(p.live_dal):"dall'avvio"]]:[]).concat([["60/40",bs.oos,"dal 2016"]]);
  const RIG=[["Rendimento annuo",x=>x.cagr==null?pc(x.totale)+" tot.":pc(x.cagr)],["Volatilità",x=>fx(x.vol,1)+"%"],["Max drawdown",x=>pc(x.maxdd),C.down],["Peggior mese",x=>x.peggior_mese?pc(x.peggior_mese[1]):"n/d"],["Win rate mensile",x=>(x.mesi_pos??"n/d")+"%"]];
  y=d.serve(y,150,T);y=E.sezione(d,y+26,"Risultati per periodo");
  const c0=150,cw=(LW-c0)/col.length;d.rett(M,y,LW,28,{f:C.navy,r:4});
  col.forEach((c,i)=>{const x=M+c0+cw*i+cw-10;d.testo(x,y+12,c[0],{s:8.2,b:true,c:C.bianco,a:"r"});d.testo(x,y+22,c[2],{s:6.8,c:"#a9b8d0",a:"r"});});
  y+=28;RIG.forEach((r,j)=>{if(j%2)d.rett(M,y,LW,19,{f:C.soft});d.testo(M+10,y+13,r[0],{s:8.5});
   col.forEach((c,i)=>d.testo(M+c0+cw*i+cw-10,y+13,c[1]?r[1](c[1]):"n/d",{s:8.5,b:j==2,c:r[2]||C.ink,a:"r"}));y+=19;});

  // rischio del mese della rotazione: termometro del drawdown, anno per anno, numeri chiave, stagionalita'
  const m=p.mese;if(m&&m.anni&&m.anni.length){
   const peg=m.anni.reduce((q,x)=>x.dd<q.dd?x:q,m.anni[0]),lim=-p.dd_rif,oltre=m.dd_max<lim,s0=p.stat.totale||{},o0=p.stat.oos||{},ddTot=Math.min(s0.maxdd??0,o0.maxdd??0);
   y=d.serve(y,330,T);y=E.sezione(d,y+28,"Rischio di "+m.mese,`questa composizione tenuta in ogni ${m.mese} dal ${m.anni[0].a} (${m.n} anni)`);
   d.testo(M,y+4,"Drawdown peggiore di "+m.mese,{s:8.5,b:true});
   d.testo(PW-M,y+4,oltre?`Oltre il limite di ${fx(Math.abs(m.dd_max-lim),1)} punti`:"Dentro il limite del profilo",{s:8.5,b:true,c:oltre?C.down:C.up,a:"r"});
   const fondo=Math.min(m.dd_max,lim)*1.18,pos=v=>M+LW*v/fondo;y+=24;
   d.rett(M,y,LW,10,{f:C.soft,r:5});d.rett(M,y,pos(m.dd_max)-M,10,{f:C.down,r:5});
   d.linea(pos(lim),y-4,pos(lim),y+14,{c:C.ink,lw:1.4});d.testo(pos(lim),y-7,"limite "+pc(lim,0),{s:7,c:C.ink,a:"c"});
   d.testo(M,y+22,"0%",{s:7,c:C.mute});d.testo(pos(m.dd_max),y+22,pc(m.dd_max),{s:7,b:true,c:C.down,a:"c"});y+=34;
   y+=d.paragrafo(M,y,`Peggior caso: ${m.mese} ${peg.a}. Con 10.000 € il conto sarebbe sceso fino a ${eur(10000*(1+m.dd_max/100))} durante il mese.`,LW,{s:8.5,c:C.mute})+6;
   // anno per anno: una riga per decennio, verde = guadagno, rosso = perdita (piu' intenso = piu' grande)
   const per={};m.anni.forEach(x=>per[x.a]=x);const d0=Math.floor(m.anni[0].a/10)*10,d1=Math.floor(m.anni[m.anni.length-1].a/10)*10,cw2=(LW-58)/10;
   for(let dc=d0;dc<=d1;dc+=10){y=d.serve(y,30,T);d.testo(M,y+16,dc==1990?"anni '90":"anni "+dc,{s:7.5,c:C.mute});
    for(let a2=dc;a2<dc+10;a2++){const x=per[a2],xc=M+58+(a2-dc)*cw2;if(!x)continue;const tt=Math.min(1,Math.abs(x.r)/5);
     d.rett(xc+1.5,y,cw2-3,26,{f:E.chiaro(x.r<0?"#e0524c":"#2bb383",.14+.7*tt),r:4,s:x.a==peg.a?C.ink:null,lw:1});
     d.testo(xc+cw2/2,y+10,String(a2),{s:6.5,c:C.mute,a:"c"});d.testo(xc+cw2/2,y+21,pc(x.r),{s:7.8,b:true,a:"c"});}
    y+=30;}
   const wr=Math.round(100*m.positivi/m.n),Mz=m.mese[0].toUpperCase()+m.mese.slice(1);
   const K2=[["Peggior "+m.mese,pc(m.peggiore[1]),String(m.peggiore[0]),C.down],[Mz+" medio",pc(m.media),"su "+m.n+" anni",m.media>=0?C.up:C.down],["Anni positivi",`${m.positivi} su ${m.n}`,"win rate "+wr+"%",C.ink],["Max drawdown storico",pc(ddTot),"intero backtest",C.down]];
   y=d.serve(y,62,T);y+=6;K2.forEach((k,i)=>{const x=M+i*(bw+8);d.rett(x,y,bw,50,{f:C.soft,r:7});
    d.testo(x+11,y+15,k[0],{s:7.6,c:C.mute});d.testo(x+11,y+32,k[1],{s:13,b:true,c:k[3]});d.testo(x+11,y+43,k[2],{s:7,c:C.mute});});y+=50;
   if(m.mercati&&m.mercati.length){y=d.serve(y,40,T);d.testo(M,y+22,`Stagionalità di ${m.mese} per mercato (informativa)`,{s:8.5,b:true});y+=30;
    m.mercati.forEach(x=>{y=d.serve(y,16,T);d.testo(M,y+9,d.taglia(nomeK(x.k),170,8),{s:8});const bx=M+180,bl=LW-300,w=Math.min(1,Math.abs(x.media)/12.5)*bl/2;
     d.rett(bx,y+3,bl,6,{f:C.soft,r:3});d.linea(bx+bl/2,y+1,bx+bl/2,y+11,{c:"#c3ccd8",lw:.5});
     d.rett(x.media>=0?bx+bl/2:bx+bl/2-w,y+3,Math.max(1,w),6,{f:x.media>=0?C.up:C.down,r:3});
     d.testo(PW-M-60,y+9,pc(x.media),{s:8,b:true,c:x.media>=0?C.up:C.down,a:"r"});d.testo(PW-M,y+9,x.pos+"% positivi",{s:7.5,c:C.mute,a:"r"});y+=16;});}}

  // ultime rotazioni: entrati / usciti / rimasti e risultato del mese chiuso
  if(p.rotazioni&&p.rotazioni.length){const perMese={};(p.mesi_chiusi||[]).forEach(q=>perMese[q.mese]=q);
   y=d.serve(y,80,T);y=E.sezione(d,y+28,"Ultime rotazioni","+ entrati · − usciti · = rimasti");
   p.rotazioni.slice(0,6).forEach(r=>{const L=[];
    if(r.entrati.length)L.push(["+ "+r.entrati.map(nomeK).join(", "),C.up]);if(r.usciti.length)L.push(["− "+r.usciti.map(nomeK).join(", "),C.down]);
    if(r.tenuti.length)L.push(["= "+r.tenuti.map(nomeK).join(", "),C.ink]);if(!L.length)L.push(["tutto in liquidità",C.mute]);
    const mm=perMese[r.data.slice(0,7)],ris=r.attesa?`si esegue all'apertura del ${gg(r.data)}`:mm?`Risultato ${pc(mm.r)} · drawdown ${pc(mm.dd)}`:"mese in corso";
    const righe=L.flatMap(l=>d.righe(l[0],LW-70-185,8).map(t2=>[t2,l[1]])),h=Math.max(16,righe.length*11)+10;
    y=d.serve(y,h,T);d.testo(M,y+10,gg(r.data),{s:8.5,b:true});righe.forEach((q,i)=>d.testo(M+70,y+10+i*11,q[0],{s:8,c:q[1]}));
    d.testo(PW-M,y+10,ris,{s:7.6,c:mm?(mm.r>=0?C.up:C.down):C.mute,a:"r",b:!!mm});if(r.liquidita)d.testo(PW-M,y+21,`liquidità ${r.liquidita}%`,{s:7,c:C.mute,a:"r"});
    y+=h;d.linea(M,y-4,PW-M,y-4,{c:C.line,lw:.4});});}
  d.salva(E.nomeFile("Portafoglio "+p.nome),T+" - BoardEdge",(n,tot)=>E.piede(d,n,tot,"Portafogli modello BoardEdge"));}

 // ridisegna mantenendo la posizione della pagina (v6.52: prima ogni tocco riportava in cima)
 // v6.58: la pagina NON deve muoversi al clic. Due cause del "salto": (1) mentre si riscrive la scheda l'altezza
 //   cala per un istante e il browser accorcia lo scorrimento; (2) html{scroll-behavior:smooth} faceva ANIMARE il
 //   ritorno (sfarfallio). Soluzione: si blocca l'altezza durante il ridisegno e si riporta il pulsante cliccato
 //   esattamente dov'era (ancora), con scorrimento istantaneo.
 function ridisegna(ancora){const a=ancora&&el.querySelector(ancora),y0=a?a.getBoundingClientRect().top:null,sy=window.scrollY;
  el.style.minHeight=el.offsetHeight+"px";disegna();
  // i sottotitoli diventano subito "(i)" chiusi (01_base.js): senza questa riga lo farebbe un attimo DOPO,
  // accorciando la pagina di ~200 px dopo il riposizionamento = il salto che si vedeva
  try{if(typeof etichetteInfo=="function")etichetteInfo(el);}catch(e){}
  const b=ancora&&el.querySelector(ancora);
  if(b&&y0!=null)window.scrollTo({top:window.scrollY+b.getBoundingClientRect().top-y0,behavior:"instant"});
  else window.scrollTo({top:sy,behavior:"instant"});
  requestAnimationFrame(()=>{el.style.minHeight="";});}
 function disegna(){const p=P.profili.find(x=>x.id==sel);
  el.innerHTML=`<h2>Portafogli modello</h2><p class="sub">Tre profili di rischio, solo acquisti, controllo ogni mese. Numeri in euro, costi inclusi. Come funziona: Guida, sezione 9.</p>
   <div class="pdate">${P.attesa?`<div class="pdinfo pnew"><i></i><div><span class="pdl">Nuova rotazione</span><b>${gg(P.rotazione)}</b><span class="pdsub">decisa sulla chiusura del ${gg(P.decisa_al)}</span></div></div>`:`<div class="pdinfo"><i></i><div><span class="pdl">Rotazione in vigore</span><b>${gg(P.rotazione)}</b></div></div>`}<span class="pcount" data-t="${P.prossima||""}" title="${P.attesa?"Si esegue":"Prossimo ribilanciamento"}: ${gg(P.prossima)} all'apertura delle borse europee (09:00 ora italiana)">${P.attesa?"Si esegue all'apertura tra":"Prossimo ribilanciamento"} <b class="pcd">${gg(P.prossima)}</b></span></div>
   <div class="pseg" role="tablist" aria-label="Scegli il portafoglio">${P.profili.map(x=>`<button role="tab" aria-selected="${x.id==sel}" class="${x.id==sel?"on":""}" data-p="${x.id}">${x.nome}</button>`).join("")}</div>
   <label class="pcap pcapbar">Il tuo capitale <input type="text" inputmode="numeric" value="${capitale.toLocaleString("it-IT")}" aria-label="Capitale da investire in euro"> &euro;</label>
   ${hero(p)}
   ${corso(p)}
   <div class="card pacq" id="pacq">${acquistoHTML(p)}</div>
   <div class="pgrid">${composizione(p)}${contro(p)}</div>
   <h3 class="vft">Andamento del capitale <details class="info"><summary title="Come leggerlo" aria-label="Come leggerlo">i</summary><div>Base 100, scala logaritmica: la stessa percentuale ha la stessa altezza in ogni periodo. Linea turchese = portafoglio, tratteggio = 60/40 di confronto, linea luminosa = live dalla prima rotazione pubblicata.</div></details></h3>
   <div class="vfswitch pper">${[["tutto","Tutto"],["oos","Dal 2016"]].map(x=>`<button data-per="${x[0]}" class="${per==x[0]?"on":""}">${x[1]}</button>`).join("")}</div>
   <div class="card pgraf">${curva(p)}</div>
   ${tabella(p)}
   ${simulatoreHTML(p)}
   ${crisiHTML(p)}
   <details class="psez"><summary><h3 class="vft">Confronto dei 3 profili</h3><span class="small">mese per mese</span></summary>${confronto()}</details>
   <div class="pbasso"><h3 class="vft">Ultime rotazioni <details class="info"><summary title="Come leggerle" aria-label="Come leggerle">i</summary><div>+ entrati, &minus; usciti, = rimasti. La riga in alto &egrave; la rotazione in vigore o in partenza; sotto ogni mese chiuso c'&egrave; il risultato con il dettaglio per mercato.</div></details></h3>${rotazioni(p)}</div>`;
  el.querySelectorAll(".pseg button").forEach(b=>b.onclick=()=>{sel=b.dataset.p;try{localStorage.setItem("ebProfilo",sel);}catch(e){}ridisegna(".pseg");});
  // clic su un titolo delle azioni scelte: apre la sua scheda nell'Azionario (azioni.js)
  el.querySelectorAll("[data-az]").forEach(b=>b.onclick=()=>{if(window.ebApriTitolo)window.ebApriTitolo(b.dataset.az);});
  el.querySelectorAll(".pper button").forEach(b=>b.onclick=()=>{per=b.dataset.per;ridisegna(".pper");});
  el.querySelectorAll(".pcfsw button").forEach(b=>b.onclick=()=>{cfrSel=b.dataset.c;ridisegna(".pcfsw");});
  const bt=el.querySelector(".ptutte");if(bt)bt.onclick=()=>{tutteRot=!tutteRot;ridisegna(".ptutte");};
  isinAzioni(el);
  // v6.78 pulsante "Scarica PDF" del profilo scelto (01b_pdf.js)
  const pb=el.querySelector(".phero .pdfbtn");if(pb)pb.onclick=()=>ebPdf.avvia(pb,pdfPort);
  // copia dell'ISIN: feedback "Copiato" per 1,5 secondi
  el.querySelectorAll(".pisin").forEach(b=>b.onclick=async()=>{try{await navigator.clipboard.writeText(b.dataset.isin);}catch(e){}
   b.classList.add("ok");b.querySelector("code").textContent="Copiato";setTimeout(()=>{b.classList.remove("ok");b.querySelector("code").textContent=b.dataset.isin;},1500);});
  // capitale: ricalcola gli importi in euro mentre si scrive (solo cifre), salvato nel browser
  const ci=el.querySelector(".pcap input");if(ci){ci.oninput=()=>{const v=+ci.value.replace(/\D/g,"");capitale=v||0;
   aggiornaEuro(p);};ci.onblur=()=>{ci.value=capitale.toLocaleString("it-IT");try{localStorage.setItem("ebCapitale",capitale);}catch(e){}};}
  simEventi(p);
  crEventi(p);
  liveOggi(p);
  tipMesi(el.querySelector(".pcontro"),p);
  conto();
  suggerimento(el.querySelector(".pgraf"),p);}
 // --- v6.73 ISIN DELLE AZIONI SCELTE: dal profilo dell'azienda (Wikidata, cot_radar/profili.py), per cercare il titolo
 //     nell'app del broker anche quando il ticker di Yahoo (es. 2801.T) non c'e'. Tocco = copia (non apre la scheda).
 const ISIN_AZ={};
 // ISIN di un titolo (una sola richiesta per titolo, ricordata): usato dalla pagina e dal PDF
 const isinDi=t=>ISIN_AZ[t]||(ISIN_AZ[t]=fetch("../azioni/profili/"+encodeURIComponent(t.replace("^","_"))+".json",{cache:"no-cache"})
  .then(r=>r.ok?r.json():null).catch(()=>null).then(x=>x&&x.isin));
 function isinAzioni(el){el.querySelectorAll("[data-isinaz]").forEach(sp=>{const t=sp.dataset.isinaz;
  const p=isinDi(t);
  p.then(isin=>{if(!isin||!sp.isConnected)return;sp.hidden=false;sp.title="Copia l'ISIN da cercare nell'app del broker";
   sp.innerHTML=`ISIN <code>${esc(isin)}</code><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>`;
   sp.onclick=async e=>{e.stopPropagation();try{await navigator.clipboard.writeText(isin);}catch(_){}
    const c=sp.querySelector("code");sp.classList.add("ok");c.textContent="Copiato";setTimeout(()=>{sp.classList.remove("ok");c.textContent=isin;},1500);};});});}
 // --- CONTO ALLA ROVESCIA al prossimo ribilanciamento: primo giorno di borsa del mese alle 09:00 ora italiana
 //     (apertura di Xetra/Borsa Italiana, dove si comprano gli strumenti UCITS). Un solo timer per tutta la pagina,
 //     fermo quando la scheda del browser non e' visibile; se la data manca o e' passata mostra un testo fisso.
 let timer=0;
 function oraRoma(ymd,h){// Date per "ymd hh:00" a Roma, con ora legale/solare corretta (senza librerie)
  const [y,m,d]=ymd.split("-").map(Number),g=Date.UTC(y,m-1,d,h);
  const parti=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Rome",hour:"2-digit",hourCycle:"h23"}).formatToParts(new Date(g));
  const hr=+parti.find(x=>x.type=="hour").value;return new Date(g-((hr-h+24)%24)*3600e3);}
 function conto(){clearInterval(timer);const box=el.querySelector(".pcount");if(!box||!box.dataset.t)return;
  let fine;try{fine=oraRoma(box.dataset.t,9);}catch(e){return;}
  const out=box.querySelector(".pcd"),z=n=>String(n).padStart(2,"0");
  const tick=()=>{if(!document.body.contains(box)){clearInterval(timer);return;}
   const ms=fine-Date.now();
   // v6.81: arrivata l'ora (09:00 di Roma del giorno di rotazione) niente piu' "tra oggi": etichetta IN CORSO
   if(ms<=0){if(box.firstChild&&box.firstChild.nodeType===3)box.firstChild.textContent="Rotazione ";
    out.innerHTML='<i class="pcdot"></i>IN CORSO';box.classList.add("ora");
    box.title="Rotazione in corso: si esegue oggi all'apertura delle borse europee (09:00 ora italiana)";clearInterval(timer);return;}
   const t=Math.floor(ms/1000),gi=Math.floor(t/86400),o=Math.floor(t%86400/3600),mi=Math.floor(t%3600/60),se=t%60;
   out.innerHTML=`${gi?`<u>${gi}</u>g `:""}<u>${z(o)}</u>h <u>${z(mi)}</u>m <u>${z(se)}</u>s`;};
  tick();timer=setInterval(()=>{if(!document.hidden)tick();},1000);}
 // importi in euro senza ridisegnare tutto (il campo resta a fuoco mentre si scrive)
 // v7.1 VARIAZIONE DI OGGI del portafoglio (prezzi Xetra in euro, ritardo di borsa): somma di peso x variazione
 //     dall'ultima chiusura di ogni ETF; liquidita' = 0. Si mostra solo se la seduta di oggi non e' gia' nella chiusura.
 function liveOggi(p){const box=el.querySelector(".pmc-oggi"),L=window.ebLive,c=p.corrente;if(!box||!L||!L.ue||!c||c.attesa)return;
  let r=0,w=0,t=0;p.composizione.forEach(x=>{const v=L.ue[x.k]||(x.k=="AZ"&&L.ue.SP500);if(x.k=="CASH")w+=x.peso;
   else if(v&&v.p&&v.prev){r+=x.peso/100*(v.p/v.prev-1)*100;w+=x.peso;t=Math.max(t,v.t||0);}});
  const giorno=t?new Date(t*1000).toISOString().slice(0,10):null;if(!giorno||giorno<=c.al||w<50){box.hidden=true;return;}
  const ora=new Date(t*1000).toLocaleTimeString("it-IT",{hour:"2-digit",minute:"2-digit"}),mese=((1+c.r/100)*(1+r/100)-1)*100;
  box.hidden=false;box.innerHTML=`<span class="plive on"><i></i>Oggi alle ${ora}</span><b class="${r>=0?"up":"down"}">${pc(r,2)}</b><span>mese stimato <b class="${mese>=0?"up":"down"}">${pc(mese)}</b></span>
   <details class="info"><summary title="Come si calcola" aria-label="Come si calcola">i</summary><div>Variazione di oggi degli ETF in euro su Xetra (ritardo di borsa di circa 15-20 minuti), pesata con la composizione del mese. &Egrave; una stima: il risultato ufficiale del mese usa le chiusure di fine giornata.</div></details>`;}
 window.addEventListener("eb-live",()=>{const p=P.profili.find(x=>x.id==sel);if(!p)return;aggiornaEuro(p);liveOggi(p);});
 function aggiornaEuro(p){const pesi=[];MACRO.forEach(g=>p.composizione.filter(c=>g[1].includes(c.classe)).forEach(c=>pesi.push(c.peso)));
  el.querySelectorAll(".pcomp .peur").forEach((e,i)=>{e.textContent=eur(capitale*(pesi[i]||0)/100);});
  el.querySelectorAll(".paz-p em").forEach(e=>{e.textContent=eur(capitale*(+e.dataset.peso||0)/100);});
  const a=el.querySelector("#pacq");if(a){const aperti=[...a.querySelectorAll("details")].map(d=>d.open);a.innerHTML=acquistoHTML(p);   // v6.91
   a.querySelectorAll("details").forEach((d,i)=>{d.open=!!aperti[i];});}}
 // tooltip del grafico del rischio del mese: anno, rendimento, max drawdown
 function tipMesi(card,p){if(!card||!p.mese)return;const m=p.mese,box=card.querySelector(".phmbox"),tip=card.querySelector(".phmtip");if(!box)return;
  // interruttore Risultato del mese / Scenario peggiore: ridisegna solo la griglia
  card.querySelectorAll(".phmsw button").forEach(b=>b.onclick=()=>{hmModo=b.dataset.m;
   card.querySelectorAll(".phmsw button").forEach(x=>{x.classList.toggle("on",x===b);x.setAttribute("aria-selected",x===b);});
   box.querySelector(".phm").innerHTML=hmCelle(m,hmModo);card.querySelector(".phmleg").innerHTML=hmLeg(hmModo);tip.hidden=true;});
  // fumetto: mouse, tastiera e tocco
  const mostra=e=>{const c=e.target.closest(".phmc[data-a]");if(!c){tip.hidden=true;return;}
   const x=m.anni.find(q=>q.a==c.dataset.a),r=box.getBoundingClientRect(),cb=c.getBoundingClientRect();
   tip.innerHTML=`<b>${m.mese[0].toUpperCase()+m.mese.slice(1)} ${x.a}</b><span>Risultato del mese <b class="${x.r>=0?"up":"down"}">${pc(x.r)}</b></span><span>Scenario peggiore <b class="down">${pc(x.dd)}</b></span><span>10.000 € &rarr; ${eur(10000*(1+x.r/100))} a fine mese</span>`;
   tip.hidden=false;const w=tip.offsetWidth,h=tip.offsetHeight;
   tip.style.left=Math.max(0,Math.min(r.width-w,cb.left-r.left+cb.width/2-w/2))+"px";
   tip.style.top=(cb.top-r.top-h-8<0?cb.bottom-r.top+8:cb.top-r.top-h-8)+"px";};
  box.addEventListener("mouseover",mostra);box.addEventListener("focusin",mostra);box.addEventListener("click",mostra);
  box.addEventListener("mouseleave",()=>tip.hidden=true);}

 // --- passando il mouse sulla curva: linea verticale, punto e valore della settimana
 function suggerimento(box,p){const svg=box&&box.querySelector("svg.pcurva");if(!svg)return;const tip=box.querySelector(".ptip");
  const lin=svg.querySelector(".pcur"),pt=svg.querySelector(".pcurp"),path=svg.querySelector(".plinea");
  const dal=per=="oos"?P.oos_dal:per=="live"?(p.live_dal||P.oos_dal):null;
  const s=p.curva.filter(x=>!dal||x[0]>=dal),b0=s.length?s[0][1]:1;
  svg.addEventListener("mousemove",e=>{const r=svg.getBoundingClientRect(),fx_=(e.clientX-r.left)/r.width;
   const vb=svg.viewBox.baseVal,x=fx_*vb.width;if(x<52||x>vb.width-14)return;
   const t0=+svg.dataset.t0,t1=+svg.dataset.t1,t=t0+(x-52)/(vb.width-66)*(t1-t0);
   let i=s.findIndex(q=>+new Date(q[0])>=t);if(i<0)i=s.length-1;
   const len=path.getTotalLength();let a=0,z=len,P2=null;
   for(let k=0;k<22;k++){const m=(a+z)/2;P2=path.getPointAtLength(m);if(P2.x<x)a=m;else z=m;}
   lin.setAttribute("x1",x);lin.setAttribute("x2",x);lin.style.display="";pt.setAttribute("cx",P2.x);pt.setAttribute("cy",P2.y);pt.style.display="";
   tip.hidden=false;tip.innerHTML=`<b>${gg(s[i][0])}</b> ${fx(s[i][1]/b0*100,1)} <span>(${pc(s[i][1]/b0*100-100)})</span>`;
   tip.style.left=Math.min(r.width-170,Math.max(0,e.clientX-r.left+12))+"px";});
  svg.addEventListener("mouseleave",()=>{lin.style.display="none";pt.style.display="none";tip.hidden=true;});}
 disegna();
})();}catch(e){fail('Portafogli','port',e);}
