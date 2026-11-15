# Deep Water — global earthquakes as the main driver (2026-11-14)

**Observed problem.** Alex asked for Deep Water to respond to global earthquakes. In v1, earthquakes only triggered
one giant bubble per new quake from the USGS hour feed (often minutes apart), so most of the sound came from Wikipedia.

**Mechanism chosen.** Every quake in the USGS 24-hour feed becomes a sea-floor "vent" that keeps releasing bubbles at
the rate aftershocks decay: rate ∝ 10^(αM) / (c + t)^p.
- Omori–Utsu aftershock decay: Utsu, Ogata & Matsu'ura (1995), J. Phys. Earth 43, 1–33; typical p ≈ 1.1, c small (hours).
- Productivity grows exponentially with magnitude, α ≈ 0.8–1 (e.g. Helmstetter 2003, PRL 91, 058501; Felzer et al. 2004).
- Bubble physics unchanged: Minnaert (1933) resonance, Davies & Taylor (1950) rise speed.
- Data: USGS GeoJSON summary feeds (all_day, all_hour), refreshed each minute: earthquake.usgs.gov/earthquakes/feed/v1.0.

**Mapping.** magnitude → vent productivity and bubble size; quake depth → bubble depth (20 m + 1.5 m per km, ≤ 220 m);
longitude → left/right; latitude → distance. New quakes open with a giant bubble, kept ≥ 24 Hz so a subwoofer can play it.
User density setting sets the total bubble rate; the data set the shares (a big recent quake dominates, as aftershocks do).

**Limits / competing views.** Omori parameters vary by region and sequence; one global p, c, α is a simplification.
The feed includes many small regional events (dense US networks), so US quakes are over-represented relative to their
global share — a property of the data, kept as is.

**Validation.** Stand-in feed in a headless browser: vents built (5), new quake detected on the next poll and released
as a giant, bubbles drawn from vents in proportion to Omori rate (M4.8 3 h ago dominated a M1.2 20 min ago), no errors.
Pass if, on Alex's phone, the top line shows "Earthquakes: N in the last day · newest …" and bubbles name their quake.
