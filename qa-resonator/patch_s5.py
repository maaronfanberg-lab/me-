# Stage 5 (preview): each modulator can be an LFO (as before), an envelope (attack / decay / sustain /
# release, started by keys) or an envelope follower (how loud a mic is becomes movement). Envelopes and
# followers push one way, up or down, and show a live meter. Also fixes Depth 0 leaving the destination
# stuck at its last modulated value. Edits apps/resonator-next.html in place; aborts on any mismatch.
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1, where='page'):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f'ABORT ({where}): expected {count} match(es), found {n}: {old[:90]!r}')
    s = s.replace(old, new)

def eng(old, new):
    global s
    assert '`' not in new and '${' not in new, 'ABORT: template characters in engine edit'
    a = s.index('const WORKLET = String.raw`'); b = s.index('`;', a); seg = s[a:b]
    if seg.count(old) != 1:
        sys.exit(f'ABORT (engine): expected 1 match, found {seg.count(old)}: {old[:90]!r}')
    s = s[:a] + seg.replace(old, new) + s[b:]

# ---------------- engine ----------------
eng("    this.mods=[{d:'',r:1,a:0,s:0,ph:0,sh:0},{d:'',r:1,a:0,s:0,ph:0,sh:0},{d:'',r:1,a:0,s:0,ph:0,sh:0}];",
    "    this.mods=[{d:'',r:1,a:0,s:0,ph:0,sh:0},{d:'',r:1,a:0,s:0,ph:0,sh:0},{d:'',r:1,a:0,s:0,ph:0,sh:0}];\n"
    "    // S5: modulator type (0 LFO, 1 envelope, 2 follower), its state, and what followers listen to\n"
    "    for(const m of this.mods){ m.ty=0; m.e=0; m.st=0; m.kA=0; m.kD=0; m.kR=0; m.S=0; m.aA=0; m.aR=0; m.y1=0; m.y=0; m.sens=2; m.src=0; m.inv=0; }\n"
    "    this.fIn=new Float64Array(5); this.fOn=false; this.held=new Float64Array(16); this.nHeld=0;")
eng("        m.d=d.d; m.r=d.r; m.a=d.a; m.sh=d.sh;\n",
    "        m.d=d.d; m.r=d.r; m.a=d.a; m.sh=d.sh;\n"
    "        { const ty=(d.ty===1||d.ty===2)?d.ty:0; if(ty!==m.ty){ m.e=0; m.st=0; m.y1=0; m.y=0; } m.ty=ty;   // S5\n"
    "          if(ty){ const fs=sampleRate, T=x=>Math.max(0.0005,+x||0.001);\n"
    "            m.inv=d.inv?1:0; m.src=Math.max(0,Math.min(4,d.src|0)); m.sens=Math.max(0,+d.sens||0); m.S=Math.max(0,Math.min(1,+d.S||0));\n"
    "            // envelope segments are analog-style curves that arrive in the set time: attack aims past 1 (at 1.5),\n"
    "            // decay and release aim 0.05 past their goal\n"
    "            m.kA=1-Math.exp(-Math.log(3)/(T(d.A)*fs)); m.kD=1-Math.exp(-Math.log((1.05-m.S)/0.05)/(T(d.D)*fs)); m.kR=1-Math.exp(-Math.log(21)/(T(d.R)*fs));\n"
    "            m.aA=Math.exp(-1/(T(d.fa)*fs)); m.aR=Math.exp(-1/(T(d.fr)*fs)); }\n"
    "          this.fOn=this.mods[0].ty===2||this.mods[1].ty===2||this.mods[2].ty===2; }\n")
eng("        if(d.d&&this.modBase[d.d]===undefined) this.modBase[d.d]=this[d.d];\n        break;",
    "        if(d.d&&this.modBase[d.d]===undefined) this.modBase[d.d]=this[d.d];\n"
    "        if(m.d&&!(m.a>0)&&this.modBase[m.d]!==undefined&&this[m.d]!==this.modBase[m.d]){ this[m.d]=this.modBase[m.d]; if(m.d==='tune'||m.d==='nl'||m.d==='ratio') this.pitch(); }   // S5: Depth 0 returns the parameter to its own setting\n"
    "        break;")
