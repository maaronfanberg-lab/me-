# Room: audible mid-turn address and response obligation (2026-10-29)

## Observed failure
In the public choir discussion at cycle 36294, Owen said, “I'm curious, Mara, did you notice anything unusual when you moved the cable?” The next published speaker was Sarah, not Mara. The floor's `is_directed()` recognized only utterance-initial vocatives and terminal “, Mara”, not the clearly audible interior question vocative “, Mara, did you…”. This is an observed turn-allocation error independent of whether Owen's presupposition about moving the cable is true. A recipient being selected does not imply agreement with that presupposition; Mara can correct it.

## Research foundations, competing mechanisms and transfer limits
Sacks, Schegloff & Jefferson (1974), DOI 10.2307/412243, document recipient selection and next-speaker obligations in naturally occurring human interaction. Schegloff, Jefferson & Sacks on conversational repair (1977), DOI 10.2307/412107, supports preserving the selected recipient's chance to disagree or correct a misleading question. The observation could alternatively reflect a failed first-choice candidate, asleep recipient, or model timeout; floor traces were not published for this exact beat. However, the code-level test proves that this audible vocative is not recognized, a deterministic bug independent of runtime selection outcomes. Human turn-taking evidence does not imply our four model speakers will produce better answers automatically.

## Mechanism and implementation
Recognize a conservative embedded vocative that is immediately preceded by a comma and followed by a comma plus an interrogative auxiliary/wh-word. Preserve the rule that hidden internal targets, third-person name mentions and ambiguous multi-recipient turns do not select an arbitrary person. Do not require a specific speech act; a selected recipient can answer, refuse, repair or correct a mistaken premise. This is not a topic-word ban, speaker quota, or artificial novelty gate.

## Ten-level gate
1 Observed floor mismatch and source excerpt. 2,3 Foundational turn-allocation research; recent synthetic-agent studies on collaboration and grounding do not change the specific lexical detection requirement. 4 Natural human recipient selection in mid-utterance vocatives. 5 Narrow audible address mechanism. 6 Competing candidate-failure explanation acknowledged. 7 No claims of cross-dataset replication. 8 Four-agent generation may still ignore the question. 9 Minimal edit to `scripts/room_conversational_floor.py`. 10 CI tests require correct speaker and reason for real source wording, plus no selection on ordinary name mentions, then inspect published dialogue after merge.

## Validation
A successful unit test is necessary but insufficient. Check real production's chosen speaker and whether the addressee takes up or explicitly repairs the question. If an addressee frequently cannot answer or system repeatedly forces an unavailable person, revise the mechanism rather than masking the failure with quotas.
