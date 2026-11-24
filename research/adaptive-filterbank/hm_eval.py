import sys, numpy as np, hidden_melody as H, stage4 as s
def evaluate(proc_name, proc):
    x, notes = H.make(3.0)
    m_in, (lev, th, mg, w) = H.melody_margins(x, notes)
    y = proc(x, lev, th, mg, w)
    m_out, _ = H.melody_margins(y, notes)
    r = {"proc": proc_name, "in_median": round(float(np.median(m_in)), 2), "out_median": round(float(np.median(m_out)), 2),
         "median_gain": round(float(np.median(m_out - m_in)), 2), "audible_in_pct": round(float((m_in > 0).mean() * 100), 1),
         "audible_out_pct": round(float((m_out > 0).mean() * 100), 1), "lufs_delta": round(s.lufs(y) - s.lufs(x), 2)}
    r["H_pass"] = bool(r["median_gain"] >= H.PASS["H1_median_margin_gain_db"] and r["audible_out_pct"] >= H.PASS["H2_audible_pct"] and abs(r["lufs_delta"]) <= H.PASS["H3_lufs_db"])
    return r
def pipeline_vs_exact():
    """Permanent check (added after the own-sound bug): the live pipeline's margin for the hidden
    melody must be within 3 dB of the exact Stage-2 margin (-5 dB by construction)."""
    x, notes = H.make(3.0)
    m_in, _ = H.melody_margins(x, notes)
    d = float(np.median(m_in)) - (-5.0)
    return {"pipeline_median_margin": round(float(np.median(m_in)), 2), "exact": -5.0, "diff_db": round(d, 2), "pass": abs(d) <= 3.0}

if __name__ == "__main__":
    import json
    rep = {"pass_conditions": H.PASS, "check_pipeline_vs_exact": pipeline_vs_exact(),
           "eq_recover_tame": evaluate("gains2 eq", lambda x, lev, th, mg, w: s.process(x, s.gains2(lev, w, "cambridge", 1, 1)))}
    conv = lambda o: o.item() if hasattr(o, "item") else str(o)
    json.dump(rep, open("hidden-melody-report.json", "w"), indent=1, default=conv)
    print(json.dumps(rep, indent=1, default=conv))
