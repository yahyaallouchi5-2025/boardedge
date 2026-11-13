/* ---------- v7.64 AVVISO FESTIVITA' (fascia fissa in cima alla Dashboard, sopra gli eventi) ----------
   Compare SOLO quando serve e sparisce da sola:
   1) COT RINVIATO: una festivita' federale USA tra martedi' e venerdi' sposta il report al lunedi' dopo
      (D.sources[0].rinvio = nome della festa, da cot_radar/calendario.py). Resta fino all'ora di uscita.
   2) BORSE CHIUSE: festivita' di borsa di oggi e dei prossimi 3 giorni (ebMercati.feste, calendario EODHD).
      Resta fino all'ultimo giorno di chiusura compreso.
   Una riga per avviso, testo breve. DEBUG: F12 -> Console -> ebMercati.feste(30) */
try{(function(){const ev=$("eventi");if(!ev)return;
 const box=document.createElement("div");box.id="avvisi";ev.before(box);
 // nomi delle festivita' di borsa in italiano (il calendario EODHD li da' in inglese)
 const IT=[[/thanksgiving/i,"Giorno del Ringraziamento"],[/christmas eve/i,"Vigilia di Natale"],[/christmas/i,"Natale"],[/boxing/i,"Santo Stefano"],
  [/new year.?s eve/i,"San Silvestro"],[/new year/i,"Capodanno"],[/good friday/i,"Venerd&igrave; Santo"],[/easter monday/i,"Pasquetta"],
  [/labou?r/i,"Festa del lavoro"],[/independence/i,"Giorno dell'Indipendenza"],[/memorial/i,"Memorial Day"],[/juneteenth/i,"Juneteenth"],
  [/martin luther|mlk/i,"Martin Luther King Day"],[/president|washington/i,"Presidents' Day"]];
 const nomeIt=n=>{const x=IT.find(r=>r[0].test(n||""));return x?x[1]:esc(n||"festivit&agrave;");};
 const GGL=["domenica","luned&igrave;","marted&igrave;","mercoled&igrave;","gioved&igrave;","venerd&igrave;","sabato"];
 const romaYmd=d=>new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Rome"}).format(d);
 function giornoTxt(ymd){const oggi=romaYmd(new Date()),dom=romaYmd(new Date(Date.now()+864e5));
  if(ymd==oggi)return "Oggi";if(ymd==dom)return "Domani";
  const [y,m,g]=ymd.split("-").map(Number),t=GGL[new Date(Date.UTC(y,m-1,g)).getUTCDay()];
  return t.charAt(0).toUpperCase()+t.slice(1)+" "+g+"/"+m;}
 function disegna(){const righe=[],cot=(D.sources||[])[0]||{};
  if(cot.rinvio&&cot.next_ms&&Date.now()<cot.next_ms)
   righe.push(`<b>Report COT rinviato</b> a ${esc(cot.next||"")} per festivit&agrave; USA (${esc(cot.rinvio)}): fino ad allora restano i segnali della settimana scorsa.`);
  (window.ebMercati&&ebMercati.feste?ebMercati.feste(3):[]).forEach(f=>
   righe.push(`<b>${giornoTxt(f.ymd)} ${f.mercati.length>1?"borse chiuse":"borsa chiusa"}</b>: ${f.mercati.join(", ")} (${nomeIt(f.nome)}).`));
  box.innerHTML=righe.length?`<div class="avv" role="status"><svg class="avv-i" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/></svg><div>${righe.map(r=>`<p>${r}</p>`).join("")}</div></div>`:"";}
 disegna();window.addEventListener("eb-mercati",disegna);setInterval(disegna,5*60*1000);   // il calendario arriva dopo; ogni 5 minuti si ricontrolla
})();}catch(e){fail("Avviso festivita'","avvisi",e);}
