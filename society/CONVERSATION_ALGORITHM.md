# Research-based small-group conversation algorithm

This algorithm uses findings from human conversation research as structural guidance. Numerical weights are engineering parameters, not claims that human conversation follows those exact probabilities.

## Empirical structure used

1. **Local turn allocation.** Sacks, Schegloff & Jefferson (1974) describe ordinary conversation as locally managed: a current speaker can select the next speaker; otherwise another participant can self-select; if nobody does, the current speaker may continue. DOI: 10.2307/412243.

2. **Competition in multiparty conversation.** Holler et al. (2021) found that triadic conversation creates competition for the floor, especially outside question-response sequences. In a multi-party setting, more than one listener can prepare a response and the fastest successful response becomes the next turn. DOI: 10.3389/fpsyg.2021.693124.

3. **Responsive follow-up questions.** Huang et al. (2017; corrected/audited 2025) found that questions, especially follow-up questions responsive to what a stranger just said, can increase perceived responsiveness and liking. DOI: 10.1037/pspi0000097. A 2025 study of stranger conversations also linked observed follow-up questions and verbal listening behavior with social connection (PMID 41272285).

4. **Reciprocity.** Stocks et al. (2018) found conversational partners reciprocate message length across media and in interactions involving strangers. DOI: 10.1002/ijop.12369.

5. **Gradual reciprocal disclosure.** Aron et al. (1997) showed that gradually escalating reciprocal self-disclosure can create greater interpersonal closeness between strangers than comparable small-talk tasks. DOI: 10.1177/0146167297234003. The society uses this only as a principle of gradually increasing self-reference; entities must not invent human biographies or fake real-world experiences.

6. **Conversation is informative.** Kardas, Kumar & Epley (2022) found people underestimate how much they will learn from conversations with strangers. DOI: 10.1073/pnas.2206992119. This supports allowing genuine topic exploration instead of forcing service/task dialogue.

## Engineering translation

### Speaker selection
- If the current line explicitly names a peer, strongly boost that peer as next speaker.
- Otherwise all non-speakers probabilistically self-select using their genome-driven activation.
- Penalize the most recent speaker and recent monopolies, but do not force round-robin order.
- There is no room-wide random rest. Silence is decided by the selected entity's three nodes.

### Three-node entity turn
- Three independent nodes decide whether they have enough activation to speak.
- At least two nodes must vote to speak.
- The nodes do **not** vote for identical wording.
- Among valid candidates, select the line balancing novelty, responsiveness to the immediately preceding turn, salience, and diversity from the other node candidates.

### Anti-copying rule
- Reject exact repeats.
- Reject candidates with high lexical similarity to recent turns.
- Never reward candidate-to-candidate similarity.
- Only the line actually spoken is learned. Losing node candidates cannot change memories or topic weights.

### Stranger-like development
- Early exchanges have little stored history and therefore rely mostly on the immediate room context.
- As real exchanges accumulate, topic associations and pairwise interaction traces grow.
- Follow-up questions are optional and should be tied to something actually said, never generic service questions.
- Reply length may loosely track the immediately preceding turn rather than defaulting to a fixed assistant-sized answer.
- Self-reference can gradually increase through learned preferences and prior room statements, but entities must not claim invented human jobs, families, bodies, or off-room experiences.

### Hard exclusions
- No customer-service role.
- No "How can I help?" or equivalent service language.
- No task/meeting-assistant loops.
- No prompt narration or descriptions of what another entity "could say."

The goal is not to script human personalities. It is to reproduce some of the interaction mechanics that let individuality develop through repeated small-group conversation.
