/* ---------- CARRY TRADE (v6.61): vista "Carry" della scheda Backtest storico ----------
   Dati: D.carry (tassi attuali, paniere di oggi) e D.carry_st (studio storico mensile dal 1999, da verifica.json).
   Calcoli tutti in cot_radar/carry.py: qui solo la presentazione. Testi brevi in pagina, spiegazioni nelle (i).
   H = aiuti della scheda Verifica (kcard, infoBtn, infoP, pc): cosi' l'aspetto e' identico alle altre viste.
   Il grafico e' disegnato alla larghezza VERA del riquadro (come "Giorno per giorno"): linee sottili, testo nitido,
   dettaglio del mese al passaggio del mouse o al tocco. I pulsanti delle varianti ridisegnano SOLO la vista. */
const CR={v:"classico",H:null},CR_BREVE={classico:"Classico",trend:"+ trend",cot:"+ COT"};   // nomi corti (telefono)
try{const s=JSON.parse(localStorage.getItem("ebCarry")||"{}");if(["classico","trend","cot"].includes(s.v))CR.v=s.v;}catch(e){}

function ebCarryVista(H){CR.H=H;const S=D.carry_st,C=D.carry||{};
 if(!S||!S.varianti||!S.varianti[CR.v])return `<div class="card vfvuoto">Studio del carry non disponibile in questo aggiornamento.</div>`;
 return `<div id="crvista">${crCorpo()}</div>`;}

