/* 31_paesi.js - PAESI EMERGENTI nella Dashboard (v6.72)
   Dati: D.paesi da cot_radar/paesi.py = {anno, agg, copia, fonte, paesi:[{iso,nome,area,pil,prec,prox,tend,inf,stato}]}
   gia' ordinati dal PIL piu' alto. I filtri non ricalcolano nulla: mostrano/nascondono le schede.
   Senza dati (FMI giu' e nessuna copia) il blocco intero sparisce. */
try{(function(){
 const P=D.paesi,blocco=$("peblocco");
 if(!P||!P.paesi||!P.paesi.length){if(blocco)blocco.style.display="none";return;}
 const A=P.anno,pct=v=>v==null?"n/d":(v>0?"+":"")+fx(v,1)+"%";
 // FILTRI: [etichetta, prova sulla riga]. "Tutti" sempre per primo
 const FIL=[["Tutti",r=>true],["In crescita",r=>r.stato=="crescita"],["In decrescita",r=>r.stato=="decrescita"],
            ["Accelerano",r=>r.tend>0],["Rallentano",r=>r.tend<0]];
 let sel="In crescita";                                     // si apre su chi cresce (la domanda piu' frequente)
 // SCHEDA di un paese: nome e area, PIL dell'anno grande, sotto previsione dell'anno prossimo e inflazione
 const scheda=r=>{const fr=r.tend>0?["&#9650;","up","accelera"]:r.tend<0?["&#9660;","down","rallenta"]:["=","flat","stabile"];
  return `<div class="card pecard" data-iso="${r.iso}"><div class="petesta"><b>${esc(r.nome)}</b><span class="small">${esc(r.area)}</span></div>
  <div class="pepil ${r.pil>0?"up":"down"}">${pct(r.pil)}</div><div class="small">PIL ${A}${r.prec!=null?` &middot; ${A-1}: ${pct(r.prec)}`:""}</div>
  <div class="perighe"><span>${A+1} <b class="${fr[1]}">${pct(r.prox)} ${fr[0]}</b></span><span>Inflazione ${A} <b>${pct(r.inf)}</b></span></div></div>`;};
 const disegna=()=>{const f=FIL.find(x=>x[0]==sel)[1],v=P.paesi.filter(f);
  $("pefiltri").querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.f==sel));
  $("pegrid").innerHTML=v.length?v.map(scheda).join(""):`<div class="card vuota">Nessun paese in questo gruppo.</div>`;};
 $("pefiltri").innerHTML=FIL.map(([n,f])=>`<button data-f="${n}">${n} <small>${P.paesi.filter(f).length}</small></button>`).join("");
 $("pefiltri").querySelectorAll("button").forEach(b=>b.onclick=()=>{sel=b.dataset.f;disegna();});
 $("pefonte").innerHTML=`Fonte: ${esc(P.fonte)}${P.agg?` &middot; scaricato il ${P.agg.split("-").reverse().join("/")}`:""}${P.copia?" &middot; ultima copia disponibile":""}`;
 disegna();
})();}catch(e){fail('Paesi emergenti','sig',e);}