eng("      case 'off': for(let v=0;v<this.VMAX;v++) if(this.oscOn[v]&&this.vf0[v]===d.f) this.oscOn[v]=0; break;   // S3: key released",
    "      case 'off': for(let v=0;v<this.VMAX;v++) if(this.oscOn[v]&&this.vf0[v]===d.f) this.oscOn[v]=0; this.envNote(d.f,0); break;   // S3: key released; S5: envelopes")
eng("      case 'hush': this.gateTarget=0; this.pendingReset=true; this.bow=0; this.modBase.bow=0;\n",
    "      case 'hush': this.gateTarget=0; this.pendingReset=true; this.bow=0; this.modBase.bow=0;\n"
    "        for(const m of this.mods){ m.e=0; m.st=0; m.y1=0; m.y=0; } this.nHeld=0; this.fIn.fill(0);   // S5\n")
eng("  applyMods(perSample){\n    let pitchDirty=false;\n    for(const m of this.mods){\n      if(!m.d||m.a<=0) continue;\n"
    "      m.ph+=m.r/sampleRate; if(m.ph>=1) m.ph-=Math.floor(m.ph);\n      const w=this.modShape(m.sh,m.ph,m);\n",
    "  // S5: one sample of an envelope or a follower. The follower is a smooth decoupled peak detector\n"
    "  // (Giannoulis, Massberg and Reiss, JAES 2012): no steps in its output, whatever the input does.\n"
    "  modStep(m){\n"
    "    if(m.ty===1){\n"
    "      if(m.st===1){ m.e+=(1.5-m.e)*m.kA; if(m.e>=1){ m.e=1; m.st=2; } }\n"
    "      else if(m.st===2){ if(m.e>m.S){ m.e+=(m.S-0.05-m.e)*m.kD; if(m.e<m.S) m.e=m.S; } else if(m.e<m.S) m.e+=(m.S-m.e)*m.kD; }\n"
    "      else if(m.st===3){ m.e+=(-0.05-m.e)*m.kR; if(m.e<=0){ m.e=0; m.st=0; } }\n"
    "    } else {\n"
    "      const x=this.fIn[m.src]||0, r=m.aR*m.y1+(1-m.aR)*x;\n"
    "      m.y1=x>r?x:r; m.y=m.aA*m.y+(1-m.aA)*m.y1;\n"
    "      const c=m.y*m.sens; m.e=c<1?c:1;\n"
    "    }\n"
    "  }\n"
    "  envNote(f,on){   // S5: every key starts the envelopes; they let go when the last key comes up\n"
    "    const H=this.held; let i=-1; for(let k=0;k<this.nHeld;k++) if(H[k]===f){ i=k; break; }\n"
    "    if(on){ if(i<0&&this.nHeld<16) H[this.nHeld++]=f; for(const m of this.mods) if(m.ty===1) m.st=1; return; }\n"
    "    if(i>=0) H[i]=H[--this.nHeld];\n"
    "    if(!this.nHeld) for(const m of this.mods) if(m.ty===1&&m.st&&m.st<3) m.st=3;\n"
    "  }\n"
    "  applyMods(perSample){\n    let pitchDirty=false;\n    for(const m of this.mods){\n"
    "      if(m.ty&&perSample) this.modStep(m);   // S5: envelopes and followers run even at Depth 0 (the meter shows them)\n"
    "      if(!m.d||m.a<=0) continue;\n"
    "      let w;\n"
    "      if(m.ty) w=m.inv?-m.e:m.e;\n"
    "      else { m.ph+=m.r/sampleRate; if(m.ph>=1) m.ph-=Math.floor(m.ph); w=this.modShape(m.sh,m.ph,m); }\n")
eng("  noteOn(f,vel){\n    const v=this.pickVoice();\n",
    "  noteOn(f,vel){\n    this.envNote(f,1);   // S5\n    const v=this.pickVoice();\n")
eng("    for(let k=0;k<n;k++){\n      this.applyMods(true);\n",
    "    const fin=inputs&&inputs[0]&&inputs[0][0];   // S5: the phone mic, for followers\n"
    "    for(let k=0;k<n;k++){\n      if(this.fOn) this.fIn[4]=fin?Math.abs(fin[k]):0;\n      this.applyMods(true);\n")
eng("      const ao=o<0?-o:o; if(ao>this.peak) this.peak=ao;\n",
    "      const ao=o<0?-o:o; if(ao>this.peak) this.peak=ao;\n      if(this.fOn) this.fIn[0]=ao*this.lvl;   // S5: follower source, Mic 1, as loud as it is heard (after the shape trim)\n")
