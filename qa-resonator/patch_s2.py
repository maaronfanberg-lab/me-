# Stage 2 (preview): free building — add and delete masses; undoable shape/Size changes;
# second-mic guard. Edits apps/resonator-next.html in place; aborts on any mismatch.
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, where='page'):
    global s
    n = s.count(old)
    if n != 1:
        sys.exit(f'ABORT ({where}): expected 1 match, found {n}: {old[:90]!r}')
    s = s.replace(old, new)

# ---------- engine: the second mic must point at a mass that exists and moves ----------
a = s.index('const WORKLET = String.raw`'); b = s.index('`;', a)
old = "    this.micI=d.mic; this.hitI=d.hit; this.micA=d.axis; this.hitA=d.axis; this.axis=d.axis;\n"
new = old + "    if(this.micJ>=N||(this.micJ>=0&&this.fixed[this.micJ])) this.micJ=-1;   // S2: second mic re-placed if its mass is gone or pinned\n"
seg = s[a:b]
if seg.count(old) != 1: sys.exit('ABORT (engine): micJ anchor')
s = s[:a] + seg.replace(old, new) + s[b:]

# ---------- tools ----------
rep('<button class="tool" data-tool="pin" aria-pressed="false">pin</button>',
    '<button class="tool" data-tool="pin" aria-pressed="false">pin</button>\n'
    '      <button class="tool" data-tool="add" aria-pressed="false">add</button>\n'
    '      <button class="tool" data-tool="del" aria-pressed="false">delete</button>')

rep("  if(state.tool==='orbit'){ drag={x:e.clientX,y:e.clientY}; state.spin=false; return; }\n",
    "  if(state.tool==='orbit'){ drag={x:e.clientX,y:e.clientY}; state.spin=false; return; }\n"
    "  if(state.tool==='add'){ addMassAt(e.clientX,e.clientY); return; }   // S2\n")
rep("  if(i<0){ state.sel=-1; return; }\n",
    "  if(i<0){ state.sel=-1; return; }\n"
    "  if(state.tool==='del'){ deleteMass(i); return; }   // S2\n")

BUILD = r'''
// ---- S2: free building -----------------------------------------------------------------
// add: tap empty space; the new mass appears under the finger, in the plane of the nearest mass,
// and is wired to its nearest neighbour so it can vibrate. delete: tap a mass; its springs go with
// it, and the strike and mic move to the nearest remaining mass if they were on it.
const MAX_MASSES=100;   // keeps background tuning to seconds on a phone; check "slowest" in Copy report
let toolMsgTimer=0;
function toolMsg(t){ const m=document.getElementById('nudgeMsg'); if(!m) return; m.textContent=t||''; clearTimeout(toolMsgTimer); if(t) toolMsgTimer=setTimeout(()=>{ m.textContent=''; },2600); }
function addMassAt(cx,cy){
  const g=state.geo; if(!g) return;
  if(g.P.length>=MAX_MASSES){ toolMsg('Limit reached: '+MAX_MASSES+' masses'); return; }
  const r=cv.getBoundingClientRect(), x=cx-r.left, y=cy-r.top;
  let near=-1, nd=1e9;
  for(let i=0;i<g.P.length;i++){ const dx=_px[i]-x, dy=_py[i]-y, d=dx*dx+dy*dy; if(d<nd){ nd=d; near=i; } }
  if(near>=0&&nd<18*18){ toolMsg('tap empty space'); return; }
  const M=state.M, q=near>=0?g.P[near]:[0,0,0];
  const Z0=M[6]*q[0]+M[7]*q[1]+M[8]*q[2];
  const sc=Math.min(W,H)*0.86, f=2.9/(2.9-Z0);
  const X=(x-W/2)/(sc*f), Y=(y-H*0.46)/(sc*f);
  const p=[0,1,2].map(k=>+Math.max(-0.6,Math.min(0.6,M[k]*X+M[3+k]*Y+M[6+k]*Z0)).toFixed(4));
  let link=-1, ld=1e9;
  for(let i=0;i<g.P.length;i++){ const o=g.P[i], d=(o[0]-p[0])**2+(o[1]-p[1])**2+(o[2]-p[2])**2; if(d<ld){ ld=d; link=i; } }
  if(link<0||ld<1e-4){ toolMsg('too close to another mass'); return; }
  geoPush();
  g.P.push(p); g.F=Uint8Array.from([...g.F,0]); g.S.push([link,g.P.length-1]);
  state.sel=g.P.length-1; rebuild(); toolMsg('');
}
function pieceOf(g,start){   // every mass connected to `start` through springs
  const seen=new Set([start]), st=[start];
  while(st.length){ const a=st.pop(); for(const t of g.S){ const o=t[0]===a?t[1]:(t[1]===a?t[0]:-1); if(o>=0&&!seen.has(o)){ seen.add(o); st.push(o); } } }
  return seen;
}
function deleteMass(i){
  const g=state.geo; if(!g) return;
  let freeLeft=0; for(let k=0;k<g.P.length;k++) if(k!==i&&!g.F[k]) freeLeft++;
  if(g.P.length<=3||freeLeft<1){ toolMsg('keep at least 3 masses'); return; }
  const S2=g.S.filter(t=>t[0]!==i&&t[1]!==i).map(t=>[t[0]>i?t[0]-1:t[0], t[1]>i?t[1]-1:t[1]]);
  if(!S2.length){ toolMsg('that would leave no springs'); return; }
  geoPush();
  const P0=g.P[i];
  g.P.splice(i,1); g.F=Uint8Array.from(Array.from(g.F).filter((_,k)=>k!==i)); g.S=S2;
  const d2=(a,b)=>(a[0]-b[0])**2+(a[1]-b[1])**2+(a[2]-b[2])**2;
  const nearestFree=(set)=>{ let best=-1, bd=1e9; g.P.forEach((p,k)=>{ if(g.F[k]||(set&&!set.has(k))) return; const d=d2(p,P0); if(d<bd){ bd=d; best=k; } }); return best; };
  const shift=idx=>idx>i?idx-1:idx;
  // a deletion can cut a body in two. A strike or mic that loses its mass moves to the nearest mass
  // on its partner's piece, so the pair stays connected; pickups you didn't touch stay put.
  const hitGone=state.hitIdx===i, micGone=state.micIdx===i;
  if(!hitGone) state.hitIdx=shift(state.hitIdx);
  if(!micGone) state.micIdx=shift(state.micIdx);
  const onPiece=(partner)=>{ const set=partner>=0?pieceOf(g,partner):null; const k=set?nearestFree(set):-1; return k>=0?k:nearestFree(); };
  if(hitGone) state.hitIdx=onPiece(micGone?-1:state.micIdx);
  if(micGone) state.micIdx=onPiece(state.hitIdx);
  const piece=pieceOf(g,state.hitIdx);
  state.sel=-1; rebuild();
  const sepMsg=piece.has(state.micIdx)?'':'strike and mic are on separate pieces now';
  // second mic: as far from the first as the struck piece allows (as on load, but never on a silent piece)
  let far=-1, fd=-1; const pm=g.P[state.micIdx];
  g.P.forEach((p,k)=>{ if(g.F[k]||k===state.micIdx||!piece.has(k)) return; const d=d2(p,pm); if(d>fd){ fd=d; far=k; } });
  if(far<0){ const F=state.free, n=F.length; far=n?F[(Math.max(0,F.indexOf(state.micIdx))+Math.max(1,Math.floor(n/2)))%n]:-1; }
  state.micIdx2=far;
  if(node) node.port.postMessage({t:'mic2',i:state.micIdx2});
  syncPickSliders(); toolMsg(sepMsg);
}
'''
rep("function geoSnap(){\n", BUILD + "function geoSnap(){\n")

