/* ---------- v7.64/v7.65 AVVISO FESTIVITA' E ORARI (fascia fissa in cima alla Dashboard, sopra gli eventi) ----------
   Tutto automatico: compare SOLO quando serve e sparisce da solo.
   1) DATI RINVIATI: una festivita' federale USA sposta il COT (al lunedi') o il bilancio Fed (al venerdi'):
      D.sources[i].rinvio = nome della festa, da cot_radar/calendario.py. Resta fino all'ora di uscita.
   2) BORSE CHIUSE: festivita' di borsa di oggi e dei prossimi 3 giorni (ebMercati.feste, calendario EODHD).
      Resta fino all'ultimo giorno di chiusura compreso.
   3) FESTA FEDERALE USA con Wall Street aperta (Columbus Day, Veterans Day): Treasury chiusi, dati in ritardo.
   4) ORA LEGALE SFASATA tra USA e Italia: orari USA un'ora prima, fino al riallineamento.
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
 // ---- v7.65 FESTIVITA' FEDERALI USA calcolate qui (stesse regole di cot_radar/calendario.py): la fascia funziona
 //  anche se il sito non viene ricostruito. Sabato -> venerdi', domenica -> lunedi' (giorno "osservato").
 //  Columbus Day e Veterans Day: Wall Street resta APERTA ma Treasury e uffici federali chiudono (dati in ritardo).
 function festeUsa(y){const o={},p=n=>String(n).padStart(2,"0"),k=d=>d.getUTCFullYear()+"-"+p(d.getUTCMonth()+1)+"-"+p(d.getUTCDate());
  const oss=(m,g)=>{const d=new Date(Date.UTC(y,m-1,g)),w=d.getUTCDay();if(w==6)d.setUTCDate(g-1);if(w==0)d.setUTCDate(g+1);return k(d);};
  const nth=(m,wd,n)=>{if(n>0){const d=new Date(Date.UTC(y,m-1,1));d.setUTCDate(1+(wd-d.getUTCDay()+7)%7+7*(n-1));return k(d);}
   const d=new Date(Date.UTC(y,m,0));d.setUTCDate(d.getUTCDate()-(d.getUTCDay()-wd+7)%7);return k(d);};
  o[oss(1,1)]="Capodanno";o[nth(1,1,3)]="Martin Luther King Day";o[nth(2,1,3)]="Presidents' Day";o[nth(5,1,-1)]="Memorial Day";
  o[oss(6,19)]="Juneteenth";o[oss(7,4)]="Giorno dell'Indipendenza";o[nth(9,1,1)]="Labor Day";o[nth(10,1,2)]="Columbus Day";
  o[oss(11,11)]="Veterans Day";o[nth(11,4,4)]="Giorno del Ringraziamento";o[oss(12,25)]="Natale";return o;}
 // ---- v7.65 ORA LEGALE SFASATA: USA e Italia cambiano ora in date diverse (2-3 settimane a marzo, 1 a fine ottobre).
 //  In quei giorni New York e' a 5 ore da Roma invece di 6: tutti gli orari USA arrivano un'ora PRIMA in Italia.
 const oraIn=(fuso,d)=>{const x={};new Intl.DateTimeFormat("en-GB",{timeZone:fuso,hourCycle:"h23",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"})
   .formatToParts(d).forEach(q=>x[q.type]=+q.value);return Date.UTC(x.year,x.month-1,x.day,x.hour,x.minute);};
 const scarto=d=>Math.round((oraIn("Europe/Rome",d)-oraIn("America/New_York",d))/36e5);   // normale: 6
 function sfasata(){const ora=new Date();if(scarto(ora)==6)return null;
  for(let k=1;k<=40;k++){const d=new Date(ora.getTime()+k*864e5);if(scarto(d)==6)return d;}return ora;}
 function disegna(){const righe=[],oggi=romaYmd(new Date());
  // 1) dati rinviati da una festivita' USA (COT, bilancio Fed): fino all'ora di uscita
  (D.sources||[]).forEach(f=>{if(!f.rinvio||!f.next_ms||Date.now()>=f.next_ms)return;const cot=/^COT/.test(f.name||"");
   righe.push(`<b>${cot?"Report COT":esc(f.name)} rinviato</b> a ${esc(f.next||"")} per festivit&agrave; USA (${esc(f.rinvio)})${cot?": fino ad allora restano i segnali della settimana scorsa":""}.`);});
  // 2) borse chiuse per festivita' (oggi e i prossimi 3 giorni)
  const chiuse=window.ebMercati&&ebMercati.feste?ebMercati.feste(3):[];
  chiuse.forEach(f=>righe.push(`<b>${giornoTxt(f.ymd)} ${f.mercati.length>1?"borse chiuse":"borsa chiusa"}</b>: ${f.mercati.join(", ")} (${nomeIt(f.nome)}).`));
  // 3) festa federale USA con Wall Street aperta (oggi e i prossimi 3 giorni)
  for(let k=0;k<=3;k++){const ymd=romaYmd(new Date(Date.now()+k*864e5)),y=+ymd.slice(0,4),nome=festeUsa(y)[ymd]||festeUsa(y+1)[ymd];   // y+1: Capodanno di sabato si osserva il 31/12
   if(nome&&!chiuse.some(f=>f.ymd==ymd&&f.mercati.includes("USA")))
    righe.push(`<b>${giornoTxt(ymd)} festa federale USA</b> (${nome}): Wall Street aperta, mercato dei Treasury e uffici federali chiusi. I dati USA possono uscire in ritardo.`);}
  // 4) ora legale sfasata tra USA e Italia
  const fine=sfasata();
  if(fine){const t=romaYmd(fine).split("-");
   righe.push(`<b>Ora legale sfasata</b> tra USA e Italia fino al ${+t[2]}/${+t[1]}: gli orari USA arrivano un'ora prima (Wall Street 14:30-21:00, COT alle 20:30).`);}
  box.innerHTML=righe.length?`<div class="avv" role="status"><svg class="avv-i" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/></svg><div>${righe.map(r=>`<p>${r}</p>`).join("")}</div></div>`:"";}
 disegna();window.addEventListener("eb-mercati",disegna);setInterval(disegna,5*60*1000);   // il calendario arriva dopo; ogni 5 minuti si ricontrolla
})();}catch(e){fail("Avviso festivita'","avvisi",e);}