eng("      if(this.xmN){   // S4: extra mics, each a clean point pickup with its own level and pan\n",
    "      if(this.fOn){ this.fIn[1]=0; this.fIn[2]=0; this.fIn[3]=0; }   // S5\n"
    "      if(this.xmN){   // S4: extra mics, each a clean point pickup with its own level and pan\n")
eng("          let o3=Math.tanh(y3*this.gain*13)*this.gate*this.xmG[q]; if(!isFinite(o3)) o3=0;\n",
    "          let o3=Math.tanh(y3*this.gain*13)*this.gate*this.xmG[q]; if(!isFinite(o3)) o3=0;\n"
    "          if(this.fOn) this.fIn[q+1]=(o3<0?-o3:o3)*this.lvl;   // S5: follower sources, Mics 2-4\n")
eng("      this.port.postMessage({t:'frame',pk:this.peak});",
    "      const M=this.mods;   // S5: envelope and follower meters\n"
    "      this.port.postMessage(M[0].ty||M[1].ty||M[2].ty?{t:'frame',pk:this.peak,mv:[M[0].e,M[1].e,M[2].e]}:{t:'frame',pk:this.peak});")

# ---------------- page ----------------
rep("</style>",
    ".mmeter{height:4px;background:#101A2E;border-radius:2px;margin:-4px 0 12px;overflow:hidden}\n"
    ".mmeter i{display:block;height:100%;width:0;background:var(--compress)}\n"
    ".mhint{font-size:10.5px;color:var(--faint);margin:-4px 0 14px;line-height:1.45}\n"
    "</style>")
K = []
for i in (1, 2, 3):
    first = i == 1
    K.append(f" m{i}at:{{label:'Attack {i}',min:0,max:1,step:0.005,val:0.175,fmt:v=>fmtTime(v),hint:'{'How long the envelope takes to rise when a key goes down.' if first else ''}'}},\n")
    K.append(f" m{i}dc:{{label:'Decay {i}',min:0,max:1,step:0.005,val:0.62,fmt:v=>fmtTime(v),hint:'{'How long it takes to fall to the sustain level.' if first else ''}'}},\n")
    K.append(f" m{i}su:{{label:'Sustain {i}',min:0,max:1,step:0.01,val:0,fmt:v=>Math.round(v*100)+'%',hint:'{'Where it rests while keys stay down. At 0% it is a one-shot.' if first else ''}'}},\n")
    K.append(f" m{i}rl:{{label:'Release {i}',min:0,max:1,step:0.005,val:0.62,fmt:v=>fmtTime(v),hint:'{'How long it takes to fall away after the last key comes up.' if first else ''}'}},\n")
    K.append(f" m{i}fa:{{label:'Follow attack {i}',min:0,max:1,step:0.005,val:0.335,fmt:v=>fmtTime(v),hint:'{'How fast it rises when the mic gets louder. About 20 ms follows loudness roughly the way ears do.' if first else ''}'}},\n")
    K.append(f" m{i}fr:{{label:'Follow release {i}',min:0,max:1,step:0.005,val:0.425,fmt:v=>fmtTime(v),hint:'{'How fast it falls when the mic gets quieter.' if first else ''}'}},\n")
    K.append(f" m{i}se:{{label:'Sensitivity {i}',min:0,max:1,step:0.01,val:0.36,fmt:v=>fmtSens(v),hint:'{'How loud the mic must be to reach full movement. At +13 dB a firm hit reaches most of the way.' if first else ''}'}},\n")
rep(" m3a:{label:'Depth 3',min:0,max:1,step:0.01,val:0,fmt:v=>Math.round(v*100)+'%',hint:''},\n",
    " m3a:{label:'Depth 3',min:0,max:1,step:0.01,val:0,fmt:v=>Math.round(v*100)+'%',hint:''},\n" + ''.join(K))
old_mod = ''.join(f'      <div class="secttl">Modulator {i+1}</div>\n      <div class="mrow" data-m="{i}"></div>\n'
                  f'      <div class="knob" data-k="m{i+1}r"></div>\n      <div class="knob" data-k="m{i+1}a"></div>\n' for i in range(3))
