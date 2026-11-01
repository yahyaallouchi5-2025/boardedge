/* ---------- navigazione ----------
   Le schede sono <section>: si mostra solo quella con la classe "on". */
try{
// v6.67 SCHEDE RAGGRUPPATE: Dashboard, Portafogli e Azionario sempre visibili; le altre in tre menu (Mercati, Analisi,
// Ricerca). I bottoni veri delle schede restano dentro la barra (nascosti): link diretti, go(), feedback e statistiche
// funzionano come prima. Il menu che si vede e' una COPIA disegnata in fondo alla pagina (#ngmenu) sotto il bottone
// del gruppo: dentro la barra verrebbe tagliato (la barra scorre di lato sul telefono e ha lo sfondo sfocato).
// Si chiude scegliendo una scheda, cliccando fuori, con Esc o scorrendo la pagina. Il bottone del gruppo si colora
// quando la scheda aperta e' sua e ne mostra il nome.
const NGR=[...document.querySelectorAll("#nav .ngrp")];
const NGM=document.createElement("div");NGM.id="ngmenu";NGM.className="ngmenu";NGM.setAttribute("role","menu");NGM.hidden=true;document.body.appendChild(NGM);
let ngAperto=null;
function chiudiMenu(){ngAperto=null;NGM.hidden=true;NGR.forEach(g=>{g.classList.remove("aperto");g.querySelector(".ngb").setAttribute("aria-expanded","false");});}
function posiziona(){if(!ngAperto)return;const r=ngAperto.querySelector(".ngb").getBoundingClientRect(),w=Math.max(r.width,220);
 NGM.style.minWidth=w+"px";NGM.style.top=(r.bottom+6)+"px";NGM.style.left=Math.min(Math.max(8,r.left),window.innerWidth-NGM.offsetWidth-8)+"px";}
function apriMenu(g){chiudiMenu();ngAperto=g;g.classList.add("aperto");g.querySelector(".ngb").setAttribute("aria-expanded","true");
 // solo le schede visibili (es. "Registro" sparisce se il registro admin non e' pubblicato)
 NGM.innerHTML=[...g.querySelectorAll(".ngm button[data-t]")].filter(b=>b.style.display!="none")
  .map(b=>`<button type="button" role="menuitem" data-ng="${b.dataset.t}" class="${b.classList.contains("on")?"on":""}">${b.innerHTML}</button>`).join("");
 NGM.hidden=false;posiziona();
 NGM.querySelectorAll("[data-ng]").forEach(x=>x.onclick=()=>{const v=document.querySelector(`#nav button[data-t=${x.dataset.ng}]`);if(v)v.click();});}
function segnaGruppi(){NGR.forEach(g=>{const on=g.querySelector(".ngm button.on");g.classList.toggle("att",!!on);
 g.querySelector(".ngsel").textContent=on?on.textContent.trim():"";});}
NGR.forEach(g=>{g.querySelector(".ngb").onclick=e=>{e.stopPropagation();ngAperto==g?chiudiMenu():apriMenu(g);};});
document.addEventListener("click",e=>{if(ngAperto&&!e.target.closest("#ngmenu"))chiudiMenu();});
document.addEventListener("keydown",e=>{if(e.key=="Escape")chiudiMenu();});
window.addEventListener("scroll",chiudiMenu,{passive:true});window.addEventListener("resize",chiudiMenu);
$("nav").addEventListener("scroll",posiziona,{passive:true});      // la barra che scorre di lato riallinea il menu
document.querySelectorAll("#nav button[data-t]").forEach(b=>b.onclick=()=>{document.querySelectorAll("#nav button[data-t],section").forEach(x=>x.classList.remove("on"));
 b.classList.add("on");const sez=$(b.dataset.t);if(sez)sez.classList.add("on");chiudiMenu();segnaGruppi();window.scrollTo({top:0});});
var go=t=>document.querySelector(`#nav button[data-t=${t}]`).click();
document.addEventListener("click",ev=>{const a=ev.target.closest("[data-vai]");if(!a)return;ev.preventDefault();
 try{if(!$("tvmodal").hidden)chiudiGrafico();}catch(e){}go(a.dataset.vai);});
// LINK DIRETTO a una scheda (es. .../#registro dai messaggi Telegram): si apre dopo che tutte le schede sono pronte
// (solo schede che esistono davvero: "registro" sparisce quando il registro admin non e' pubblicato)
setTimeout(()=>{const t=location.hash.slice(1);if(/^[a-z]+$/.test(t)&&$(t)&&document.querySelector(`#nav button[data-t=${t}]`))go(t);},0);
}catch(e){fail('Navigazione','nav',e);}

/* ---------- grafici ----------
   spark(): mini linea senza assi.  lineChart(): grafico con assi, griglia e legenda.
   Entrambi producono SVG (grafica vettoriale): nitidi su qualsiasi schermo, nessuna libreria esterna. */
try{
function spark(v,col){v=v.filter(x=>x!=null);if(v.length<2)return"";const mn=Math.min(...v),mx=Math.max(...v),W=300,H=54;
 const p=v.map((y,i)=>`${(i/(v.length-1)*W).toFixed(1)},${(H-4-(y-mn)/((mx-mn)||1)*(H-8)).toFixed(1)}`).join(" ");
 return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><polyline points="${p}" fill="none" stroke="${col}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>`;}
function lineChart(x,series,unit){const W=760,H=280,L=48,R=16,T=14,B=30;const all=series.flatMap(s=>s.v.filter(v=>v!=null));
 if(!all.length)return"";let mn=Math.min(...all),mx=Math.max(...all);const pad=(mx-mn)*.08||.5;mn-=pad;mx+=pad;
 const X=i=>L+i/(x.length-1)*(W-L-R),Y=v=>T+(1-(v-mn)/(mx-mn))*(H-T-B);
 const ticks=[0,1,2,3,4].map(i=>mn+(mx-mn)*i/4);
 let g=ticks.map(t=>`<line x1="${L}" x2="${W-R}" y1="${Y(t)}" y2="${Y(t)}" stroke="var(--line)"/><text x="${L-8}" y="${Y(t)+4}" text-anchor="end" font-size="11" fill="var(--mute)">${t.toFixed(1)}${unit}</text>`).join("");
 const xi=[0,Math.floor((x.length-1)/2),x.length-1];g+=xi.map(i=>`<text x="${X(i)}" y="${H-8}" text-anchor="${i==0?'start':i==x.length-1?'end':'middle'}" font-size="11" fill="var(--mute)">${x[i]}</text>`).join("");
 series.forEach(s=>{let d="",pen=false;s.v.forEach((v,i)=>{if(v==null){pen=false;return;}d+=(pen?"L":"M")+X(i).toFixed(1)+","+Y(v).toFixed(1);pen=true;});
  g+=`<path d="${d}" fill="none" stroke="${s.c}" stroke-width="${s.w||2.2}" ${s.dash?'stroke-dasharray="5 4"':''} stroke-linejoin="round"/>`;
  const li=s.v.map((v,i)=>[v,i]).filter(p=>p[0]!=null).pop();if(li)g+=`<circle cx="${X(li[1])}" cy="${Y(li[0])}" r="3.5" fill="${s.c}"/>`;});
 return `<div class="legend">${series.map(s=>`<span><i style="background:${s.c}"></i>${s.n}</span>`).join("")}</div><svg class="chart" viewBox="0 0 ${W} ${H}">${g}</svg>`;}
}catch(e){fail('Grafici',null,e);}

