# Coupling gain experiment — 2026-11-24

Historical source: apps/omef-exclusive.html, blob 50650a404b0537779f71556ead9695d337a60caf. Native default filament preset on both engines, seed 0.5/1/2, mix .16, interference .16, projection 5, native eight links. Run 2,000 warmup iterations and 16,000 measured iterations at global coupling 0, .45, 4, 8. All points finite. Independently normalize each point set to its own bounding box and compare total variation of 32×32 and 64×64 spatial histograms. Dense mass = fraction of samples in the 12% densest bins.

|seed|grid|TV(0,4)|TV(0,8)|TV(.45,4)|TV(.45,8)|density at 4|density at 8|
|---|---|---|---|---|---|---|---|
|.5|32|.79394|.80550|.73544|.75106|.72463|.69244|
|.5|64|.85988|.87069|.75831|.77081|.73894|.70675|
|1|32|.82131|.83313|.75894|.78006|.75513|.70463|
|1|64|.86863|.88231|.78063|.79988|.76925|.71838|
|2|32|.83419|.81225|.79719|.77294|.70919|.66450|
|2|64|.88831|.87125|.81931|.79638|.72456|.68138|

Decision: reject blanket doubling of gain; inconsistent improvement and reduced concentration in all cases. TV is resolution-dependent and concentration is only a proxy, not proof of visual quality. No changes to app, no browser or device validation yet. First Claude request failed at max turns; narrowed retry nonce omef-baseline-review-20261124-1137b.
