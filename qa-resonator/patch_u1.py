# Stage U1 (preview): scrolling the controls no longer moves them. docs/research/resonator-U1-scroll-2026-10-13.md
#  Before: every slider bar and +/- button acted on touchstart, called preventDefault and had touch-action:none, so a
#  scroll that began on a control changed it and could not scroll; the label's double-tap reset fired on any two
#  touch-downs within 400 ms, so two quick flicks across labels could reset a knob.
#  After (touch slop, as native scroll views do it): nothing happens until the finger shows what it means.
#   - bar: touch-action pan-y (the browser may scroll vertically); moved 10 px mostly sideways = slider drag from
#     there on; moved 10 px otherwise = a scroll, ignored; lifted within 10 px and 500 ms = a tap, which sets the value
#     where it landed.
#   - +/- buttons: a tap (lifted within 10 px) = one step; held still 400 ms = repeat; moved 10 px = a scroll, ignored.
#   - label: double-tap reset counts real taps only (click events, which a scroll never produces).
#   - mouse and pen: unchanged (they act at once, as before); pointer events of type touch are ignored, touch events
#     drive touch, so a gesture is never handled twice.
# Engine untouched. Edits apps/resonator-next.html in place; aborts on any mismatch.
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f'ABORT: expected {count} match(es), found {n}: {old[:100]!r}')
    s = s.replace(old, new)

rep(""".step{flex:0 0 46px;height:42px;appearance:none;border:1px solid var(--rule);background:#101A2E;""",
    """.step{flex:0 0 46px;height:42px;appearance:none;border:1px solid var(--rule);background:#101A2E;touch-action:pan-y;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none;""")
rep(""".bar{position:relative;flex:1 1 auto;height:42px;cursor:pointer;touch-action:none;""",
    """.bar{position:relative;flex:1 1 auto;height:42px;cursor:pointer;touch-action:pan-y;-webkit-user-select:none;user-select:none;""")
rep(""".step:active{background:var(--compress);color:var(--ink)}""",
    """.step.held{background:var(--compress);color:var(--ink)}   /* U1: lit while it acts, not while a scroll passes over it */""")

rep(""" let down=false;
 bar.addEventListener('pointerdown',e=>{DIAG.down++;down=true;try{bar.setPointerCapture(e.pointerId);}catch(err){DIAG.err=String(err.message||err);}set(e.clientX);e.preventDefault();});
 bar.addEventListener('pointermove',e=>{DIAG.move++;if(down){set(e.clientX);e.preventDefault();}});
 bar.addEventListener('pointerup',e=>{DIAG.up++;down=false;});
 bar.addEventListener('pointercancel',e=>{DIAG.cancel++;down=false;});
 // Some webviews deliver touch events but not usable pointer events. Handle both;
 // a guard stops the same gesture being counted twice.
 let touching=false;
 bar.addEventListener('touchstart',e=>{
   touching=true; DIAG.tdown++;
   const t=e.touches[0]; if(t) set(t.clientX);
   e.preventDefault();
 },{passive:false});
 bar.addEventListener('touchmove',e=>{
   DIAG.tmove++;
   if(touching){ const t=e.touches[0]; if(t) set(t.clientX); }
   e.preventDefault();
 },{passive:false});
 bar.addEventListener('touchend',e=>{touching=false;},{passive:true});
 bar.addEventListener('touchcancel',e=>{touching=false;},{passive:true});""",
""" // Mouse and pen act at once. Touch is decided by the finger (U1): see TOUCH_SLOP.
 let down=false;
 bar.addEventListener('pointerdown',e=>{DIAG.down++;if(e.pointerType==='touch')return;down=true;try{bar.setPointerCapture(e.pointerId);}catch(err){DIAG.err=String(err.message||err);}set(e.clientX);e.preventDefault();});
 bar.addEventListener('pointermove',e=>{DIAG.move++;if(down&&e.pointerType!=='touch'){set(e.clientX);e.preventDefault();}});
 bar.addEventListener('pointerup',e=>{DIAG.up++;down=false;});
 bar.addEventListener('pointercancel',e=>{DIAG.cancel++;down=false;});
 // U1: a touch does nothing until it shows what it is. Sideways past the slop: a drag. Any other way past it: a
 // scroll, left to the page. Lifted inside it, quickly: a tap, which sets the value where the finger landed.
 let tch=null;
 bar.addEventListener('touchstart',e=>{
   DIAG.tdown++; const t=e.changedTouches[0]; if(!t||e.touches.length>1){ tch=null; return; }
   tch={id:t.identifier,x0:t.clientX,y0:t.clientY,t0:performance.now(),mode:''};
 },{passive:true});
 bar.addEventListener('touchmove',e=>{
   DIAG.tmove++; if(!tch) return;
   let t=null; for(const q of e.changedTouches) if(q.identifier===tch.id) t=q; if(!t) return;
   if(!tch.mode){
     const dx=t.clientX-tch.x0, dy=t.clientY-tch.y0;
     if(Math.abs(dx)>=TOUCH_SLOP&&Math.abs(dx)>1.5*Math.abs(dy)) tch.mode='drag';
     else if(Math.hypot(dx,dy)>=TOUCH_SLOP){ tch.mode='scroll'; DIAG.scrolls++; }
   }
   if(tch.mode==='drag'){ if(e.cancelable) e.preventDefault(); set(t.clientX); }
 },{passive:false});
 bar.addEventListener('touchend',e=>{
   if(!tch) return; const c=tch; tch=null;
   let t=null; for(const q of e.changedTouches) if(q.identifier===c.id) t=q;
   if(!c.mode&&t&&performance.now()-c.t0<500&&Math.hypot(t.clientX-c.x0,t.clientY-c.y0)<TOUCH_SLOP){ set(c.x0); if(e.cancelable) e.preventDefault(); }
 },{passive:false});
 bar.addEventListener('touchcancel',()=>{ tch=null; },{passive:true});""")