function crCorpo(){const H=CR.H,S=D.carry_st,C=D.carry||{},X=S.varianti[CR.v],pc=H.pc;
 const anno=m=>m?m.slice(0,4):"";const mese=m=>m?m.slice(5,7)+"/"+m.slice(0,4):"";
 const VERD={si:["si","VANTAGGIO DIMOSTRATO"],no:["no","NESSUN VANTAGGIO DIMOSTRATO"],peggio:["ko","PEGGIO DEL CASO"]};
 const vd=VERD[X.verdetto]||VERD.no,R=S.regole||{};
 // 1) verdetto + varianti
 const testa=`<div class="card vfverd ${vd[0]}"><div class="ptsth"><span class="vfvb">${vd[1]}</span>
   <span class="small">${esc(X.nome)} &middot; ${mese(X.dal)}&ndash;${mese(X.al)} &middot; ${X.n} mesi &middot; ${(R.valute||[]).length} valute</span>
   ${H.infoBtn("crinfo","Come funziona lo studio")}</div>
  ${H.infoP("crinfo",`Ogni fine mese le ${(R.valute||[]).length} valute (${(R.valute||[]).join(", ")}) sono ordinate per tasso d'interesse del <b>mese prima</b> (i dati OECD arrivano in ritardo: niente sbirciate al futuro). Si comprano le ${R.n_lato} con il tasso pi&ugrave; alto e si vendono le ${R.n_lato} con il tasso pi&ugrave; basso, per un mese. Guadagno = cambio + interessi. Costi: ${String(R.costo).replace(".",",")}% a ogni cambio di valuta + ${String(R.ricarico).replace(".",",")}% l'anno di ricarico del broker sugli swap. <b>+ trend</b>: una valuta resta solo se negli ultimi 3 mesi si &egrave; mossa nel verso giusto rispetto alle altre. <b>+ COT</b>: una valuta esce quando il COT &egrave; chiaramente contro (punteggio oltre ${R.cot_contro}). Vantaggio = rendimento sopra zero anche nel caso peggiore dell'intervallo al 95% (corretto per 3 varianti). Statistica del passato, non un consiglio.`)}</div>
  <div class="vfriga crvar"><div class="filters">${Object.entries(S.varianti).map(([k,x])=>`<button data-crv="${k}" class="${k==CR.v?"on":""}">${esc(x.nome)}</button>`).join("")}</div></div>`;
 // 2) quattro numeri chiave
 const kpi=`<div class="grid k4 vfkpi">
   ${H.kcard("crk1","Rendimento annuo",pc(X.cagr),"ultimi 5 anni "+pc(X.ultimi5),`Crescita media composta all'anno, costi inclusi, senza leva: 100 investiti diventano ${(100*X.curva[X.curva.length-1][1]).toFixed(0)} in ${Math.round(X.n/12)} anni. Negli ultimi 5 anni: ${pc(X.ultimi5)} l'anno.`,X.cagr>=0?"up":"down")}
   ${H.kcard("crk2","Drawdown massimo",pc(X.maxdd,1),"dal massimo precedente",`La perdita pi&ugrave; grande da un massimo al minimo successivo. Il carry guadagna piano e perde in fretta: questo &egrave; il numero da guardare per decidere quanto rischiare.`,"down")}
   ${H.kcard("crk3","Rendimento / rischio",X.rr==null?"n/d":X.rr.toLocaleString("it-IT",{minimumFractionDigits:2}),"volatilit&agrave; "+pc(X.vol,1),`Rendimento medio annuo diviso la volatilit&agrave; annua (${pc(X.vol,1)}). Sopra 0,5 &egrave; buono, sotto 0,3 &egrave; debole.`)}
   ${H.kcard("crk4","Mese peggiore",pc(X.peggior_mese[1],1),mese(X.peggior_mese[0])+" &middot; positivi "+X.positivi+"%",`Il mese con la perdita pi&ugrave; grande. I mesi chiusi in guadagno sono stati il ${X.positivi}%.`,"down")}</div>`;
 // 3) grafico della crescita (tutte le varianti, quella scelta in evidenza)
 const graf=`<div class="card vfgraf" id="crgraf"><div class="vfgtesta"><b>Crescita di 100 investiti ${H.infoBtn("crginfo","Come leggere il grafico")}</b>
   <div class="vfleg small crleg">${Object.entries(S.varianti).map(([k,x])=>`<span class="${k==CR.v?"on":""}"><i style="background:${crColore(k)}"></i>${esc(x.nome)}</span>`).join("")}</div></div>
   ${H.infoP("crginfo",`Valore di 100 investiti all'inizio, mese per mese, costi inclusi. La linea spessa &egrave; la variante scelta. Le fasce rosse sono i periodi di crisi: il carry tende a perdere tutto insieme quando i mercati hanno paura. Passa il mouse (o tocca) per i valori del mese.`)}
   <div class="vfgarea"><svg class="vfgsvg" role="img" aria-label="Crescita delle varianti del carry"></svg><div class="vfgtip" hidden></div></div></div>`;
 // 4) confronto delle varianti
 const VC={si:"s&igrave;",no:"no",peggio:"peggio"};
 const tab=`<h3 class="vft">Le tre varianti a confronto ${H.infoBtn("crtinfo","Cosa dice la tabella")}</h3>
  ${H.infoP("crtinfo",`Intervallo 95% = dove sta, con buona probabilit&agrave;, il rendimento medio annuo vero (corretto per 3 varianti). Vantaggio &laquo;s&igrave;&raquo; solo se anche il limite basso &egrave; sopra zero. Le crisi mostrano il risultato cumulato in quei mesi.`)}
  <div class="tablewrap"><table class="compatta crtab"><tr><th>Variante</th><th class="num">Annuo</th><th class="num crmob">Rend./rischio</th><th class="num">Drawdown</th><th class="num crmob">Intervallo 95%</th>${(X.stress||[]).map(s=>`<th class="num crmob">${esc(s[0])}</th>`).join("")}<th class="num">Vantaggio</th></tr>
  ${Object.entries(S.varianti).map(([k,x])=>`<tr class="${k==CR.v?"crsel":""}"><td><span class="crmob">${esc(x.nome)}</span><span class="crbreve">${CR_BREVE[k]||esc(x.nome)}</span></td><td class="num ${x.cagr>=0?"up":"down"}"><b>${pc(x.cagr)}</b></td>
   <td class="num crmob">${x.rr==null?"n/d":x.rr.toLocaleString("it-IT",{minimumFractionDigits:2})}</td><td class="num down">${pc(x.maxdd,1)}</td>
   <td class="num crmob">${pc(x.ic_anno[0],1)} &hellip; ${pc(x.ic_anno[1],1)}</td>${(x.stress||[]).map(s=>`<td class="num crmob ${s[1]>=0?"up":"down"}">${pc(s[1],1)}</td>`).join("")}
   <td class="num"><span class="ptv ${x.verdetto}">${VC[x.verdetto]||"no"}</span></td></tr>`).join("")}</table></div>`;
 // 5) paniere di oggi + tassi usati
 const T=C.tassi||{},P=C.paniere;
 const chip=(v,r,lato)=>`<span class="crchip ${lato}" title="${esc((T[v]||{}).nome||v)}"><b>${v}</b>${pc(r)}</span>`;
 const pan=P?`<h3 class="vft">Il paniere di oggi ${H.infoBtn("crpinfo","Cosa vuol dire")}</h3>
  ${H.infoP("crpinfo",`Le ${R.n_lato} valute che il carry classico comprerebbe e venderebbe oggi, con i tassi pi&ugrave; recenti. Carry del paniere = interessi annui incassati (tasso medio comprate &minus; tasso medio vendute), prima del ricarico del broker. Non tiene conto di COT e trend: guarda la tabella Forex per le coppie dove carry e COT vanno d'accordo.`)}
  <div class="card crpan"><div class="crlato"><span class="vfetich">Compra</span>${P.compra.map(x=>chip(x[0],x[1],"up")).join("")}</div>
   <div class="crlato"><span class="vfetich">Vendi</span>${P.vendi.map(x=>chip(x[0],x[1],"down")).join("")}</div>
   <div class="crtot">Carry del paniere <b class="up">${pc(P.carry)}</b> <span class="small">l'anno</span></div></div>`:"";
 const vec=Object.values(T).some(x=>x.vecchio);
 const tassi=`<details class="vfdett crtassi"><summary>Tassi d'interesse usati${vec?' <span class="tag">alcuni in ritardo</span>':""}</summary>
  <div class="tablewrap"><table class="compatta"><tr><th>Valuta</th><th class="num">Tasso</th><th class="num">Mese</th><th class="crmob">Fonte FRED</th></tr>
  ${Object.entries(T).sort((a,b)=>b[1].v-a[1].v).map(([v,x])=>`<tr><td><b>${v}</b> <span class="small crmob">${esc(x.nome)}</span></td><td class="num">${pc(x.v)}</td>
   <td class="num${x.vecchio?" crold":""}">${mese(x.mese)}${x.vecchio?' <span title="Dato vecchio: la fonte non ha ancora pubblicato i mesi recenti">&#9888;</span>':""}</td><td class="crmob small">${esc(x.fonte||"")}</td></tr>`).join("")}</table></div>
  <p class="small">Tassi interbancari a 3 mesi (OECD) o a brevissimo termine, mensili, con 1-2 mesi di ritardo. Il broker applica swap un po' peggiori.</p></details>`;
 setTimeout(crDisegna,0);
 return testa+kpi+graf+tab+pan+tassi;}

