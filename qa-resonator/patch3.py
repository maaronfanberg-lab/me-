# F5: fast eigen-solver for large bodies (>60 degrees of freedom) so building Tank and
# max-size shapes no longer freezes the audio thread. Bodies at or under 60 dof keep the
# original Jacobi path untouched. Verified edits: abort on any mismatch.
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()
tql = open(sys.argv[2], encoding='utf-8').read()
def rep(old, new):
    global s
    n = s.count(old)
    if n != 1: sys.exit(f'ABORT: expected 1, found {n}: {old[:70]!r}')
    s = s.replace(old, new)

# turn the standalone function into a class method
body = tql[tql.index('function eigTQL(A, n, valuesOnly) {'):tql.index('if (typeof module')].rstrip()
body = body.replace('function eigTQL(A, n, valuesOnly) {', '  tql(A,n,valuesOnly){', 1)
body = '\n'.join(('  ' + l if l.strip() and not l.startswith('  tql(') else l) for l in body.split('\n'))
assert '`' not in body and '${' not in body, 'ABORT: template chars in solver'

rep("  // Rank modes by how loudly they actually arrive: modal amplitude for an\n  // impulsive force at the strike point, sensed by the mic vector.\n  modeSpectrum(kT,kL,sub){\n    const n=3*this.F; if(n===0) return null;\n    const K=this.assembleK(kT,kL,sub);\n    const {lam,V}=this.jacobi(K,n);\n",
    "  // F5: symmetric eigen-solver for large bodies. Householder tridiagonalisation + implicit QL\n"
    "  // (public-domain JAMA/EISPACK tred2/tql2). Agrees with jacobi() to ~1e-13 relative and is\n"
    "  // 8x faster with mode shapes, ~25x faster for frequencies alone.\n"
    + body + "\n"
    "  // Rank modes by how loudly they actually arrive: modal amplitude for an\n  // impulsive force at the strike point, sensed by the mic vector.\n"
    "  modeSpectrum(kT,kL,sub,valuesOnly){\n    const n=3*this.F; if(n===0) return null;\n    const K=this.assembleK(kT,kL,sub);\n"
    "    const big=n>60;                                            // F5: small bodies keep the original solver\n"
    "    if(big&&valuesOnly){                                       // frequencies only: drop the rigid modes counted at full solve\n"
    "      const ev=this.tql(K,n,true).lam, keep=[];\n"
    "      for(let m=0;m<n;m++) if(ev[m]>1e-9) keep.push(ev[m]);\n"
    "      keep.sort((a,b)=>a-b);\n"
    "      const out=[]; for(let m=this.rigidN;m<keep.length;m++){ const w=Math.sqrt(keep[m]); out.push({f:w/(2*Math.PI),amp:0}); }\n"
    "      return out;\n"
    "    }\n"
    "    const {lam,V}=big?this.tql(K,n,false):this.jacobi(K,n);\n"
    "    let rigN=0,rigLow=true,elastic=0;                          // F5: record whether rigid modes are the lowest ones\n")
rep("      if(!this.anchored && tot>0 && rig/tot>0.5) continue;   // anchored bodies have no rigid modes\n",
    "      if(!this.anchored && tot>0 && rig/tot>0.5){ rigN++; if(elastic) rigLow=false; continue; }   // anchored bodies have no rigid modes\n")
rep("      out.push({f:w/(2*Math.PI), amp:Math.abs(h*c)/w});\n    }\n    out.sort((p,q)=>p.f-q.f);\n    return out;\n  }",
    "      out.push({f:w/(2*Math.PI), amp:Math.abs(h*c)/w});\n    }\n    out.sort((p,q)=>p.f-q.f);\n    this.rigidN=rigN; this.rigidLow=rigLow&&this.orderedScan;\n    return out;\n  }")
# rigLow needs modes visited in ascending frequency; tql returns them ascending, jacobi does not
rep("    const {lam,V}=big?this.tql(K,n,false):this.jacobi(K,n);\n",
    "    const {lam,V}=big?this.tql(K,n,false):this.jacobi(K,n);\n"
    "    this.orderedScan=big; if(big){ for(let m=1;m<n;m++) if(lam[m]<lam[m-1]){ this.orderedScan=false; break; } }\n")
rep("      const sp=this.modeSpectrum(kT,q.kL,Math.max(this.sub,subFloor)*kT);\n",
    "      const sp=this.modeSpectrum(kT,q.kL,Math.max(this.sub,subFloor)*kT,fast);\n")
rep("    let bi=0; for(let i=1;i<sp0.length;i++) if(sp0[i].amp>sp0[bi].amp) bi=i;\n",
    "    let bi=0; for(let i=1;i<sp0.length;i++) if(sp0[i].amp>sp0[bi].amp) bi=i;\n"
    "    // F5: large bodies take the frequencies-only path when the full solve shows the rigid\n"
    "    // modes are exactly the lowest ones; both table ends are then re-checked with full solves.\n"
    "    const fast=3*this.F>60 && this.rigidLow;\n")
rep("    for(let i=1;i<T.length;i++) if(T[i][1]<=T[i-1][1]) T[i][1]=T[i-1][1]+1e-6;\n    this.table=T.length>1?T:null;\n  }",
    "    if(fast){\n"
    "      let ok=T.length===P;\n"
    "      if(ok) for(const i of [0,P-1]){\n"
    "        const kT=this.kRef*Math.pow(10,-4+6*i/(P-1)), q=this.kLfor(kT);\n"
    "        const sp=this.modeSpectrum(kT,q.kL,Math.max(this.sub,subFloor)*kT);\n"
    "        if(!sp||sp.length<=bi||!this.rigidLow||Math.abs(Math.log(sp[bi].f)-T[i][1])>1e-9){ ok=false; break; }\n"
    "      }\n"
    "      if(!ok){ T.length=0; this.fastFallbacks=(this.fastFallbacks||0)+1;\n"
    "        for(let i=0;i<P;i++){\n"
    "          const kT=this.kRef*Math.pow(10,-4+6*i/(P-1)), q=this.kLfor(kT);\n"
    "          const sp=this.modeSpectrum(kT,q.kL,Math.max(this.sub,subFloor)*kT);\n"
    "          if(!sp||sp.length<=bi) continue;\n"
    "          T.push([Math.log(kT),Math.log(sp[bi].f)]);\n"
    "        }\n"
    "      }\n"
    "    }\n"
    "    for(let i=1;i<T.length;i++) if(T[i][1]<=T[i-1][1]) T[i][1]=T[i-1][1]+1e-6;\n    this.table=T.length>1?T:null;\n  }")
open(P, 'w', encoding='utf-8').write(s)
print('patched OK')