rep(""" let lastTap=0;
 wrap.querySelector('.lab').addEventListener('pointerdown',()=>{
   const now=Date.now();
   if(now-lastTap<400){ inp.value=K.val; inp.dispatchEvent(new Event('input',{bubbles:true})); }
   lastTap=now;
 });""", """ let lastTap=0;
 wrap.querySelector('.lab').addEventListener('click',()=>{   // U1: taps only (a scroll never makes a click)
   const now=Date.now();
   if(now-lastTap<400){ inp.value=K.val; inp.dispatchEvent(new Event('input',{bubbles:true})); lastTap=0; return; }
   lastTap=now;
 });""")

rep("""   let timer=null, held=0;
   const stop=()=>{ if(timer){clearInterval(timer);timer=null;} held=0; };
   const start=()=>{
     bump(); held=0;
     timer=setInterval(()=>{ held++; const n=held>14?4:held>6?2:1; for(let q=0;q<n;q++) bump(); },110);
   };
   sb.addEventListener('pointerdown',e=>{e.preventDefault();start();});
   sb.addEventListener('pointerup',stop);
   sb.addEventListener('pointerleave',stop);
   sb.addEventListener('pointercancel',stop);
   sb.addEventListener('touchstart',e=>{e.preventDefault();if(!timer)start();},{passive:false});
   sb.addEventListener('touchend',stop,{passive:true});
   sb.addEventListener('touchcancel',stop,{passive:true});
   sb.addEventListener('click',e=>{e.preventDefault();});""", """   let timer=null, held=0, wait=0, tb=null;
   const stop=()=>{ if(timer){clearInterval(timer);timer=null;} if(wait){clearTimeout(wait);wait=0;} held=0; sb.classList.remove('held'); };
   const repeat=()=>{ sb.classList.add('held'); held=0;
     timer=setInterval(()=>{ held++; const n=held>14?4:held>6?2:1; for(let q=0;q<n;q++) bump(); },110); };
   // mouse and pen: at once, as before
   sb.addEventListener('pointerdown',e=>{ if(e.pointerType==='touch') return; e.preventDefault(); stop(); bump(); repeat(); });
   sb.addEventListener('pointerup',e=>{ if(e.pointerType!=='touch') stop(); });
   sb.addEventListener('pointerleave',e=>{ if(e.pointerType!=='touch') stop(); });
   sb.addEventListener('pointercancel',e=>{ if(e.pointerType!=='touch') stop(); });
   // U1 touch: a tap is one step; held still, it repeats; moved, it was a scroll and does nothing
   sb.addEventListener('touchstart',e=>{ const t=e.changedTouches[0]; if(!t||e.touches.length>1){ tb=null; stop(); return; }
     stop(); tb={id:t.identifier,x0:t.clientX,y0:t.clientY,on:false};
     wait=setTimeout(()=>{ wait=0; if(tb&&!tb.moved){ tb.on=true; bump(); repeat(); } },HOLD_MS); },{passive:true});
   sb.addEventListener('touchmove',e=>{ if(!tb) return; for(const t of e.changedTouches) if(t.identifier===tb.id&&Math.hypot(t.clientX-tb.x0,t.clientY-tb.y0)>=TOUCH_SLOP){
       if(tb.on){ if(e.cancelable) e.preventDefault(); } else { tb.moved=true; stop(); DIAG.scrolls++; } } },{passive:false});
   sb.addEventListener('touchend',e=>{ if(!tb) return; const c=tb; tb=null; const was=c.on; stop();
     if(!was&&!c.moved){ bump(); sb.classList.add('held'); setTimeout(()=>sb.classList.remove('held'),120); }
     if(e.cancelable) e.preventDefault(); },{passive:false});   // no click and no double-tap zoom afterwards
   sb.addEventListener('touchcancel',()=>{ tb=null; stop(); },{passive:true});
   sb.addEventListener('click',e=>{e.preventDefault();});""")

rep("""function attachDrag(bar,inp,paint){""", """// U1: how far a finger may wander before a touch counts as a drag or a scroll (Android's touch slop is 8 dp; 10 CSS px
// here, a little more forgiving for a resting thumb), and how long a +/- must be held still before it repeats
const TOUCH_SLOP=10, HOLD_MS=400;
function attachDrag(bar,inp,paint){""")
rep("""const DIAG={errs:[],down:0,move:0,up:0,cancel:0,tdown:0,tmove:0,taps:0,sets:0,""", """const DIAG={errs:[],down:0,move:0,up:0,cancel:0,tdown:0,tmove:0,taps:0,sets:0,scrolls:0,""")
rep("""  '+/- taps         '+DIAG.taps+'\\n'+""", """  '+/- taps         '+DIAG.taps+'\\n'+
  'scrolls ignored  '+DIAG.scrolls+'   <- touches on a control that turned out to be a scroll\\n'+""")
open(P, 'w', encoding='utf-8').write(s)
print('patch_u1: ok')
