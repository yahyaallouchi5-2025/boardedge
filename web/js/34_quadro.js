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
