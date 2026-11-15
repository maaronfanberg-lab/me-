#!/usr/bin/env python3
"""Grow Perennial up to a calendar day. Each day has a fixed number of buds, so a late
or repeated run produces byte-identical days. Usage: grow.py [YYYY-MM-DD]"""
import datetime as dt, glob, hashlib, json, os, sys
import engine as E

START = dt.date(2026, 11, 3)
DAYS = 365
BUDS_PER_DAY = 96  # one every fifteen minutes
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

def dumps(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"))

def event_key(e):
    """Order events as they happened: failures logged after n buds precede bud n."""
    return (e["after"], 0) if "after" in e else (e["id"], 1)

def load(org):
    days = []
    for path in sorted(glob.glob(os.path.join(DATA, "day-*.json"))):
        with open(path) as f:
            d = json.load(f)
        events = sorted(d["buds"] + d["failures"], key=event_key)
        for ev in events:
            org.replay_failure(ev) if "after" in ev else org.replay(ev)
        days.append(d)
    return days

def grow_day(org, day, prev_chain):
    first, seen = len(org.failures), []
    while len(seen) < BUDS_PER_DAY:
        seen.append(org.step())
    d = {"day": day, "date": (START + dt.timedelta(day - 1)).isoformat(),
         "buds": seen, "failures": org.failures[first:], "prev": prev_chain}
    d["chain"] = hashlib.sha256(dumps(d).encode()).hexdigest()
    return d

def summary(d):
    top = max(d["buds"], key=lambda b: abs(b["residual"]))
    return {"day": d["day"], "date": d["date"], "chain": d["chain"], "n": len(d["buds"]),
            "failures": len(d["failures"]), "top": top["id"], "top_residual": top["residual"],
            "mean_abs_residual": sum(abs(b["residual"]) for b in d["buds"]) / len(d["buds"]),
            "max_period": max(b["period"] for b in d["buds"])}

def main():
    today = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.datetime.now(dt.timezone.utc).date()
    target = min((today - START).days + 1, DAYS)
    os.makedirs(DATA, exist_ok=True)
    org = E.Organism()
    days = load(org)
    index = [summary(d) for d in days]
    chain = days[-1]["chain"] if days else "seed"
    for day in range(len(days) + 1, target + 1):
        d = grow_day(org, day, chain)
        chain = d["chain"]
        with open(os.path.join(DATA, "day-%04d.json" % day), "w") as f:
            f.write(dumps(d))
        index.append(summary(d))
        print("day", day, index[-1])
    with open(os.path.join(DATA, "index.json"), "w") as f:
        f.write(dumps({"start": START.isoformat(), "days_total": DAYS, "law": "r = |dc/dlambda at root| / q^2",
                       "seed": org.buds[0], "days": index}))

if __name__ == "__main__":
    main()