new_mod = ''.join(f'      <div class="secttl">Modulator {i+1}</div>\n'
                  f'      <div class="row" data-mty="{i}"></div>\n'
                  f'      <div class="mrow" data-m="{i}"></div>\n'
                  f'      <div class="row" data-msrc="{i}"></div>\n'
                  f'      <div class="mmeter" data-mm="{i}"><i></i></div>\n'
                  f'      <div class="knob" data-k="m{i+1}r"></div>\n'
                  + ''.join(f'      <div class="knob" data-k="m{i+1}{x}"></div>\n' for x in ('at', 'dc', 'su', 'rl', 'fa', 'fr', 'se')) +
                  f'      <div class="knob" data-k="m{i+1}a"></div>\n'
                  f'      <div class="row" data-mdir="{i}"></div>\n'
                  f'      <div class="mhint" data-mhint="{i}"></div>\n' for i in range(3))
rep('    <section class="page" id="page-mod">\n' + old_mod + '    </section>',
    '    <section class="page" id="page-mod">\n' + new_mod + '    </section>')
rep("function sendMod(i){\n  if(!node)return;\n  const r=RATE(val[['m1r','m2r','m3r'][i]]), a=val[['m1a','m2a','m3a'][i]];\n"
    "  node.port.postMessage({t:'mod',i,d:state.mods[i].d,r,a,sh:state.mods[i].sh});\n}",
    "function sendMod(i){\n  if(!node)return;\n  const r=RATE(val[['m1r','m2r','m3r'][i]]), a=val[['m1a','m2a','m3a'][i]], m=state.mods[i];\n"
    "  const msg={t:'mod',i,d:m.d,r,a,sh:m.sh};\n"
    "  if(m.ty){ const p='m'+(i+1); msg.ty=m.ty; msg.inv=m.dn?1:0; msg.src=m.src||0;   // S5: envelope / follower\n"
    "    msg.A=MTIME(val[p+'at']); msg.D=MTIME(val[p+'dc']); msg.S=val[p+'su']; msg.R=MTIME(val[p+'rl']);\n"
    "    msg.fa=MTIME(val[p+'fa']); msg.fr=MTIME(val[p+'fr']); msg.sens=Math.pow(64,val[p+'se']); }\n"
    "  node.port.postMessage(msg);\n}")
rep("   else if(/^m[123][ra]$/.test(k)) sendMod(+k[1]-1);",
    "   else if(/^m[123]([ra]|at|dc|su|rl|fa|fr|se)$/.test(k)) sendMod(+k[1]-1);   // S5: envelope and follower knobs too")
rep("   if(d.t==='frame'){\n     state.peak=d.pk; state.ranOnce=true; drawLevel();",
    "   if(d.t==='frame'){\n     state.peak=d.pk; state.ranOnce=true; drawLevel();\n     if(d.mv||state.mvShown) modMeters(d.mv||null);   // S5")
