# F2 revision: true-peak (4x oversampled) lookahead limiter. Verified edits; abort on mismatch.
import sys
P=sys.argv[1]; s=open(P,encoding='utf-8').read()
def rep(old,new):
    global s
    n=s.count(old)
    if n!=1: sys.exit(f'ABORT: expected 1, found {n}: {old[:60]!r}')
    s=s.replace(old,new)
rep("    this.lvl=1; this.limG=1; this.limC=0.8414; this.limRel=1-Math.exp(-1/(0.08*sampleRate));\n",
    "    this.lvl=1; this.limG=1; this.limC=0.8414; this.limRel=1-Math.exp(-1/(0.08*sampleRate));\n"
    "    // 16-sample lookahead (0.33 ms at 48 kHz). Peaks between samples are found by 4x\n"
    "    // windowed-sinc interpolation, so the ceiling holds as true peak, not just sample peak.\n"
    "    this.tpD=16; this.tpL=new Float64Array(32); this.tpR=new Float64Array(32); this.tpGr=new Float64Array(32).fill(1); this.tpI=0;\n"
    "    this.tpK=[]; for(let f=1;f<4;f++){ const fr=f/4, k=new Float64Array(16);\n"
    "      for(let j=0;j<16;j++){ const t=(j-7)-fr; const w=0.5+0.5*Math.cos(Math.PI*t/8.5); k[j]=(t===0?1:Math.sin(Math.PI*t)/(Math.PI*t))*w; }\n"
    "      this.tpK.push(k); }\n")
rep("      { const pk=Math.max(ll<0?-ll:ll, rr<0?-rr:rr); let g=this.limG;   // F2: ceiling limiter, -1 dBTP\n"
    "        if(g<1){ g+=(1-g)*this.limRel; if(g>0.99999) g=1; }\n"
    "        if(pk*g>this.limC) g=this.limC/pk;\n"
    "        this.limG=g; if(g<1){ ll*=g; rr*=g; } }\n"
    "      L[k]=ll; if(R) R[k]=rr;\n",
    "      { // F2: true-peak lookahead limiter, ceiling -1 dBTP. Gain is exactly 1 below the ceiling.\n"
    "        const B=this.tpL, C=this.tpR, I=this.tpI, D=this.tpD, Cc=this.limC;\n"
    "        B[I]=ll; C[I]=rr;\n"
    "        // peak around the sample 8 behind the newest, including the three points between it and the next\n"
    "        const c0=(I-8)&31; let pk=Math.max(Math.abs(B[c0]),Math.abs(C[c0]));\n"
    "        let near=0; for(let j=0;j<16;j++){ const q=(I-15+j)&31; const a=Math.max(Math.abs(B[q]),Math.abs(C[q])); if(a>near) near=a; }\n"
    "        if(near>Cc*0.3){ for(let f=0;f<3;f++){ const K=this.tpK[f]; let xl=0,xr=0;\n"
    "            for(let j=0;j<16;j++){ const q=(I-15+j)&31; xl+=B[q]*K[j]; xr+=C[q]*K[j]; }\n"
    "            const a=Math.max(Math.abs(xl),Math.abs(xr)); if(a>pk) pk=a; } }\n"
    "        this.tpGr[c0]=pk>Cc?Cc/pk:1;\n"
    "        let need=1; for(let j=0;j<24;j++){ const q=(I-8-j)&31; if(this.tpGr[q]<need) need=this.tpGr[q]; }\n"
    "        let g=this.limG; if(g<1){ g+=(1-g)*this.limRel; if(g>0.99999) g=1; } if(need<g) g=need;\n"
    "        this.limG=g; const o=(I-D)&31; let ol=B[o], or=C[o]; if(g<1){ ol*=g; or*=g; }\n"
    "        this.tpI=(I+1)&31;\n"
    "        L[k]=ol; if(R) R[k]=or; }\n")
open(P,'w',encoding='utf-8').write(s); print('patched OK')
