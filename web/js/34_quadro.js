/* 34_quadro.js - v7.20 QUADRO ECONOMICO USA nella Dashboard (solo informativo, NON un segnale operativo)
   Dati: D.quadro da cot_radar/quadro.py = {mese, regime, cresce, sale, infl, infl6, prod, disoc, sahm, curva,
   invertita, hy, allarme, prima:{infl,prod,disoc,curva}, storico:{regime:{sp|tr|oro:[media annua %, mesi]}}}.
   Mappa 2x2 (crescita in verticale, inflazione in orizzontale) con la fase di oggi evidenziata, 4 indicatori con
   la freccia rispetto a 3 mesi prima e l'allarme recessione. Spiegazioni e storico solo nella (i).
   Senza dati la card non compare. */
try{(function(){
 const Q=D.quadro,el=$("quadro");
 if(!el)return;
 if(!Q||!Q.regime){el.innerHTML="";return;}
 const MESI=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];
 const mese=MESI[+Q.mese.slice(5,7)-1]+" "+Q.mese.slice(0,4);
 const pc=(v,d=1)=>v==null?"n/d":(v>0?"+":"")+fx(v,d)+"%";
 // le 4 fasi: [nome, frase breve, classe colore]; posizione nella mappa = [riga, colonna]
 // nomi scelti da Ya (ciclo economico); tra parentesi nella (i) il nome internazionale ("Investment Clock")
 const FASI={Ripresa:["cresce, inflazione in calo","qe-esp","Recovery"],Espansione:["cresce, inflazione in salita","qe-rec","Overheat"],
             Recessione:["rallenta, inflazione in calo","qe-sta","Reflation"],Stagflazione:["rallenta, inflazione in salita","qe-sur","Stagflation"]};
 const ORD=["Ripresa","Espansione","Recessione","Stagflazione"];            // in alto: crescita su; a destra: inflazione su
 // freccia di tendenza rispetto a 3 mesi prima. tipo: "bene" = salire e' una buona notizia (produzione),
 // "male" = salire e' una cattiva notizia (inflazione, disoccupazione), "neu" = solo direzione (curva)
 const fr=(ora,prima,tipo)=>{if(ora==null||prima==null||Math.abs(ora-prima)<0.05)return `<i class="qe-fr flat" title="Stabile rispetto a 3 mesi prima">=</i>`;
  const su=ora>prima,cl=tipo=="neu"?"neu":((tipo=="bene")==su?"up":"down");
  return `<i class="qe-fr ${cl}" title="${su?"In salita":"In discesa"} rispetto a 3 mesi prima">${su?"&#9650;":"&#9660;"}</i>`;};
 const P=Q.prima||{};
 const ind=(nome,val,sotto,freccia)=>`<div class="qe-i"><small>${nome}</small><b>${val}${freccia}</b><span>${sotto}</span></div>`;
 // tabella storica della (i)
 const st=Q.storico,cel=x=>x?`<td class="num ${x[0]>=0?"up":"down"}">${pc(x[0])}</td>`:`<td class="num">n/d</td>`;
 const tab=st?`<table class="qe-tab"><tr><th>Fase</th><th class="num">S&amp;P 500</th><th class="num">Treasury</th><th class="num">Oro</th></tr>${ORD.filter(r=>st[r]).map(r=>`<tr${r==Q.regime?' class="on"':""}><td>${r}</td>${cel(st[r].sp)}${cel(st[r].tr)}${cel(st[r].oro)}</tr>`).join("")}</table>`:"";
 const info=`<details class="info"><summary title="Come si legge" aria-label="Come si legge">i</summary><div>
   <b>Fase del ciclo economico USA</b> (Ripresa, Espansione, Stagflazione, Recessione; in inglese Recovery, Overheat, Stagflation, Reflation) con gli ultimi dati disponibili. <b>Crescita</b>: produzione industriale sopra quella di un anno prima e nessun segnale della regola di Sahm. <b>Inflazione</b>: in salita se l'inflazione annua &egrave; pi&ugrave; alta di 6 mesi prima. Sotto il riquadro: <b>Deflazione</b> (prezzi in calo, sotto zero), <b>Disinflazione</b> (inflazione in calo), <b>Reflazione</b> (riparte da sotto il 2%, l'obiettivo della Fed), <b>In salita</b> (sale gi&agrave; da sopra il 2%).<br><br>
   <b>Regola di Sahm</b>: di quanto la disoccupazione (media 3 mesi) &egrave; salita dal minimo dell'ultimo anno; da 0,5 punti in su ha segnato l'inizio di ogni recessione USA dal 1970. <b>Curva 10-2</b>: tasso a 10 anni meno tasso a 2 anni; sotto zero (invertita) spesso anticipa una recessione. <b>Allarme</b>: Sahm da 0,5 in su, oppure curva invertita nell'ultimo anno con lo spread delle aziende pi&ugrave; indebitate salito di oltre 1 punto in 6 mesi.<br><br>
   ${tab?`<b>Com'&egrave; andata</b>: rendimento medio annuo del mese dopo, per fase, dal 1990 (oro dal 2004).${tab}`:""}
   <b>Solo contesto, non un segnale</b>: lo studio storico mostra che i mercati si muovono prima dei dati (in recessione l'S&amp;P 500 ha spesso gi&agrave; ripreso a salire). I portafogli seguono il filtro di trend sui prezzi, non questa card.</div></details>`;
 const f=FASI[Q.regime];
 el.innerHTML=`<div class="card qe"><div class="qe-t"><h3>Quadro economico USA</h3>${info}
   <span class="qe-al ${Q.allarme?"on":""}">${Q.allarme?"Allarme recessione":"Nessun allarme recessione"}</span></div>
  <div class="qe-main">
   <div class="qe-mappa" role="img" aria-label="Fase di oggi: ${Q.regime}"><span class="qe-ax qe-ay">Crescita &#9650;</span>
    ${ORD.map(r=>`<div class="qe-c ${FASI[r][1]}${r==Q.regime?" on":""}"><b>${r}</b>${r==Q.regime?`<span>oggi</span>`:""}</div>`).join("")}
    <span class="qe-ax qe-ax2">Inflazione &#9654;</span></div>
   <div class="qe-dx"><div class="qe-oggi"><b class="${f[1]}">${Q.regime}</b><span>L'economia ${f[0]} &middot; dati di ${mese}</span></div>
    <div class="qe-ind">
     ${ind("Inflazione",fx(Q.infl,1)+"%",`${Q.tipo_infl?`<em class="qe-ti">${Q.tipo_infl}</em> &middot; `:""}6 mesi fa ${fx(Q.infl6,1)}%`,fr(Q.infl,P.infl,"male"))}
     ${ind("Produzione",pc(Q.prod),"rispetto a un anno fa",fr(Q.prod,P.prod,"bene"))}
     ${ind("Disoccupazione",fx(Q.disoc,1)+"%",`Sahm ${fx(Q.sahm,2)} su 0,50`,fr(Q.disoc,P.disoc,"male"))}
     ${ind("Curva 10-2 anni",Q.curva==null?"n/d":(Q.curva>0?"+":"")+fx(Q.curva,2),Q.curva==null?"":Q.curva<0?"invertita":"normale",fr(Q.curva,P.curva,"neu"))}
    </div></div></div></div>`;
})();}catch(e){console.error("quadro economico",e);}
