# Fast Oracle Predictor research record — 2026-08-28

## Goal
Replace slow or rarely changing Live Earth Oracle variables with signals that can plausibly change by the second or minute, then use the user's prior recurrence formula as an intentionally experimental predictor for a user-selected Yahoo-style market symbol.

## Fast-source audit
- Coinbase Exchange WebSocket ticker: public, unauthenticated market-data WebSocket. Ticker updates on matches and includes price, 24h open, best bid/ask and bid/ask sizes. Used for BTC-USD, ETH-USD and SOL-USD plus a derived bid/ask-size imbalance.
- Wikimedia EventStreams `recentchange`: browser-consumable Server-Sent Events stream emitting MediaWiki recent-change events continuously. Used as a rolling 10-second edit-rate signal.
- ADSB.lol coordinate/radius endpoint: public aircraft data. Polled every 10 seconds.
- Where The ISS At: public ISS state endpoint. Polled every 5 seconds.
- NOAA SWPC compact solar-wind speed and magnetic-field summary JSON: small current products. Polled every 60 seconds.
- NOAA SWPC `planetary_k_index_1m.json`: one-minute geomagnetic product. Polled every 60 seconds.
- NOAA SWPC GOES primary `xrays-6-hour.json`: recent X-ray flux time series. Polled every 60 seconds and only the newest valid flux is used.
- Existing `/api/market` Cloudflare bridge to Yahoo chart data: user-selected symbol, `1m` chart bars, polled every 10 seconds to notice new one-minute observations quickly. `prepost=1` is requested.

## Removed from the predictor
The Mk II tide gauge, buoy, river gauge, auroral field, air-quality field, ordinary weather, earthquake count, GitHub activity, and slower Kp-style variables were removed from the prediction input because they either naturally update more slowly, can remain unchanged for long stretches, or do not meet the requested seconds-to-minutes emphasis.

## Symbol scope
The target input accepts Yahoo-style symbols up to 32 characters, including examples such as `ES=F`, `NQ=F`, `CL=F`, `GC=F`, `^VIX`, `TLT`, `WMT`, and `BTC-USD`. Support ultimately depends on what Yahoo chart data accepts through the existing bridge.

## User recurrence reused
The prior user formula is preserved:

`F₀(x)=x`

`Fₙ(x)=(x²+n·x+Fₙ₋₁(x)) mod 1,000,003`

`Result=F₁₀₀₀(F₉₉₉(…F₂(F₁(seed))…))`

For a fixed x, the recurrence has the equivalent closed form:

`Fₙ(x) = x + n·x² + x·n(n+1)/2 (mod 1,000,003)`

The app applies this closed form for n=1..1000 using BigInt, preserving the recurrence/composition while avoiding unnecessary nested summation work on every live update.

## Experimental prediction mapping
Available fast-stream factors are deterministically quantized into an integer seed mod 1,000,003. The recurrence result R is mapped to `[-1,1]` and then to a deliberately arbitrary predicted short-horizon move capped at approximately ±0.35%. This mapping has no empirical justification and is intentionally part of the experiment.

## Evaluation
- Forecast horizons selectable: 30, 60, 120 seconds.
- A forecast is issued only when the target's latest one-minute market observation advances.
- A forecast settles only when a later target observation is at least the chosen horizon newer.
- Settled forecasts store predicted return, actual return, and direction hit/miss.
- The app calculates direction hit rate and Pearson correlation between predicted and realized returns.
- Negative correlation is retained rather than hidden; sufficiently negative correlation is surfaced as a possible reverse-oracle signal.
- Results persist in browser localStorage for up to 200 settled observations.

## Reliability controls
Each polled source has an overlap guard, fetch timeout, independent LIVE/STALE/ERROR state, and last-good value. Coinbase reconnects after closure while visible. Wikimedia EventSource uses the browser's native reconnect behavior. Returning to the foreground refreshes polling feeds and reconnects missing push streams. The target symbol switch clears pending forecasts so predictions from one instrument cannot settle against another.

## Limitations
This is not a validated forecasting model and must not be presented as investment advice. Apparent hit rate or correlation may be chance, nonstationary, contaminated by overlapping forecasts, or driven by target/source timing artifacts. Yahoo chart data may be delayed depending on instrument/exchange. A source updating every minute does not imply a new independent observation every minute.
