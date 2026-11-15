# Room: full-turn action identity, not word bans

Status: isolated conversational integrity canary, initial implementation not deployed.

## Observed failure

On 2026-10-28 / 2026-10-29, the published Room repeatedly exchanged essentially the same long question about how a species lineage might change shape: Owen offered a multi-sentence question, Jules copied it with altered punctuation, Owen and Sarah reused its final question. These utterances had different model move labels, including repair/answer, but did not advance the inquiry. Live example is captured as a fixture in scripts/test_room_long_action_gate.py.

## Why this mechanism

Conversation analysis distinguishes sequence position from lexical overlap. Repeating part of another's speech can establish common ground or initiate repair; repeating an entire long previous question with no additional work does not by itself provide that evidence. The existing validation allowed a first exact question echo labeled repair, regardless of how long the source was. The new boundary detects equality of the WHOLE long utterance, not repeated terms, topics or n-grams.

## Ten-level research gate

1. Observation: exact publicly witnessed repeated multi-sentence question and reproducible validation gap.
2. Foundation: Sacks, Schegloff & Jefferson's turn-taking organization; Schegloff/Jefferson/Sacks repair organization.
3. Current evidence: direct 1B production-wrapper trial on PR #336 found 3/4 identical full-statement echoes with source retention and a later trial improved exact-copy counts with bounded regeneration but still lacked semantic continuity.
4. Natural behavior: allow short trouble-source echoes, emphatic repetition and shared-reference lexical alignment.
5. Mechanism: classify a complete repeated >=20-word question or >=12-word nonquestion as an unadvanced second-position action; preserve the existing first short question repair exception.
6. Alternatives: genuine extended quotation and purposeful dramatic repetition; supported when followed by substantive independent contribution. A rare 20-word verbatim trouble-source quotation alone could be a false positive, hence the threshold.
7. Limitations: exact whole-action equality misses paraphrases; model failures may increase if the tiny generator cannot produce a different action. Human review remains necessary.
8. Context transfer: humans repair by precise quotation, whereas synthetic model artifacts can copy the whole source; thresholds are heuristic and not empirically optimized.
9. Mapping: in room_sequence_uptake.validate_uptake reject only whole long copied actions; also retry at existing 3-attempt generation boundary before selected-turn publication, preserving PR #340 self-identity retry and final gates.
10. Post-deploy validation: existing floor/sequence regressions green; publish no fake reply; confirm improved non-copied speech without increased beat failures and manually judge 30+ consecutive turns for responsive, specific multi-turn exchange. Roll back if liveness or quality deteriorates.

## Acceptance

Four exact fixture checks: long question echo rejected despite punctuation variation; long statement entire copy rejected; short legitimate repair accepted; quotation plus meaningful extension accepted; model retry on first copied expression yields a second distinct published candidate. No broad forbidden terms, no topic quotas, no canned dialogue.

Deployment: pending CI and explicit live canary; even a successful guard does NOT establish sustained quality.
