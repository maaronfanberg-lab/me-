# Stage H (preview): factory presets and a Learn tab. Page only; the engine is untouched.
#  - Factory presets: listed first in Presets ("Factory"), each built from a fresh template body plus a
#    few settings, so they never depend on stored geometry. Delete refuses them.
#  - Learn tab: nine A/B lessons (guess, hear A and B, then read why) and one how-to for free building.
#    Every "why" quotes numbers measured on the engine with the lesson's own values
#    (qa-resonator/h1_claims.mjs). The instrument as it was is kept and comes back with one tap.
#  - Presets come back as they were saved (errors found while building this stage):
#      * the tuning reference (the strike and mic the body was built with) is saved and rebuilt, so a
#        preset saved with the strike and mic near an end no longer reloads an octave down;
#      * the spectrum choice, the bow and Mic axis X are applied on load; the axis and scale chips and the
#        shape's description follow what was loaded;
#      * a load message stays readable (the readout's redraw used to clear it at once).
# Edits apps/resonator-next.html in place; aborts on any mismatch.
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f'ABORT: expected {count} match(es), found {n}: {old[:90]!r}')
    s = s.replace(old, new)

# ---------- markup ----------
rep('    <button class="tab" data-page="mod" aria-selected="false">Mod</button>\n',
    '    <button class="tab" data-page="mod" aria-selected="false">Mod</button>\n'
    '    <button class="tab" data-page="learn" aria-selected="false">Learn</button>\n')
rep('    <section class="page" id="page-mod">\n',
    '    <section class="page" id="page-learn">\n'
    '      <div class="lintro">Every sound here is an <b>object</b>, <b>struck</b> somewhere and <b>heard</b> from somewhere. '
    'Each lesson changes one thing: guess first, then tap A and B and listen. The explanation opens once you have heard both. '
    'Lessons borrow your instrument; the button below gives it back.<br>'
    '<i>Brightness centre</i> is the pitch the sound\'s energy balances on: higher sounds brighter. Every number was measured on this instrument.</div>\n'
    '      <div class="row"><button class="chip" id="lback" disabled>Put my instrument back</button></div>\n'
    '      <div id="lessons"></div>\n'
    '    </section>\n'
    '    <section class="page" id="page-mod">\n')
rep("</style>",
    ".lintro{font-size:12px;color:var(--text);margin:4px 2px 10px;line-height:1.5}\n"
    ".lintro i{font-style:normal;color:var(--live)}\n"
    ".lesson{border:1px solid var(--rule);border-radius:4px;padding:10px 10px 4px;margin:0 0 10px;background:rgba(20,29,51,.45)}\n"
    ".lesson h3{margin:0 0 4px;font-family:var(--display);font-weight:600;font-size:14px;color:var(--live)}\n"
    ".lesson .lq{font-size:12px;color:var(--dim);margin:0 0 8px}\n"
    ".lesson .lwhy{display:none;font-size:12px;color:var(--text);border-left:2px solid var(--compress);padding:4px 8px;margin:4px 0 8px;line-height:1.5}\n"
    ".lesson.heard .lwhy{display:block}\n"
    ".lesson .lsteps{font-size:12px;color:var(--text);margin:0 0 8px;padding-left:18px;line-height:1.55}\n"
    "</style>")

# ---------- every new body records the strike and mic it was tuned with ----------
rep("node.port.postMessage({t:'struct',", "postStruct({t:'struct',", count=3)

# ---------- snapshot keeps that reference ----------
rep("mods:state.mods.map(m=>({d:m.d,sh:m.sh,ty:m.ty||0,dn:m.dn||0,src:m.src||0})),xm:state.xm?state.xm.map(x=>({i:x.i,g:x.g,p:x.p})):null};",
    "mods:state.mods.map(m=>({d:m.d,sh:m.sh,ty:m.ty||0,dn:m.dn||0,src:m.src||0})),xm:state.xm?state.xm.map(x=>({i:x.i,g:x.g,p:x.p})):null,\n"
    "    ref:state.ref?{h:state.ref.h,m:state.ref.m,a:state.ref.a}:null};   // H: the strike and mic the body was tuned with")

