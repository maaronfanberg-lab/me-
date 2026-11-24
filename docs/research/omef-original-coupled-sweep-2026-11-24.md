# Matched original/coupled sweep — 2026-11-24

Input: published recovery preview blob ad94d3fa99f32eed747948431dc96b9f73e0870a. Identical historical 61 parameters in A and B. B seeds 0,.5,1,2; native mode 5, mix .16, interference .16, all eight historical links. Fresh deterministic start for each condition. 4,000 warmup + 24,000 measured per condition. Independently normalized 48x48 density histograms. TV from same-seed uncoupled joint image; dense = mass in top 12% bins. A/B changes compare each to own uncoupled geometry.

|Global|TV joint|TV A|TV B|Dense mass|Normalized mean travel|Mean drive|
|---|---|---|---|---|---|---|
|0|0|0|0|.9033|.0211|0|
|.15|.4913|.4578|.5986|.8543|.0205|.4719|
|.45|.6247|.6244|.6746|.7731|.0193|1.348|
|1|.6816|.6803|.6999|.6285|.0176|2.9336|
|2|.8456|.8522|.7784|.6656|.0223|5.4951|
|4|.8536|.8597|.7817|.7427|.0407|10.0645|

Zero pointwise difference between Original and uncoupled A in every run. At g=0, joint still differs from Original due to projected B: average TV .2385; seed 1 .3295. At g=2/4 direct projection joint vs A TV roughly .11-.15 (independently normalized); much larger change in A due to real feedback. This separates dynamics from coordinate blending. All configurations finite. Seed 1 aspect-preserving 32x32 point density images show branching thin loops at original, thickened at .15/.45, filled diffuse region at 2. Density is not a validated measure of beauty and the plots are not browser screenshots. High global gain meets TV target but can destroy desired open geometry. Do not equate change with improvement. No app changes. Claude request omef-coupling-sweep-20261124-01.
