import { bandFrames, diffDb, sameBits } from '/home/claude/me-/qa-resonator/metrics.mjs';
const OLD = await import('/home/claude/me-/qa-resonator/harness.mjs?src=' + process.argv[2]);
const NEW = await import('/home/claude/me-/qa-resonator/harness.mjs');
const LV = { String: 1.4928, Tine: 0.8082, Chime: 0.866, Drum: 0.9784, Hoop: 1.5171, Web: 0.7379, Tank: 8.8716, Twins: 1.8793 };
const built = (H, name, n) => { const p = H.makeProc(32000), S = H.SHAPES[name], g = S.make(n);
  const pos = new Float32Array(g.P.length*3); g.P.forEach((q,i)=>{pos[i*3]=q[0];pos[i*3+1]=q[1];pos[i*3+2]=q[2];});
  const t = performance.now();
  p.port.onmessage({data:{t:'struct',n:g.P.length,pos,fixed:Uint8Array.from(g.F),si:Int32Array.from(g.S.map(s=>s[0])),sj:Int32Array.from(g.S.map(s=>s[1])),mic:g.mic,hit:g.hit,axis:g.axis}});
  return { p, ms: performance.now() - t }; };
const rows = [];
for (const name of Object.keys(NEW.SHAPES)) { const S = NEW.SHAPES[name];
  for (const n of [...new Set([S.min, S.def, S.max])]) {
    const a = built(OLD, name, n), b = built(NEW, name, n), dof = 3*b.p.F;
    let dt = 0; a.p.table.forEach((r,i)=>{ dt = Math.max(dt, Math.abs(r[1]-b.p.table[i][1])); });
    const ra = OLD.render({ secs: 3, shape: name, n, rate: 32000, lvl: LV[name] }), rb = NEW.render({ secs: 3, shape: name, n, rate: 32000, lvl: LV[name] });
    const ident = sameBits(ra.L, rb.L) && sameBits(ra.R, rb.R);
    const d = ident ? 0 : diffDb(bandFrames(ra.L, 32000), bandFrames(rb.L, 32000)).max;
    rows.push({ shape: name, size: n, dof, path: dof > 60 ? 'fast' : 'original', 'old ms': +a.ms.toFixed(0), 'new ms': +b.ms.toFixed(0),
      sameRefMode: a.p.modeIdx === b.p.modeIdx, 'table Δ cents': +(dt*1200/Math.LN2).toExponential(1), audioBitIdentical: ident, 'max band Δ dB': +d.toFixed(4),
      fallbacks: b.p.fastFallbacks || 0 });
  } }
console.table(rows);
