
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

 // colori della stampa: stessi toni della pagina, scuriti per leggerli su carta bianca
 const C={ink:"#14202e",mute:"#5d6b80",line:"#d5dde8",soft:"#f3f6fa",acc:"#1a9e93",up:"#11935f",down:"#d2453f",navy:"#0a1628",warn:"#c98a14",bianco:"#ffffff"};

 function Doc(o){o=o||{};const land=!!o.land,PW=land?841.89:595.28,PH=land?595.28:841.89,M=36;
  const pg=[];let cur=null;
  const d={PW,PH,M,C,
   // nuova pagina (diventa quella su cui si disegna)
   pagina(){cur=[];pg.push(cur);return d;},
   larghezza(s,sz,b){return larg(codici(s),sz||9,b);},
   // testo: y = linea di base misurata dall'alto; op.a = "l" | "r" | "c"
   testo(x,y,s,op){op=op||{};const sz=op.s||9,b=!!op.b,cod=codici(s),w=larg(cod,sz,b);
    const x0=op.a=="r"?x-w:op.a=="c"?x-w/2:x;
    cur.push(`BT ${rgb(op.c||C.ink)} rg /F${b?2:1} ${n2(sz)} Tf ${n2(x0)} ${n2(PH-y)} Td (${escP(cod)}) Tj ET`);return w;},
   // testo troncato con "..." se supera la larghezza w
   taglia(s,w,sz,b){s=String(s==null?"":s);if(d.larghezza(s,sz,b)<=w)return s;let t=s;
    while(t.length>1&&d.larghezza(t+"…",sz,b)>w)t=t.slice(0,-1);return t.trimEnd()+"…";},
   // a capo automatico: righe che stanno nella larghezza w
   righe(s,w,sz,b){const out=[];let r="";for(const p of String(s||"").split(/\s+/)){if(!p)continue;const t=r?r+" "+p:p;
     if(r&&d.larghezza(t,sz,b)>w){out.push(r);r=p;}else r=t;}if(r)out.push(r);return out;},
   // paragrafo a capo automatico; ritorna l'altezza occupata
   paragrafo(x,y,s,w,op){op=op||{};const sz=op.s||9,lh=op.lh||sz*1.38,r=d.righe(s,w,sz,op.b);r.forEach((t,i)=>d.testo(x,y+i*lh,t,op));
    return r.length*lh;},
   // rettangolo (y = bordo alto), con angoli arrotondati se op.r
   rett(x,y,w,h,op){op=op||{};const yy=PH-y-h,r=Math.min(op.r||0,w/2,h/2);let p;
    if(r>0){const k=r*.5523;p=`${n2(x+r)} ${n2(yy)} m ${n2(x+w-r)} ${n2(yy)} l ${n2(x+w-r+k)} ${n2(yy)} ${n2(x+w)} ${n2(yy+r-k)} ${n2(x+w)} ${n2(yy+r)} c `+
     `${n2(x+w)} ${n2(yy+h-r)} l ${n2(x+w)} ${n2(yy+h-r+k)} ${n2(x+w-r+k)} ${n2(yy+h)} ${n2(x+w-r)} ${n2(yy+h)} c ${n2(x+r)} ${n2(yy+h)} l `+
     `${n2(x+r-k)} ${n2(yy+h)} ${n2(x)} ${n2(yy+h-r+k)} ${n2(x)} ${n2(yy+h-r)} c ${n2(x)} ${n2(yy+r)} l ${n2(x)} ${n2(yy+r-k)} ${n2(x+r-k)} ${n2(yy)} ${n2(x+r)} ${n2(yy)} c h`;}
    else p=`${n2(x)} ${n2(yy)} ${n2(w)} ${n2(h)} re`;
    cur.push(`${op.f?rgb(op.f)+" rg ":""}${op.s?rgb(op.s)+" RG "+n2(op.lw||.6)+" w ":""}${p} ${op.f&&op.s?"B":op.f?"f":"S"}`);},
   linea(x1,y1,x2,y2,op){op=op||{};cur.push(`${rgb(op.c||C.line)} RG ${n2(op.lw||.6)} w ${op.tratt?"["+op.tratt.join(" ")+"] 0 d ":""}${n2(x1)} ${n2(PH-y1)} m ${n2(x2)} ${n2(PH-y2)} l S${op.tratt?" [] 0 d":""}`);},
   // spezzata o poligono: pts = [[x,y],...] con y dall'alto
   poli(pts,op){op=op||{};if(pts.length<2)return;const p=pts.map((q,i)=>`${n2(q[0])} ${n2(PH-q[1])} ${i?"l":"m"}`).join(" ");
    cur.push(`${op.f?rgb(op.f)+" rg ":""}${op.s?rgb(op.s)+" RG "+n2(op.lw||1)+" w 1 j 1 J ":""}${op.tratt?"["+op.tratt.join(" ")+"] 0 d ":""}${p}${op.f?" h":""} ${op.f&&op.s?"B":op.f?"f":"S"}${op.tratt?" [] 0 d":""}`);},
   // spicchio di anello (ciambella): angoli in gradi, 0 = in alto, senso orario
   anello(cx,cy,r0,r1,a0,a1,col){const pts=[],n=Math.max(2,Math.ceil((a1-a0)/3)),P=(r,a)=>[cx+r*Math.sin(a*Math.PI/180),cy-r*Math.cos(a*Math.PI/180)];
    for(let i=0;i<=n;i++)pts.push(P(r1,a0+(a1-a0)*i/n));for(let i=n;i>=0;i--)pts.push(P(r0,a0+(a1-a0)*i/n));d.poli(pts,{f:col});},
   cerchio(cx,cy,r,col){d.anello(cx,cy,0,r,0,360,col);},
   // spazio rimasto: se il blocco alto h non entra, nuova pagina con la testata ridotta; ritorna la y da usare
   serve(y,h,titolo){if(y+h<=PH-46)return y;d.pagina();return testataMini(d,titolo);},
   // unisce tutto e scarica; piede(n, totale) disegna il fondo di ogni pagina
   salva(nome,titolo,piedeF){
    if(piedeF)pg.forEach((p,i)=>{cur=p;piedeF(i+1,pg.length);});
    let out="%PDF-1.4\n%\xe2\xe3\xcf\xd3\n";const off=[],N=pg.length,info=5+2*N;
    const add=(n,b)=>{off[n]=out.length;out+=n+" 0 obj\n"+b+"\nendobj\n";};
    add(1,"<< /Type /Catalog /Pages 2 0 R >>");
    add(2,`<< /Type /Pages /Kids [${pg.map((_,i)=>(6+2*i)+" 0 R").join(" ")}] /Count ${N} >>`);
    add(3,"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");
    add(4,"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>");
    pg.forEach((p,i)=>{const s=p.join("\n");add(5+2*i,`<< /Length ${s.length} >>\nstream\n${s}\nendstream`);
     add(6+2*i,`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${n2(PW)} ${n2(PH)}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${5+2*i} 0 R >>`);});
    const z=x=>String(x).padStart(2,"0"),t=new Date();
    add(info,`<< /Title (${escP(codici(titolo))}) /Creator (BoardEdge) /Producer (BoardEdge) /CreationDate (D:${t.getFullYear()}${z(t.getMonth()+1)}${z(t.getDate())}${z(t.getHours())}${z(t.getMinutes())}${z(t.getSeconds())}) >>`);
    const x0=out.length;out+=`xref\n0 ${info+1}\n0000000000 65535 f \n`;
    for(let i=1;i<=info;i++)out+=String(off[i]).padStart(10,"0")+" 00000 n \n";
    out+=`trailer\n<< /Size ${info+1} /Root 1 0 R /Info ${info} 0 R >>\nstartxref\n${x0}\n%%EOF\n`;
    const by=new Uint8Array(out.length);for(let i=0;i<out.length;i++)by[i]=out.charCodeAt(i)&255;
    if(nome)scarica(new Blob([by],{type:"application/pdf"}),nome);return by;}};
  return d;}

 // download senza aprire nuove schede: link temporaneo con l'attributo download (telefono e PC)
 function scarica(blob,nome){const u=URL.createObjectURL(blob),a=document.createElement("a");a.href=u;a.download=nome;a.rel="noopener";
  document.body.appendChild(a);a.click();setTimeout(()=>{a.remove();URL.revokeObjectURL(u);},4000);}

 const ora=()=>{const t=new Date(),z=x=>String(x).padStart(2,"0");return `${z(t.getDate())}/${z(t.getMonth()+1)}/${t.getFullYear()} ${z(t.getHours())}:${z(t.getMinutes())}`;};
 // nome del file: BoardEdge-<parte>-AAAA-MM-GG.pdf (senza spazi e accenti)
 const nomeFile=parte=>{const t=new Date(),z=x=>String(x).padStart(2,"0");
  return `BoardEdge-${String(parte).normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/[^A-Za-z0-9]+/g,"-").replace(/^-|-$/g,"")}-${t.getFullYear()}-${z(t.getMonth()+1)}-${z(t.getDate())}.pdf`;};
 // marchio: quadratino turchese + "BoardEdge" (stesso nome e colore della pagina)
 function marchio(d,x,y,sz,col){d.rett(x,y-sz*.78,sz*.78,sz*.78,{f:C.acc,r:sz*.18});return d.testo(x+sz,y,"BoardEdge",{s:sz,b:true,c:col});}
 // testata della prima pagina: fascia blu notte, titolo e sottotitolo; ritorna la y da cui partire
 function testata(d,titolo,sotto){const {PW,M}=d;d.rett(0,0,PW,50,{f:C.navy});marchio(d,M,31,15,C.bianco);
  d.testo(PW-M,30,"Creato il "+ora(),{s:8.5,c:"#a9b8d0",a:"r"});
  d.testo(M,86,titolo,{s:19,b:true});let y=86;if(sotto)y+=6+d.paragrafo(M,y+16,sotto,PW-2*M,{s:9.5,c:C.mute});
  return y+22;}
 function testataMini(d,titolo){const {PW,M}=d;d.rett(0,0,PW,26,{f:C.navy});marchio(d,M,17.5,10,C.bianco);
  d.testo(PW-M,17,titolo||"",{s:8.5,c:"#a9b8d0",a:"r"});return 52;}
 // piede comune: avviso e numero di pagina
 function piede(d,n,tot,fonte){const {PW,PH,M}=d;d.linea(M,PH-34,PW-M,PH-34,{c:C.line});
  d.testo(M,PH-22,d.taglia((fonte?fonte+" · ":"")+"Solo a scopo educativo, non consulenza finanziaria. Si pu\u00f2 perdere il capitale anche senza leva. I risultati passati non garantiscono quelli futuri.",PW-2*M-70,7.2),{s:7.2,c:C.mute});
  d.testo(PW-M,PH-22,`Pagina ${n} di ${tot}`,{s:7.2,c:C.mute,a:"r"});}
 // titolo di sezione con filetto turchese a sinistra; ritorna la y sotto il titolo
 function sezione(d,y,t,sub){d.rett(d.M,y-11,3,14,{f:C.acc});d.testo(d.M+10,y,t,{s:12.5,b:true});
  if(sub)d.testo(d.M+16+d.larghezza(t,12.5,true),y,d.taglia(sub,d.PW-2*d.M-26-d.larghezza(t,12.5,true),8.5),{s:8.5,c:C.mute});return y+18;}
 // pulsante "Scarica PDF" (stesso stile in tutte le schede): icona + testo; durante la creazione mostra "Creo il PDF..."
 const ICONA='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11"/><path d="M7 10l5 5 5-5"/><path d="M5 19h14"/></svg>';
 const bottone=(cls)=>`<button type="button" class="pdfbtn${cls?" "+cls:""}" title="Scarica in PDF quello che vedi">${ICONA}<span>Scarica PDF</span></button>`;
 // esegue la funzione che crea il PDF con il pulsante in stato "occupato" (niente doppi clic)
 function avvia(btn,fn){if(btn.disabled)return;const t=btn.querySelector("span"),orig=t.textContent;btn.disabled=true;t.textContent="Creo il PDF…";
  setTimeout(()=>{Promise.resolve().then(fn).catch(e=>{console.error("[BoardEdge] pdf:",e);alert("PDF non creato: riprova tra poco.");})
   .finally(()=>{btn.disabled=false;t.textContent=orig;});},30);}

 window.ebPdf={Doc,C,chiaro,testata,testataMini,piede,sezione,ora,scarica,nomeFile,bottone,avvia};
})();}catch(e){console.error("[BoardEdge] pdf:",e);}
