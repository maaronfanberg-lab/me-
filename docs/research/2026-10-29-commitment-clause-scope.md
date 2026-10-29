# Source-phrase validation for follow-through memory, October 29, 2026

The first greenhouse turn (published cycle 36329) was Jules saying: "I'm going to check the irrigation filter, since it's the first thing I noticed that might be causing the issue, and see if it's clogged or dirty, as a clogged filter could be preventing water from flowing properly."

The initial intention detector disqualified the whole sentence because it contained "might", "could" and "if" in explanations of uncertainty, even though the main clause made an affirmative first-person plan. This is a confirmed source-to-parser mismatch and a falsification of the overbroad earlier filter. Amend detection to apply hypothetical-token guards to the initial self-committing clause, not the later explanatory clause. A conditional such as "I'll inspect the filter if somebody asks" is still not counted. Plans remain explicitly *unfulfilled* and are never converted to physical actions. Tests use the exact observed live line and competing conditional examples.

Mechanism grounding: Clark & Wilkes-Gibbs (1986) on collaborative grounding, and Sacks, Schegloff & Jefferson (1974) on speech-action sequencing. Caution: a comma is an imperfect clause boundary; run source fidelity and real-agent follow-up, not just regex tests. The natural model may still avoid action, which is a separate hypothesis.
