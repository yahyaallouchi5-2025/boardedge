
/* ---------- ESPORTAZIONE PDF (v6.78) ----------
   Generatore PDF scritto da zero, SENZA librerie esterne (niente CDN, niente chiavi): il file nasce nel browser
   e si scarica subito, su telefono e su PC. Lo usano Portafogli (21_portafogli.js) e Azionario (22_azioni.js).
   COME FUNZIONA
   - pagine A4 (verticale o orizzontale), coordinate in punti (1 pt = 1/72 di pollice) misurate DALL'ALTO;
   - testo con i caratteri standard Helvetica e Helvetica-Bold (presenti in ogni lettore PDF, nessun font da
     incorporare) con codifica WinAnsi: accenti italiani ed euro inclusi; i caratteri fuori codifica si sostituiscono
     (es. freccia -> "->"). Le larghezze dei caratteri (W1/W2, millesimi della dimensione) servono per allineare a
     destra, centrare e andare a capo;
   - grafici disegnati come vettori (linee, poligoni, anelli): nitidi a ogni zoom e leggeri;
   - salva(): unisce gli oggetti PDF, scrive la tabella xref e scarica il file con un link temporaneo.
   DEBUG: se il PDF non si apre, F12 -> Console; un PDF valido inizia con "%PDF-1.4" e finisce con "%%EOF". */
try{(function(){
 // larghezze Helvetica / Helvetica-Bold per i codici 32..255 (WinAnsi), in millesimi della dimensione del testo
 const W1=[278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,500,500,500,334,260,334,584,761,556,761,222,556,333,1000,556,556,333,1000,667,333,1000,761,611,761,761,222,222,333,333,350,556,1000,333,1000,500,333,944,761,500,667,278,333,556,556,556,556,260,556,333,737,370,556,584,333,737,333,400,584,333,333,333,556,537,278,333,333,365,556,834,834,834,611,667,667,667,667,667,667,1000,722,667,667,667,667,278,278,278,278,722,722,778,778,778,778,778,584,778,722,722,722,722,667,667,611,556,556,556,556,556,556,889,500,556,556,556,556,278,278,278,278,556,556,556,556,556,556,556,584,611,556,556,556,556,500,556,500],W2=[278,333,474,556,556,889,722,238,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,333,333,584,584,584,611,975,722,722,722,722,667,611,778,722,278,556,722,611,833,722,778,667,778,722,667,611,722,667,944,667,667,611,333,278,333,584,556,333,556,611,556,611,556,333,611,611,278,278,556,278,889,611,611,611,611,389,556,333,611,556,778,556,556,500,389,280,389,584,761,556,761,278,556,500,1000,556,556,333,1000,667,333,1000,761,611,761,761,278,278,500,500,350,556,1000,333,1000,556,333,944,761,500,667,278,333,556,556,556,556,280,556,333,737,370,556,584,333,737,333,400,584,333,333,333,611,556,278,333,333,365,556,834,834,834,611,722,722,722,722,722,722,1000,722,667,667,667,667,278,278,278,278,722,722,778,778,778,778,778,584,778,722,722,722,722,667,667,611,556,556,556,556,556,556,889,556,556,556,556,556,278,278,278,278,611,611,611,611,611,611,611,584,611,611,611,611,611,556,611,556];
 // caratteri Unicode che in WinAnsi stanno nei codici 128-159
 const SPEC={8364:128,8218:130,402:131,8222:132,8230:133,8224:134,8225:135,710:136,8240:137,352:138,8249:139,338:140,381:142,8216:145,8217:146,8220:147,8221:148,8226:149,8211:150,8212:151,732:152,8482:153,353:154,8250:155,339:156,382:158,376:159};
 // sostituzioni per i caratteri che WinAnsi non ha
 const SOST={8722:"-",8594:"->",8592:"<-",8805:">=",8804:"<=",8239:" ",8201:" ",8202:" ",9650:"+",9660:"-"};
 function codici(s){const o=[];for(const ch of String(s==null?"":s)){const c=ch.codePointAt(0);
   if(SOST[c]!=null){for(const x of SOST[c])o.push(x.charCodeAt(0));continue;}
   if(c<32)continue;if(c<128||(c>=160&&c<256))o.push(c);else if(SPEC[c])o.push(SPEC[c]);else o.push(63);}   // 63 = "?"
  return o;}
 const larg=(cod,sz,b)=>{const W=b?W2:W1;let w=0;for(const c of cod)w+=W[c-32]||556;return w*sz/1000;};
 // stringa PDF: parentesi e barra rovesciata con "\", codici fuori ASCII in ottale
 const escP=cod=>cod.map(c=>c==40||c==41||c==92?"\\"+String.fromCharCode(c):c<32||c>126?"\\"+c.toString(8).padStart(3,"0"):String.fromCharCode(c)).join("");
 const n2=v=>String(Math.round(v*100)/100);
 const rgb=h=>{h=String(h||"#000").replace("#","");return [0,2,4].map(i=>(parseInt(h.slice(i,i+2),16)/255).toFixed(3)).join(" ");};
 // colore mescolato col bianco (a = intensita' 0..1): serve per le caselle "trasparenti" della heat map
 const chiaro=(h,a)=>{h=h.replace("#","");return "#"+[0,2,4].map(i=>{const v=parseInt(h.slice(i,i+2),16);return Math.round(255-(255-v)*a).toString(16).padStart(2,"0");}).join("");};

})();}catch(e){console.error("[BoardEdge] pdf:",e);}