# ---------- restore: axis X, the reference, the spectrum, the bow, chips and description ----------
rep("state.scale=o.scale||0; state.root=o.root||52; state.axis=o.axis||1;",
    "state.scale=o.scale||0; state.root=o.root||52; state.axis=(o.axis===0||o.axis===1||o.axis===2)?o.axis:1;   // H: X (0) is a real axis")
rep("""  [...specEl.children].forEach((c,j)=>c.setAttribute('aria-pressed',j===state.spec));
  for(const k in KNOBS) syncKnob(k);
  if(state.hist){state.hist.length=0;state.redo.length=0;syncUndo();}
  rebuild();
  for(let i=0;i<3;i++) sendMod(i);
  buildPads();
  return true;
}""", """  [...specEl.children].forEach((c,j)=>c.setAttribute('aria-pressed',j===state.spec));
  [...axesEl.children].forEach((c,j)=>c.setAttribute('aria-pressed',j===state.axis));   // H
  document.querySelectorAll('[data-scale]').forEach(x=>x.setAttribute('aria-pressed',String(+x.dataset.scale===state.scale)));   // H
  { const S=SHAPES[state.shape], bt=document.getElementById('bodytext'); if(S&&bt) bt.textContent=S.note; }   // H
  for(const k in KNOBS) syncKnob(k);
  if(state.hist){state.hist.length=0;state.redo.length=0;syncUndo();}
  // H: build with the strike and mic the body was tuned with, then move them to where they were saved.
  // The engine tunes the loudest partial at the build-time strike and mic (S1); building with the saved
  // ones instead could tune a different partial, an octave away on a string.
  const NP=state.geo.P.length, okI=i=>Number.isInteger(i)&&i>=0&&i<NP&&!state.geo.F[i];
  const ref=o.ref&&okI(o.ref.h)&&okI(o.ref.m)?o.ref:null, want={m:state.micIdx,h:state.hitIdx,a:state.axis};
  if(ref){ state.micIdx=ref.m; state.hitIdx=ref.h; if(ref.a===0||ref.a===1||ref.a===2) state.axis=ref.a; }
  rebuild();
  state.micIdx=want.m; state.hitIdx=want.h; state.axis=want.a; pickSend();
  for(let i=0;i<3;i++) sendMod(i);
  if(node) node.port.postMessage({t:'spec',v:state.spec||0});   // H: the spectrum choice reaches the engine
  if(o.val&&'bow' in o.val){ val.bow=+o.val.bow||0; const bb=document.getElementById('bow'); if(bb) bb.setAttribute('aria-pressed',String(val.bow>0)); send('bow'); }   // H
  buildPads();
  return true;
}""")

# ---------- presets: factory list, load, refuse delete; messages that stay readable ----------
rep("""  const names=Object.keys(all).sort();
  {const o=document.createElement('option');o.value='';
   o.textContent=names.length?'— pick a preset —':'(nothing saved yet)';l.appendChild(o);}
  names.forEach(nm=>{const o=document.createElement('option');o.value=nm;o.textContent=nm;l.appendChild(o);});
  if(sel) l.value=sel;
}""", """  const names=Object.keys(all).sort();
  {const o=document.createElement('option');o.value='';o.textContent='— pick a preset —';l.appendChild(o);}
  // H: factory presets first, then the ones saved on this phone
  const fg=document.createElement('optgroup'); fg.label='Factory';
  FACTORY.forEach(f=>{const o=document.createElement('option');o.value='factory:'+f.name;o.textContent=f.name;fg.appendChild(o);});
  l.appendChild(fg);
  const sg=document.createElement('optgroup'); sg.label=names.length?'Saved on this phone':'Saved on this phone (none yet)';
  names.forEach(nm=>{const o=document.createElement('option');o.value=nm;o.textContent=nm;sg.appendChild(o);}); l.appendChild(sg);
  if(sel) l.value=sel;
}""")
rep("""  const nm=document.getElementById('plist').value; if(!nm) return;
  const all=store.get();
  document.getElementById('msg').textContent=restore(all[nm])?'Loaded '+nm:'Could not load '+nm;
};""", """  const nm=document.getElementById('plist').value; if(!nm) return;
  if(nm.startsWith('factory:')){ const f=FACTORY.find(x=>'factory:'+x.name===nm); if(f){ restore(presetFrom(f)); say('Loaded '+f.name+'. '+f.note); } return; }   // H
  const all=store.get();
  if(restore(all[nm])) say('Loaded '+nm); else say('Could not load '+nm,true);
};""")
rep("""  const nm=document.getElementById('plist').value; if(!nm) return;
  const all=store.get(); delete all[nm]; store.set(all); refreshList();""",
    """  const nm=document.getElementById('plist').value; if(!nm) return;
  if(nm.startsWith('factory:')){ say('Factory presets stay. Load it, change it, then Save to keep your own version.'); return; }   // H
  const all=store.get(); delete all[nm]; store.set(all); refreshList();""")
