# Stage F (preview): a plate reverb after everything else and before the true-peak limiter.
# Topology and constants: J. Dattorro, "Effect Design Part 1: Reverberator and Other Filters",
# JAES 45(9), 1997 (Table 1 coefficients, Table 2 output taps; Fs = 29761 Hz). Delay lengths
# cross-checked against the freeverb3 technical notes (Figure 5); every output tap lies inside its
# line. Reverb at 0 is bypassed entirely, so the sound without it is unchanged bit for bit.
# Edits apps/resonator-next.html in place; aborts on any mismatch.
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
eng("    this.spL=0; this.spR=0; this.fxL=0; this.fxR=0;\n",
    "    this.spL=0; this.spR=0; this.fxL=0; this.fxR=0;\n"
    "    // F: plate reverb (Dattorro 1997). Off until Reverb is above 0; buffers made on first use.\n"
    "    this.rvMix=0; this.rvTime=2.5; this.rvTone=9000; this.rvPre=20; this.rvOn=false; this.rv=null;\n"
    "    this.rvDec=0.5; this.rvDd2=0.5; this.rvDamp=0; this.rvPreN=0; this.rvK=1; this.rvOutL=0; this.rvOutR=0;\n")
eng("        if(d.k==='pkAp'||d.k==='pkSpc'){ this.buildCoils(); }\n",
    "        if(d.k==='pkAp'||d.k==='pkSpc'){ this.buildCoils(); }\n"
    "        if(d.k==='rvMix'||d.k==='rvTime'||d.k==='rvTone'||d.k==='rvPre') this.rvSet();   // F\n")
eng("      case 'hush': this.gateTarget=0;",
    "      case 'hush': if(this.rv) this.rvClear(); this.gateTarget=0;")
eng("  observe(dtBlock){",
    "  // F: plate reverb. Dattorro's figure-of-eight tank, scaled from his 29761 Hz to this engine's rate.\n"
    "  // T60 from Reverb time: one trip round the eight is 21589 samples at 29761 Hz with decay applied four\n"
    "  // times, so decay = 0.001^(trip / (4 T60)) (low frequencies; the damping filter shortens the highs).\n"
    "  rvSet(){\n"
    "    const was=this.rvOn; this.rvOn=this.rvMix>0.0005;\n"
    "    const trip=21589/29761;\n"
    "    this.rvDec=Math.exp(Math.log(0.001)*trip/(4*Math.max(0.1,this.rvTime)));\n"
    "    this.rvDd2=Math.min(0.5,Math.max(0.25,this.rvDec+0.15));          // Dattorro: decay + 0.15, 0.25..0.50\n"
    "    this.rvDamp=Math.exp(-2*Math.PI*Math.min(this.rvTone,0.45*sampleRate)/sampleRate);   // one-pole: y=(1-d)x+d*y1\n"
    "    this.rvPreN=Math.max(0,Math.round(Math.min(250,this.rvPre)*sampleRate/1000));\n"
    "    if(this.rvOn&&!was){ if(!this.rv) this.rvAlloc(); this.rvClear(); }\n"
    "  }\n"
    "  rvAlloc(){\n"
    "    const k=sampleRate/29761, r=n=>Math.max(1,Math.round(n*k)), ex=Math.ceil(16*k)+3;\n"
    "    const L=(n,extra)=>({b:new Float64Array(r(n)+(extra||0)+2),p:0,n:r(n)});\n"
    "    this.rv={ap1:L(142),ap2:L(107),ap3:L(379),ap4:L(277),m1:L(672,ex),d1:L(4453),a1:L(1800),d2:L(3720),\n"
    "      m2:L(908,ex),d3:L(4217),a2:L(2656),d4:L(3163),pre:{b:new Float64Array(Math.ceil(0.26*sampleRate)+2),p:0,n:0},\n"
    "      bw:0,lp1:0,lp2:0,lOut:0,rOut:0,ph:0,dph:1/sampleRate,exc:16*k,\n"
    "      tL:[r(266),r(2974),r(1913),r(1996),r(1990),r(187),r(1066)],tR:[r(353),r(3627),r(1228),r(2673),r(2111),r(335),r(121)]};\n"
    "  }\n"
    "  rvClear(){ const R=this.rv; if(!R) return;\n"
    "    for(const o of [R.ap1,R.ap2,R.ap3,R.ap4,R.m1,R.d1,R.a1,R.d2,R.m2,R.d3,R.a2,R.d4,R.pre]){ o.b.fill(0); o.p=0; }\n"
    "    R.bw=0; R.lp1=0; R.lp2=0; R.lOut=0; R.rOut=0; R.ph=0; this.rvOutL=0; this.rvOutR=0; }\n"
    "  rvRd(o,k){ let i=o.p-k; if(i<0) i+=o.b.length; return o.b[i]; }            // input k samples ago\n"
    "  rvWr(o,x){ o.b[o.p]=x; if(++o.p>=o.b.length) o.p=0; }\n"
    "  rvTap(o,k){ let i=o.p-1-k; if(i<0) i+=o.b.length; return o.b[i]; }        // after this sample's write\n"
    "  rvAp(o,x,g){ const d=this.rvRd(o,o.n), w=x+g*d; this.rvWr(o,w); return d-g*w; }   // (-g+z^-N)/(1-g z^-N)\n"
    "  rvApm(o,x,g,off){ const dd=o.n+off, i0=Math.floor(dd), f=dd-i0;\n"
    "    const a=this.rvRd(o,i0), b=this.rvRd(o,i0+1), d=a+(b-a)*f, w=x+g*d; this.rvWr(o,w); return d-g*w; }\n"
    "  reverbSample(xl,xr){\n"
    "    const R=this.rv, pre=R.pre;\n"
    "    pre.b[pre.p]=(xl+xr)*0.5; let ip=pre.p-this.rvPreN; if(ip<0) ip+=pre.b.length; let x=pre.b[ip]; if(++pre.p>=pre.b.length) pre.p=0;\n"
    "    R.bw+=0.9995*(x-R.bw); x=R.bw;                                   // bandwidth 0.9995\n"
    "    x=this.rvAp(R.ap1,x,0.75); x=this.rvAp(R.ap2,x,0.75); x=this.rvAp(R.ap3,x,0.625); x=this.rvAp(R.ap4,x,0.625);\n"
    "    R.ph+=R.dph; if(R.ph>=1) R.ph-=1;                                 // 1 Hz, quadrature left/right\n"
    "    const w=2*Math.PI*R.ph, dec=this.rvDec, dd2=this.rvDd2, dm=this.rvDamp;\n"
    "    let l=x+dec*R.rOut, r=x+dec*R.lOut, d;\n"
    "    l=this.rvApm(R.m1,l,-0.70,R.exc*Math.sin(w));                      // decay diffusion 1, negative\n"
    "    d=this.rvRd(R.d1,R.d1.n); this.rvWr(R.d1,l); l=d;\n"
    "    R.lp1=(1-dm)*l+dm*R.lp1; l=R.lp1*dec;\n"
    "    l=this.rvAp(R.a1,l,dd2);\n"
    "    d=this.rvRd(R.d2,R.d2.n); this.rvWr(R.d2,l); l=d;\n"
    "    r=this.rvApm(R.m2,r,-0.70,R.exc*Math.cos(w));\n"
    "    d=this.rvRd(R.d3,R.d3.n); this.rvWr(R.d3,r); r=d;\n"
    "    R.lp2=(1-dm)*r+dm*R.lp2; r=R.lp2*dec;\n"
    "    r=this.rvAp(R.a2,r,dd2);\n"
    "    d=this.rvRd(R.d4,R.d4.n); this.rvWr(R.d4,r); r=d;\n"
    "    R.lOut=l; R.rOut=r;\n"
    "    const tL=R.tL, tR=R.tR;   // Dattorro Table 2: every tap x 0.6\n"
    "    this.rvOutL=0.6*(this.rvTap(R.d3,tL[0])+this.rvTap(R.d3,tL[1])-this.rvTap(R.a2,tL[2])+this.rvTap(R.d4,tL[3])-this.rvTap(R.d1,tL[4])-this.rvTap(R.a1,tL[5])-this.rvTap(R.d2,tL[6]));\n"
    "    this.rvOutR=0.6*(this.rvTap(R.d1,tR[0])+this.rvTap(R.d1,tR[1])-this.rvTap(R.a1,tR[2])+this.rvTap(R.d2,tR[3])-this.rvTap(R.d3,tR[4])-this.rvTap(R.a2,tR[5])-this.rvTap(R.d4,tR[6]));\n"
    "  }\n"
    "  observe(dtBlock){")
