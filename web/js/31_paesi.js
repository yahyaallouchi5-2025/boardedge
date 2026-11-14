/* 31_paesi.js - PAESI EMERGENTI nella Dashboard: TABELLA economia + borsa (v7.67; prima erano schede col solo PIL)
   Dati: D.paesi da cot_radar/paesi.py = {anno, agg, copia, fonte, paesi:[{iso,nome,area,pil,prec,prox,tend,inf,stato,
         etf, b:{t,m1,a1,su,vb,vl,reg}}]}   (b = borsa del paese dall'ETF; manca se il paese non ha un ETF)
   Una riga per paese. Sul PC e' una tabella con le colonne ordinabili (clic sul titolo); sul telefono ogni riga
   diventa una scheda compatta con gli stessi numeri (stesso HTML, cambia solo la griglia: vedi .petab in stile.css).
   I filtri mostrano/nascondono le righe, non ricalcolano nulla. Senza dati il blocco intero sparisce. */
try{(function(){
 const P=D.paesi,blocco=$("peblocco");
 if(!P||!P.paesi||!P.paesi.length){if(blocco)blocco.style.display="none";return;}
 const A=P.anno,pct=v=>v==null?"&ndash;":(v>0?"+":"")+fx(v,1)+"%",vol=v=>v==null?"&ndash;":fx(v,0)+"%",cl=v=>v>0?"up":v<0?"down":"";
 const B=r=>r.b||{};
 // FILTRI: [etichetta, prova sulla riga]. "Tutti" sempre per primo
 const FIL=[["Tutti",r=>true],["In crescita",r=>r.stato=="crescita"],["In decrescita",r=>r.stato=="decrescita"],
            ["Borsa al rialzo",r=>B(r).su===true],["Borsa al ribasso",r=>B(r).su===false],["Agitati",r=>B(r).reg=="agitata"]];
 // COLONNE: [chiave, titolo, valore per l'ordinamento, HTML della cella, etichetta corta per il telefono]
 const REG={calma:["Calma","up"],normale:["Normale","flat"],agitata:["Agitata","down"]};
 const COL=[
  ["pil","PIL "+A,r=>r.pil,r=>`<span><b class="${cl(r.pil)}">${pct(r.pil)}</b><i class="pefr ${r.tend>0?"up":r.tend<0?"down":""}" title="${A+1}: ${pct(r.prox)}">${r.tend>0?"&#9650;":r.tend<0?"&#9660;":""}</i></span>`,"PIL"],
  ["m1","1 mese",r=>B(r).m1,r=>`<b class="${cl(B(r).m1)}">${pct(B(r).m1)}</b>`,"1 mese"],
  ["a1","12 mesi",r=>B(r).a1,r=>`<b class="${cl(B(r).a1)}">${pct(B(r).a1)}</b>`,"12 mesi"],
  ["su","Tendenza",r=>B(r).su==null?null:B(r).su?1:0,r=>B(r).su==null?"&ndash;":B(r).su?`<span class="up">&#9650; Rialzo</span>`:`<span class="down">&#9660; Ribasso</span>`,"Tendenza"],
  ["vb","Vol. breve",r=>B(r).vb,r=>vol(B(r).vb),"Vol. breve"],
  ["vl","Vol. lunga",r=>B(r).vl,r=>vol(B(r).vl),"Vol. lunga"],
  ["reg","Regime",r=>({calma:0,normale:1,agitata:2})[B(r).reg],r=>{const g=REG[B(r).reg];return g?`<span class="pereg ${g[1]}">${g[0]}</span>`:"&ndash;";},"Regime"]];
 const PRIMI=10;let tutti=false;                            // all'inizio i primi 10: il resto con "Mostra tutti"
 let sel="Tutti",ord="pil",giu=true;                        // si apre ordinata per PIL, dal piu' alto
 const riga=r=>`<div class="per" data-iso="${r.iso}"><div class="pen"><b>${esc(r.nome)}</b><span>${esc(r.area)}${r.etf?" &middot; "+esc(r.etf):""}</span></div>${
   COL.map(c=>`<div class="pec pec-${c[0]}" data-l="${c[4]}">${c[3](r)}</div>`).join("")}</div>`;
 const testa=()=>`<div class="per peth"><div class="pen pegr"><span></span><em>Economia</em><em>Borsa</em><em>Volatilit&agrave;</em></div><div class="pen">Paese</div>${
   COL.map(c=>`<button class="pec pec-${c[0]}${ord==c[0]?" on":""}" data-o="${c[0]}" title="Ordina">${c[1]}<i>${ord==c[0]?(giu?"&#9662;":"&#9652;"):""}</i></button>`).join("")}</div>`;
 const disegna=()=>{const f=FIL.find(x=>x[0]==sel)[1],c=COL.find(x=>x[0]==ord),v=P.paesi.filter(f);
  // ordinamento: i paesi senza il dato vanno sempre in fondo
  v.sort((a,b)=>{const x=c[2](a),y=c[2](b);if(x==null&&y==null)return 0;if(x==null)return 1;if(y==null)return -1;return giu?y-x:x-y;});
  $("pefiltri").querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.f==sel));
  const vis=tutti?v:v.slice(0,PRIMI);
  $("pegrid").innerHTML=v.length?testa()+vis.map(riga).join("")+(v.length>PRIMI?`<button class="pepiu" id="pepiu">${tutti?"Mostra meno":`Mostra tutti (${v.length})`}</button>`:""):`<div class="card vuota">Nessun paese in questo gruppo.</div>`;
  if($("pepiu"))$("pepiu").onclick=()=>{tutti=!tutti;disegna();};
  $("pegrid").querySelectorAll("button[data-o]").forEach(b=>b.onclick=()=>{if(ord==b.dataset.o)giu=!giu;else{ord=b.dataset.o;giu=true;}disegna();});};
 $("pefiltri").innerHTML=FIL.map(([n,f])=>`<button data-f="${n}">${n} <small>${P.paesi.filter(f).length}</small></button>`).join("");
 $("pefiltri").querySelectorAll("button").forEach(b=>b.onclick=()=>{sel=b.dataset.f;disegna();});
 const gg=d=>d?d.split("-").reverse().join("/"):"",ult=P.paesi.map(r=>B(r).t).filter(Boolean).sort().pop();
 $("pefonte").innerHTML=`Economia: ${esc(P.fonte)}${P.agg?` (${gg(P.agg)})`:""}${P.copia?", ultima copia":""}${ult?` &middot; Borsa: prezzi al ${gg(ult)}`:""}`;
 disegna();
})();}catch(e){fail('Paesi emergenti','sig',e);}
