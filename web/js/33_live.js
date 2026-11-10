/* ---------- v7.1 PREZZI INTRADAY (ritardo di borsa ~15-20 minuti) ----------
   Il workflow prezzi-live-continuo.yml (ciclo continuo, v7.24) scrive ogni 15 minuti (orari di borsa) il file live.json nel ramo "live" con i prezzi
   EODHD degli strumenti dei Portafogli. Qui lo si rilegge ogni minuto (solo con la pagina visibile) e si avvisano le
   schede interessate con l'evento "eb-live" (window.ebLive = dati). Le decisioni del modello restano sulle chiusure. */
try{(function(){
 const RAW="https://raw.githubusercontent.com/yahyaallouchi5-2025/cot-radar/live/live.json";
 let ultimo=0;
 async function leggi(){if(document.hidden)return;
  try{const r=await fetch(RAW+"?t="+Date.now(),{cache:"no-store"});if(!r.ok)return;const d=await r.json();
   if(!d||!d.quando||d.quando===ultimo)return;
   if(Date.now()/1000-d.quando>6*3600)return;            // dati di oltre 6 ore fa: non sono "intraday", si ignorano
   ultimo=d.quando;window.ebLive=d;window.dispatchEvent(new CustomEvent("eb-live",{detail:d}));}catch(e){}}
 leggi();setInterval(leggi,60000);document.addEventListener("visibilitychange",leggi);
})();}catch(e){console.warn("live",e);}
