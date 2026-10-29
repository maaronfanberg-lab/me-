# Room: act-completion grammar vs proposed actions (2026-10-29)

## Observed failure
At published cycle 36303 Mara said, "I just moved the microphone cable..." in the choir-recording scene. The `room_world_actions.action_consequence()` parser requires an action verb immediately after "I" or "we". The common adverb "just" prevents recognition, so no consequent reduction in buzz is made available to the next speaker even though a source-identified public character stated a completed action. Subsequent turns continue proposing checks. This is a deterministic mechanism failure, not a stylistic issue.

## Research and competing explanations
Conversation analysis distinguishes projections of future acts from claims of completed action. Grounding and joint projects depend on the conversational consequences of what speakers did (Sacks, Schegloff & Jefferson 1974 DOI 10.2307/412243; Clark & Wilkes-Gibbs 1986 DOI 10.1016/0010-0277(86)90010-7). The actual utterance is a model-authored *claim* of an action, not a camera-verified act; in this fictional environment, the published assertion is the explicit triggering contract. The action-to-result mapping is deterministic, and real people or visitors cannot trigger it. The broader failure may also involve the model's preference for hypothetical future actions or sparse world memory; this fix alone cannot solve those.

## Mechanism and conservative bounds
Allow optional "just", "already" or "now" between the first-person subject and a listed action verb. Do not match "I'm going to", "I'll", "might", "could", quoted commands, third-person reports, or visitor messages. Existing scene-specific object and verb aliases remain authoritative. No synthetic participant speech is produced, and no new source is promoted to private common ground.

## Ten-level gate and validation
1 Observed exact source turn and parser mismatch. 2–4 natural language aspect/turn completion and collaborative grounding. 5 Mechanism is source-linked action recognition. 6–7 Other explanations and false matches are tested. 8 Human behavior does not guarantee small-model uptake. 9 Minimal parser patch and one regression suite. 10 CI plus actual source replay should cause "quieter" effect after Mara's public action, while proposals remain ineffectual. If the dialogue still ignores the new consequence, the remaining issue is downstream grounding/contingency, not this parser.
