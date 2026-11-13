/* ---------- v7.62 STAGIONALITA' IN ORA DI ROMA (orario, giornaliero, settimanale, mensile) ----------
   Dati: ramo "orari" (workflow orari.yml -> cot_radar/stagionalita_orari.py), letti da raw.githubusercontent.com:
     orari/pubblico/indice.json            elenco degli strumenti {s, n, f (fase), dal, al, breve}
     orari/pubblico/<SIMBOLO>.json         tabelle: ora{tutti,"0".."6"}, gsett, gmese, data, sett, mese
   Ogni cella = [N, % rialzo, media %, media rialzi, media ribassi, rapporto, z, affidabile] (come il backtester MT5).
   ORA DI ROMA: giorno, ora, data e settimana di "adesso" si leggono con Intl e timeZone "Europe/Rome": l'ora legale
   cambia da sola (stesse regole del calcolo in Python, controllate ogni notte; se non tornano arriva la mail).
   Le celle non affidabili restano visibili ma grigie (scelta di Ya, 13/11/2026). */
try{(function(){const el=$("stag");if(!el)return;
 const BASE=EB_RAW+"orari/pubblico/",GG=["Lun","Mar","Mer","Gio","Ven","Sab","Dom"],
  GGL=["lunedì","martedì","mercoledì","giovedì","venerdì","sabato","domenica"],
  MM=["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"],
  MML=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"],
  FASI={1:"Forex e metalli",2:"Crypto",3:"ETF USA",4:"Indici (storia breve)"};
 const gg=d=>d?d.slice(8,10)+"/"+d.slice(5,7)+"/"+d.slice(0,4):"";   // data AAAA-MM-GG -> GG/MM/AAAA
 const pc=(v,d=3)=>v==null?"n/d":(v>0?"+":"")+fx(v,d)+"%";
 // "adesso" a Roma: giorno della settimana (0 = lunedi'), ora, giorno, mese, settimana ISO
 function roma(){const p={};new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Rome",weekday:"short",hour:"2-digit",hourCycle:"h23",
   day:"2-digit",month:"2-digit",year:"numeric"}).formatToParts(new Date()).forEach(x=>p[x.type]=x.value);
  const wd=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].indexOf(p.weekday),d=new Date(Date.UTC(+p.year,+p.month-1,+p.day));
  const t=new Date(d);t.setUTCDate(t.getUTCDate()+3-wd);const w1=new Date(Date.UTC(t.getUTCFullYear(),0,4));
  const sett=1+Math.round(((t-w1)/864e5-3+((w1.getUTCDay()+6)%7))/7);
  return {wd,ora:+p.hour,g:+p.day,m:+p.month,sett,data:p.month+"-"+p.day};}
 const R={idx:null,sel:null,dati:{},vista:"ora",gsel:null,sotto:"gsett"};
 try{const v=JSON.parse(localStorage.getItem("eb_stagroma")||"{}");Object.assign(R,{sel:v.sel||null,vista:v.vista||"ora",sotto:v.sotto||"gsett"});}catch(e){}
 const salva=()=>{try{localStorage.setItem("eb_stagroma",JSON.stringify({sel:R.sel,vista:R.vista,sotto:R.sotto}));}catch(e){}};
 const box=document.createElement("div");box.className="sr";
 const metti=()=>{if(el.contains(box))return;const sub=el.querySelector(":scope > p.sub");sub?sub.after(box):el.prepend(box);};
 metti();new MutationObserver(metti).observe(el,{childList:true});
 const info=t=>`<details class="info"><summary title="Come leggerla" aria-label="Informazioni">i</summary><div>${t}</div></details>`;
 // una "tessera" della card Oggi
 function tessera(tit,c,nota){if(!c)return `<div class="sr-t vuota"><span>${tit}</span><b>n/d</b><small>${nota||"pochi dati"}</small></div>`;
  const [n,su,med,,, ,,ok]=c,col=su>=50?"var(--b)":"var(--s)";
  return `<div class="sr-t${ok?" ok":""}"><span>${tit}</span><b style="color:${ok?col:"var(--ink2)"}">${fx(su,0)}%<i>in rialzo</i></b>
   <small>media ${pc(med)} &middot; ${n.toLocaleString("it-IT")} casi</small>${ok?`<em class="tag ok">affidabile</em>`:`<em class="tag">non affidabile</em>`}</div>`;}
 // tabella stile backtester MT5
 function tabella(righe,attuale){return `<div class="tablewrap sr-tw"><table class="vftab sr-tab"><tr><th></th><th class="num">Casi</th><th class="num">% rialzo</th>
   <th class="num">Media</th><th class="num sr-x">Media rialzi</th><th class="num sr-x">Media ribassi</th><th class="num">Rapporto</th><th></th></tr>
  ${righe.map(([et,k,c])=>{if(!c)return "";const [n,su,med,mu,md,rap,z,ok]=c;
   return `<tr class="${ok?"":"sr-grigio"}${k==attuale?" sr-ora":""}"><td><b>${et}</b></td><td class="num">${n.toLocaleString("it-IT")}</td>
    <td class="num"><span class="sr-bar"><i style="width:${su}%;background:${su>=50?"var(--b)":"var(--s)"}"></i></span>${fx(su,1)}%</td>
    <td class="num ${med>0?"up":med<0?"down":""}">${pc(med)}</td><td class="num sr-x up">${pc(mu)}</td><td class="num sr-x down">${pc(md)}</td>
    <td class="num">${rap==null?"n/d":fx(rap,2)}</td><td>${ok?`<span class="tag ${su>=50?"ok":"ko"}" title="z ${fx(z,1)}">${su>=50?"&uarr;":"&darr;"}</span>`:""}</td></tr>`;}).join("")}</table></div>`;}
 // v7.64 niente titoli "Ora di Roma" e "Oggi a Roma ...": la data e' gia' nelle caselle, le spiegazioni sono nell'unica (i) di Stagionalita'
 function disegna(){const I=R.idx,X=R.dati[R.sel],a=roma();
  if(!I||!I.simboli||!I.simboli.length){box.innerHTML=`<div class="card sr-vuota"><h3>Ora di Roma</h3><p class="small">Lo storico orario &egrave; in download (17 anni di dati per il forex): le tabelle compaiono qui da sole appena pronte.</p></div>`;return;}
  const opz=Object.keys(FASI).map(f=>{const s=I.simboli.filter(x=>x.f==f);return s.length?`<optgroup label="${FASI[f]}">${s.map(x=>`<option value="${esc(x.s)}"${x.s==R.sel?" selected":""}>${esc(x.n)}</option>`).join("")}</optgroup>`:"";}).join("");
  const meta=I.simboli.find(x=>x.s==R.sel)||{};
  let corpo='<p class="small sr-car">Caricamento&hellip;</p>';
  if(X){const cO=X.ora[String(a.wd)]||{},ora=cO[String(a.ora)];
   const t1=(X.gsett||{})[String(a.wd)],t2=(X.gmese||{})[String(a.g)],t3=(X.data||{})[a.data];
   const tre=[t1,t2,t3].filter(Boolean),media=tre.length?[tre.reduce((s,c)=>s+c[0],0),tre.reduce((s,c)=>s+c[1],0)/tre.length,tre.reduce((s,c)=>s+c[2],0)/tre.length]:null;
   const oggi=`<div class="card sr-oggi"><div class="sr-grid">${tessera("Fascia "+String(a.ora).padStart(2,"0")+"-"+String((a.ora+1)%24).padStart(2,"0"),ora,"mercato chiuso")}${tessera("Tutti i "+GGL[a.wd],t1)}${tessera("Ogni giorno "+a.g,t2)}${tessera("Ogni "+a.g+" "+MML[a.m-1],t3)}
     <div class="sr-t media"><span>Media giornata</span><b style="color:${media?"var(--ink2)":"var(--mute)"}">${media?fx(media[1],0)+"%":"n/d"}<i>${media?"in rialzo":""}</i></b><small>${media?"media "+pc(media[2])+" &middot; "+tre.length+" letture":"pochi dati"}</small></div></div></div>`;
   let tab="",sub="";
   if(R.vista=="ora"){const g=R.gsel??String(a.wd),T=g=="tutti"?X.ora.tutti:X.ora[g]||{};
    const giorniD=Object.keys(X.ora).filter(k=>k!="tutti").sort();
    sub=`<div class="sr-sub">${["tutti",...giorniD].map(k=>`<button data-g="${k}" class="${k==g?"on":""}">${k=="tutti"?"Tutti":GG[+k]}</button>`).join("")}</div>`;
    tab=tabella([...Array(24).keys()].map(h=>[String(h).padStart(2,"0")+"-"+String((h+1)%24).padStart(2,"0"),String(h),T[String(h)]]),g==String(a.wd)||g=="tutti"?String(a.ora):null);}
   else if(R.vista=="giorno"){const s=R.sotto;
    sub=`<div class="sr-sub">${[["gsett","Giorno della settimana"],["gmese","Giorno del mese"],["data","Data"]].map(([k,t])=>`<button data-s="${k}" class="${k==s?"on":""}">${t}</button>`).join("")}</div>`;
    if(s=="gsett")tab=tabella([0,1,2,3,4,5,6].map(i=>[GGL[i][0].toUpperCase()+GGL[i].slice(1),String(i),X.gsett[String(i)]]),String(a.wd));
    else if(s=="gmese")tab=tabella([...Array(31).keys()].map(i=>["Giorno "+(i+1),String(i+1),X.gmese[String(i+1)]]),String(a.g));
    else{const mm=String(a.m).padStart(2,"0");tab=tabella([...Array(31).keys()].map(i=>{const k=mm+"-"+String(i+1).padStart(2,"0");return [(i+1)+" "+MML[a.m-1],k,X.data[k]];}),a.data);}}
   else if(R.vista=="sett")tab=tabella([...Array(53).keys()].map(i=>["Settimana "+(i+1),String(i+1),X.sett[String(i+1)]]),String(a.sett));
   else tab=tabella(MM.map((m,i)=>[MML[i][0].toUpperCase()+MML[i].slice(1),String(i+1),X.mese[String(i+1)]]),String(a.m));
   corpo=oggi+`<div class="card sr-det"><div class="vfswitch sr-sw">${[["ora","Orario"],["giorno","Giornaliero"],["sett","Settimanale"],["mese","Mensile"]].map(([k,t])=>`<button data-v="${k}" class="${k==R.vista?"on":""}">${t}</button>`).join("")}</div>
    ${sub}${tab}<p class="small sr-nota">Ora di Roma, ora legale inclusa &middot; dati dal ${gg(meta.dal)} al ${gg(meta.al)}${meta.breve?" &middot; <b>storia breve</b>":""} &middot; in grigio le righe non affidabili; evidenziata quella di adesso.</p></div>`;}
  box.innerHTML=`<div class="vfsez">
   <div class="card vfcomandi"><div class="vfriga"><span class="vfetich">Strumento</span><select id="srsel" class="vfsel">${opz}</select></div></div>${corpo}</div>`;
  $("srsel").onchange=e=>{R.sel=e.target.value;R.gsel=null;salva();carica();};
  box.querySelectorAll("[data-v]").forEach(b=>b.onclick=()=>{R.vista=b.dataset.v;salva();disegna();});
  box.querySelectorAll("[data-g]").forEach(b=>b.onclick=()=>{R.gsel=b.dataset.g;disegna();});
  box.querySelectorAll("[data-s]").forEach(b=>b.onclick=()=>{R.sotto=b.dataset.s;salva();disegna();});}
 function carica(){disegna();if(R.dati[R.sel])return;
  fetch(BASE+encodeURIComponent(R.sel)+".json").then(r=>r.ok?r.json():null).then(j=>{if(j){R.dati[R.sel]=j;disegna();}}).catch(e=>console.error("[BoardEdge] stagionalita oraria:",e));}
 // l'indice si scarica solo quando si apre la scheda (il terminale resta leggero)
 let avviato=false;const avvia=()=>{if(avviato)return;avviato=true;
  fetch(BASE+"indice.json").then(r=>r.ok?r.json():null).then(j=>{R.idx=j;if(j&&j.simboli&&j.simboli.length){if(!j.simboli.some(x=>x.s==R.sel))R.sel=j.simboli[0].s;carica();}else disegna();}).catch(()=>{R.idx=null;disegna();});};
 const vis=()=>{if(el.offsetParent!==null)avvia();};
 new MutationObserver(vis).observe(el,{attributes:true,attributeFilter:["class","style"]});document.addEventListener("click",()=>setTimeout(vis,50));vis();
 // ogni minuto si controlla l'ora di Roma: si ridisegna solo quando cambia la fascia (l'ora legale cambia da sola)
 let ultima="";setInterval(()=>{const a=roma(),k=a.data+a.ora;if(k!=ultima){ultima=k;if(R.dati[R.sel])disegna();}},60000);
})();}catch(e){fail("Stagionalita' oraria","stag",e);}