rep("""  document.getElementById('msg').textContent=(o&&restore(o))?'Loaded from code':'That code could not be read';""",
    """  if(o&&restore(o)) say('Loaded from code'); else say('That code could not be read',true);""")
# a message from something you just did stays readable for a few seconds; the readout's own notes
# (heavy body, buffered engine) come back when it expires
rep(""" if(load>190){m.className='warn';m.textContent='This one is heavy""",
    """ if(performance.now()<(state.msgUntil||0)){}   // H: a message from something you just did stays readable
 else if(load>190){m.className='warn';m.textContent='This one is heavy""")

# ---------- the data and the code ----------
rep("function refreshList(sel){",
    r"""// H: a message that the readout's next redraw leaves alone for a few seconds
function say(t,warn){ const m=document.getElementById('msg'); if(!m) return; m.className=warn?'warn':''; m.textContent=t; state.msgUntil=performance.now()+6000;
  clearTimeout(state.msgT); state.msgT=setTimeout(()=>{ state.msgUntil=0; drawInfo(); },6050); }
// H: every new body goes through here, so the page knows which strike and mic it was tuned with
function postStruct(msg){ state.ref={h:msg.hit,m:msg.mic,a:msg.axis}; node.port.postMessage(msg); }
// H: send the strike and both mics where the page has them (the second mic as the mic tool places it)
function pickSend(){ if(!node) return; const F=state.free, n=F.length; if(!n) return;
  const k=Math.max(0,F.indexOf(state.micIdx)); state.micIdx2=F[(k+Math.max(1,Math.floor(n/2)))%n];
  node.port.postMessage({t:'mic',i:state.micIdx,a:state.axis}); node.port.postMessage({t:'mic2',i:state.micIdx2});
  node.port.postMessage({t:'hit',i:state.hitIdx,a:state.axis}); }

// H: factory presets. Starting points; how they sound is a matter of taste. Each is a fresh template body
// (never stored geometry), tuned with the shape's own strike and mic, plus a few settings; everything else
// is at its default. qa-resonator/h1_claims.mjs checks every note below.
const FACTORY=[
 {name:'Harp',shape:'String',mode:2,val:{hard:0.5,decay:5,voices:6,loss:0.2,rvMix:0.3,rvTime:3,gain:1.6},note:'A string plucked with a plectrum, ringing on in a plate.'},
 {name:'Kalimba',shape:'Tine',val:{hard:0.3,decay:2.2,voices:4,angle:0.2,rvMix:0.2,rvTime:1.8},note:'Tines clamped at one end, struck firmly.'},
 {name:'Glass bar (bowed)',shape:'Chime',bow:true,val:{decay:10,bowSpd:0.9,bowVc:0.5,rvMix:0.35,rvTime:4},note:'A free bar under a bow, sounding with no key. Tap Bow on the Strike tab to stop it.'},
 {name:'Steel tank',shape:'Tank',val:{hard:0.5,decay:14,voices:2,rvMix:0.4,rvTime:6,rvTone:7000},note:'A big steel vessel with a long ring.'},
 {name:'Gong',shape:'Drum',val:{hard:0.6,drive:2.2,nl:4,decay:9,voices:2,rvMix:0.3,rvTime:5},note:'Hit it hard and the head stiffens, so the pitch starts high and sinks as it settles.'},
 {name:'Wind harp',shape:'Web',val:{wind:0.55,decay:8,rvMix:0.45,rvTime:6,gain:0.5},note:'Moving air on every mass, sounding with no key. Wind is on the Strike tab.'},
 {name:'Breathing pad',shape:'String',mods:[{d:'tone',sh:0,ty:1,dn:0,src:0}],val:{hard:0.1,decay:8,voices:6,tone:600,rvMix:0.45,rvTime:5,gain:1.3,m1a:0.8,m1at:0.7,m1dc:0.8,m1su:0.4,m1rl:0.75},note:'Long strings. Hold a key and an envelope opens the tone, then lets it settle.'},
 {name:'Turning bell',shape:'Chime',val:{decay:6,voices:4,spRot:0.6,spImg:0.8,spDop:0.5,rvMix:0.3,rvTime:3,gain:1.2},note:'A bell turning slowly. On headphones it drifts between your ears.'},
 {name:'Pickup twang',shape:'String',pk:1,val:{hard:0.1,decay:3,voices:4,amp:0.5,cab:0.7,bass:0.3,gain:0.4},note:'A humbucker, an amp and a speaker box.'},
 {name:'Sympathetic twins',shape:'Twins',mode:2,val:{hard:0.7,decay:7,rvMix:0.25,rvTime:3.5},note:'You pluck one string; the mic is on the other, which answers.'}
];
function presetFrom(f){
  const S=SHAPES[f.shape], n=f.n||S.def, g=S.make(n), v={};
  for(const k in KNOBS) v[k]=KNOBS[k].val;
  const free=g.P.map((_,i)=>i).filter(i=>!g.F[i]), span=Math.max(1,free.length-1);
  v.mic=Math.max(0,free.indexOf(g.mic))/span; v.hit=Math.max(0,free.indexOf(g.hit))/span;   // the shape's own strike and mic
  if(g.needSub&&v.sub<g.needSub) v.sub=g.needSub;
  Object.assign(v,f.val||{}); v.size=S.max>S.min?(n-S.min)/(S.max-S.min):0; v.bow=f.bow?0.16:0;
  const at=x=>free[Math.min(free.length-1,Math.round(x*(free.length-1)))];
  const mods=[0,1,2].map(i=>(f.mods&&f.mods[i])||{d:'',sh:0,ty:0,dn:0,src:0});
  return {v:1,shape:f.shape,n,scale:0,root:52,axis:g.axis,pk:f.pk||0,mode:f.mode||0,spec:0,
    micIdx:at(v.mic),hitIdx:at(v.hit),P:g.P,F:Array.from(g.F),S:g.S,val:v,mods,xm:null,ref:{h:g.hit,m:g.mic,a:g.axis}};
}

// H: Learn. Each lesson changes one thing and plays the same key (E4) at the same strength, so A and B
// differ only in that one thing. Every "why" quotes measurements made on this engine with these exact
// values; qa-resonator/h1_claims.mjs re-measures them and checks the text.
const LESSONS=[
 {t:'Hard or soft',q:'Will a soft mallet sound brighter or darker than a hard one?',base:{shape:'String',val:{decay:2.5}},
  A:['Hard',{hard:0}],B:['Soft',{hard:0.6}],
  why:'A short, hard contact kicks every partial; a long, soft one only moves the lowest. Measured: the brightness centre falls from about 1030 Hz to 330 Hz, the note itself. The soft one is also about 7 dB quieter: a slow push passes on less energy.'},
 {t:'Pluck or ring',q:'Short Decay, then long. What changes besides the length?',base:{shape:'String'},
  A:['Short',{decay:0.3}],B:['Long',{decay:2}],
  why:'Decay sets how fast the whole body gives its energy away, and nothing else. Measured: about 0.5 s to fall 60 dB at the short setting and 1.9 s at the long one, while the attack is the same colour (brightness centre about 520 Hz in both).'},
 {t:'Ringing metal, dull wood',q:'Take the damping out of the springs, then put lots in. Which one sounds like wood, and why?',base:{shape:'String'},
  A:['No damping',{loss:0}],B:['Damped',{loss:1}],
  why:'Damping in the springs takes the high partials first; Decay (lesson 2) takes them all alike. Measured: without spring damping the note and its octave ring for the same 4 s before falling 30 dB. With it, the note lasts 0.9 s, the octave 0.3 s, and the partials above that about a tenth of a second: short and dull, like wood beside metal.'},
 {t:'Where you strike',q:'Strike near the end, then dead centre. What disappears?',base:{shape:'String',n:15,val:{decay:3,hard:0}},
  A:['Near the end',{hit:0.12}],B:['Centre',{hit:0.5}],
  why:'Every even partial has a still point at the centre, so a strike there cannot move it. Measured: the 2nd partial, an octave above the note, drops from 13 dB below the note to 68 dB below, gone. The odd ones stay. Rounder and purer.'},
 {t:'Where you listen',q:'Move the mic from near the end to the centre. What vanishes?',base:{shape:'String',n:15,val:{decay:3,hard:0,hit:0.12}},
  A:['Near the end',{mic:0.06}],B:['Centre',{mic:0.5}],
  why:'The same still points, heard instead of struck: a mic at the centre cannot hear the even partials. Measured: the 2nd partial drops from 11 dB below the note to 99 dB below.'},
 {t:'Pitch or no pitch',q:'Why does the drum have no clear note?',base:{shape:'String'},
  A:['String',{shape:'String'}],B:['Drum',{shape:'Drum'}],
  why:'A string\'s partials sit near whole-number steps, 1 : 2 : 3 : 4 (measured here 1 : 1.98 : 2.94 : 3.87), which the ear fuses into one note. A drumhead\'s do not: this one\'s sit at 1 : 1.38 : 1.54 : 1.63 (measured), a real round drum\'s at 1 : 1.59 : 2.14 : 2.30. The ear cannot fuse them into one note.'},
 {t:'Strike or pluck',q:'A mallet kicks the string; a plectrum pulls it aside and lets go. Which is brighter?',base:{shape:'String',val:{hard:0}},
  A:['Mallet',{mode:0}],B:['Plectrum',{mode:2}],
  why:'A strike gives every partial the same kick; a pluck starts from a bent shape whose partials fall away faster. Measured: the brightness centre is about 1030 Hz struck and 380 Hz plucked; the plucked upper partials sit 5 to 16 dB lower.'},
 {t:'A room',q:'What does a plate add when the body itself is short?',base:{shape:'Tine',val:{decay:0.8}},
  A:['Dry',{rvMix:0}],B:['Plate',{rvMix:0.5}],
  why:'The plate keeps the sound going after the body has stopped. Measured: one second after the strike, the dry tine has fallen 47 dB; with the plate it is only 26 dB down. The body decays exactly as before; the plate carries it on.'},
 {t:'Make it move',q:'An envelope opens the tone while you hold a key, then closes it. Can you hear it breathe?',base:{shape:'String',val:{tone:700,decay:3,hard:0.1}},
  hold:1.5,env:{a:0.8,at:0.6,dc:0.725,su:0.2,rl:0.675},
  A:['Still',{env:0}],B:['Envelope on tone',{env:1}],
  why:'An envelope rises when a key goes down and falls back when it comes up; here it pushes Mic tone. Measured: still, the brightness centre only falls (about 440 Hz to 355 Hz). With the envelope it climbs to about 940 Hz a quarter of a second in, then sinks back.'},
 {t:'Build your own',how:true,q:'Every body here is masses and springs. Make your own.',base:{shape:'String',n:6},
  steps:['Tap <b>add</b> (in the row of buttons along the bottom of the picture), then tap empty space in the picture: a new mass appears there, wired to its nearest neighbour.',
         'Tap <b>delete</b>, then a mass, to take it away. <b>&#8630;</b> undoes either.',
         'Tap <b>link</b>, then two masses: a spring appears between them, or goes if there was one. <b>pin</b> fixes a mass in place; tap it again to free it.',
         'Tap <b>move</b>, then a mass, then the arrows to push it.',
         'Play after each change. The body is re-tuned in the background, so its loudest partial lands on the key you press.']}
];
const LEARN={saved:null,offT:0};
function lessonApply(ch,L){
  for(const [k,v] of Object.entries(ch)){
    if(k==='shape'){ const c=[...shapesEl.children].find(x=>x.textContent===v); if(c&&state.shape!==v) c.click(); }
    else if(k==='mode'){ const c=modeEl.children[v]; if(c) c.click(); }
    else if(k==='env'){ const m=state.mods[0], e=L.env; m.d=v?'tone':''; m.sh=0; m.ty=v?1:0; m.dn=0; m.src=0;
      val.m1a=v?e.a:0; val.m1at=e.at; val.m1dc=e.dc; val.m1su=e.su; val.m1rl=e.rl;
      const sels=document.querySelectorAll('.mrow[data-m="0"] select'); if(sels[0]) sels[0].value=m.d; if(sels[1]) sels[1].value='0';
      for(const kk of ['m1a','m1at','m1dc','m1su','m1rl']) syncKnob(kk); modUI(0); sendMod(0); }
    else if(k==='hit'||k==='mic'){ val[k]=v; placeMicHit(); syncKnob(k); }
    else { val[k]=v; syncKnob(k); send(k); }
  }
}
// the same key (E4) at the same strength every time; held for the lesson's hold time
function lessonRelease(){ if(LEARN.offT){ clearTimeout(LEARN.offT); LEARN.offT=0; stop(12); } }   // never leave a lesson's key held
function lessonPlay(L){
  const semi=12, hold=(L&&L.hold)||0.15;
  lessonRelease(); play(semi,0.8);
  const pad=padsEl.children[SCALES[state.scale].length]; if(pad){ pad.classList.add('lit'); setTimeout(()=>pad.classList.remove('lit'),Math.max(130,hold*1000)); }
  LEARN.offT=setTimeout(()=>{ LEARN.offT=0; stop(semi); },hold*1000);
}
function lessonSetup(L){
  lessonRelease();
  if(!LEARN.saved){ LEARN.saved=snapshot(); document.getElementById('lback').disabled=false; }
  restore(presetFrom(L.base));
}
// a lesson's explanation, once earned, stays open
function lessonsReset(){ document.querySelectorAll('.lesson').forEach(x=>{ x.dataset.on='';
  x.querySelectorAll('[data-a=A],[data-a=B]').forEach(b=>b.setAttribute('aria-pressed','false')); }); }
function buildLessons(){
  const box=document.getElementById('lessons'); if(!box) return; box.innerHTML='';
  LESSONS.forEach((L,i)=>{
    const d=document.createElement('div'); d.className='lesson'; d.dataset.l=i;
    let h='<h3>'+(i+1)+' · '+L.t+'</h3><div class="lq">'+L.q+'</div>';
    if(L.how) h+='<ol class="lsteps">'+L.steps.map(x=>'<li>'+x+'</li>').join('')+'</ol><div class="row"><button class="chip" data-a="go">Start from a small string</button></div>';
    else h+='<div class="row"><button class="chip" data-a="A" aria-pressed="false">A · '+L.A[0]+'</button><button class="chip" data-a="B" aria-pressed="false">B · '+L.B[0]+'</button><button class="chip" data-a="play">Play again</button></div><div class="lwhy">'+L.why+'</div>';
    d.innerHTML=h; box.appendChild(d);
    const heard={A:false,B:false};
    d.querySelectorAll('button').forEach(b=>b.onclick=()=>{
      if(!state.running||!node){ say('Wake the instrument up first.',true); return; }
      const a=b.dataset.a;
      if(a==='go'){ lessonsReset(); lessonSetup(L); const t=document.querySelector('.tool[data-tool=add]'); if(t) t.click(); say('A small string, and the add tool is on: tap empty space on the picture.'); return; }
      if(a==='play'){ if(d.dataset.on==='1') lessonPlay(L); else say('Tap A or B first.'); return; }
      if(d.dataset.on!=='1'){ lessonsReset(); lessonSetup(L); d.dataset.on='1'; }
      lessonApply(a==='A'?L.A[1]:L.B[1],L);
      d.querySelectorAll('[data-a=A],[data-a=B]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
      setTimeout(()=>lessonPlay(L),250);
      heard[a]=true; if(heard.A&&heard.B) d.classList.add('heard');
    });
  });
  const back=document.getElementById('lback');
  if(back) back.onclick=()=>{ if(!LEARN.saved) return; lessonRelease(); restore(LEARN.saved); LEARN.saved=null; back.disabled=true; lessonsReset();
    say('Your instrument is back.'); };
}
buildLessons();
function refreshList(sel){""")
open(P, 'w', encoding='utf-8').write(s)
print('patched OK')
