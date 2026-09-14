// Bubble World scientific worker. Kept separate so the UI stays responsive on mobile.
import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v314.0.6/full/pyodide.mjs';

const CDN = 'https://cdn.jsdelivr.net/pyodide/v314.0.6/full/';
const VALIDATED = '21a551fb13ab78ec7a6d0d714e29bf4cba07b33a';
const CORE = `https://raw.githubusercontent.com/maaronfanberg-lab/me-/${VALIDATED}/bubble/core.py`;
const COUPLED = `https://raw.githubusercontent.com/maaronfanberg-lab/me-/${VALIDATED}/bubble/coupled.py`;
let py = null;

function say(type, text) { postMessage({ type, text }); }

async function init() {
  try {
    say('status', 'Loading Python 3.14 runtime…');
    py = await loadPyodide({ indexURL: CDN });
    say('status', 'Loading NumPy and SciPy…');
    await py.loadPackage(['numpy', 'scipy']);
    say('status', 'Loading validated bubble engine…');
    const [a, b] = await Promise.all([fetch(CORE), fetch(COUPLED)]);
    if (!a.ok || !b.ok) throw new Error('Could not fetch pinned bubble engine source');
    const core = await a.text();
    const coupled = await b.text();
    py.FS.mkdirTree('/bubble');
    py.FS.writeFile('/bubble/__init__.py', '');
    py.FS.writeFile('/bubble/core.py', core);
    py.FS.writeFile('/bubble/coupled.py', coupled);
    await py.runPythonAsync("import sys; sys.path.insert(0,'/'); from bubble.core import BubbleParams; from bubble.coupled import CoupledConfig, simulate_coupled_world");
    say('ready', 'Validated Python engine ready');
  } catch (e) {
    say('error', String(e && e.stack || e));
  }
}

onmessage = async (ev) => {
  if (ev.data.type !== 'run' || !py) return;
  try {
    say('running', 'Integrating 12 coupled bubbles…');
    py.globals.set('CONFIG_JSON', JSON.stringify(ev.data.config));
    const out = await py.runPythonAsync(`import json
cfg=json.loads(CONFIG_JSON)
base=BubbleParams(R0=cfg.pop('R0'), drive_amplitude=cfg.pop('drive_amplitude'), drive_frequency=cfg.pop('drive_frequency'))
world=CoupledConfig(**cfg)
json.dumps(simulate_coupled_world(base, world), allow_nan=False)`);
    postMessage({ type: 'result', payload: String(out) });
  } catch (e) {
    say('error', String(e && e.stack || e));
  }
};

init();