MOD5 = r'''
// ---- S5: envelopes and envelope followers ------------------------------------------------
// Each modulator is an LFO (as before), an envelope (every key starts it; it lets go when the last key
// comes up) or a follower (how loud a mic is becomes movement). Envelopes and followers push one way.
const MTYPES=['LFO','Envelope','Follower'], MSRCS=['Mic 1','Mic 2','Mic 3','Mic 4','Phone mic'];
function MTIME(v){ return 0.001*Math.pow(10000,v); }   // 1 ms … 10 s
function fmtTime(v){ const t=MTIME(v); return t<1?Math.round(t*1000)+' ms':t.toFixed(t<10?2:1)+' s'; }
function fmtSens(v){ return '+'+(20*Math.log10(Math.pow(64,v))).toFixed(1)+' dB'; }   // 0 … +36 dB
function modHint(i){
  const m=state.mods[i], ty=m.ty||0, h=document.querySelector('[data-mhint="'+i+'"]'); if(!h) return;
  let t='';
  if(ty===1) t='Every key starts it; it lets go when the last key comes up.';
  else if(ty===2){ const sc=m.src||0;
    if(sc>=1&&sc<=3&&state.xm&&state.xm[sc-1].i<0) t='Mic '+(sc+1)+' is off: place it on the Mic tab (More mics).';
    else if(sc===4&&!MIC.on) t='Turn on Mic in (Strike tab). With Mic input at 0, your voice steers without driving the body.';
    else t='How loud '+MSRCS[sc]+' is becomes movement.'; }
  if(ty&&!m.d) t+=' Pick what it moves above.';
  h.textContent=t; h.style.display=t?'':'none';
}
function modUI(i){
  const m=state.mods[i], ty=m.ty||0, p='m'+(i+1);
  const show=(el,on)=>{ if(el) el.style.display=on?'':'none'; }, knob=k=>document.querySelector('.knob[data-k="'+k+'"]');
  document.querySelectorAll('[data-mty="'+i+'"] .chip').forEach((c,j)=>c.setAttribute('aria-pressed',String(j===ty)));
  document.querySelectorAll('[data-msrc="'+i+'"] .chip').forEach((c,j)=>c.setAttribute('aria-pressed',String(j===(m.src||0))));
  document.querySelectorAll('[data-mdir="'+i+'"] .chip').forEach((c,j)=>c.setAttribute('aria-pressed',String(j===(m.dn?1:0))));
  show(document.querySelectorAll('.mrow[data-m="'+i+'"] select')[1],!ty);   // the LFO wave
  show(document.querySelector('[data-msrc="'+i+'"]'),ty===2); show(document.querySelector('[data-mdir="'+i+'"]'),!!ty); show(document.querySelector('[data-mm="'+i+'"]'),!!ty);
  show(knob(p+'r'),!ty); for(const x of ['at','dc','su','rl']) show(knob(p+x),ty===1); for(const x of ['fa','fr','se']) show(knob(p+x),ty===2);
  modHint(i);
}
function modMeters(mv){ for(let i=0;i<3;i++){ const b=document.querySelector('[data-mm="'+i+'"] i'); if(b) b.style.width=(mv?Math.max(0,Math.min(1,mv[i]||0))*100:0)+'%'; } state.mvShown=!!mv; }
for(let i=0;i<3;i++){
  const chips=(sel,names,set)=>{ const r=document.querySelector(sel); names.forEach((n,j)=>{ const b=document.createElement('button'); b.className='chip'; b.textContent=n; b.onclick=()=>{ set(j); modUI(i); sendMod(i); }; r.appendChild(b); }); };
  chips('[data-mty="'+i+'"]',MTYPES,j=>{ state.mods[i].ty=j; });
  chips('[data-msrc="'+i+'"]',MSRCS,j=>{ state.mods[i].src=j; });
  chips('[data-mdir="'+i+'"]',['Push up','Push down'],j=>{ state.mods[i].dn=j; });
  const ds=document.querySelectorAll('.mrow[data-m="'+i+'"] select')[0]; if(ds) ds.addEventListener('change',()=>modHint(i));
  modUI(i);
}
{ const mt=document.querySelector('.tab[data-page=mod]'); if(mt) mt.addEventListener('click',()=>{ for(let i=0;i<3;i++) modHint(i); }); }
'''
rep("  ds.onchange=()=>{state.mods[i].d=ds.value;sendMod(i);};\n  ss.onchange=()=>{state.mods[i].sh=+ss.value;sendMod(i);};\n  row.appendChild(ds);row.appendChild(ss);\n}\n",
    "  ds.onchange=()=>{state.mods[i].d=ds.value;sendMod(i);};\n  ss.onchange=()=>{state.mods[i].sh=+ss.value;sendMod(i);};\n  row.appendChild(ds);row.appendChild(ss);\n}\n" + MOD5)
# presets remember each modulator's type, direction and source
rep("mods:state.mods.map(m=>({d:m.d,sh:m.sh}))", "mods:state.mods.map(m=>({d:m.d,sh:m.sh,ty:m.ty||0,dn:m.dn||0,src:m.src||0}))")
rep("  state.mods=(o.mods||[]).map(m=>({d:m.d||'',sh:m.sh||0}));",
    "  state.mods=(o.mods||[]).map(m=>({d:m.d||'',sh:m.sh||0,ty:m.ty||0,dn:m.dn||0,src:m.src||0}));   // S5")
rep("    if(sels[1]) sels[1].value=String(state.mods[i].sh);\n  });\n",
    "    if(sels[1]) sels[1].value=String(state.mods[i].sh);\n  });\n  for(let i=0;i<3;i++) modUI(i);   // S5\n")

open(P, 'w', encoding='utf-8').write(s)
print('patched', P)
