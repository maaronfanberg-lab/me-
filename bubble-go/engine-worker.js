// Bubble Lab scientific worker. Single-bubble explorer using the validated radial core.
import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v314.0.6/full/pyodide.mjs';

const CDN = 'https://cdn.jsdelivr.net/pyodide/v314.0.6/full/';
const VALIDATED = '21a551fb13ab78ec7a6d0d714e29bf4cba07b33a';
const CORE = `https://raw.githubusercontent.com/maaronfanberg-lab/me-/${VALIDATED}/bubble/core.py`;
let py = null;

function say(type, text) { postMessage({ type, text }); }

async function init() {
  try {
    say('status', 'Loading Python scientific runtime…');
    py = await loadPyodide({ indexURL: CDN });
    await py.loadPackage(['numpy', 'scipy']);
    say('status', 'Loading validated bubble equations…');
    const r = await fetch(CORE);
    if (!r.ok) throw new Error('Could not load validated bubble core');
    py.FS.mkdirTree('/bubble');
    py.FS.writeFile('/bubble/__init__.py', '');
    py.FS.writeFile('/bubble/core.py', await r.text());
    await py.runPythonAsync("import sys; sys.path.insert(0,'/'); from bubble.core import BubbleParams, CouplingRamp, acceleration");
    say('ready', 'Bubble engine ready');
  } catch (e) {
    say('error', String(e && e.stack || e));
  }
}

onmessage = async (ev) => {
  if (ev.data.type !== 'run' || !py) return;
  try {
    say('running', 'Solving bubble trajectory…');
    py.globals.set('CONFIG_JSON', JSON.stringify(ev.data.config));
    const out = await py.runPythonAsync(`
import json, math
import numpy as np
from scipy.integrate import solve_ivp
from bubble.core import BubbleParams, CouplingRamp, acceleration

c=json.loads(CONFIG_JSON)
R0=float(c['R0'])
f=float(c['drive_frequency'])
cycles=float(c['cycles'])
duration=max(float(c.get('duration',0.0)), cycles/max(f,1.0))
p=BubbleParams(
    R0=R0,
    drive_amplitude=float(c['drive_amplitude']),
    drive_frequency=f,
    mu=float(c['mu']),
    sigma=float(c['sigma']),
    kappa=float(c['kappa'])
)
model=c['model']
ramp=CouplingRamp(0.0,duration,0.0,0.0)
initial_scale=float(c.get('initial_scale',1.0))
y0=[R0*initial_scale,float(c.get('initial_velocity',0.0))]
collapse_radius=max(1e-12,R0*1e-5)

def rhs(t,y):
    R=max(float(y[0]),1e-15); U=float(y[1])
    return [U, acceleration(t,R,U,p,model,ramp)]

def collapse(t,y): return float(y[0])-collapse_radius
collapse.terminal=True
collapse.direction=-1
samples=int(c.get('samples',520))
t_eval=np.linspace(0.0,duration,samples)
sol=None; used='DOP853'
for method in ('DOP853','Radau'):
    try:
        candidate=solve_ivp(rhs,(0.0,duration),y0,method=method,rtol=1e-8,
            atol=[max(1e-18,R0*1e-11),1e-10],max_step=duration/240.0,
            t_eval=t_eval,events=collapse)
        sol=candidate; used=method
        if candidate.success: break
    except Exception:
        pass
if sol is None: raise RuntimeError('Bubble integration failed')
T=sol.t.astype(float); R=sol.y[0].astype(float); U=sol.y[1].astype(float)
A=[]
for tt,rr,uu in zip(T,R,U):
    A.append(float(acceleration(float(tt),float(rr),float(uu),p,model,ramp)))
A=np.asarray(A)
Pg=p.drive_amplitude*np.sin(2*np.pi*p.drive_frequency*T)
wall_mach=np.max(np.abs(U))/p.c if len(U) else 0.0
omega2=(3*p.kappa*(p.p0-p.pv)+(6*p.kappa-2)*p.sigma/p.R0)/(p.rho*p.R0*p.R0)
f0=math.sqrt(max(0.0,omega2))/(2*math.pi)
collapsed=bool(sol.t_events and len(sol.t_events[0])>0)
result={
 'status':'collapsed' if collapsed else ('complete' if sol.success else 'failed'),
 'message':str(sol.message),'solver':used,'model':model,
 't_s':T.tolist(),'radius_m':R.tolist(),'velocity_m_s':U.tolist(),'acceleration_m_s2':A.tolist(),
 'drive_pressure_pa':Pg.tolist(),'R0':R0,'natural_frequency_hz':f0,
 'min_radius_m':float(np.min(R)),'max_radius_m':float(np.max(R)),
 'max_abs_velocity_m_s':float(np.max(np.abs(U))),'max_wall_mach':float(wall_mach),
 'collapsed':collapsed,'nfev':int(sol.nfev),'config':c
}
json.dumps(result,allow_nan=False)
`);
    postMessage({ type: 'result', payload: String(out) });
  } catch (e) {
    say('error', String(e && e.stack || e));
  }
};

init();
