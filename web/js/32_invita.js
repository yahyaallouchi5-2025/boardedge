/* ---------- v6.94 LOGO E INVITA AMICI ----------
   1) LOGO: il marchio BoardEdge (barra laterale e in alto) riporta alla Dashboard, senza ricaricare la pagina.
   2) INVITA AMICI: su telefono apre la condivisione del sistema (WhatsApp, Telegram...); dove non c'e' (PC),
      copia il link della pagina di presentazione e lo conferma con un piccolo avviso che sparisce da solo. */
try{(function(){
 const LINK=EB_SITO;              // pagina di presentazione (landing)
 const TESTO="BoardEdge: analisi dei mercati (COT, forex, portafogli) gratis. Dai un'occhiata:";
 document.querySelectorAll(".blhome").forEach(a=>a.addEventListener("click",e=>{
  e.preventDefault();
  if(typeof go=="function")go("sig");                                       // stessa funzione delle schede
  try{history.replaceState(null,"","#sig");}catch(x){}
  document.documentElement.classList.remove("sideon");const o=$("sombra");if(o)o.hidden=true;   // telefono: chiude il menu
  window.scrollTo({top:0,behavior:"smooth"});}));
 function avviso(t){                                                         // piccolo avviso in basso, 2,5 secondi
  let d=document.querySelector(".invavv");if(!d){d=document.createElement("div");d.className="invavv";d.setAttribute("role","status");document.body.appendChild(d);}
  d.textContent=t;d.classList.add("on");clearTimeout(d._t);d._t=setTimeout(()=>d.classList.remove("on"),2500);}
 const b=$("invita");if(!b)return;
 b.onclick=async()=>{
  if(navigator.share){try{await navigator.share({title:"BoardEdge",text:TESTO,url:LINK});return;}catch(e){if(e&&e.name=="AbortError")return;}}
  try{await navigator.clipboard.writeText(TESTO+" "+LINK);avviso("Link copiato: incollalo dove vuoi");}
  catch(e){prompt("Copia il link:",LINK);}};
})();}catch(e){console.warn("invita",e);}