# ---------- undo covers shape and Size changes, so a hand-built instrument can't vanish ----------
rep("""  return {P:g.P.map(p=>p.slice()),F:Array.from(g.F),S:g.S.map(s=>s.slice()),
          mic:state.micIdx,hit:state.hitIdx};""",
    """  return {P:g.P.map(p=>p.slice()),F:Array.from(g.F),S:g.S.map(s=>s.slice()),
          mic:state.micIdx,hit:state.hitIdx,shape:g.shape||state.shape,n:g.n||state.n,axis:g.axis!=null?g.axis:state.axis};   // S2: the body's own shape and size""")
rep("""  state.micIdx=s.mic; state.hitIdx=s.hit;
  rebuild();
}""",
    """  state.micIdx=s.mic; state.hitIdx=s.hit;
  if(s.shape&&SHAPES[s.shape]&&(s.shape!==state.shape||s.n!==state.n)){   // S2: undo across a shape or Size change
    const S=SHAPES[s.shape]; state.shape=s.shape; state.n=s.n; state.axis=s.axis!=null?s.axis:state.axis; g.axis=state.axis; g.shape=s.shape; g.n=s.n;
    val.size=(s.n-S.min)/Math.max(1,S.max-S.min); syncKnob('size');
    [...shapesEl.children].forEach(c=>c.setAttribute('aria-pressed',c.textContent===s.shape));
    const bt=document.getElementById('bodytext'); if(bt) bt.textContent=S.note;
  }
  rebuild();
}""")
rep("function buildShape(resetPickups){\n if(state.hist){state.hist.length=0;state.redo.length=0;syncUndo();}\n",
    "function buildShape(resetPickups){\n if(state.hist&&state.geo){state.hist.push(geoSnap());if(state.hist.length>40)state.hist.shift();state.redo.length=0;syncUndo();}   // S2: shape/Size changes are undoable\n")
# every body carries the shape and size it was built from, so a snapshot can't pair one body
# with another body's label (the Size knob and shape buttons update the label before rebuilding)
rep(" const S=SHAPES[state.shape],g=S.make(state.n);state.geo=g;state.axis=g.axis;",
    " const S=SHAPES[state.shape],g=S.make(state.n);g.shape=state.shape;g.n=state.n;state.geo=g;state.axis=g.axis;")
rep("             axis:state.axis,mic:o.micIdx,hit:o.hitIdx,note:''};",
    "             axis:state.axis,mic:o.micIdx,hit:o.hitIdx,note:'',shape:state.shape,n:state.n};   // S2")

open(P, 'w', encoding='utf-8').write(s)
print('patched', P)