eng("      if(this.lvl!==1){ ll*=this.lvl; rr*=this.lvl; }          // F3: per-shape level calibration\n",
    "      if(this.lvl!==1){ ll*=this.lvl; rr*=this.lvl; }          // F3: per-shape level calibration\n"
    "      if(this.rvOn){ this.reverbSample(ll,rr); const gw=this.rvMix*this.rvK; ll+=gw*this.rvOutL; rr+=gw*this.rvOutR; }   // F: plate reverb\n")

# ---------------- page ----------------
rep("      <div class=\"knob\" data-k=\"fxSat\"></div>\n    </section>\n",
    "      <div class=\"knob\" data-k=\"fxSat\"></div>\n"
    "      <div class=\"secttl\">Plate reverb</div>\n"
    "      <div class=\"knob\" data-k=\"rvMix\"></div>\n"
    "      <div class=\"knob\" data-k=\"rvTime\"></div>\n"
    "      <div class=\"knob\" data-k=\"rvTone\"></div>\n"
    "      <div class=\"knob\" data-k=\"rvPre\"></div>\n"
    "    </section>\n")
rep(" cab:{label:'Cabinet',",
    " rvMix:{label:'Reverb',min:0,max:1,step:0.01,val:0,fmt:v=>v<0.005?'off':Math.round(v*100)+'%',hint:'A plate reverb, after everything else: the sound in a large ringing steel plate (Dattorro, 1997). At 0 it is switched off entirely.'},\n"
    " rvTime:{label:'Reverb time',min:0.3,max:12,step:0.05,val:2.5,fmt:v=>v.toFixed(1)+' s',hint:'How long the tail takes to fall by 60 dB.'},\n"
    " rvTone:{label:'Reverb tone',min:1000,max:16000,step:100,val:9000,fmt:v=>(v/1000).toFixed(1)+' kHz',hint:'The plate loses highs above this on every pass, so the tail darkens as it fades.'},\n"
    " rvPre:{label:'Pre-delay',min:0,max:250,step:1,val:20,fmt:v=>Math.round(v)+' ms',hint:'A gap before the reverb answers, like the distance to the first wall.'},\n"
    " cab:{label:'Cabinet',")
rep("'spElev','bowSpd','bowVc','wind','inGain'])", "'spElev','bowSpd','bowVc','wind','inGain','rvMix','rvTime','rvTone','rvPre'])", count=3)
rep("  for(const k in o.val) if(k in val) val[k]=o.val[k];\n",
    "  for(const k of ['rvMix','rvTime','rvTone','rvPre']) val[k]=KNOBS[k].val;   // F: a preset from before reverb has none\n"
    "  for(const k in o.val) if(k in val) val[k]=o.val[k];\n")

open(P, 'w', encoding='utf-8').write(s)
print('patched OK')
