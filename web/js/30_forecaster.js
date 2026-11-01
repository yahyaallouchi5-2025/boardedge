
/* ---------- FORECASTER (v6.65) ----------
   Dati da D.fore (vedi cot_radar/forecaster.py). Tutto quello che si vede e' stato REGISTRATO prima che il mese
   cominciasse (registro in catena nel ramo "storico", con data e ora di GitHub) e verificato dopo la chiusura:
     1. quattro numeri: mesi verificati e precisione di stagionalita', COT e modello (contro "sempre rialzo");
     2. "Previsioni di <mese>": direzione prevista da ogni fonte per ogni mercato e andamento del mese finora;
     3. "Sfidanti": le varianti dei portafogli contro il portafoglio attuale, per profilo (selettore a segmenti);
        clic su una riga = pesi della variante;
     4. archivio dei mesi registrati con il link alla prova su GitHub.
   Testi brevi in pagina, spiegazioni nelle (i). Profilo scelto salvato nel browser (localStorage "ebFcProf"). */
try{(function(){const F=D.fore,el=$("fore");if(!el)return;
 const MESI=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];
 const meseN=m=>m?MESI[+m.slice(5,7)-1]+" "+m.slice(0,4):"";
 const gg=d=>d?d.slice(8,10)+"/"+d.slice(5,7)+"/"+d.slice(0,4):"";
 const ora=iso=>{try{return new Date(iso.replace("Z",":00Z")).toLocaleString("it-IT",{timeZone:"Europe/Rome",day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"});}catch(e){return iso;}};
 const pc=(v,d=2)=>v==null?'<span class="fcnd">&ndash;</span>':`<span class="${v>0?"up":v<0?"down":""}">${v>0?"+":""}${fx(v,d)}%</span>`;
 const info=(id,t)=>`<button type="button" class="info" data-apri="${id}" data-k="${id}" aria-expanded="${infoAperte.has(id)}" aria-label="${t}" title="${t}">i</button>`;
 const testo=(id,t)=>`<p id="${id}" class="sub infotesto${infoAperte.has(id)?" aperta":""}">${t}</p>`;
 const testa=`<h2>Forecaster ${info("fcinfo","Come funziona il Forecaster")}</h2>
  ${testo("fcinfo",`Ogni mese, alla rotazione dei portafogli (decisa sulla chiusura dell'ultimo giorno, eseguita all'apertura del primo), il sito <b>scrive prima</b> cosa prevede per ogni mercato e come investirebbero alcune varianti dei portafogli, poi a mese chiuso <b>misura</b> com'è andata. Le righe del registro sono in catena (ognuna contiene l'impronta della precedente) e salvate su GitHub con data e ora: nessuna si può cambiare dopo senza che si veda. Le regole sono fissate dal primo mese e non si ritoccano guardando i risultati. È un test del futuro, non una promessa: con pochi mesi i numeri sono rumore, un giudizio arriva solo dopo ${F?F.min_mesi:12} mesi.`)}
  <p class="sub">Previsioni e varianti dei portafogli scritte prima di ogni mese, verificate dopo. Registro pubblico${F?` dal ${meseN(F.dal)}`:""}.</p>`;
 if(!F||!F.corrente){el.innerHTML=testa+`<div class="card fcvuoto"><b>Primo mese in arrivo</b><span class="small">Le prime previsioni si registrano alla prossima rotazione dei portafogli.</span></div>`;return;}
 const C=F.corrente,PR=F.precisione||{},SD=F.sfidanti_def||[],PF=F.profili||[];
 let prof=PF.length>1?PF[1].id:(PF[0]||{}).id,aperto=null;
 try{const s=localStorage.getItem("ebFcProf");if(s&&PF.some(p=>p.id==s))prof=s;}catch(e){}
 // testi dei giudizi (costanti: due graffe aperte di fila rompono il modello della pagina)
 const VP={meglio:"Meglio del caso",peggio:"Peggio del caso",uguale:"Nessun vantaggio"},VS={meglio:"Meglio",peggio:"Peggio",uguale:"Nessuna differenza"};
 const nome=k=>k=="AZ10"?"Azioni scelte (10 titoli)":(F.nomi&&F.nomi[k])||k;

 // freccia della direzione prevista; con il mese avviato, segno di spunta se finora la direzione e' giusta
 function dir(d,r,v,un){if(!d)return `<span class="fcd no" title="nessuna previsione">&ndash;</span>${v!=null?`<em>${un(v)}</em>`:""}`;
  const ok=r==null?"":(d*r>0?'<i class="fcok" title="finora giusta">&#10003;</i>':'<i class="fcko" title="finora sbagliata">&#10007;</i>');
  return `<span class="fcd ${d>0?"su":"giu"}" title="${d>0?"rialzo":"ribasso"}">${d>0?"&#9650;":"&#9660;"}</span>${v!=null?`<em>${un(v)}</em>`:""}${ok}`;}
 const unS=v=>(v>0?"+":"")+fx(v,1)+"%",unC=v=>(v>0?"+":"")+fx(v,0),unM=v=>(v>0?"+":"")+fx(v,2)+"%";

 function kpi(id,tit,x,inf){let big,nota,cls="";
  if(!x||!x.n){big="&ndash;";nota="nessuna previsione verificata";}
  else{big=x.hit+"%";nota=`${x.n} previsioni &middot; sempre rialzo ${x.base}%`;cls=x.verdetto=="meglio"?"up":x.verdetto=="peggio"?"down":"";}
  const v=!x||!x.n||x.verdetto=="raccolta"?`<span class="fcv oss">In raccolta${x&&x.n?` &middot; ${x.n}/${F.min_prev}`:""}</span>`:
   `<span class="fcv ${x.verdetto}">${VP[x.verdetto]}</span>`;
  return `<div class="card kpi fck"><h3>${tit} ${info(id,"Spiegazione")}</h3><div class="big ${cls}">${big}</div><div class="note">${nota}</div>${v}${testo(id,inf)}</div>`;}

 function previsioni(){const avviato=!!C.al;
  const righe=C.mercati.slice().sort((a,b)=>(Math.abs(b.stag)+Math.abs(b.cot))-(Math.abs(a.stag)+Math.abs(a.cot))||nome(a.k).localeCompare(nome(b.k)));
  const stato=C.chiuso?`<span class="fcstato chiuso">Mese chiuso</span>`:avviato?`<span class="fcstato live"><i></i>In corso &middot; al ${gg(C.al)}</span>`:`<span class="fcstato attesa">Parte all'apertura</span>`;
  return `<div class="card fcprev"><div class="fchead"><div><b class="fctit">Previsioni di ${meseN(C.mese)}</b>
    <span class="small">Registrate il ${ora(C.creato)} &middot; decise sulla chiusura del ${gg(C.decisa_al)}${C.in_ritardo?' &middot; <b class="fcrit">registrate in ritardo</b>':""}</span></div>
    <div class="fchead-dx">${stato}${info("fcprevinfo","Come leggere le previsioni")}</div></div>
   ${testo("fcprevinfo",`&#9650; rialzo, &#9660; ribasso, &ndash; nessuna previsione. <b>Stagionalità</b>: solo i mesi che superano i filtri della scheda Stagionalità (almeno 10 anni, trend tolto, stabile nel tempo, test t); il numero è il rendimento tipico del mese. <b>COT</b>: etichetta del punteggio COT già pubblicato alla rotazione (BUY/SELL, il numero è il punteggio); sotto ±25 nessuna previsione. <b>Modello</b>: regressione lineare con coefficienti ristretti, addestrata ogni mese solo sui mesi passati di tutti i mercati insieme (punteggio COT, distanza dalla media a 200 giorni, momento a 12 mesi, stagionalità); il numero è il rendimento atteso del mese. Il modello indica quasi sempre &#9650; perché in media i mercati salgono: conta il confronto tra mercati (la variante &laquo;Inclinazione del modello&raquo; pesa di più quelli sopra la media). La spunta dice se finora la direzione è giusta: conta solo a fine mese.`)}
   <div class="tablewrap fctab"><table class="compatta"><tr><th>Mercato</th><th>Stagionalit&agrave;</th><th>COT</th><th>Modello</th><th class="num">${C.chiuso?"Mese":"Mese finora"}</th></tr>
    ${righe.map(m=>`<tr><td class="fcnome">${esc(nome(m.k))}</td><td class="fcc">${dir(m.stag,m.r,m.stag?m.stag_v:null,unS)}</td>
     <td class="fcc">${dir(m.cot,m.r,m.cot_v,unC)}</td><td class="fcc">${dir(m.mod==null?0:(m.mod>0?1:-1),m.r,m.mod,unM)}</td>
     <td class="num">${pc(m.r)}</td></tr>`).join("")}</table></div></div>`;}

 function sfidanti(){const S=F.sfidanti||{},cur=C.sfidanti||{},pesi=C.pesi||{};
  const verd=x=>{if(!x||!x.mesi||x.verdetto=="osservazione")return `<span class="fcv oss">In osservazione &middot; ${x?x.mesi||0:0}/${F.min_mesi}</span>`;
   return `<span class="fcv ${x.verdetto}">${VS[x.verdetto]}</span>`;};
  const riga=s=>{const x=(S[s.id]||{})[prof],c=(cur[s.id]||{})[prof],w=(pesi[s.id]||{})[prof],camp=s.id=="campione";
   if(!w&&!x)return "";
   const tit=s.id=="az10"&&C.az10?`<p class="fctit10">I 10 titoli del mese: ${C.az10.map(esc).join(", ")}</p>`:"";
   const det=aperto==s.id&&w?`<tr class="fcdett"><td colspan="6"><div class="fcdbox"><p class="fcdescr">${esc(s.descr)}</p>${tit}<div class="fcpesi">${Object.entries(w).sort((a,b)=>(a[0]=="CASH")-(b[0]=="CASH")||b[1]-a[1]).map(([k,v])=>{
     const d=((pesi.campione||{})[prof]||{})[k],diff=camp||d==null?null:v-d;
     return `<span class="fcpeso${diff&&Math.abs(diff)>0.0005?(diff>0?" piu":" meno"):""}"><b>${fx(v*100,1)}%</b>${esc(nome(k))}</span>`;}).join("")}</div></div></td></tr>`:"";
   return `<tr class="clic fcr${camp?" camp":""}${aperto==s.id?" aperta":""}" data-s="${s.id}" tabindex="0"><td class="fcnome wrap-ok"><b>${esc(s.nome)}</b><span>${esc(s.descr)}</span></td>
    <td class="num">${pc(c)}</td><td class="num">${x&&x.mesi?pc(x.tot):'<span class="fcnd">&ndash;</span>'}</td><td class="num">${x&&x.mesi?pc(x.dd):'<span class="fcnd">&ndash;</span>'}</td>
    <td class="num">${camp?"":x&&x.mesi?pc(x.diff):'<span class="fcnd">&ndash;</span>'}</td><td>${camp?'<span class="fcv camp">Riferimento</span>':verd(x)}</td></tr>${det}`;};
  return `<div class="card fcsfid"><div class="fchead"><div><b class="fctit">Sfidanti dei portafogli</b><span class="small">Clic su una riga per vedere i pesi del mese</span></div>
    <div class="fchead-dx"><div class="vfswitch fcprof" role="tablist">${PF.map(p=>`<button data-p="${p.id}" class="${p.id==prof?"on":""}" role="tab">${esc(p.nome)}</button>`).join("")}</div>${info("fcsfinfo","Come si giudicano gli sfidanti")}</div></div>
   ${testo("fcsfinfo",`Ogni variante parte dagli stessi dati del portafoglio attuale e cambia una sola regola. Ogni mese tiene i pesi fissati alla rotazione fino alla rotazione dopo, con un costo dello 0,10% sul capitale scambiato (il primo mese parte alla pari, senza costi). <b>Differenza</b> = rendimento medio al mese in più o in meno del portafoglio attuale. Dopo ${F.min_mesi} mesi il giudizio usa un intervallo al 99%: &laquo;Meglio&raquo; o &laquo;Peggio&raquo; solo se tutto l'intervallo sta da una parte. Una variante migliore diventa una <b>proposta</b>, mai un cambio automatico del sito. I pesi in verde e rosso sono quelli diversi dal portafoglio attuale.`)}
   <div class="tablewrap fctab"><table class="compatta"><tr><th>Variante</th><th class="num">${C.chiuso?"Ultimo mese":"Mese finora"}</th><th class="num">Totale</th><th class="num">Drawdown</th><th class="num">Differenza</th><th>Giudizio</th></tr>
    ${SD.map(riga).join("")}</table></div></div>`;}

 function archivio(){const A=F.archivio||[];
  return `<div class="card fcarch"><div class="fchead"><div><b class="fctit">Registro</b><span class="small">${F.catena?'<b class="fcint">&#10003; catena integra</b>':'<b class="fcrit">catena da controllare</b>'}${F.ultimo_hash?` &middot; ultima impronta <code>${esc(F.ultimo_hash.slice(0,12))}&hellip;</code>`:""}</span></div>
    <a class="tvbtn fcprova" href="${esc(F.prova)}" target="_blank" rel="noopener">Prova su GitHub &#8599;</a></div>
   <div class="fcmesi">${A.map(a=>`<div class="fcmese"><b>${meseN(a.mese)}</b><span class="small">registrato ${ora(a.creato)}${a.in_ritardo?' &middot; <b class="fcrit">in ritardo</b>':""}</span>
     <span class="fcesito">${a.esito?`Attuale ${PF.map(p=>`${esc(p.nome.slice(0,4))}. ${pc((a.campione||{})[p.id],1)}`).join(" &middot; ")}`:'<span class="fcv oss">in corso</span>'}</span></div>`).join("")}</div></div>`;}

 function disegna(){const P=F.precisione||{};
  el.innerHTML=testa+`<div class="grid k4 fckpi">
    <div class="card kpi fck"><h3>Mesi verificati ${info("fcmesiinfo","Spiegazione")}</h3><div class="big">${F.mesi}</div><div class="note">giudizio dopo ${F.min_mesi} mesi</div>
     <span class="fcv oss">${F.mesi>=F.min_mesi?"Giudizio attivo":`Mancano ${F.min_mesi-F.mesi} mesi`}</span>${testo("fcmesiinfo",`Mesi chiusi e verificati dal ${meseN(F.dal)}. Prima di ${F.min_mesi} mesi ogni differenza può essere caso: i giudizi restano &laquo;in osservazione&raquo;.`)}</div>
    ${kpi("fckst","Stagionalit&agrave;",P.stag,`Percentuale di direzioni giuste nei mesi chiusi. I mercati salgono più spesso di quanto scendano, quindi il confronto onesto è con &laquo;sempre rialzo&raquo; sugli stessi mercati e mesi. Giudizio dopo ${F.min_prev} previsioni, intervallo al 99%.`)}
    ${kpi("fckcot","COT",P.cot,`Direzione dell'etichetta COT (BUY/SELL) alla rotazione contro il movimento del mese. Confronto con &laquo;sempre rialzo&raquo;, giudizio dopo ${F.min_prev} previsioni.`)}
    ${kpi("fckmod","Modello",P.mod,`Segno del rendimento atteso dal modello contro il movimento del mese. Confronto con &laquo;sempre rialzo&raquo;, giudizio dopo ${F.min_prev} previsioni.`)}</div>
   ${previsioni()}${sfidanti()}${archivio()}`;
  el.querySelectorAll(".fcprof button").forEach(b=>b.onclick=()=>{prof=b.dataset.p;try{localStorage.setItem("ebFcProf",prof);}catch(e){}disegna();});
  el.querySelectorAll("tr.fcr").forEach(r=>{const f=()=>{aperto=aperto==r.dataset.s?null:r.dataset.s;disegna();};r.onclick=f;r.onkeydown=e=>{if(e.key=="Enter")f();};});}
 disegna();})();}catch(e){fail('Forecaster','fore',e);}
