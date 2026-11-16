"""Deep Water archive builder (runs in GitHub Actions).
For each great earthquake in events.json: find the exact origin in the USGS catalogue, download the real vertical
seismogram recorded at a global station (EarthScope / IRIS FDSN dataselect, IU network), from 2 min before the P wave
to ~100 min after it (P, S and the long surface waves), decimate to 20 samples/s, remove mean/trend, and store it as
int16 + metadata so the app can play it from the same site (no cross-origin fetch on the phone)."""
import json, os, sys, traceback
import numpy as np
from obspy import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.geodetics import locations2degrees
from obspy.taup import TauPyModel

HERE = os.path.dirname(os.path.abspath(__file__))
STATIONS = [("IU", "ANMO", "00", "BHZ", "Albuquerque, New Mexico", 34.9459, -106.4572),
            ("IU", "HRV", "00", "BHZ", "Harvard, Massachusetts", 42.5064, -71.5583),
            ("IU", "COLA", "00", "BHZ", "College, Alaska", 64.8736, -147.8616),
            ("IU", "TUC", "00", "BHZ", "Tucson, Arizona", 32.3098, -110.7847)]
usgs = Client("USGS")
def data_client():
    for key in ("https://service.earthscope.org", "IRIS"):
        try:
            return Client(key) if key == "IRIS" else Client(base_url=key)
        except Exception as e:
            print("client", key, "failed:", e)
    raise RuntimeError("no FDSN data client")
dc = data_client()
model = TauPyModel("iasp91")
events = json.load(open(os.path.join(HERE, "events.json")))
index = []
for ev in events:
    try:
        t0 = UTCDateTime(ev["date"])
        cat = usgs.get_events(starttime=t0 - 86400, endtime=t0 + 2 * 86400, minmagnitude=ev["mag"] - 0.3, orderby="magnitude", limit=1)
        e = cat[0]; o = e.preferred_origin() or e.origins[0]; m = e.preferred_magnitude() or e.magnitudes[0]
        done = False
        for net, sta, loc, cha, sname, slat, slon in STATIONS:
            deg = locations2degrees(o.latitude, o.longitude, slat, slon)
            arr = model.get_travel_times(source_depth_in_km=max(0, (o.depth or 0) / 1000), distance_in_degree=deg, phase_list=["P", "Pdiff", "PKP", "PKIKP", "S", "Sdiff", "SKS"])
            p = min([a.time for a in arr if a.name.startswith("P")] or [deg * 8.0])
            s = min([a.time for a in arr if a.name.startswith("S")] or [p * 1.8])
            start, end = o.time + p - 120, o.time + p + 100 * 60
            try:
                st = dc.get_waveforms(net, sta, loc, cha, start, end)
            except Exception as err:
                print(ev["id"], sta, "no data:", err); continue
            st.merge(fill_value=0); tr = st[0]
            if tr.stats.npts < 0.8 * (end - start) * tr.stats.sampling_rate:
                print(ev["id"], sta, "too short", tr.stats.npts); continue
            tr.detrend("demean"); tr.detrend("linear"); tr.taper(0.01)
            if tr.stats.sampling_rate > 20:
                tr.filter("lowpass", freq=8.0, corners=4, zerophase=True)
                tr.resample(20.0)
            x = tr.data.astype(np.float64); peak = float(np.max(np.abs(x))) or 1.0
            q = np.round(x / peak * 32767).astype("<i2")
            fn = ev["id"] + ".i16"; q.tofile(os.path.join(HERE, fn))
            index.append({"id": ev["id"], "name": ev["name"], "mag": round(m.mag, 1), "magType": m.magnitude_type,
                          "time": str(o.time), "lat": o.latitude, "lon": o.longitude, "depth_km": round((o.depth or 0) / 1000, 1),
                          "station": f"{net}.{sta}.{loc}.{cha}", "stationName": sname, "distance_deg": round(deg, 1),
                          "start": str(tr.stats.starttime), "sps": 20.0, "n": int(q.size), "peakCounts": peak,
                          "p_s": round(float(tr.stats.starttime - o.time) * -1 + p, 1), "s_s": round(float(o.time + s - tr.stats.starttime), 1),
                          "file": fn, "usgsId": str(e.resource_id).split("/")[-1].split("=")[-1]})
            print("OK", ev["id"], sta, q.size, "samples, M", m.mag, "deg", round(deg, 1)); done = True; break
        if not done: print("FAILED", ev["id"])
    except Exception:
        traceback.print_exc()
json.dump(index, open(os.path.join(HERE, "index.json"), "w"), indent=1, ensure_ascii=False)
print(len(index), "of", len(events), "events archived")
sys.exit(0 if index else 1)
