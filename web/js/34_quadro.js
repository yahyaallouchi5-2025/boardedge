/* 34_quadro.js - v7.21 QUADRO ECONOMICO nella Dashboard (solo informativo, NON un segnale operativo)
   Dati: D.economie da cot_radar/economie.py = {economie:[{id, nome, regime, cresce, sale, tipo_infl, mese, cli, cli3,
   infl, infl6, disoc, sahm, allarme, valuta, curva (solo USA)}], storico:{fase:{sp|tr|oro:[media annua %, mesi]}}}
   + ../azioni/top.json "economie" (azioni.py economie_borsa): per USA, Eurozona e Giappone i settori di borsa
   (titoli in trend rialzista e punteggio medio) e gli indici.
   FLUSSO: una fila di card con la bandiera (una fase per economia) -> clic -> dettaglio sotto: mappa delle 4 fasi,
   indicatori, ciambelle dei settori (% di titoli in trend), indici e ciambelle COT di valuta e mercati collegati.
   Spiegazioni solo nelle (i). Senza dati la sezione non compare. */
try{(function(){
 const el=$("quadro");if(!el)return;
 const E=D.economie;
 if(!E||!E.economie||!E.economie.length){el.innerHTML="";return;}
 const MESI=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];
 const meseIt=m=>m?MESI[+m.slice(5,7)-1]+" "+m.slice(0,4):"";
 const pc=(v,d=1)=>v==null?"n/d":(v>0?"+":"")+fx(v,d)+"%";
 // le 4 fasi: frase breve, classe colore, nome internazionale ("Investment Clock")
 const FASI={Ripresa:["cresce, inflazione in calo","qe-esp","Recovery"],Espansione:["cresce, inflazione in salita","qe-rec","Overheat"],
             Recessione:["rallenta, inflazione in calo","qe-sta","Reflation"],Stagflazione:["rallenta, inflazione in salita","qe-sur","Stagflation"]};
 const ORD=["Ripresa","Espansione","Recessione","Stagflazione"];           // in alto: crescita su; a destra: inflazione su
 // mercati collegati a ogni economia (punteggio COT della Dashboard: D.assets[chiave].score da -100 a +100)
 const COLLEGATI={usa:["DXY","SP500","US10Y"],eur:["EUR","EAFE"],jpn:["JPY"],gbr:["GBP"],aus:["AUD","COPPER","GOLD"],can:["CAD","WTI"]};
 const NOMI={DXY:"Indice del dollaro",SP500:"S&P 500",US10Y:"Treasury 10 anni",EUR:"Euro",EAFE:"Azioni Europa e Asia",JPY:"Yen",
             GBP:"Sterlina",AUD:"Dollaro australiano",COPPER:"Rame",GOLD:"Oro",CAD:"Dollaro canadese",WTI:"Petrolio WTI"};
 // BANDIERE (SVG semplificati, 3:2)
 const BAND={
  usa:`<rect width="30" height="20" fill="#fff"/>${[0,2,4,6,8,10,12].map(i=>`<rect y="${i*20/13}" width="30" height="${20/13}" fill="#b22234"/>`).join("")}<rect width="13" height="${20*7/13}" fill="#3c3b6e"/>${[[2.5,2],[6.5,2],[10.5,2],[4.5,4.5],[8.5,4.5],[2.5,7],[6.5,7],[10.5,7],[4.5,9.5],[8.5,9.5]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r=".7" fill="#fff"/>`).join("")}`,
  eur:`<rect width="30" height="20" fill="#003399"/>${Array.from({length:12},(_,i)=>{const a=i*Math.PI/6;return `<circle cx="${(15+6*Math.sin(a)).toFixed(2)}" cy="${(10-6*Math.cos(a)).toFixed(2)}" r="1" fill="#ffcc00"/>`;}).join("")}`,
  jpn:`<rect width="30" height="20" fill="#fff"/><circle cx="15" cy="10" r="6" fill="#bc002d"/>`,
  gbr:`<rect width="30" height="20" fill="#012169"/><path d="M0 0L30 20M30 0L0 20" stroke="#fff" stroke-width="4"/><path d="M0 0L30 20M30 0L0 20" stroke="#c8102e" stroke-width="1.5"/><path d="M15 0V20M0 10H30" stroke="#fff" stroke-width="6"/><path d="M15 0V20M0 10H30" stroke="#c8102e" stroke-width="3.4"/>`,
  aus:`<rect width="30" height="20" fill="#012169"/><path d="M0 0L15 10M15 0L0 10" stroke="#fff" stroke-width="2"/><path d="M7.5 0V10M0 5H15" stroke="#fff" stroke-width="3"/><path d="M7.5 0V10M0 5H15" stroke="#c8102e" stroke-width="1.6"/>${[[7.5,15,1.6],[22.5,4,1],[19,9,1],[26,8.5,1],[22.5,16,1],[24,12,.6]].map(([x,y,r])=>`<circle cx="${x}" cy="${y}" r="${r}" fill="#fff"/>`).join("")}`,
  can:`<rect width="30" height="20" fill="#fff"/><rect width="7.5" height="20" fill="#d52b1e"/><rect x="22.5" width="7.5" height="20" fill="#d52b1e"/><path d="M15 4l1.2 2.4 1.6-.6-.4 3 2-1.4.3 1.4 1.6-.3-1 2.2.8.6-3.4 2.4.3 1.2H15.6V16h-1.2v-1.8h-2.4l.3-1.2-3.4-2.4.8-.6-1-2.2 1.6.3.3-1.4 2 1.4-.4-3 1.6.6z" fill="#d52b1e"/>`};
 const bandiera=id=>`<svg class="qe-flag" viewBox="0 0 30 20" aria-hidden="true">${BAND[id]||""}</svg>`;
 // freccia di tendenza. tipo: "bene" = salire e' una buona notizia, "male" = cattiva, "neu" = solo direzione
 const fr=(ora,prima,tipo)=>{if(ora==null||prima==null||Math.abs(ora-prima)<0.05)return `<i class="qe-fr flat" title="Stabile">=</i>`;
  const su=ora>prima,cl=tipo=="neu"?"neu":((tipo=="bene")==su?"up":"down");
  return `<i class="qe-fr ${cl}" title="${su?"In salita":"In discesa"}">${su?"&#9650;":"&#9660;"}</i>`;};
 // CIAMBELLA: v da 0 a 100 (riempimento), colore per soglie (>=60 verde, 40-60 giallo, sotto rosso) o forzato
 const ciambella=(v,testo,cl)=>{const C=2*Math.PI*20,p=Math.max(0,Math.min(100,v||0));
  const c=cl||(p>=60?"up":p>=40?"mid":"down");
  return `<svg class="qe-don ${c}" viewBox="0 0 50 50" aria-hidden="true"><circle cx="25" cy="25" r="20" class="bg"/><circle cx="25" cy="25" r="20" class="fg" stroke-dasharray="${(C*p/100).toFixed(1)} ${C.toFixed(1)}" transform="rotate(-90 25 25)"/><text x="25" y="29" text-anchor="middle">${testo}</text></svg>`;};
 const info=(t,cl="")=>`<details class="info ${cl}"><summary title="Come si legge" aria-label="Come si legge">i</summary><div>${t}</div></details>`;
 const st=E.storico,cel=x=>x?`<td class="num ${x[0]>=0?"up":"down"}">${pc(x[0])}</td>`:`<td class="num">n/d</td>`;
 const tab=st?`<table class="qe-tab"><tr><th>Fase</th><th class="num">S&amp;P 500</th><th class="num">Treasury</th><th class="num">Oro</th></tr>${ORD.filter(r=>st[r]).map(r=>`<tr><td>${r}</td>${cel(st[r].sp)}${cel(st[r].tr)}${cel(st[r].oro)}</tr>`).join("")}</table>`:"";
 const infoSez=info(`<b>Fase del ciclo</b> di ogni economia, con la stessa regola per tutte. <b>Crescita</b>: in salita se l'indicatore anticipatore dell'OCSE (CLI) &egrave; pi&ugrave; alto di 3 mesi prima (Eurozona: media di Germania, Francia, Italia e Spagna pesata per il PIL). <b>Inflazione</b>: in salita se quella annua &egrave; pi&ugrave; alta di 6 mesi prima.<br><br>
   <b>Ripresa</b> (Recovery): cresce, inflazione in calo. <b>Espansione</b> (Overheat): cresce, inflazione in salita. <b>Stagflazione</b>: rallenta, inflazione in salita. <b>Recessione</b> (Reflation): rallenta, inflazione in calo.<br><br>
   <b>Allarme recessione</b>: regola di Sahm, cio&egrave; la disoccupazione (media 3 mesi) salita di almeno 0,5 punti dal minimo dell'ultimo anno; per gli USA anche curva dei tassi invertita con spread delle aziende pi&ugrave; indebitate in salita.<br><br>
   ${tab?`<b>USA, com'&egrave; andata</b>: rendimento medio annuo del mese dopo, per fase, dal 1990 (oro dal 2004).${tab}`:""}
   <b>Solo contesto, non un segnale</b>: i mercati si muovono prima dei dati economici (in recessione l'S&amp;P 500 ha spesso gi&agrave; ripreso a salire). I portafogli seguono il filtro di trend sui prezzi.`,"qe-is");
 // v7.22d: il dettaglio (mappa, indicatori, ciambelle) si apre SOLO al click su una card; un secondo click lo chiude
 let sel=null;
 let borsa=null;                                           // top.json "economie": arriva dopo, se c'e'
 const card=x=>{const f=FASI[x.regime];
  return `<button type="button" class="qe-card${x.id==sel?" on":""}" data-id="${x.id}" aria-expanded="${x.id==sel}" aria-controls="qe-det" title="${x.id==sel?"Chiudi il dettaglio":"Apri il dettaglio"}">
   <span class="qe-cn">${bandiera(x.id)}<b>${esc(x.nome)}</b>${x.allarme?`<i class="qe-dot" title="Allarme recessione"></i>`:""}<svg class="qe-chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></span>
   <span class="qe-chip ${f[1]}">${x.regime}</span>
   <span class="qe-cs"><span>Crescita ${fr(x.cli,x.cli3,"bene")}</span><span>Inflazione ${fx(x.infl,1)}% ${fr(x.infl,x.infl6,"male")}</span></span></button>`;};
 function dettaglio(x){const f=FASI[x.regime],b=borsa&&borsa.economie&&borsa.economie[x.id],nomiS=(borsa&&borsa.settori)||{};
  const ind=(nome,val,sotto,freccia)=>`<div class="qe-i"><small>${nome}</small><b>${val}${freccia||""}</b><span>${sotto}</span></div>`;
  const mappa=`<div class="qe-mappa" role="img" aria-label="Fase: ${x.regime}"><span class="qe-ax qe-ay">Crescita &#9650;</span>
    ${ORD.map(r=>`<div class="qe-c ${FASI[r][1]}${r==x.regime?" on":""}"><b>${r}</b>${r==x.regime?`<span>oggi</span>`:""}</div>`).join("")}
    <span class="qe-ax qe-ax2">Inflazione &#9654;</span></div>`;
  const tiles=[ind("Anticipatore OCSE",fx(x.cli,1),`3 mesi fa ${fx(x.cli3,1)} &middot; 100 = media`,fr(x.cli,x.cli3,"bene")),
   ind("Inflazione",fx(x.infl,1)+"%",`<em class="qe-ti">${x.tipo_infl}</em> &middot; 6 mesi fa ${fx(x.infl6,1)}%`,fr(x.infl,x.infl6,"male"))];
  if(x.disoc!=null)tiles.push(ind("Disoccupazione",fx(x.disoc,1)+"%",x.sahm!=null?`Sahm ${fx(x.sahm,2)} su 0,50`:"",""));
  if(x.curva!=null)tiles.push(ind("Curva 10-2 anni",(x.curva>0?"+":"")+fx(x.curva,2),x.curva<0?"invertita":"normale",""));
  // settori di borsa: % di titoli in trend rialzista (ciambella), sotto il numero di titoli
  const sett=b&&b.settori?Object.entries(b.settori).filter(([,s])=>s.n).sort((p,q)=>q[1].su/q[1].n-p[1].su/p[1].n):[];
  const settHTML=sett.length?`<div class="qe-sez"><div class="qe-st"><h4>Borsa per settore</h4>${info("Per ogni settore, la quota di titoli dell'Azionario di questa economia in <b>trend rialzista</b> (prezzo e SMA 50 sopra la SMA 200). Verde da 60% in su, giallo tra 40 e 60%, rosso sotto il 40%. Dice <b>dove si muove il denaro</b>: i settori verdi stanno guidando, quelli rossi sono evitati. Con pochi titoli (numero sotto la ciambella) il dato &egrave; meno solido. L'immobiliare &egrave; uno dei settori.")}</div>
   <div class="qe-dons">${sett.map(([id,s])=>{const v=Math.round(s.su/s.n*100);return `<div class="qe-d" title="${esc(nomiS[id]||id)}: ${s.su} titoli su ${s.n} in trend rialzista, punteggio medio ${s.pt}">${ciambella(v,v+"%")}<b>${esc(nomiS[id]||id)}</b><small>${s.n} titol${s.n==1?"o":"i"}</small></div>`;}).join("")}</div></div>`:"";
  const idx=b&&b.indici&&b.indici.length?`<div class="qe-sez"><div class="qe-st"><h4>Indici</h4>${info("Freccia del trend (prezzo e SMA 50 contro SMA 200) e rendimento degli ultimi 3 mesi e 12 mesi.")}</div><div class="qe-idx">${b.indici.map(i=>`<div class="qe-ix"><b>${esc(i.n)}</b><span>${i.tr==1?'<i class="qe-fr up">&#9650;</i>':i.tr==-1?'<i class="qe-fr down">&#9660;</i>':'<i class="qe-fr flat">=</i>'} 3 mesi <em class="${(i.v3m||0)>=0?"up":"down"}">${pc(i.v3m)}</em> &middot; 12 mesi <em class="${(i.v1a||0)>=0?"up":"down"}">${pc(i.v1a)}</em></span></div>`).join("")}</div></div>`:"";
  const col=(COLLEGATI[x.id]||[]).filter(k=>D.assets&&D.assets[k]).map(k=>Object.assign({},D.assets[k],{name:NOMI[k]||D.assets[k].name}));
  const cot=col.length?`<div class="qe-sez"><div class="qe-st"><h4>Valuta e mercati collegati</h4>${info("Punteggio finale della Dashboard (COT e mercato) da &minus;100 a +100: verde comprato, rosso venduto, grigio neutro. La ciambella &egrave; piena a +100 e vuota a &minus;100. Per l'Australia contano rame e oro, per il Canada il petrolio: sono le materie prime che muovono la loro economia e la valuta.")}</div>
   <div class="qe-dons">${col.map(a=>{const l=a.label||"NEUTRO",c=/BUY/.test(l)?"up":/SELL/.test(l)?"down":"neu";return `<div class="qe-d" title="${esc(a.name)}: ${l}">${ciambella((a.score+100)/2,(a.score>0?"+":"")+Math.round(a.score),c)}<b>${esc(a.name)}</b><small>${l}</small></div>`;}).join("")}</div></div>`:"";
  return `<div class="qe-dh">${bandiera(x.id)}<b class="${f[1]}">${x.regime}</b><span>${esc(x.nome)}: l'economia ${f[0]} &middot; dati di ${meseIt(x.mese)}</span>
    <span class="qe-al ${x.allarme?"on":""}">${x.allarme?"Allarme recessione":"Nessun allarme recessione"}</span></div>
   <div class="qe-main">${mappa}<div class="qe-ind">${tiles.join("")}</div></div>${settHTML}${idx}${cot}`;}
 function disegna(){const x=E.economie.find(e=>e.id==sel);
  el.innerHTML=`<div class="qe-sec"><div class="qe-h"><h2>Quadro economico</h2>${infoSez}</div>
   <div class="qe-row${x?" qe-scelta":""}">${E.economie.map(card).join("")}</div>
   ${x?`<div class="card qe-det" id="qe-det">${dettaglio(x)}</div>`:""}</div>`;
  el.querySelectorAll(".qe-card").forEach(b=>b.onclick=()=>{const apri=sel!=b.dataset.id;sel=apri?b.dataset.id:null;disegna();
   if(apri){const d=el.querySelector(".qe-det");if(d&&d.getBoundingClientRect().top>innerHeight*.75)d.scrollIntoView({behavior:"smooth",block:"start"});}});}
 disegna();
 fetch("../azioni/top.json",{cache:"no-cache"}).then(r=>r.ok?r.json():null).then(d=>{if(d&&d.economie){borsa=d;disegna();}}).catch(()=>{});
})();}catch(e){console.error("quadro economico",e);}
