# Pulls the sound engine out of the app page, so renders always use exactly the app's math.
import re,sys,pathlib
here=pathlib.Path(__file__).resolve().parent
s=(here.parent/'index.html').read_text()
m=re.search(r"const DSP_SRC=String\.raw`(.*?)`;\s*const WORKER_SRC",s,re.S)
if not m: sys.exit('engine source not found in index.html')
(here/'engine.js').write_text(m.group(1)+"\nmodule.exports={ND,formulaAttr,formulaSearch,EFFECTS,ATTR,SWARM_ROUTES,makeDSP};\n")
print('engine.js written',len(m.group(1)),'chars')
