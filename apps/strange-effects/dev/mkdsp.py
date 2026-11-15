import re
s=open('strange-effects.html').read()
m=re.search(r"const DSP_SRC=String\.raw`(.*?)`;\s*const WORKER_SRC",s,re.S)
open('dsp.js','w').write(m.group(1)+"\nmodule.exports={ND,formulaAttr,formulaSearch,EFFECTS,ATTR,DEFAULT_ROUTES,CINE_ROUTES,ALIVE_ROUTES,RANK_ROUTES,SWARM_ROUTES,makeDSP,rk4,IDX,Hall,pan5,rankPipeline,rankOf,mulberry};\n")
