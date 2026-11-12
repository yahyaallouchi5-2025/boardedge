
/* ---------- portafogli modello ----------
   Dati da D.port (vedi cot_radar/portafogli.py): tre profili (conservativo, moderato, aggressivo), solo acquisti,
   rotazione il primo giorno di borsa di ogni mese. In alto un selettore a segmenti (Conservativo / Moderato /
   Aggressivo: "stesso motore, rischio diverso") e la CARD PRINCIPALE del profilo: rischio, descrizione, rendimento
   annuo, max drawdown, 10.000 euro dall'inizio dello storico, composizione per classe, le azioni scelte del mese
   e la spiegazione apribile della rotazione. Sotto, per il profilo scelto:
     1. "Portafoglio di <mese>" del profilo scelto: righe raggruppate per classe (Azionario, Obbligazionario,
        Materie prime, Cripto, Liquidita'), per ogni mercato lo strumento UCITS/ETC/ETP da comprare in Europa con
        ISIN copiabile, peso e importo in euro sul capitale scritto dall'utente; le azioni scelte elencate una per
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
 // v7.36 migliaia SEMPRE con il punto: Intl it-IT non separa i numeri di 4 cifre ("5000 €" accanto a "10.000 €")
 const mil=v=>{const n=Math.round(v),t=String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g,".");return (n<0?"-":"")+t;};
 const eur=v=>v==null?"n/d":mil(v)+" €";
 const gg=d=>d?d.slice(8,10)+"/"+d.slice(5,7)+"/"+d.slice(0,4):"";
 const nomeK=k=>{for(const p of P.profili){const c=p.composizione.find(x=>x.k==k);if(c)return c.nome;const a=p.ammessi.find(x=>x.k==k);if(a)return a.nome;}return k;};
 let sel=P.profili[1].id,per="tutto",tutteRot=false;
 // v7.9 la scheda in 3 sezioni (meno scorrimento, soprattutto da telefono): Oggi / Storico / Rotazioni (ricordata)
 const VISTE=[["oggi","Oggi"],["storico","Storico"],["rotazioni","Rotazioni"]];
 let vista="oggi";try{const v=localStorage.getItem("ebPortVista");if(VISTE.some(x=>x[0]==v))vista=v;}catch(e){}
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
  // v7.61 fino a 20 titoli: in pagina i primi VISIBILI, gli altri in un elenco che si apre (meno rumore visivo)
  if(c.k=="AZ"){const VISIBILI=5,reg=c.titoli&&c.titoli.length,an=c.anteprima,lista=reg?c.titoli:(an&&an.titoli)||[];
   const quota=lista.length?c.peso/lista.length:0;
   if(lista.length)tit=`<div class="paz">${reg?"":`<div class="paz-ante"><b>Anteprima per ${MESI[+an.mese.slice(5,7)-1]}</b> &middot; calcolata il ${gg(an.al)} con i prezzi di oggi. La lista definitiva si fissa l'ultimo giorno di borsa dopo la chiusura ed entra il ${gg(P.prossima)}.</div>`}
    ${lista.map((x,ix)=>{const b=borsa(x.t),sett=(SETT[x.s]||[x.s||""])[0];return `<button class="paz-r clic" data-az="${esc(x.t)}" title="Apri nell'Azionario">
     <span class="paz-id"><b>${esc(x.t)}</b><span class="paz-n">${esc(x.n)}</span>${x.sost?`<span class="paz-sost" title="${esc(x.sost_n||x.sost)} (${esc(x.sost)}) non si compra su Scalable: sostituito dal candidato acquistabile successivo, stessi filtri">al posto di ${esc(x.sost_n||x.sost)}</span>`:""}<span class="paz-isin" data-isinaz="${esc(x.t)}" hidden></span></span><span class="paz-s">${esc(sett)}</span><span class="paz-b${b[1]?"":" no"}" title="${b[1]?"Borsa di quotazione":"Di solito non acquistabile dai broker europei per privati"}">${b[0]}</span><span class="paz-p"><b>${fx(quota,quota<1?2:1)}%</b><em data-peso="${quota}">${eur(capitale*quota/100)}</em></span></button>${ix==VISIBILI-1&&lista.length>VISIBILI+1?`<details class="paz-piu"><summary>Altre ${lista.length-VISIBILI} azioni</summary><div class="paz">`:""}${ix==lista.length-1&&lista.length>VISIBILI+1?"</div></details>":""}`;}).join("")}</div>`;
   else tit=`<div class="small paz-vuoto">Le azioni (fino a 20) si scelgono l'ultimo giorno di borsa del mese, dopo la chiusura, ed entrano con la rotazione del ${gg(P.prossima)}.</div>`;}
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
 //     il prezzo e' quello di chiusura e durante il giorno si muove). Le azioni scelte: se 1 azione costa piu' della sua
 //     quota, al suo posto la prima RISERVA (stessa regola, punteggio successivo) che ci sta (fino a novembre 2026
 //     max 1 titolo per settore; v7.61 da dicembre nessun limite per settore, come la regola fino a 20 titoli).
 //     Quello che avanza resta sul conto. Il modello e il registro live non cambiano: e' solo come lo realizzi tu.
 const MARG=1.005;
 // --- v7.6 VERSIONE COMPATTA (capitali sotto P.compatto.sotto): Nasdaq unito all'S&P 500 (pesi calcolati dal backend,
 //     cot_radar/portafogli.py profilo_compatto) e S&P 500 comprato con l'ETF Vanguard (quota piu' piccola, stesso indice)
 const compatto=cap=>!!(P.compatto&&cap>0&&cap<P.compatto.sotto);
 function compAcq(p,cap){if(!compatto(cap)||!p.compatto)return p.composizione;const w=p.compatto.pesi;
  return p.composizione.filter(c=>w[c.k]!=null).map(c=>Object.assign({},c,{peso:w[c.k]}));}
 // strumento da comprare per un mercato: {lk (chiave dei prezzi live), nome, isin, prezzo}
 function strumentoAcq(c,cap){
  if(c.k=="SP500"&&compatto(cap)&&P.compatto.sp500)return Object.assign({lk:"SP500C"},P.compatto.sp500);
  return c.ue?Object.assign({lk:c.k},c.ue):null;}
 const prezzoLive=(lk,base)=>{const lv=window.ebLive&&ebLive.ue&&ebLive.ue[lk];return (lv&&lv.p)||base||null;};
 // v7.33: capitale come parametro (test del profilo); senza = il capitale scritto dall'utente
 function piano(p,cap){cap=cap||capitale;const righe=[];let spesa=0;
  const ordine=[];MACRO.forEach(g=>compAcq(p,cap).filter(c=>g[1].includes(c.classe)).forEach(c=>ordine.push(c)));
  ordine.forEach(c=>{const obi=cap*c.peso/100;
   if(c.k=="AZ"){const lista=c.titoli||[];if(!lista.length)return;const per=obi/lista.length,ris=(c.riserve||[]).slice(),settori=new Set(c.regola20?[]:lista.map(x=>x.s));
    lista.forEach(x=>{let t=x,nota=null;
     if(!x.eur||x.eur*MARG>per){                                // 1 azione costa piu' della quota (o prezzo mancante)
      settori.delete(x.s);const i=ris.findIndex(r=>r.eur*MARG<=per&&(c.regola20||!settori.has(r.s))&&!lista.some(y=>y.t==r.t));
      if(i>=0){t=ris.splice(i,1)[0];nota=`al posto di ${x.n}${x.eur?` (1 azione &asymp; ${eur(x.eur)})`:""}`;}else{t=null;nota=`${x.n}: 1 azione costa pi&ugrave; della quota e nessuna riserva ci sta, resta sul conto`;}
      if(t&&!c.regola20)settori.add(t.s);}
     if(!t){righe.push({az:true,nome:x.n,tk:x.t,q:0,prezzo:x.eur,obi:per,nota});return;}
     const q=Math.floor(per/(t.eur*MARG));spesa+=q*t.eur;righe.push({az:true,nome:t.n,tk:t.t,q,prezzo:t.eur,obi:per,nota});});
    return;}
   // v7.1 LIQUIDITA' SUL CONTO: niente ETF overnight da comprare, la quota resta sul conto del broker (interessi)
   // v7.5 regola BCE: tasso sui depositi sotto zero = niente XEON (perde ogni giorno), si resta sul conto a 0%
   if(c.k=="CASH"){const t=P.tasso_bce,neg=t!=null&&t<=0;
    righe.push({cash:true,neg,nome:"Liquidità sul conto",obi,real:obi,q:null,prezzo:null,
     nota:t==null?null:neg?`tasso BCE ${fx(t,2)}%: niente XEON`:`oppure XEON (LU0290358497) &middot; tasso BCE ${fx(t,2)}%`});return;}
   const u=strumentoAcq(c,cap),pr=u&&prezzoLive(u.lk,u.prezzo);   // v7.1: intraday se c'e'
   if(!pr){righe.push({nome:u?u.nome:c.nome,isin:u&&u.isin,q:null,prezzo:null,obi});return;}
   const q=Math.floor(obi/(pr*MARG));spesa+=q*pr;
   righe.push({nome:u.nome,isin:u.isin,q,prezzo:pr,obi,nota:q?null:`1 quota costa di pi&ugrave;: resta sul conto`});});
  const scost=righe.reduce((a,r)=>a+Math.abs((r.real??(r.q||0)*(r.prezzo||0))-r.obi),0)/2/(cap||1)*100;
  return {righe,spesa,resto:cap-spesa,scost};}
 // v7.33 CAPITALE MINIMO di un profilo: il piu' piccolo importo (griglia sotto) con cui, a quote intere e ai prezzi di oggi,
 //     il conto resta entro SCOST_OK punti percentuali dal modello. Sotto, alcune quote non si comprano e restano sul conto.
 const SCOST_OK=5,GRIGLIA_CAP=[1000,2000,3000,4000,5000,6000,7500,10000,12500,15000,20000,25000,30000,40000,50000,75000,100000];
 // (da quel capitale in su lo scarto resta sempre entro la soglia: sopra i 10.000 euro si torna alla versione intera,
 //  con quote piu' care, e lo scarto puo' risalire)
 const minimoCap=p=>{let m=null;for(let i=GRIGLIA_CAP.length-1;i>=0;i--){if(piano(p,GRIGLIA_CAP[i]).scost<=SCOST_OK)m=GRIGLIA_CAP[i];else break;}return m;};
 window.__scostamento=(id,cap)=>{const p=P.profili.find(x=>x.id==id);return p?{scost:piano(p,cap).scost,minimo:minimoCap(p)}:null;};   // DEBUG
 function compattoHTML(p){const c=p.compatto,s=c&&c.stat.totale,t=p.stat.totale||{};
  return `<div class="pacq-cmp"><span class="pacq-cb">Versione compatta</span><span class="small">sotto ${eur(P.compatto.sotto)}</span>
   <details class="info"><summary title="Cos'&egrave;" aria-label="Cos'&egrave;">i</summary><div>Con meno di ${eur(P.compatto.sotto)} alcune quote intere costano troppo (S&amp;P 500 circa 700 &euro;, Nasdaq-100 circa 1.300 &euro;) e il conto si allontana dal modello. Qui l'<b>S&amp;P 500</b> si compra con l'ETF Vanguard: stesso indice, quota pi&ugrave; piccola.${c?` Il <b>Nasdaq-100</b> &egrave; unito all'S&amp;P 500, che lo contiene gi&agrave; in buona parte.<br><br><b>Nello storico</b>: ${fx(s.cagr,1)}% l'anno contro ${fx(t.cagr,1)}% del modello completo, drawdown massimo ${pc(s.maxdd)} contro ${pc(t.maxdd)}. Stessa misura del sito: euro, costi inclusi.`:" Il resto del portafoglio non cambia."}</div></details></div>`;}
 // v7.25 STATO DEI PREZZI di "Acquisto diretto": verde a Xetra aperta con prezzi di oggi; rosso a borsa chiusa (con la
 // prossima apertura, festivita' comprese: 02b_mercati.js) e la data della chiusura usata. Mai un orario "nudo" vecchio.
 function statoPrezzi(ora,oggi,dt){const eu=window.ebMercati?ebMercati.stato("Europa"):null,aperta=eu?eu.aperto:!!oggi;
  if(aperta&&ora&&oggi)return `<span class="plive on" title="Prezzi intraday con il ritardo di borsa (circa 15-20 minuti)"><i></i>Xetra aperta &middot; prezzi delle ${ora} &middot; ritardo ~15 min</span>`;
  const quando=dt?(oggi?"di oggi":"del "+dt.toLocaleDateString("it-IT",{day:"2-digit",month:"2-digit"})):"dell'ultima seduta";
  if(aperta)return `<span class="plive" title="I prezzi di oggi arrivano entro pochi minuti"><i></i>Xetra aperta &middot; prezzi di chiusura ${quando}</span>`;
  const riapre=eu&&eu.prossima?` &middot; riapre ${ebMercati.oraIt(eu.prossima)}`:"";
  return `<span class="pacq-st"><span class="azmk off"><i></i>${eu&&eu.festivo?"Borse chiuse per festivit&agrave;":"Xetra chiusa"}${riapre}</span><span class="small">prezzi di chiusura ${quando}</span></span>`;}
 function acquistoHTML(p){const pi=piano(p);if(!pi.righe.length)return "";
  // orario dei PREZZI (non della corsa): a borse chiuse e' l'ultima seduta, quindi si mostra anche la data
  const L=window.ebLive,tt=L&&L.ue?Math.max(0,...Object.values(L.ue).map(v=>v.t||0)):0,dt=tt?new Date(tt*1000):null,
   oggi=dt&&dt.toDateString()==new Date().toDateString(),
   ora=dt?(oggi?"":dt.toLocaleDateString("it-IT",{day:"2-digit",month:"2-digit"})+" ")+dt.toLocaleTimeString("it-IT",{hour:"2-digit",minute:"2-digit"}):null;
  return `<div class="pacq-t"><h3>Acquisto diretto <span class="small">quote intere su ${eur(capitale)}</span></h3>
    ${statoPrezzi(ora,oggi,dt)}
    <details class="info pacq-i"><summary title="Come si calcola" aria-label="Informazioni">i</summary><div>Con l'ordine normale il broker compra solo <b>quote intere</b>: per ogni strumento il numero di quote &egrave; la parte intera di importo del modello &divide; prezzo di 1 quota (prezzo di chiusura, con 0,5% di margine). Quello che avanza resta sul conto. Le <b>azioni scelte</b>: se 1 azione costa pi&ugrave; della sua quota, al suo posto c'&egrave; il candidato successivo della stessa regola che ci sta. Con capitali piccoli lo <b>scostamento dal modello</b> &egrave; normale; il modello e i risultati pubblicati non cambiano. Prezzi indicativi: controllali sul broker prima di confermare.<br><br><b>A borsa chiusa</b> i prezzi sono quelli di chiusura dell'ultima seduta (Xetra, 17:30). Su Scalable (gettex) gli ordini si possono inviare anche la sera: il prezzo &egrave; quello del market maker in quel momento e pu&ograve; scostarsi dalla chiusura.</div></details></div>
   ${compatto(capitale)?compattoHTML(p):""}
   <div class="pacq-l">${pi.righe.map(r=>`<div class="pacq-r${r.q===0?" zero":""}"><div class="pacq-n"><b>${esc(r.nome)}</b><span>${r.cash&&!r.nota?"nessun acquisto":r.cash?"":r.isin?`ISIN ${esc(r.isin)}`:esc(r.tk||"")}${r.nota?(r.cash&&!r.neg?r.nota:`${r.cash?"":" &middot; "}<em>${r.nota}</em>`):""}</span></div>
    <div class="pacq-q">${r.cash?`<b>${eur(r.obi)}</b><span>resta sul conto</span>`:r.q==null?`<span class="small">prezzo n/d &middot; ${eur(r.obi)}</span>`:`<b>${r.q} ${r.q==1?"quota":"quote"}</b><span>${r.prezzo?"&times; "+fx(r.prezzo,2)+" € = "+eur(r.q*r.prezzo):""}</span>`}</div></div>`).join("")}</div>
   <div class="pacq-tot"><span>Investito <b>${eur(pi.spesa)}</b></span><span>Resta sul conto <b>${eur(pi.resto)}</b></span></div>
   <details class="pacq-come"><summary>Come comprare su Scalable</summary><ol>
    <li>Copia l'<b>ISIN</b> (o il ticker per le azioni) e cercalo nella barra di ricerca.</li>
    <li>Premi <b>Acquista</b>: la borsa proposta (es. European Investor Exchange) va bene.</li>
    <li>Passa da <b>Importo target</b> alla scheda <b>Numero di titoli</b> e scrivi le quote indicate qui sopra (con l'importo Scalable arrotonda per difetto alle quote intere).</li>
    <li><b>Prepara ordine</b>, controlla il totale e conferma, in orario di borsa (09:00-17:30).</li>
    <li><b>Versamenti mensili</b>: inseriscili in &laquo;Il mio conto&raquo;, che indica dove mettere i soldi nuovi. Con il piano di accumulo aggiorna gli importi a ogni rotazione.</li></ol></details>`;}

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
  // v7.38 riquadro con 3 righe fisse: intestazione (etichetta a sinistra, etichetta di contesto a destra) | valore | piede
  //   stesse altezze e stessa dimensione del valore in tutti e tre, cosi' i testi sono allineati in orizzontale
  const tk=(lab,tag,val,cls,piede)=>`<div class="pk"><div class="pk-h"><span>${lab}</span>${tag?`<em>${tag}</em>`:""}</div><b class="pk-v ${cls||""}">${val}</b><div class="pk-f">${piede||""}</div></div>`;
  const NM=MES(m&&m.mese||c.mese),pos=m&&m.n?`${m.positivi} anni su ${m.n}`:"storico non disponibile";
  if(c.attesa)return `<div class="card pmc"><div class="pmc-t"><h3>${MES(c.mese)} in partenza <span class="pbprof">${esc(p.nome)}</span></h3>
    <span class="pmc-b">Composizione decisa &middot; si entra il ${gg(c.dal)}</span></div>
   <div class="pmc-k pk3">${tk("Giorni di borsa","",c.tot,"","nel mese")}${tk("Positivo",NM,wr==null?"n/d":wr+"%",wr!=null&&wr>=50?"up":"",pos)}${tk("Media storica",NM,m&&m.media!=null?pc(m.media):"n/d",m&&m.media>=0?"up":"down","rendimento medio del mese")}</div>
   ${chiusi.length?`<div class="pmc-h"><div class="pmc-ht">Mesi chiusi (live)</div>${chiusi.map(x=>{const r=x.profili[p.id];return `<div class="pmc-hr"><span>${MES(MESI[+x.mese.slice(5)-1])} ${x.mese.slice(0,4)}</span><b class="${r.r>=0?"up":"down"}">${pc(r.r)}</b><em>drawdown ${pc(r.dd)}</em></div>`;}).join("")}</div>`:""}</div>`;
  return `<div class="card pmc"><div class="pmc-t"><h3>${MES(c.mese)} in corso <span class="pbprof">${esc(p.nome)}</span><details class="info pmci"><summary title="Come si legge" aria-label="Come si legge">i</summary><div>Risultato del mese dalla chiusura del giorno di rotazione all'ultima chiusura. La barra sotto confronta il mese con gli stessi mesi degli anni passati (minimo, media, massimo). Il risultato &egrave; provvisorio fino a fine mese.</div></details></h3>
    <span class="pmc-b${c.live?"":" sim"}">${c.live?"Provvisorio &middot; si chiude a fine mese":"Simulazione &middot; il live parte il "+gg(P.prossima)}</span></div>
   <div class="pmc-g"><b class="${cl}">${pc(r)}</b><span>da inizio mese &middot; ingresso alla chiusura del ${gg(c.dal)} &middot; <em class="pmc-al${fermi(c.al)?" fermo":""}" title="${fermi(c.al)?"Prezzi non aggiornati: il risultato non include le ultime sedute":"Ultima chiusura usata"}">prezzi al ${gg(c.al)}${fermi(c.al)?" (in aggiornamento)":""}</em></span></div>
   <div class="pmc-oggi" hidden></div>
   <div class="pmc-k pk3">
    ${tk("Giorno di borsa","",`${c.gg} <span class="pk-di">di ${c.tot}</span>`,"",`<span class="pmc-bar"><i style="width:${Math.min(100,c.gg/c.tot*100).toFixed(0)}%"></i></span>`)}
    ${tk("Drawdown del mese","",pc(c.dd),"down","dal massimo del mese")}
    ${tk("Positivo",NM,wr==null?"n/d":wr+"%",wr!=null&&wr>=50?"up":"",pos)}</div>
   ${termo?`<div class="pmc-fw"><span class="pmc-ft">${MES(m&&m.mese||c.mese)} negli anni passati</span>${termo}</div>`:""}
   ${chiusi.length?`<div class="pmc-h"><div class="pmc-ht">Mesi chiusi (live)</div>${chiusi.map(x=>{const r=x.profili[p.id];return `<div class="pmc-hr"><span>${MES(MESI[+x.mese.slice(5)-1])} ${x.mese.slice(0,4)}</span><b class="${r.r>=0?"up":"down"}">${pc(r.r)}</b><em>drawdown ${pc(r.dd)}</em></div>`;}).join("")}</div>`:""}
</div>`;}

 function tabella(p){const st=p.stat,b=(P.bench||{}).stat||{};
  // v6.52: la colonna Live compare solo quando ci sono dati live (prima era una colonna di "in arrivo")
  const col=[["Storico",st.storico,`fino al 2015`],["Verifica",st.oos,`dal 2016`]].concat(st.live?[["Live",st.live,p.live_dal?`dal ${gg(p.live_dal)}`:"dall'avvio"]]:[]).concat([["60/40",b.oos,"dal 2016"]]);
  const r=(t,f)=>`<tr><th>${t}</th>${col.map(c=>`<td>${c[1]?f(c[1]):'<span class="small">n/d</span>'}</td>`).join("")}</tr>`;
  return `<div class="tablewrap ptab"><table><tr><th class="ptab0">Risultati<span>per periodo <details class="info pti"><summary title="Periodi" aria-label="Periodi">i</summary><div>Regole decise sui dati fino al 2015 e verificate dal 2016 in poi. 60/40 = 60% azioni USA e 40% Treasury, per confronto.${p.robusto&&p.robusto[150]&&p.robusto[250]?`<br><br><b>Test di robustezza</b> (tutto lo storico): con la media a 150 giorni ${pc(p.robusto[150].cagr)} l'anno e drawdown ${pc(p.robusto[150].maxdd)}; a 250 giorni ${pc(p.robusto[250].cagr)} e ${pc(p.robusto[250].maxdd)}; con 200 giorni (il modello) ${pc((st.totale||{}).cagr)} e ${pc((st.totale||{}).maxdd)}. Il rendimento cambia poco: il modello non dipende da un numero scelto ad arte. Il drawdown varia di pi&ugrave;: considera il peggiore come quello realistico.`:""}${st.live?"":` La colonna Live compare dopo la prima rotazione con le regole attuali.`}</div></details></span></th>${col.map(c=>`<th>${c[0]}<span>${c[2]}</span></th>`).join("")}</tr>
   ${r("Rendimento annuo",x=>x.cagr==null?pc(x.totale)+" tot.":pc(x.cagr))}
   ${r("Max drawdown",x=>`<b class="down">${pc(x.maxdd)}</b>`)}${r("Peggior mese",x=>x.peggior_mese?pc(x.peggior_mese[1]):"n/d")}${r("Mesi positivi",x=>(x.mesi_pos??"n/d")+"%")}</table></div>
   ${tasseHTML(p)}`;}
 // --- v7.8 DOPO LE TASSE (cot_radar/portafogli.py simula_tasse): regime amministrato italiano, dal primo ribilancio
 // v7.19 CONFRONTO dopo le tasse (portafogli.py tasse_profilo): profilo, meta' S&P 500 + meta' profilo, solo S&P 500.
 //     Tre numeri per riga (rendimento netto, drawdown peggiore con barra, tempo per tornare in pari): niente altro.
 function tasseHTML(p){const t=p.tasse;if(!t)return "";
  const cf=t.confronto||[{k:"prof",netto:t.cagr_netto},{k:"sp",netto:t.sp500_netto}];
  const nomi={prof:esc(p.nome),mix:"Met&agrave; S&amp;P 500, met&agrave; "+esc(p.nome),sp:"Solo S&amp;P 500"};
  const peg=Math.min(...cf.map(x=>x.dd||0),-1);
  const pari=m=>m==null?"non ancora":m<12?`${m} mesi`:`${fx(m/12,1)} anni`;
  const riga=x=>`<div class="ptax-r${x.k=="prof"?" ptax-me":""}"><span class="ptax-n">${nomi[x.k]}</span>
    <span class="ptax-c"><small>Rende l'anno</small><b class="${x.netto>=0?"up":"down"}">${pc(x.netto)}</b></span>
    <span class="ptax-c ptax-dd"><small>Drawdown max</small>${x.dd!=null?`<b class="down">${pc(x.dd)}</b><i><em style="width:${Math.round(x.dd/peg*100)}%"></em></i>`:"<b>n/d</b>"}</span>
    <span class="ptax-c"><small>In pari dopo</small><b>${x.dd!=null?pari(x.rec):"n/d"}</b></span></div>`;
  return `<div class="ptax"><div class="ptax-t"><span class="ptax-l">Dopo le tasse <small>dal ${t.dal.slice(0,4)}</small></span><details class="info"><summary title="Come si calcola" aria-label="Come si calcola">i</summary><div><b>Il confronto</b>: tre modi di investire lo stesso capitale dal primo ribilancio, quindi con la crisi del 2008 dentro. <b>Met&agrave; e met&agrave;</b> = met&agrave; nell'S&amp;P 500 comprato e tenuto e met&agrave; nel profilo, due parti separate del conto mai ribilanciate tra loro. <b>In pari dopo</b> = tempo dal picco prima del drawdown peggiore al ritorno sopra quel picco.<br><br><b>Regime amministrato</b> (il broker trattiene le tasse a ogni vendita, come Scalable): ETF azionari 26% sul guadagno, Treasury 12,5%, ETC, Bitcoin e azioni 26% con compensazione delle perdite dei 4 anni prima; le perdite sugli ETF non si compensano con guadagni di altri ETF. Interessi della liquidit&agrave; al 26%, bollo 0,2% l'anno. Il numero suppone di vendere tutto l'ultimo giorno.<br><br><b>Perch&eacute; il portafoglio perde di pi&ugrave; dell'S&amp;P 500</b>: il filtro di trend vende quando un mercato scende sotto la media a 200 giorni e paga le tasse sui guadagni accumulati; chi compra e tiene le paga solo alla fine. &Egrave; il prezzo della protezione: drawdown molto pi&ugrave; piccoli (nel 2008 l'S&amp;P 500 in euro ha perso il 50%).<br><br><b>Regime dichiarato</b> (broker esteri che non fanno da sostituto d'imposta): stesse aliquote, ma le tasse le calcoli e versi tu con la dichiarazione dei redditi e al posto del bollo c'&egrave; l'IVAFE (0,2%). Regole semplificate: per la tua situazione chiedi a un commercialista.</div></details></div>
   ${cf.map(riga).join("")}</div>`;}

 /* v6.52: ogni rotazione mostra com'e' andato il mese (netto e drawdown) e, aprendo "Dettaglio", ogni mercato con
    peso, rendimento, contributo al totale (punti %) e drawdown; per le Azioni scelte anche i singoli titoli. */
 // v7.38 mese in corso: al posto della scritta "mese in corso" il risultato PROVVISORIO (stessi numeri del riquadro del mese)
 // v7.39 ogni mese chiuso dice da dove viene il numero: "Live" = mese seguito dal vivo (registro chiusure, i suoi
 //   numeri hanno la precedenza), "Simulato" = calcolato dal modello con le stesse regole e i prezzi reali.
 function fonteMese(mese,pid){const x=(P.chiusure||[]).find(z=>z.mese==mese&&z.profili&&z.profili[pid]);return x?x.profili[pid]:null;}
 const tagFonte=live=>live?`<span class="pfonte live" title="Mese seguito dal vivo: rotazione e prezzi registrati in tempo reale">Live</span>`
  :`<span class="pfonte sim" title="Calcolato dal modello con le stesse regole e i prezzi reali, prima dell'avvio del live (novembre 2026)">Simulato</span>`;
 function dettMese(m,cor,live){if(m&&live)m=Object.assign({},m,{r:live.r!=null?live.r:m.r,dd:live.dd!=null?live.dd:m.dd});
  if(!m){if(!cor||cor.attesa||cor.r==null)return `<div class="prisul small">mese in corso</div>`;
   return `<div class="prisul"><span class="pmc-b">Provvisorio</span><span>Risultato <b class="${cor.r>=0?"up":"down"}">${pc(cor.r)}</b></span><span>drawdown <b class="down">${pc(cor.dd)}</b></span>${cor.gg&&cor.tot?`<span>giorno di borsa <b>${cor.gg}</b> di ${cor.tot}</span>`:""}</div>`;}
  const riga=a=>`<tr><td>${esc(a.nome)}${a.titoli&&a.titoli.length?`<div class="ptit">${a.titoli.map(t=>`<span>${esc(t.n)} <em class="${t.r==null?"":t.r>=0?"up":"down"}">${t.r==null?"in corso":pc(t.r)}</em></span>`).join("")}</div>`:""}</td>
   <td class="num">${fx(a.w,0)}%</td>${a.attesa?`<td class="num small" colspan="3" title="I rendimenti delle azioni scelte di questo mese arrivano con il prossimo aggiornamento dell'Azionario">dati in arrivo</td>`:`<td class="num ${a.r>=0?"up":"down"}">${pc(a.r)}</td><td class="num ${a.c>=0?"up":"down"}">${a.c>0?"+":""}${fx(a.c,2)}</td><td class="num down">${pc(a.dd)}</td>`}</tr>`;
  const peg=m.asset.filter(x=>x.c!=null).sort((x,y)=>x.c-y.c)[0];
  return `<div class="prisul">${tagFonte(!!live)}<span>Risultato <b class="${m.r>=0?"up":"down"}">${pc(m.r)}</b></span><span>drawdown <b class="down">${pc(m.dd)}</b></span></div>
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
   <div class="psim-c"><label class="pcap">Capitale <input type="text" inputmode="numeric" value="${mil(simCap)}" aria-label="Capitale del simulatore in euro"> &euro;</label>
    ${b(["1","3","5","10"],simOrz,"orz",x=>x+(x=="1"?" anno":" anni"))}${b(["1.0","1.3","1.5"],simLeva,"leva",x=>x=="1.0"?"Senza leva":"Leva "+x.replace(".",",")+"&times;")}</div>
   <div class="psim-b">${simCorpo(p)}</div></div>`;}
 function simEventi(p){const c=el.querySelector("#psim");if(!c)return;const corpo=()=>{c.querySelector(".psim-b").innerHTML=simCorpo(p);};
  const salva=(k,v)=>{try{localStorage.setItem(k,v);}catch(e){}};
  c.querySelectorAll("[data-orz]").forEach(x=>x.onclick=()=>{simOrz=x.dataset.orz;salva("ebSimOrz",simOrz);c.querySelectorAll("[data-orz]").forEach(y=>y.classList.toggle("on",y==x));corpo();});
  c.querySelectorAll("[data-leva]").forEach(x=>x.onclick=()=>{simLeva=x.dataset.leva;salva("ebSimLeva",simLeva);c.querySelectorAll("[data-leva]").forEach(y=>y.classList.toggle("on",y==x));corpo();});
  const ci=c.querySelector("input");ci.oninput=()=>{simCap=+ci.value.replace(/\D/g,"")||0;corpo();};
  ci.onblur=()=>{ci.value=mil(simCap);salva("ebSimCap",simCap);};}


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

 // --- v7.6 IL MIO CONTO: le quote che l'utente ha davvero sul conto (salvate SOLO in questo browser, localStorage
 //     "ebConto"), confrontate con il profilo scelto: valore, risultato (se c'e' il prezzo di carico), distanza dal
 //     modello e ordini a quote intere per riallinearsi alla rotazione. Strumenti equivalenti (Vanguard S&P 500 = S&P 500)
 //     contano come lo stesso mercato: non si vende uno per comprare l'altro (costi e tasse inutili).
 let mioConto={righe:[],altri:[],liq:0,vers:0},contoEdit=false;
 try{const c=JSON.parse(localStorage.getItem("ebConto")||"null");if(c&&Array.isArray(c.righe))mioConto=Object.assign({righe:[],altri:[],liq:0,vers:0},c);}catch(e){}
 const salvaConto=()=>{try{localStorage.setItem("ebConto",JSON.stringify(mioConto));}catch(e){}};
 const EQUIV={SP500C:"SP500"};                       // strumento -> mercato del modello
 const strum=k=>(P.strumenti||{})[k]||null;
 const num=v=>{const x=parseFloat(String(v||"").replace(/\./g,"").replace(",","."));return isFinite(x)&&x>0?x:0;};
 const SOGLIA_ORD=0.02;                               // ordini sotto il 2% del conto: scarto tollerato (niente micro-scambi)
 function contoCalc(p){
  const pos=mioConto.righe.filter(r=>r.k&&r.q>0).map(r=>{const s=strum(r.k)||{},pr=prezzoLive(r.k,s.prezzo);
   return Object.assign({},r,{nome:s.nome||r.k,pr,v:pr?r.q*pr:0,mk:EQUIV[r.k]||r.k});});
  const altri=mioConto.altri.filter(a=>a.v>0),vAltri=altri.reduce((a,x)=>a+x.v,0),liq=+mioConto.liq||0;
  const T=pos.reduce((a,x)=>a+x.v,0)+vAltri+liq;
  let cst=0,gain=0;
  pos.forEach(r=>{if(r.pm>0&&r.pr){cst+=r.q*r.pm;gain+=r.q*(r.pr-r.pm);}});
  altri.forEach(a=>{if(a.c>0){cst+=a.c;gain+=a.v-a.c;}});
  const comp=compAcq(p,T),haAZ=comp.some(c=>c.k=="AZ"),peso=k=>((comp.find(c=>c.k==k)||{}).peso||0)/100;
  // v7.17 i titoli singoli contano nella quota delle azioni scelte SOLO se sono tra quelle del modello (nome o ticker):
  //     gli altri (es. eBay quando esce dal modello) sono "fuori dal modello"
  const az=comp.find(c=>c.k=="AZ"),listaAZ=az?((az.titoli&&az.titoli.length?az.titoli:(az.anteprima||{}).titoli)||[]):[];
  const norm=x=>String(x||"").toLowerCase().replace(/[^a-z0-9]/g,"");
  const nelModello=a=>{const nn=norm(a.n);if(nn.length<2)return false;
   return listaAZ.some(x=>{const tk=norm(String(x.t).split(".")[0]),pr=norm((String(x.n||"").match(/[A-Za-z][A-Za-z&'-]{2,}/)||[""])[0]);
    return nn==tk||(pr.length>=3&&nn.includes(pr))||(nn.length>=3&&norm(x.n).includes(nn));});};
  altri.forEach(a=>{a.dentro=haAZ&&nelModello(a);});
  const tieni={};pos.forEach(r=>{tieni[r.mk]=(tieni[r.mk]||0)+r.v;});
  altri.forEach(a=>{const k=a.dentro?"AZ":"_fuori";tieni[k]=(tieni[k]||0)+a.v;});
  const investito=Object.values(tieni).reduce((a,b)=>a+b,0);
  let dist=Math.abs((T-investito)/(T||1)-peso("CASH"));
  new Set([...comp.map(c=>c.k),...Object.keys(tieni)]).forEach(k=>{if(k!="CASH")dist+=Math.abs((tieni[k]||0)/(T||1)-peso(k));});
  // v7.17 PRIMA L'ACQUISTO (deciso con Ya): il conto si riallinea comprando, non vendendo.
  //  1. sovrappeso nel modello: non si vende mai, si diluisce con gli acquisti dei mesi dopo
  //  2. fuori dal modello: si vende SOLO se e' in perdita o in pari (la perdita va nello zainetto e compensa guadagni futuri);
  //     se e' in guadagno si tiene (venderla costerebbe il 26%); senza costo inserito si tiene e si chiede il costo
  //  3. soldi da investire = liquidita' + versamento + vendite in perdita - liquidita' che il modello vuole tenere
  //  4. vanno ai mercati sotto il loro peso, in proporzione a quanto manca, a quote intere (acquisto diretto)
  const V=+mioConto.vers||0,Tt=T+V,ord=[],min=T*SOGLIA_ORD,TASSA=0.26;
  let venduto=0;
  const fuori=[];
  const gruppi={};pos.forEach(r=>(gruppi[r.mk]=gruppi[r.mk]||[]).push(r));
  Object.entries(gruppi).forEach(([mk,rr])=>{if(!peso(mk))rr.forEach(r=>{if(r.pr)fuori.push({nome:r.nome,v:r.v,g:r.pm>0?r.q*(r.pr-r.pm):null,q:r.q});});});
  altri.forEach(a=>{if(!a.dentro)fuori.push({nome:a.n||"Titolo",v:a.v,g:a.c>0?a.v-a.c:null});});
  fuori.forEach(f=>{
   if(f.g!=null&&f.g<1){ord.push({t:"v",tutto:true,nome:f.nome,v:f.v,perdita:Math.max(0,-f.g)});venduto+=f.v;}
   else ord.push({t:"t",nome:f.nome,v:f.v,tasse:f.g!=null?f.g*TASSA:null});});
  const D=liq+V+venduto-Tt*peso("CASH");
  if(D>=1){const mancano=[];
   comp.forEach(c=>{if(c.k=="CASH")return;const gap=Tt*c.peso/100-(tieni[c.k]||0);if(gap<min)return;
    if(c.k=="AZ"){mancano.push({c,gap,az:true});return;}
    const u=strumentoAcq(c,T),pr=u&&prezzoLive(u.lk,u.prezzo);if(pr)mancano.push({c,gap,u,pr});});
   const tot=mancano.reduce((a,x)=>a+x.gap,0);
   mancano.forEach(m=>{m.obi=tot>D?D*m.gap/tot:m.gap;m.q=m.az?0:Math.floor(m.obi/(m.pr*MARG));m.spesa=m.az?m.obi:m.q*m.pr*MARG;});
   let resto=D-mancano.reduce((a,m)=>a+m.spesa,0);
   // secondo giro: con il resto una quota in piu' dove manca di piu' (se ne manca almeno mezza)
   mancano.filter(m=>!m.az).sort((a,b)=>(b.gap-b.spesa)-(a.gap-a.spesa)).forEach(m=>{
    if(m.pr*MARG<=resto&&m.gap-m.spesa>=m.pr*0.5){m.q++;m.spesa+=m.pr*MARG;resto-=m.pr*MARG;}});
   mancano.forEach(m=>{if(m.az){if(m.obi>=1)ord.push({t:"c",az:true,nome:"Azioni del modello",v:m.obi});}
    else if(m.q>0)ord.push({t:"c",q:m.q,nome:m.u.nome,isin:m.u.isin,v:m.q*m.pr});});
   if(resto>=1)ord.push({t:"r",nome:"Resta sul conto",v:resto});}
  return {T,cst,gain,dist:dist/2*100,ord,haAZ,vAltri,comp,V,D};}
 function contoForm(){const S=Object.entries(P.strumenti||{});
  const opz=k=>S.map(([kk,x])=>`<option value="${kk}"${kk==k?" selected":""}>${esc(x.nome)}</option>`).join("");
  const val=v=>v?String(v).replace(".",","):"";
  const riga=r=>`<div class="pconto-fr" data-r><select aria-label="Strumento">${opz(r.k)}</select>
    <input inputmode="decimal" placeholder="quote" value="${val(r.q)}" aria-label="Quote"><input inputmode="decimal" placeholder="prezzo di carico €" value="${val(r.pm)}" aria-label="Prezzo medio di carico"><button type="button" class="pconto-x" aria-label="Togli la riga">&times;</button></div>`;
  const altro=a=>`<div class="pconto-fr" data-a><input placeholder="nome (es. eBay)" value="${esc(a.n||"")}" aria-label="Nome del titolo">
    <input inputmode="decimal" placeholder="valore oggi €" value="${val(a.v)}" aria-label="Valore oggi in euro"><input inputmode="decimal" placeholder="costo €" value="${val(a.c)}" aria-label="Costo in euro"><button type="button" class="pconto-x" aria-label="Togli la riga">&times;</button></div>`;
  return `<div class="pconto-f"><span class="pconto-lab">ETF ed ETC del modello</span><div class="pconto-fr pconto-h"><span>Strumento</span><span>Quote</span><span>Prezzo di carico &euro;</span></div><div class="pconto-g" data-g="r">${(mioConto.righe.length?mioConto.righe:[{}]).map(riga).join("")}</div>
   <button type="button" class="pconto-add" data-add="r">+ Aggiungi strumento</button>
   <span class="pconto-lab">Altri titoli</span><div class="pconto-fr pconto-h"><span>Nome</span><span>Valore oggi &euro;</span><span>Costo &euro;</span></div><div class="pconto-g" data-g="a">${mioConto.altri.map(altro).join("")}</div>
   <button type="button" class="pconto-add" data-add="a">+ Aggiungi titolo</button>
   <label class="pcap pconto-liq">Liquidit&agrave; sul conto <input inputmode="decimal" value="${val(mioConto.liq)}" aria-label="Liquidità sul conto in euro"> &euro;</label>
   <label class="pcap pconto-liq pconto-vers">Versamento (facoltativo) <input inputmode="decimal" value="${val(mioConto.vers)}" aria-label="Versamento in euro"> &euro;</label>
   <div class="pconto-b"><button type="button" class="pconto-ok">Salva</button><button type="button" class="pconto-no">Annulla</button></div>
   <template data-t="r">${riga({})}</template><template data-t="a">${altro({})}</template></div>`;}
 function contoHTML(p){const vuoto=!mioConto.righe.length&&!mioConto.altri.length&&!(+mioConto.liq);
  const testa=`<div class="pconto-t"><h3>Il mio conto <span class="pbprof">${esc(p.nome)}</span></h3>
   <details class="info"><summary title="Come funziona" aria-label="Come funziona">i</summary><div>Inserisci le quote che hai sul conto: restano <b>solo in questo browser</b>, non vengono inviate a nessuno. Il conto si confronta con il profilo scelto (con meno di ${eur((P.compatto||{}).sotto||10000)} la versione compatta).<br><br><b>Risultato</b>: guadagno o perdita sulle righe con il prezzo di carico. <b>Distanza dal modello</b>: quanta parte del conto &egrave; in posti diversi dal modello (0% = identico).<br><br><b>Prima l'acquisto</b>: il conto si riallinea comprando. La liquidit&agrave; (e l'eventuale versamento) va ai mercati <b>sotto il loro peso</b>, a quote intere; quello in sovrappeso non si vende. Un titolo <b>fuori dal modello</b> si vende solo se &egrave; in perdita (la perdita va nello zainetto e riduce le tasse future); se &egrave; in guadagno si tiene, perch&eacute; venderlo costerebbe il 26%.<br><br>Scarti sotto il 2% del conto si lasciano. Vanguard S&amp;P 500 e iShares S&amp;P 500 contano come lo stesso mercato. Prezzi indicativi: controllali sul broker.</div></details>
   ${!vuoto&&!contoEdit?`<button type="button" class="pconto-mod">Modifica</button>`:""}</div>`;
  if(contoEdit)return testa+contoForm();
  if(vuoto)return testa+`<p class="small pconto-v">Inserisci le quote che hai sul conto: vedi quanto sei lontano dal modello e cosa comprare o vendere.</p><button type="button" class="pconto-ins">Inserisci le quote</button>`;
  const c=contoCalc(p),perc=c.cst?c.gain/c.cst*100:null;
  return testa+`<div class="pmc-k pconto-k"><div><small>Valore del conto</small><b>${eur(c.T)}</b></div>
    <div><small>Risultato</small><b class="${c.gain>=0?"up":"down"}">${c.cst?(c.gain>=0?"+":"&minus;")+eur(Math.abs(c.gain))+` <em>${pc(perc)}</em>`:"n/d"}</b></div>
    <div><small>Distanza dal modello</small><b class="${c.dist<=5?"up":c.dist<=15?"":"down"}">${fx(c.dist,0)}%</b></div></div>
   <span class="pconto-lab">${c.ord.some(o=>o.t=="c"||o.t=="v")?"Ordini &middot; prima l'acquisto":"Nessun ordine da fare"}</span>
   ${c.ord.length?`<div class="pconto-o">${c.ord.sort((a,b)=>"vctr".indexOf(a.t)-"vctr".indexOf(b.t)).map(o=>{
    const cl={v:"ven",c:"com",t:"tie",r:""}[o.t],et={v:"Vendi",c:"Compra",t:"Tieni",r:"Conto"}[o.t];
    const nota=o.t=="v"?(o.perdita>=1?`fuori dal modello &middot; in perdita: ${eur(o.perdita)} nello zainetto`:"fuori dal modello &middot; in pari: nessuna tassa")
     :o.t=="t"?(o.tasse==null?"fuori dal modello &middot; inserisci il costo per decidere":`fuori dal modello &middot; in guadagno: venderla costerebbe &asymp; ${eur(o.tasse)} di tasse`)
     :o.t=="r"?"avanzo: non basta per 1 quota":o.az?"scegli i titoli nell'acquisto diretto":(o.isin?"ISIN "+esc(o.isin):"");
    const qt=o.t=="v"?"tutto":o.t=="c"&&!o.az?o.q+(o.q==1?" quota":" quote"):"";
    return `<div class="pconto-or ${cl}"><span class="pconto-ot">${et}</span><span class="pconto-on"><b>${esc(o.nome)}</b><small>${nota}</small></span>
     <span class="pconto-oq">${qt?`<b>${qt}</b><small>&asymp; ${eur(o.v)}</small>`:`<b>${eur(o.v)}</b>`}</span></div>`;}).join("")}</div>`:""}
`;}
 function contoEventi(p){const box=el.querySelector("#pconto");if(!box)return;
  const ridis=()=>{box.innerHTML=contoHTML(p);contoEventi(p);};
  const b=sel=>box.querySelector(sel);
  if(b(".pconto-ins"))b(".pconto-ins").onclick=()=>{contoEdit=true;ridis();};
  if(b(".pconto-mod"))b(".pconto-mod").onclick=()=>{contoEdit=true;ridis();};
  if(!contoEdit)return;
  box.querySelectorAll("[data-add]").forEach(x=>x.onclick=()=>{const t=b(`template[data-t="${x.dataset.add}"]`),g=b(`[data-g="${x.dataset.add}"]`);
   g.appendChild(t.content.firstElementChild.cloneNode(true));lega();});
  const lega=()=>box.querySelectorAll(".pconto-x").forEach(x=>x.onclick=()=>x.parentElement.remove());lega();
  b(".pconto-no").onclick=()=>{contoEdit=false;ridis();};
  b(".pconto-ok").onclick=()=>{
   mioConto.righe=[...box.querySelectorAll('[data-g="r"] [data-r]')].map(r=>{const i=r.querySelectorAll("input");return {k:r.querySelector("select").value,q:num(i[0].value),pm:num(i[1].value)};}).filter(r=>r.q>0);
   mioConto.altri=[...box.querySelectorAll('[data-g="a"] [data-a]')].map(r=>{const i=r.querySelectorAll("input");return {n:i[0].value.trim().slice(0,40),v:num(i[1].value),c:num(i[2].value)};}).filter(a=>a.v>0);
   mioConto.liq=num(b(".pconto-liq input").value);mioConto.vers=num(b(".pconto-vers input").value);salvaConto();contoEdit=false;ridis();};}

 // v7.38 riga di una rotazione: data | gruppi (Entrati / Usciti / Restano, etichetta a parole in colonna fissa) | liquidita'
 //   sotto: risultato del mese (chiuso) o provvisorio (mese in corso, solo la prima riga)
 function rotazioni(p){const ch=k=>`<span class="pchip" title="${esc(nomeK(k))}">${esc(nomeK(k))}</span>`;
  const gr=(cls,et,v)=>v.length?`<div class="pgr ${cls}"><span class="pgl">${et}</span><div class="pgc">${v.map(ch).join("")}</div></div>`:"";
  const perMese={};(p.mesi_chiusi||[]).forEach(m=>perMese[m.mese]=m);
  return `<div class="prot${tutteRot?" aperta":""}">${p.rotazioni.map((r,i)=>`<div class="protr${i>=3?" pextra":""}"><b>${gg(r.data)}</b><div class="pgrs">
   ${gr("pin","Entrati",r.entrati)}${gr("pout","Usciti",r.usciti)}${gr("pten","Restano",r.tenuti)}${!r.entrati.length&&!r.usciti.length&&!r.tenuti.length?'<div class="small">tutto in liquidit&agrave;</div>':""}</div>
   <span class="pliq${r.liquidita?"":" zero"}" title="Quota tenuta in liquidit&agrave; in questa rotazione">liquidit&agrave; ${r.liquidita||0}%</span>${r.attesa?`<div class="prisul small"><span class="pmc-b">si esegue all'apertura del ${gg(r.data)}</span></div>`:dettMese(perMese[r.data.slice(0,7)],i==0?p.corrente:null,fonteMese(r.data.slice(0,7),p.id))}</div>`).join("")}
   ${p.rotazioni.length>3?`<button class="ptutte">${tutteRot?"Mostra meno":`Mostra tutte (${p.rotazioni.length})`}</button>`:""}</div>`;}

 // --- CONFRONTO DEI 3 PROFILI mese per mese (v6.56): stessi mesi chiusi delle rotazioni, i tre profili affiancati,
 //     con rischio (volatilita' annua e drawdown sul periodo), mesi negativi, peggior mese, correlazione e la spiegazione
 //     automatica di ogni mese negativo (il mercato che ha pesato di piu'). Interruttore: profilo in evidenza.
 let cfrSel=null;
 // --- v7.51 RISCHIO E COSTI A CONFRONTO: i 3 profili affiancati sullo storico intero (euro, acquisto prudente).
 //     Dati: p.stat.totale (rendimento, drawdown, recupero, Calmar) e p.rischio_ext (Sortino, peggiori 12 mesi,
 //     asimmetria, capitale scambiato e costo annuo: cot_radar/portafogli.py, rischio_esteso). In verde il migliore
 //     di ogni riga. Spiegazioni nel fumetto (i), testi brevi in pagina.
 function rischioCfr(){const PR=P.profili;if(!PR.some(x=>x.rischio_ext))return "";
  // v7.56 colonna di riferimento "S&P 500" (tutto in azioni USA, comprato e tenuto): non partecipa al "migliore"
  const SP=P.sp500&&P.sp500.rischio_ext?P.sp500:null;
  const evid=cfrSel||sel,T=x=>x.stat.totale||{},E=x=>x.rischio_ext||{};
  // righe: [etichetta, valore numerico, testo, "alto"/"basso" = quale e' migliore, nota breve]
  const R=[["Rendimento annuo",x=>T(x).cagr,x=>pc(T(x).cagr),"alto","media dal "+(T(PR[0]).dal||"").slice(0,4)],
   ["Max drawdown",x=>T(x).maxdd,x=>pc(T(x).maxdd),"alto","dal picco al minimo"],
   ["Mesi per recuperare",x=>T(x).recupero_mesi,x=>T(x).recupero_mesi??"in corso","basso","dal drawdown peggiore"],
   ["Peggiori 12 mesi",x=>E(x).peggiori12&&E(x).peggiori12[0],x=>E(x).peggiori12?`<span title="da fine ${E(x).peggiori12[1]} a fine ${E(x).peggiori12[2]}">${pc(E(x).peggiori12[0])}</span><small class="prper">${E(x).peggiori12[2].slice(0,4)}</small>`:"n/d","alto","anno peggiore, in qualsiasi mese"],
   ["Drawdown in 1 anno su 10",x=>E(x).dd_1su10,x=>E(x).dd_1su10!=null?pc(E(x).dd_1su10):"n/d","alto","nei 12 mesi, anno brutto"],
   ["Media dei mesi peggiori",x=>E(x).cvar_mese,x=>E(x).cvar_mese!=null?pc(E(x).cvar_mese):"n/d","alto","il 5% dei mesi peggiori"],
   ["Sortino",x=>E(x).sortino,x=>E(x).sortino!=null?fx(E(x).sortino,2):"n/d","alto","oltre la liquidit&agrave; / ribassi"],
   ["Calmar",x=>T(x).calmar,x=>T(x).calmar!=null?fx(T(x).calmar,2):"n/d","alto","rendimento / drawdown"],
   // v7.58 riga "Asimmetria" tolta: il +1,33 dell'Aggressivo veniva da 2 mesi di Bitcoin (studio 12/11/2026), ingannava
   ["Capitale scambiato l'anno",x=>E(x).scambiato_anno,x=>E(x).scambiato_anno!=null?E(x).scambiato_anno+"%":"n/d","basso","somma delle rotazioni"],
   ["Costo annuo stimato",x=>E(x).costo_anno,x=>E(x).costo_anno!=null?(E(x).costo_anno?"&minus;"+fx(E(x).costo_anno,2)+"%":"0%"):"n/d","basso","0,10% sullo scambiato"]];
  const riga=([nome,val,txt,meglio,nota])=>{const v=PR.map(val),ok=v.filter(z=>z!=null),
    top=ok.length>1?(meglio=="alto"?Math.max(...ok):Math.min(...ok)):null;
   return `<tr><td>${nome}</td>${PR.map((x,i)=>`<td class="num${x.id==evid?" ev":""}${v[i]!=null&&v[i]===top?" prbest":""}">${txt(x)}</td>`).join("")}${SP?`<td class="num prsp">${txt(SP)}</td>`:""}<td class="pcfw small">${nota}</td></tr>`;};
  return `<div class="card pcfr prcfr">
   <div class="tablewrap"><table class="compatta pcft"><tr><th>Misura</th>${PR.map(x=>`<th class="num${x.id==evid?" ev":""}"><span class="pcl">${x.nome}</span><span class="pcs">${x.nome.slice(0,4)}.</span></th>`).join("")}${SP?`<th class="num prsp" title="Tutto in S&amp;P 500, comprato una volta e tenuto"><span class="pcl">S&amp;P 500</span><span class="pcs">S&amp;P</span></th>`:""}<th class="pcfw"></th></tr>
    ${R.map(riga).join("")}</table></div>
   <p class="small pcfnota">In verde il migliore dei 3 profili.${SP?" S&amp;P 500 = tutto in azioni USA, comprato e tenuto: il riferimento da battere.":""} Storico in euro dal ${esc((T(PR[0]).dal||"").slice(0,4))}, acquisto prudente, costi inclusi.</p></div>`;}
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
  return `<details class="info phi"><summary title="Il profilo" aria-label="Il profilo">i</summary><div>${esc(p.descr)}<br><br><b>Come si misura.</b> Numeri in euro senza copertura del cambio, liquidit&agrave; al tasso BCE, acquisto alla chiusura del giorno di rotazione, costi 0,10% inclusi.${t.oltre_liq!=null?` Oltre la liquidit&agrave;: <b>${pc(t.oltre_liq)}</b> l'anno.`:""}${t.recupero_mesi!=null?` Recupero dal drawdown peggiore: <b>${t.recupero_mesi} mesi</b>.`:""}${usd?` In dollari: ${pc(usd.cagr)} l'anno.`:""}${p.senza_btc&&p.senza_btc.cagr!=null?`<br><br><b>Peso del Bitcoin.</b> Il ${fx(p.senza_btc.quota,1)}% in Bitcoin conta molto: senza (quota in liquidit&agrave;) il rendimento storico sarebbe <b>${pc(p.senza_btc.cagr)}</b> l'anno, con max drawdown ${pc(p.senza_btc.maxdd)}.`:""}</div></details>`;}
 function hero(p){const t=p.stat.totale||{},rk=RISK[p.id]||["",""];
  const cl={};p.composizione.forEach(c=>{cl[c.classe]=(cl[c.classe]||0)+c.peso;});
  // v7.41 QUOTA DI RISCHIO per classe (p.rischio_quote dal backend: quanto rischio porta ogni mercato, somma 100).
  //   Accanto al peso: "rischio X%" e una barra sottile sotto quella del peso. Senza dati la riga resta com'era.
  const RQ=p.rischio_quote,rk_cl={};if(RQ&&RQ.quote)p.composizione.forEach(c=>{rk_cl[c.classe]=(rk_cl[c.classe]||0)+(RQ.quote[c.k]||0);});
  const azR=RQ?Math.round((rk_cl["azioni"]||0)+(rk_cl["azioni singole"]||0)):null,azP=Math.round((cl["azioni"]||0)+(cl["azioni singole"]||0));
  const rkTag=k=>{if(!RQ)return "";const v=Math.round(rk_cl[k]||0);return `<em class="phrk${v>=cl[k]+5?" su":""}" title="Quota del rischio del portafoglio portata da questa classe">rischio ${v}%</em>`;};
  const rkBar=k=>RQ?`<u><s style="width:${Math.max(0,Math.min(100,rk_cl[k]||0))}%"></s></u>`:"";
  // v7.57 TRE NUMERI DI RISCHIO al posto della frase: volatilita', mese difficile (1 su 20, in % e in euro sul
  //   capitale scritto dall'utente), rischio dal cambio. Spiegazioni solo nel fumetto (i). Dati: p.rischio_quote.
  const mEur=RQ&&RQ.mese95!=null?eur(Math.round(capitale*RQ.mese95/100)):null;
  const rkNota=RQ?`<div class="phrk3"><div><em>Volatilit&agrave;</em><b>${fx(RQ.vol,1)}%</b><span>l'anno</span></div>
    ${RQ.mese95!=null?`<div><em>Mese difficile</em><b class="${RQ.mese95<0?"down":""}">${pc(RQ.mese95)}</b><span>${mEur} &middot; 1 mese su 20</span></div>`:""}
    ${RQ.cambio!=null?`<div><em>Rischio dal cambio</em><b>${RQ.cambio}%</b><span>euro / dollaro</span></div>`:""}
    <details class="info"><summary title="Come leggere" aria-label="Come leggere">i</summary><div><b>Volatilit&agrave;</b>: quanto oscilla il portafoglio in un anno; le azioni pesano il ${azP}% e portano il ${azR}% del rischio.${RQ.mese95!=null?`<br><br><b>Mese difficile</b>: con la composizione di oggi, circa 1 mese su 20 chiude peggio di ${pc(RQ.mese95)} (${mEur} su ${eur(capitale)}). Calcolo sui 3 anni passati, in euro: nelle prove dal 2006 &egrave; stato superato nel 3&ndash;9% dei mesi. Non &egrave; la perdita massima.`:""}${RQ.cambio!=null?`<br><br><b>Rischio dal cambio</b>: quanta parte delle oscillazioni viene dal dollaro e non dai mercati (ultimi ${RQ.giorni} giorni).${RQ.cambio_media!=null?` Media storica del profilo: ${RQ.cambio_media}%.`:""} Sotto zero = il dollaro ha attenuato le oscillazioni.`:""}</div></details></div>`:"";
  const te=p.stat_eur&&p.stat_eur.totale,finale=te&&te.totale!=null?10000*(1+te.totale/100):t.totale!=null?10000*(1+t.totale/100):null   /* v6.57: 10.000 EURO -> si usa la curva in euro */,anno=(t.dal||"").slice(0,4);
  return `<div class="card phero"><div class="phtesta"><h3>${esc(p.nome)}${infoProfilo(p,t)}</h3><div class="phazioni"><span class="prisk ${rk[1]}">Rischio ${rk[0].toLowerCase()}</span>${window.ebPdf?ebPdf.bottone():""}</div></div>
   <div class="phnum"><div><em>Rendimento annuo</em><b class="up">${pc(t.cagr)}</b><span>media dal ${anno}</span></div>
    <div><em>Max drawdown</em><b class="down">${pc(t.maxdd)}</b><span>dal picco al minimo</span></div>
    <div><em>10.000 € nel ${anno}</em><b>${eur(finale)}</b><span>valore di oggi${p.stat_eur&&p.stat_eur.totale?" (in euro)":""}</span></div>
    <div><em>Mesi positivi</em><b>${t.mesi_pos??"n/d"}%</b><span>su tutti i mesi</span></div></div>
   <div class="phcomp"><h4>Composizione del mese <details class="info"><summary title="Come funziona" aria-label="Come funziona">i</summary><div><b>Ogni primo giorno di borsa del mese</b> si controlla il trend: un mercato azionario sotto la media a 200 giorni va in pausa nella liquidit&agrave;. Treasury e oro restano sempre come difesa. Si scambia solo se un mercato entra o esce, e a inizio trimestre per riportare i pesi. Durante il mese non si tocca nulla. Dettagli nella <b>Guida</b>.${RQ?`<br><br><b>Rischio</b>: quanta parte delle oscillazioni del portafoglio viene da ogni classe (barra sottile). Un mercato molto volatile porta pi&ugrave; rischio del suo peso; la liquidit&agrave; non ne porta. Calcolo sugli ultimi ${RQ.giorni} giorni di borsa, in euro: peso &times; covarianza con il portafoglio. La somma fa 100. Le 5 azioni singole sono contate come l'S&amp;P 500: il rischio vero di 5 titoli &egrave; pi&ugrave; alto.`:""}</div></details>${RQ?`<span class="phleg"><i class="lp"></i>peso<i class="lr"></i>rischio</span>`:""}</h4>${CLN.filter(x=>cl[x[0]]).map(x=>`<div class="phbar${RQ?" rk":""}"><span>${x[1]}</span>${rkTag(x[0])}<b>${fx(cl[x[0]],1)}%</b><i><s style="width:${Math.min(100,cl[x[0]])}%;--cb:${CL[x[0]]}"></s></i>${rkBar(x[0])}</div>`).join("")}${rkNota}</div>
   ${/* v7.35 tolto il riquadro "Le 5 azioni del mese": doppione (i titoli sono gia' nelle righe del portafoglio e in
       Acquisto diretto, con quote e importi) e rumore nella card principale */""}
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
   y=d.serve(y,80,T);y=E.sezione(d,y+28,"Ultime rotazioni","+ entrati · − usciti · = restano");
   p.rotazioni.slice(0,6).forEach(r=>{const L=[];
    if(r.entrati.length)L.push(["+ "+r.entrati.map(nomeK).join(", "),C.up]);if(r.usciti.length)L.push(["− "+r.usciti.map(nomeK).join(", "),C.down]);
    if(r.tenuti.length)L.push(["= "+r.tenuti.map(nomeK).join(", "),C.ink]);if(!L.length)L.push(["tutto in liquidità",C.mute]);
    const mm=perMese[r.data.slice(0,7)],ris=r.attesa?`si esegue all'apertura del ${gg(r.data)}`:mm?`${fonteMese(r.data.slice(0,7),p.id)?"Live":"Simulato"} · risultato ${pc((fonteMese(r.data.slice(0,7),p.id)||mm).r)} · drawdown ${pc((fonteMese(r.data.slice(0,7),p.id)||mm).dd)}`:(p.corrente&&!p.corrente.attesa&&p.corrente.r!=null&&r===p.rotazioni[0])?`Provvisorio ${pc(p.corrente.r)} · drawdown ${pc(p.corrente.dd)}`:"mese in corso";
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

 // --- v7.33 TEST DEL PROFILO (onboarding, 3 domande). Ogni domanda decide qualcosa con i DATI del modello, niente
 //     punteggi a sensazione:
 //   D1 CAPITALE   -> versione compatta sotto P.compatto.sotto e importi in euro delle domande dopo;
 //   D2 ORIZZONTE  -> finestre storiche del simulatore (p.sim.leve["1.0"][anni]): un profilo e' compatibile se in
 //                    quella durata e' finito in perdita in non piu' del 5% dei periodi (meno di 2 anni = finestra di 1);
 //   D3 PERDITA    -> drawdown massimo storico di ogni profilo IN EURO sul capitale scritto: compatibili i profili
 //                    con un drawdown non piu' ampio di quello accettato.
 //   Profilo finale = il PIU' PRUDENTE tra i due limiti (regola MiFID). "Non accetto perdite" = solo liquidita'.
 //   Esito salvato SOLO in questo browser (localStorage "ebTest"). DEBUG: F12 -> Console -> localStorage.ebTest
 const ORZ=[[1,"Meno di 2 anni","soldi che potrebbero servirti presto"],[3,"Da 2 a 5 anni","un obiettivo a medio termine"],[5,"Oltre 5 anni","risparmio di lungo periodo"]];
 let test={passo:0};try{const t=JSON.parse(localStorage.getItem("ebTest")||"null");if(t)test=Object.assign({passo:t.esito?4:0},t);}catch(e){}
 const salvaTest=()=>{try{localStorage.setItem("ebTest",JSON.stringify(test));}catch(e){}};
 const statT=(p,cap)=>{const c=compatto(cap)&&p.compatto&&p.compatto.stat&&p.compatto.stat.totale;return c||((p.stat_eur||{}).totale)||p.stat.totale;};
 const simT=(p,anni)=>(((p.sim||{}).leve||{})["1.0"]||{})[String(anni)]||null;
 function esitoTest(){const prof=P.profili,cap=test.cap;
  if(test.tol<0)return {liq:true};
  // limite dell'orizzonte: il profilo piu' rischioso con perdita <= 5% dei periodi in quella durata
  let lo=-1;prof.forEach((p,i)=>{const s=simT(p,test.anni);if(s&&s.perdita!=null&&s.perdita<=5)lo=i;});
  const i=Math.min(lo<0?0:lo,test.tol);
  return {p:prof[i],breve:lo<0,limite:lo<0||lo<test.tol?"orizzonte":test.tol<prof.length-1?"perdita":null};}
 function testHTML(){const prof=P.profili,cap=test.cap||capitale,nP=3;
  const info=`<details class="info"><summary title="Come funziona" aria-label="Come funziona">i</summary><div>Tre domande, ognuna legata ai dati del modello: il <b>capitale</b> sceglie la versione (compatta sotto ${eur((P.compatto||{}).sotto||10000)}) e gli importi in euro; l'<b>orizzonte</b> si confronta con tutte le finestre storiche dal 2006 (un profilo &egrave; adatto se in quella durata ha chiuso in perdita al massimo nel 5% dei casi); la <b>perdita accettata</b> con il drawdown massimo storico di ogni profilo. Vale il limite pi&ugrave; prudente.<br><br>Prima di investire tieni da parte un fondo per le emergenze (di solito 3-6 mesi di spese). Il test non conosce la tua situazione completa (debiti, entrate, altri investimenti): &egrave; un aiuto alla scelta, non una consulenza personalizzata. I risultati passati non garantiscono quelli futuri: un drawdown pu&ograve; essere pi&ugrave; ampio di quello storico.</div></details>`;
  const dots=`<div class="ptest-dots" aria-hidden="true">${[1,2,3].map(n=>`<i class="${Math.max(1,test.passo)>=n?"on":""}"></i>`).join("")}</div>`;
  const testa=(t)=>`<div class="ptest-t"><span class="ptest-k" id="ptest-tit">Trova il tuo profilo</span>${test.passo<=nP?`<span class="ptest-n">${Math.max(1,test.passo)} di ${nP}</span>`:""}${info}<button type="button" class="ptest-x" data-t="chiudi" aria-label="Chiudi">&times;</button></div>${test.passo<=nP?dots:""}<h3>${t}</h3>`;
  const piede=`<div class="ptest-b">${test.passo>1&&test.passo<=nP?`<button type="button" class="ptest-ind" data-t="ind">&larr; Indietro</button>`:"<span></span>"}<button type="button" class="ptest-salta" data-t="chiudi">${test.passo>nP?"Chiudi":"Esci"}</button></div>`;
  if(test.passo<=1){const ch=[2000,5000,10000,25000];
   return `<div class="ptest">${testa("Quanto vuoi investire?")}<div class="ptest-o c4">${ch.map(v=>`<button type="button" data-cap="${v}" class="${cap==v?"on":""}">${eur(v)}</button>`).join("")}</div>
    <label class="ptest-lib">Altro importo <input type="text" inputmode="numeric" value="${ch.includes(cap)?"":mil(cap)}" placeholder="es. 7.500" aria-label="Altro importo in euro"> &euro;<button type="button" class="ptest-ok" data-t="cap">Avanti</button></label>${piede}</div>`;}
  if(test.passo==2)
   return `<div class="ptest">${testa("Fra quanto tempo potrebbero servirti questi soldi?")}<div class="ptest-o">${ORZ.map(o=>`<button type="button" data-anni="${o[0]}" class="${test.anni==o[0]?"on":""}"><b>${o[1]}</b><small>${o[2]}</small></button>`).join("")}</div>${piede}</div>`;
  if(test.passo==3){
   return `<div class="ptest">${testa(`Il tuo conto da ${eur(cap)} scende in poche settimane. Fino a quale perdita resti investito senza vendere?`)}
    <div class="ptest-o">${prof.map((p,i)=>{const dd=statT(p,cap).maxdd;return `<button type="button" data-tol="${i}" class="${test.tol==i?"on":""}"><b>&minus;${eur(Math.abs(dd)/100*cap).replace(" €","")} &euro;</b><small>&minus;${fx(Math.abs(dd),1)}%: il drawdown peggiore del profilo ${esc(p.nome)}</small></button>`;}).join("")}
     <button type="button" data-tol="-1" class="${test.tol==-1?"on":""}"><b>Nessuna perdita</b><small>non accetto che il conto scenda</small></button></div>${piede}</div>`;}
  // RISULTATO
  const r=esitoTest();
  if(r.liq)return `<div class="ptest esito">${testa("Per te: liquidit&agrave;, non un portafoglio")}<p class="ptest-p">Tutti i portafogli hanno avuto periodi in perdita. Se non accetti che il conto scenda, tieni i soldi sul conto o in un ETF monetario come <b>XEON</b> (rende circa il tasso BCE, oscillazioni minime).</p>${piede}</div>`;
  const p=r.p,st=statT(p,cap),sm=simT(p,test.anni),orz=ORZ.find(o=>o[0]==test.anni);
  const motivo=r.breve?`Con un orizzonte sotto i 2 anni ogni profilo ha chiuso in perdita in circa 1 anno su 8: per i soldi che ti servono a breve &egrave; pi&ugrave; adatta la liquidit&agrave; (XEON).`
   :r.limite=="orizzonte"?`Deciso dall'<b>orizzonte</b>: con ${orz[1].toLowerCase()} i profili pi&ugrave; rischiosi hanno chiuso in perdita troppo spesso.`
   :r.limite=="perdita"?`Deciso dalla <b>perdita che accetti</b>: i profili pi&ugrave; rischiosi hanno avuto drawdown pi&ugrave; ampi.`:`Compatibile sia con il tuo orizzonte sia con la perdita che accetti.`;
  return `<div class="ptest esito">${testa(`Il profilo adatto a te: <span class="ptest-pr">${esc(p.nome)}</span>`)}
   <div class="ptest-r">
    <div><small>Drawdown peggiore</small><b class="down">&minus;${fx(Math.abs(st.maxdd),1)}%</b><span>&minus;${eur(Math.abs(st.maxdd)/100*cap)} su ${eur(cap)}${st.recupero_mesi?` &middot; recuperato in ${st.recupero_mesi} mesi`:""}</span></div>
    ${sm?`<div><small>Dopo ${test.anni==1?"1 anno":test.anni+" anni"}</small><b>${eur(sm.p5*cap)}</b><span>nel 5% dei casi peggiori &middot; in perdita nel ${fx(sm.perdita,0)}% dei periodi</span></div>`:""}
    <div><small>Rendimento medio annuo</small><b class="up">${pc(st.cagr)}</b><span>dal ${String(st.dal||"").slice(0,4)}, costi inclusi</span></div></div>
   <p class="ptest-p">${motivo}${compatto(cap)?` Con ${eur(cap)} si usa la <b>versione compatta</b>.`:""}</p>${avvisoCap(p,cap)}
   <p class="ptest-edu">Esempio didattico del modello, uguale per tutti: non &egrave; una consulenza personalizzata. Puoi perdere il capitale anche senza leva.</p>
   <div class="ptest-b"><button type="button" class="ptest-ind" data-t="rifai">Rifai il test</button><button type="button" class="ptest-usa" data-t="usa">Usa questo profilo</button></div></div>`;}
 // avviso se con quel capitale, a quote intere e ai prezzi di oggi, il conto si allontana troppo dal modello
 function avvisoCap(p,cap){const sc=piano(p,cap).scost;if(sc<=SCOST_OK)return "";
  const min=minimoCap(p),alt=P.profili.slice(0,P.profili.indexOf(p)).reverse().find(x=>piano(x,cap).scost<=SCOST_OK);
  return `<p class="ptest-avv"><b>Attenzione al capitale.</b> Con ${eur(cap)}, a quote intere e ai prezzi di oggi, il conto si discosta dal modello del <b>${fx(sc,1)}%</b>: alcune quote costano pi&ugrave; del loro peso e restano sul conto.${min?` Per replicarlo bene servono almeno <b>${eur(min)}</b>.`:""}${alt?` Con questo capitale si replica bene il profilo <b>${esc(alt.nome)}</b>.`:""}</p>`;}
 // --- v7.36 POPUP DEL TEST: si apre dal bottone nella barra in alto ("Trova il tuo profilo" / "Rifai il test"),
 //     l'utente vede solo il questionario; con "Usa questo profilo" si chiude, si sceglie il profilo e la pagina scorre
 //     alla sua card (che si illumina un attimo). Esc, clic fuori o X chiudono. La pagina sotto non scorre.
 let modale=null;
 function apriTest(nuovo){if(nuovo||!test.passo||test.passo>4||test.passo<1)test={passo:1,cap:test.cap||capitale};salvaTest();
  chiudiTest();modale=document.createElement("div");modale.className="ptmod";
  modale.innerHTML=`<div class="ptmod-box" role="dialog" aria-modal="true" aria-labelledby="ptest-tit"><div id="ptestbox">${testHTML()}</div></div>`;
  document.body.appendChild(modale);document.documentElement.classList.add("ptmod-on");
  requestAnimationFrame(()=>modale.classList.add("on"));
  modale.addEventListener("mousedown",e=>{if(e.target===modale)chiudiTest();});
  testEventi();const f=modale.querySelector(".ptest-o button,.ptest-usa");if(f)f.focus({preventScroll:true});}
 function chiudiTest(){if(!modale)return;const m=modale;modale=null;m.classList.remove("on");
  document.documentElement.classList.remove("ptmod-on");setTimeout(()=>m.remove(),220);}
 document.addEventListener("keydown",e=>{if(e.key=="Escape"&&modale)chiudiTest();});
 function testEventi(){const box=modale&&modale.querySelector("#ptestbox");if(!box)return;
  const vai=n=>{test.passo=n;salvaTest();box.innerHTML=testHTML();testEventi();box.scrollTop=0;
   const f=box.querySelector(".ptest-o button,.ptest-usa");if(f)f.focus({preventScroll:true});};
  // scelta: il bottone si illumina, poi (180 ms) si passa alla domanda dopo: si vede cosa si e' scelto
  const scegli=(b,fn)=>{box.querySelectorAll(".ptest-o button").forEach(x=>x.classList.toggle("on",x===b));setTimeout(fn,180);};
  box.querySelectorAll("[data-cap]").forEach(b=>b.onclick=()=>scegli(b,()=>{test.cap=+b.dataset.cap;vai(2);}));
  box.querySelectorAll("[data-anni]").forEach(b=>b.onclick=()=>scegli(b,()=>{test.anni=+b.dataset.anni;vai(3);}));
  box.querySelectorAll("[data-tol]").forEach(b=>b.onclick=()=>scegli(b,()=>{test.tol=+b.dataset.tol;vai(4);}));
  box.querySelectorAll("[data-t]").forEach(b=>b.onclick=()=>{const t=b.dataset.t;
   if(t=="cap"){const v=+String(box.querySelector(".ptest-lib input").value).replace(/\D/g,"");if(v>=100){test.cap=v;vai(2);}else box.querySelector(".ptest-lib input").focus();}
   else if(t=="ind")vai(Math.max(1,test.passo-1));
   else if(t=="chiudi")chiudiTest();
   else if(t=="rifai"){test={passo:1,cap:test.cap||capitale};vai(1);}
   else if(t=="usa"){const r=esitoTest();if(!r.p)return;test.esito=r.p.id;test.passo=5;salvaTest();
    sel=r.p.id;capitale=test.cap;try{localStorage.setItem("ebProfilo",sel);localStorage.setItem("ebCapitale",capitale);}catch(e){}
    chiudiTest();vista="oggi";disegna();try{if(typeof etichetteInfo=="function")etichetteInfo(el);}catch(e){}
    const h=el.querySelector(".phero");if(h){h.scrollIntoView({behavior:"smooth",block:"start"});h.classList.add("pglow");setTimeout(()=>h.classList.remove("pglow"),1800);}}});
  const inp=box.querySelector(".ptest-lib input");if(inp)inp.onkeydown=e=>{if(e.key=="Enter")box.querySelector('[data-t="cap"]').click();};}
 // v7.37 BARRA IN ALTO: ogni cella ha 3 righe ad altezza fissa (etichetta 16px | valore 52px | piede 36px, vedi .pcell in stile.css)
 //   cosi' etichette, valori e piedi delle 3 celle stanno sulla stessa linea. Ogni cella riempie la sua larghezza:
 //   rotazione = data + barra dei giorni di borsa, ribilanciamento = 4 riquadri del conto alla rovescia, profilo = nome + pulsanti.
 function testa(){const c=(P.profili[0]||{}).corrente||{},q=(t,v)=>`<span class="pcq"><b>${t}</b><small>${v}</small></span>`;
  const rot=P.attesa
   ?`<span class="pdl">Nuova rotazione</span><div class="pcv"><b class="pcb acc">${gg(P.rotazione)}</b><small>decisa sulla chiusura del ${gg(P.decisa_al)}</small></div>
     <div class="pcpiede"><span class="pcpiede-t">Si applica all'apertura del ${gg(P.prossima)}</span></div>`
   :`<span class="pdl">Rotazione in vigore</span><div class="pcv"><b class="pcb">${gg(P.rotazione)}</b><small>si ribilancia il primo giorno di borsa del mese</small></div>
     <div class="pcpiede">${c.gg&&c.tot?`<span class="pcpiede-t">Giorno di borsa <b>${c.gg}</b> di ${c.tot}</span><span class="pcpiede-bar"><i style="width:${Math.min(100,c.gg/c.tot*100).toFixed(0)}%"></i></span>`:""}</div>`;
  const prof=test.esito?(P.profili.find(x=>x.id==test.esito)||{}).nome||"":"";
  return `<div class="pcell">${rot}</div>
   <div class="pcell"><span class="pdl">${P.attesa?"Si esegue tra":"Prossimo ribilanciamento"}</span>
    <div class="pcv pcount" data-t="${P.prossima||""}" title="${gg(P.prossima)} all'apertura delle borse europee (09:00 ora italiana)">${q("--","giorni")}${q("--","ore")}${q("--","min")}${q("--","sec")}</div>
    <div class="pcpiede"><span class="pcpiede-t">${giorno(P.prossima)} ${gg(P.prossima)}, ore 9:00</span></div></div>
   <div class="pcell pcell-prof"><span class="pdl">Il tuo profilo</span>
    <div class="pcv">${prof?`<b class="pcb acc">${esc(prof)}</b><small>scelto con il test, su ${eur(test.cap||capitale)}</small>`:`<b class="pcb">Non ancora scelto</b><small>3 domande, meno di un minuto</small>`}</div>
    <div class="pcpiede"><button type="button" class="ptest-apri${prof?"":" nuovo"}">${prof?"Rifai il test":"Trova il tuo profilo"}<span aria-hidden="true">&rarr;</span></button>${prof?`<button type="button" class="ptest-reset" title="Cancella il profilo scelto (solo in questo browser)">Azzera</button>`:""}</div></div>`;}
 // nome del giorno della settimana ("lunedi'") di una data AAAA-MM-GG
 function giorno(ymd){try{const [y,m,d]=ymd.split("-").map(Number);return ["domenica","lunedì","martedì","mercoledì","giovedì","venerdì","sabato"][new Date(Date.UTC(y,m-1,d)).getUTCDay()];}catch(e){return "";}}
 function disegna(){const p=P.profili.find(x=>x.id==sel);
  el.innerHTML=`<h2>Portafogli modello</h2><p class="sub">Tre profili di rischio, solo acquisti, controllo ogni mese. Numeri in euro, costi inclusi. Come funziona: Guida, sezione 9.</p>
   <div class="ptop">${testa()}</div>
   <div class="pseg" role="tablist" aria-label="Scegli il portafoglio">${P.profili.map(x=>`<button role="tab" aria-selected="${x.id==sel}" class="${x.id==sel?"on":""}" data-p="${x.id}">${x.nome}</button>`).join("")}</div>
   <div class="ptool"><div class="pvista" role="tablist" aria-label="Sezione della scheda">${VISTE.map(v=>`<button role="tab" aria-selected="${vista==v[0]}" class="${vista==v[0]?"on":""}" data-v="${v[0]}">${v[1]}</button>`).join("")}</div>
   ${vista=="oggi"?`<label class="pcap pcapbar">Il tuo capitale <input type="text" inputmode="numeric" value="${mil(capitale)}" aria-label="Capitale da investire in euro"> &euro;</label>`:""}</div>
   ${vista=="oggi"?`
   ${hero(p)}
   ${corso(p)}
   <div class="card pacq" id="pacq">${acquistoHTML(p)}</div>
   <div class="card pconto" id="pconto">${contoHTML(p)}</div>
   <div class="pgrid">${composizione(p)}${contro(p)}</div>`:""}
   ${vista=="storico"?`<h3 class="vft">Andamento del capitale <details class="info"><summary title="Come leggerlo" aria-label="Come leggerlo">i</summary><div>Base 100, scala logaritmica: la stessa percentuale ha la stessa altezza in ogni periodo. Linea turchese = portafoglio, tratteggio = 60/40 di confronto, linea luminosa = live dalla prima rotazione pubblicata.</div></details></h3>
   <div class="vfswitch pper">${[["tutto","Tutto"],["oos","Dal 2016"]].map(x=>`<button data-per="${x[0]}" class="${per==x[0]?"on":""}">${x[1]}</button>`).join("")}</div>
   <div class="card pgraf">${curva(p)}</div>
   ${tabella(p)}
   ${simulatoreHTML(p)}
   ${crisiHTML(p)}
   <details class="psez" open><summary><h3 class="vft">Rischio e costi a confronto</h3><details class="info prinfo" onclick="event.stopPropagation()"><summary title="Come si leggono" aria-label="Come si leggono">i</summary><div><b>S&amp;P 500</b>: la scelta pi&ugrave; semplice, un solo ETF comprato e tenuto, misurata allo stesso modo (in euro): un profilo ha senso solo se fa meglio su rendimento <i>e</i> rischio. <b>Max drawdown</b>: la perdita pi&ugrave; grande dal massimo al minimo. <b>Mesi per recuperare</b>: dal massimo prima del drawdown al ritorno sopra quel livello. <b>Peggiori 12 mesi</b>: il risultato pi&ugrave; basso su un anno qualsiasi, non solo da gennaio a dicembre. <b>Drawdown in 1 anno su 10</b>: partendo da un mese qualsiasi, la perdita massima nei 12 mesi successivi &egrave; stata almeno questa in un caso su dieci: un anno &laquo;brutto&raquo; ma non il peggiore. <b>Media dei mesi peggiori</b> (CVaR): la perdita media nel 5% dei mesi peggiori, quanto fa male un mese davvero cattivo. <b>Sortino</b>: rendimento oltre la liquidit&agrave; diviso le sole oscillazioni negative (sopra 1 &egrave; buono): a differenza della volatilit&agrave; non penalizza i rialzi. <b>Calmar</b>: rendimento annuo diviso il drawdown massimo. <b>Capitale scambiato</b>: quanto del portafoglio si compra e vende in un anno con le rotazioni. <b>Costo annuo</b>: lo scambiato per il costo del modello (0,10%); con il tuo broker pu&ograve; essere diverso. Numeri storici simulati: non garantiscono risultati futuri.</div></details><span class="small">i 3 profili affiancati</span></summary>${rischioCfr()}</details>
   <details class="psez"><summary><h3 class="vft">Confronto dei 3 profili</h3><span class="small">mese per mese</span></summary>${confronto()}</details>`:""}
   ${vista=="rotazioni"?`<div class="pbasso"><h3 class="vft">Ultime rotazioni <span class="pbprof">${esc(p.nome)}</span><details class="info"><summary title="Come leggerle" aria-label="Come leggerle">i</summary><div><b>Entrati</b>: mercati comprati nella rotazione. <b>Usciti</b>: venduti. <b>Restano</b>: tenuti dal mese prima (con i pesi aggiornati). La riga in alto &egrave; la rotazione in vigore, con il risultato provvisorio del mese; sotto ogni mese chiuso c'&egrave; il risultato con il dettaglio per mercato. Cambiando profilo cambiano mercati, pesi e liquidit&agrave;.<br><br><b>Live</b>: mese seguito dal vivo (da novembre 2026). <b>Simulato</b>: mese precedente, calcolato dal modello con le stesse regole e i prezzi reali di quel mese, senza essere stato seguito in tempo reale.</div></details></h3>${rotazioni(p)}</div>`:""}`;
  {const b=el.querySelector(".ptest-apri");if(b)b.onclick=()=>apriTest(!!test.esito);}
  {const b=el.querySelector(".ptest-reset");if(b)b.onclick=()=>{test={passo:0};try{localStorage.removeItem("ebTest");}catch(e){}disegna();};}   // v7.37 azzera il profilo   // v7.36 test nel popup
  el.querySelectorAll(".pvista button").forEach(b=>b.onclick=()=>{vista=b.dataset.v;try{localStorage.setItem("ebPortVista",vista);}catch(e){}ridisegna(".pvista");});
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
   aggiornaEuro(p);};ci.onblur=()=>{ci.value=mil(capitale);try{localStorage.setItem("ebCapitale",capitale);}catch(e){}};}
  simEventi(p);
  crEventi(p);
  contoEventi(p);
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
  const q=[...box.querySelectorAll(".pcq b")],z=n=>String(n).padStart(2,"0");
  const tick=()=>{if(!document.body.contains(box)){clearInterval(timer);return;}
   const ms=fine-Date.now();
   // v6.81: arrivata l'ora (09:00 di Roma del giorno di rotazione): al posto dei riquadri la pastiglia IN CORSO
   if(ms<=0){box.innerHTML='<span class="pcora"><i class="pcdot"></i>IN CORSO</span>';box.classList.add("ora");
    {const lab=box.parentElement&&box.parentElement.querySelector(".pdl");if(lab)lab.textContent="Rotazione";}
    box.title="Rotazione in corso: si esegue oggi all'apertura delle borse europee (09:00 ora italiana)";clearInterval(timer);return;}
   const t=Math.floor(ms/1000),v=[Math.floor(t/86400),Math.floor(t%86400/3600),Math.floor(t%3600/60),t%60];
   v.forEach((n,i)=>{if(q[i])q[i].textContent=z(n);});};
  tick();timer=setInterval(()=>{if(!document.hidden)tick();},1000);}
 // importi in euro senza ridisegnare tutto (il campo resta a fuoco mentre si scrive)
 // v7.1 VARIAZIONE DI OGGI del portafoglio (prezzi Xetra in euro, ritardo di borsa): somma di peso x variazione
 //     dall'ultima chiusura di ogni ETF; liquidita' = 0. Si mostra solo se la seduta di oggi non e' gia' nella chiusura.
 function liveOggi(p){const box=el.querySelector(".pmc-oggi"),L=window.ebLive,c=p.corrente;if(!box||!L||!L.ue||!c||c.attesa)return;
  if(box.querySelector("details[open]"))return;                    // v7.30 fumetto aperto: non si ridisegna
  let r=0,w=0,t=0;p.composizione.forEach(x=>{const v=L.ue[x.k]||(x.k=="AZ"&&L.ue.SP500);if(x.k=="CASH")w+=x.peso;
   else if(v&&v.p&&v.prev){r+=x.peso/100*(v.p/v.prev-1)*100;w+=x.peso;t=Math.max(t,v.t||0);}});
  const giorno=t?new Date(t*1000).toISOString().slice(0,10):null;if(!giorno||giorno<=c.al||w<50){box.hidden=true;return;}
  const ora=new Date(t*1000).toLocaleTimeString("it-IT",{hour:"2-digit",minute:"2-digit"}),mese=((1+c.r/100)*(1+r/100)-1)*100;
  box.hidden=false;box.innerHTML=`<span class="plive on"><i></i>Oggi alle ${ora}</span><b class="${r>=0?"up":"down"}">${pc(r,2)}</b><span>mese stimato <b class="${mese>=0?"up":"down"}">${pc(mese)}</b></span>
   <details class="info"><summary title="Come si calcola" aria-label="Come si calcola">i</summary><div>Variazione di oggi degli ETF in euro su Xetra (ritardo di borsa di circa 15-20 minuti), pesata con la composizione del mese. &Egrave; una stima: il risultato ufficiale del mese usa le chiusure di fine giornata.</div></details>`;}
 window.addEventListener("eb-live",()=>{const p=P.profili.find(x=>x.id==sel);if(!p)return;aggiornaEuro(p);liveOggi(p);
  // v7.30 se l'utente sta leggendo un fumetto (i) del conto non si ridisegna (prima si chiudeva da solo all'arrivo dei prezzi)
  const b=el.querySelector("#pconto");if(b&&!contoEdit&&!b.querySelector("details[open]")){b.innerHTML=contoHTML(p);contoEventi(p);}});
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
