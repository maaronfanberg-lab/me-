# Room final-question action continuity (2026-10-28)

## Observed problem and pre-change baseline
At 11:48:14Z, Sarah published: "You want to be coherent and mutual understanding. Can you help me achieve that by being helpful and supportive?" Jules replied at 11:49:32Z with the trailing question only, and Mara published the same question at 11:50:37Z. The original `room_sequence_uptake.py` compared whole utterances; it failed to identify the question alone as a copy of Sarah's final interrogative action. This is one witnessed failure, not proof of all conversation loops.

## Research question
Can an exact spoken question action be tracked across a turn that also includes prefatory declarative material, while preserving legitimate quotation and repair?

## Ten-level research gate
1. **Observed problem**: Public source IDs and timestamps show a contiguous question-action echo.
2. **Foundational theory**: Sacks, Schegloff, and Jefferson, `Language` 50(4), 1974, DOI 10.2307/412243, analyze sequential allocation of turns; sequence matters beyond individual token sequences.
3. **Current evidence**: The centennial reprint (2025, DOI 10.1353/lan.2025.a954231) affirms that turn-taking remains a relevant research foundation. Not evidence that this regex alone implements conversational understanding.
4. **Natural behavior**: Repeating a question can be legitimate other-initiated repair once, but serially identical question echoes can fail to progress the exchange. Schegloff, Jefferson, and Sacks (1977), DOI 10.2307/413107, examine repair.
5. **Mechanism**: Track an exact final complete interrogative clause as a conversational action with public source IDs. Keep contiguous sequence detection rather than semantic overlap or topic penalties.
6. **Competing accounts**: Repetition may be purposeful quotation or clarification; a question's wording can legitimately recur after an intervening answer. This gate therefore permits a first repair and resets after an intervening different action.
7. **Limits**: Written punctuation is an imperfect proxy for interrogative action; abbreviations, ellipsis, direct quotes, multi-sentence questions, and embedded questions need later analysis.
8. **Transfer**: Human interaction analyses do not guarantee that a small neural generator will infer appropriate responses. Measure live publication and human-rated responsiveness separately.
9. **Implementation**: `room_sequence_uptake._final_question_action` extracts the final sentence if it ends in a question mark. `question_sequence` and `validate_uptake` compare this exact action across adjacent public turns.
10. **Validation**: Test source-specific three-turn echo, acceptance of meaningful answers, distinct clarification, first legitimate repair, third exact-question repetition, and existing selected-floor/legacy pipeline. Require green final-head GitHub CI before merge.

## Non-goals
No lexical blacklist, no artificial topic changes, no fixed dialog scripts, and no claim to comprehend question meaning. The next task is source-linked cross-turn semantic action tracking.

## Status
PR #334 includes the code and tests. Live production impact is not verified. If post-merge dialogue does not improve, investigate other failure mechanisms without asserting this patch solved them.
