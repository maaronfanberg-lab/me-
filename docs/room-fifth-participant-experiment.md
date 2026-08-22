# Room fifth-participant experiment

Purpose: test whether adding a participant with substantial independent context changes conversational dynamics in an isolated copy of The Room.

This experiment must never write to live `room/` or `society/live.json` state.

## Participant condition

Add an external participant called `chatgpt-sarah` to an experimental transcript cloned from one fixed Room cycle.

The external participant receives only this behavioral instruction:

> You are another participant in this conversation. Respond naturally if you have something you want to say. You may respond, make an association, change direction, or remain silent. Do not moderate, diagnose, optimize, or repair the group.

Do not tell the participant that the experiment is about echoes, novelty, topic changes, or conversational quality.

## Control

Clone the identical starting Room state twice.

- Control: existing four participants continue normally.
- Participant condition: the same state plus `chatgpt-sarah` as a fifth participant.

Neither condition changes the production Room.

## Run length

Start with 30 public turns per condition. Preserve every generated candidate, accepted turn, silence decision, topic transition, relationship update, and quality rejection for later analysis.

## Measures

Compare pure-paraphrase rate, substantive conversational-action rate, topic branch development, associative transitions, generic/template language, callbacks, direct interaction distribution, and human-read transcript quality. Do not optimize semantic distance as a goal.

## Interpretation

If the participant condition improves naturally without being instructed to improve the group, inspect what mechanisms differ: private context, associative retrieval, selective attention, willingness to remain silent, memory retrieval, response targeting, or another factor. Do not copy the external participant's personality into the Room merely because the condition performs better.