const crColore=k=>({classico:"var(--acc)",trend:"var(--b)",cot:"var(--warn)"}[k]||"var(--ink)");

/* grafico: crescita di 100 per ogni variante, fasce di crisi, dettaglio del mese al passaggio */
function crDisegna(){const box=document.getElementById("crgraf"),S=D.carry_st;if(!box||!S)return;
 const svg=box.querySelector(".vfgsvg"),W=Math.max(280,Math.round(svg.getBoundingClientRect().width||box.clientWidth-32));
 const mob=W<600,H=mob?230:270,L=mob?38:46,R=12,T=12,B=26;
 const V=Object.entries(S.varianti),mesi=V[0][1].curva.map(x=>x[0]),n=mesi.length;
 const val=V.flatMap(([k,x])=>x.curva.map(c=>c[1]*100));
 let lo=Math.min(100,...val),hi=Math.max(100,...val);const pad=(hi-lo)*0.06;lo-=pad;hi+=pad;
 const X=i=>L+i/Math.max(1,n-1)*(W-L-R),Y=v=>T+(hi-v)/(hi-lo)*(H-T-B);
 const grezzo=(hi-lo)/5,e=Math.pow(10,Math.floor(Math.log10(grezzo))),passo=[1,2,5,10].map(m=>m*e).find(x=>x>=grezzo);
 const tacche=[];for(let v=Math.ceil(lo/passo)*passo;v<=hi;v+=passo)tacche.push(v);
 const idx=m=>{const i=mesi.findIndex(x=>x>=m);return i<0?n-1:i;};
 // fasce di crisi (stessi periodi dello studio) + anni sull'asse orizzontale
 const crisi=[["2008-08","2008-12"],["2020-02","2020-03"],["2024-07","2024-08"]].filter(([a])=>a>=mesi[0]&&a<=mesi[n-1]);
 const passoA=mob?8:4,anni=[];for(let i=0;i<n;i++){const a=+mesi[i].slice(0,4);if(mesi[i].slice(5)=="01"&&a%passoA==0)anni.push(i);}
 svg.setAttribute("viewBox",`0 0 ${W} ${H}`);svg.style.height=H+"px";
 svg.innerHTML=`${crisi.map(([a,b])=>`<rect x="${X(idx(a)).toFixed(1)}" y="${T}" width="${Math.max(3,X(idx(b))-X(idx(a))).toFixed(1)}" height="${H-T-B}" class="crcrisi"/>`).join("")}
  ${tacche.map(v=>`<line x1="${L}" x2="${W-R}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" class="${Math.abs(v-100)<1e-9?"vfg0":"vfgl"}"/><text x="${L-6}" y="${(Y(v)+3.5).toFixed(1)}" text-anchor="end" class="vfax">${Math.round(v)}</text>`).join("")}
  ${anni.map(i=>`<text x="${X(i).toFixed(1)}" y="${H-8}" text-anchor="middle" class="vfax">${mesi[i].slice(0,4)}</text>`).join("")}
  ${V.filter(([k])=>k!=CR.v).concat(V.filter(([k])=>k==CR.v)).map(([k,x])=>`<path d="${x.curva.map((c,i)=>(i?"L":"M")+X(i).toFixed(1)+" "+Y(c[1]*100).toFixed(1)).join(" ")}" class="vfgln${k==CR.v?" crsel":" crfade"}" stroke="${crColore(k)}"/>`).join("")}
  <line class="vfgcur" y1="${T}" y2="${H-B}" x1="-10" x2="-10"/><g class="vfgpt"></g>
  <rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}" fill="transparent" class="vfghit"/>`;
 const tip=box.querySelector(".vfgtip"),cur=svg.querySelector(".vfgcur"),gp=svg.querySelector(".vfgpt"),hit=svg.querySelector(".vfghit");
 tip.hidden=true;
 const mostra=ev=>{const r=svg.getBoundingClientRect(),x=(ev.touches?ev.touches[0].clientX:ev.clientX)-r.left;
  const i=Math.max(0,Math.min(n-1,Math.round((x-L)/(W-L-R)*(n-1)))),px=X(i);
  cur.setAttribute("x1",px);cur.setAttribute("x2",px);
  gp.innerHTML=V.map(([k,x])=>`<circle cx="${px}" cy="${Y(x.curva[i][1]*100)}" r="${k==CR.v?3.5:2.5}" fill="${crColore(k)}" stroke="var(--card)" stroke-width="1.5"/>`).join("");
  tip.innerHTML=`<b>${mesi[i].slice(5,7)}/${mesi[i].slice(0,4)}</b>`+V.map(([k,x])=>`<span><i style="background:${crColore(k)}"></i>${esc(x.nome)} ${(x.curva[i][1]*100).toLocaleString("it-IT",{maximumFractionDigits:1})}</span>`).join("");
  tip.hidden=false;const tw=tip.offsetWidth;tip.style.left=Math.max(0,Math.min(r.width-tw,px+12>r.width-tw?px-tw-12:px+12))+"px";};
 hit.onmousemove=mostra;hit.onmouseleave=()=>{tip.hidden=true;cur.setAttribute("x1",-10);cur.setAttribute("x2",-10);gp.innerHTML="";};
 hit.ontouchstart=hit.ontouchmove=mostra;
 if(!CR.ro)CR.ro=new ResizeObserver(()=>{clearTimeout(CR.rt);CR.rt=setTimeout(crDisegna,80);});
 CR.ro.disconnect();CR.ro.observe(box);}

/* scelta della variante: ridisegna solo la vista del carry (la pagina resta ferma) */
document.addEventListener("click",e=>{const b=e.target.closest&&e.target.closest("#crvista [data-crv]");if(!b)return;
 CR.v=b.dataset.crv;try{localStorage.setItem("ebCarry",JSON.stringify({v:CR.v}));}catch(e){}
 const box=document.getElementById("crvista");if(!box)return;const h=box.offsetHeight;box.style.minHeight=h+"px";
 box.innerHTML=crCorpo();requestAnimationFrame(()=>{box.style.minHeight="";});});
