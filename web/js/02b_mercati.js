/* ---------- v7.25 STATO DEI MERCATI con FESTIVITA' (una sola fonte per tutte le schede) ----------
   Dati: ../azioni/calendario.json (cot_radar/orari_borse.py, da EODHD, aggiornato ogni settimana): per ogni borsa
   fuso, orari, giorni lavorativi e festivita'. Finche' il file non arriva (o se manca) valgono gli orari fissi qui
   sotto, senza festivita'.
   window.ebMercati:
     .html()           badge "Aperti: ..." (verde) o "Mercati chiusi · apre ..." (rosso lampeggiante) + (i)
     .stato(gruppo)    {aperto, prossima: Date|null, festivo: nome|null} per "USA", "Canada", "Europa", "Londra", "Australia"
     .oraIt(data)      "mar 10/11, 09:00" in ora italiana
   Quando il calendario arriva si lancia l'evento "eb-mercati" (le schede ridisegnano il badge).
   DEBUG: F12 -> Console -> ebMercati.stato("USA") */
try{(function(){
 const BASE={US:["America/New_York","09:30","16:00"],TO:["America/Toronto","09:30","16:00"],XETRA:["Europe/Berlin","09:00","17:30"],
  LSE:["Europe/London","08:00","16:30"],PA:["Europe/Paris","09:00","17:30"],AS:["Europe/Amsterdam","09:00","17:30"],
  MC:["Europe/Madrid","09:00","17:30"],MI:["Europe/Rome","09:00","17:30"],AU:["Australia/Sydney","10:00","16:00"]};
 const GRUPPI=[["USA",["US"]],["Canada",["TO"]],["Europa",["XETRA","MI","PA","AS","MC"]],["Londra",["LSE"]],["Australia",["AU"]]];
 let CAL=null;
 const fmt={};                                           // un formattatore per fuso (veloce: si chiama migliaia di volte)
 function loc(fuso,d){const f=fmt[fuso]||(fmt[fuso]=new Intl.DateTimeFormat("en-CA",{timeZone:fuso,year:"numeric",month:"2-digit",day:"2-digit",weekday:"short",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}));
  const x={};f.formatToParts(d).forEach(p=>x[p.type]=p.value);
  return {wd:["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].indexOf(x.weekday),hm:x.hour+":"+x.minute,ymd:x.year+"-"+x.month+"-"+x.day};}
 function info(b){const c=CAL&&CAL.borse&&CAL.borse[b],z=BASE[b];
  return {fuso:(c&&c.fuso)||z[0],apre:(c&&c.apre)||z[1],chiude:(c&&c.chiude)||z[2],giorni:(c&&c.giorni)||[0,1,2,3,4],festivi:(c&&c.festivi)||{}};}
 function apertaB(b,d){const i=info(b),l=loc(i.fuso,d);return i.giorni.includes(l.wd)&&!i.festivi[l.ymd]&&l.hm>=i.apre&&l.hm<i.chiude;}
 const membri=g=>(GRUPPI.find(x=>x[0]==g)||[0,[]])[1];
 const apertoG=(g,d)=>membri(g).some(b=>apertaB(b,d));
 function prossima(g,d){let t=new Date(Math.ceil(d.getTime()/6e5)*6e5);          // griglia di 10 minuti, fino a 10 giorni
  for(let k=0;k<1440;k++,t=new Date(t.getTime()+6e5))if(apertoG(g,t))return t;return null;}
 function festivoG(g,d){for(const b of membri(g)){const i=info(b),l=loc(i.fuso,d);if(i.festivi[l.ymd]&&i.giorni.includes(l.wd))return i.festivi[l.ymd];}return null;}
 const oraIt=t=>t.toLocaleString("it-IT",{timeZone:"Europe/Rome",weekday:"short",day:"numeric",month:"numeric",hour:"2-digit",minute:"2-digit"});
 function stato(g,d){d=d||new Date();const a=apertoG(g,d);return {aperto:a,prossima:a?null:prossima(g,d),festivo:festivoG(g,d)};}
 function html(){const ora=new Date(),S=GRUPPI.map(([g])=>[g,stato(g,ora)]);
  const aperti=S.filter(x=>x[1].aperto).map(x=>x[0]),prox=S.filter(x=>!x[1].aperto&&x[1].prossima).sort((a,b)=>a[1].prossima-b[1].prossima);
  const feste=S.filter(x=>x[1].festivo).map(x=>`<b>${x[0]}</b> (${esc(x[1].festivo)})`);
  const testo=`${aperti.length?`<b>Mercati aperti (${aperti.join(", ")})</b>: i prezzi accanto ai titoli si aggiornano da soli con circa 15 minuti di ritardo (punto verde).`:`<b>Mercati chiusi</b>: accanto ai titoli c'&egrave; il prezzo di chiusura dell'ultima seduta.`}`
   +(feste.length?`<br>Oggi chiuse per festivit&agrave;: ${feste.join(", ")}.`:"")
   +(prox.length?`<br>Prossime aperture: ${prox.map(x=>`<b>${x[0]}</b> ${oraIt(x[1].prossima)}`).join(", ")}.`:"")
   +`<br>Orari e festivit&agrave; ufficiali di ogni borsa${CAL?"":" (calendario in caricamento: per ora solo gli orari)"}. Un ordine inviato a mercato chiuso viene eseguito all'apertura, al prezzo di quel momento.`;
  const i=`<details class="info"><summary title="Stato dei mercati" aria-label="Informazioni">i</summary><div>${testo}</div></details>`;
  return aperti.length?`<span class="azmk on"><i></i>Aperti: ${aperti.join(" + ")}</span>${i}`
   :`<span class="azmk off"><i></i>Mercati chiusi${prox.length?` &middot; apre ${prox[0][0]} ${oraIt(prox[0][1].prossima)}`:""}</span>${i}`;}
 window.ebMercati={html,stato,oraIt,aperta:apertaB};
 fetch("../azioni/calendario.json",{cache:"no-cache"}).then(r=>r.ok?r.json():null).then(c=>{if(c&&c.borse){CAL=c;window.dispatchEvent(new Event("eb-mercati"));}}).catch(()=>{});
})();}catch(e){console.warn("mercati",e);}
