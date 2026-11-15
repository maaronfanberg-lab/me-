# Room attention-routed skills — research record

Date: 2026-08-18

## 1. Observed problem

The Room currently sends a stable role prompt plus a compacted conversation/state payload into the local model for prompted comprehension, thought, and expression nodes. As capabilities grow, adding every new behavioral or domain instruction to the permanent role prompts would make each inference pay for instructions that are usually irrelevant. The architectural risk is prompt dilution and increased competition for model attention, not a single observed conversational phrase failure.

## 2. Research question

Can The Room keep its existing resident core while making additional procedural capabilities available only when the current conversational context indicates that they are useful?

## 3. Foundational evidence

- Liu et al. (2023/2024), *Lost in the Middle: How Language Models Use Long Contexts*, arXiv:2307.03172. Long-context models do not use all positions equally; performance often degrades when relevant information is buried in longer contexts. https://arxiv.org/abs/2307.03172
- Shi et al. (2023), *Large Language Models Can Be Easily Distracted by Irrelevant Context*, arXiv:2302.00093. Irrelevant information can materially reduce reasoning accuracy. https://arxiv.org/abs/2302.00093
- Hsieh et al. (2024), *RULER: What's the Real Context Size of Your Long-Context Language Models?*, arXiv:2404.06654. Effective long-context performance drops with increasing length and task complexity despite nominally large context windows. https://arxiv.org/abs/2404.06654

## 4. Current evidence

- Yin et al. (2026), *@skills: Attention Is All You Have*, arXiv:2608.12610v1. The paper separates skill content, persistence, and automatic triggering, and argues that only capabilities requiring automatic firing should spend permanent prompt residency. It proposes reference, project/vendored, and resident tiers. https://arxiv.org/abs/2608.12610
- Yang et al. (2025), *How Is LLM Reasoning Distracted by Irrelevant Context?*, EMNLP 2025, DOI 10.18653/v1/2025.emnlp-main.674. Controlled experiments continue to find sensitivity to irrelevant context, including effects on reasoning-path selection and arithmetic accuracy. https://aclanthology.org/2025.emnlp-main.674/

## 5. Natural-behavior evidence

This change is an inference-context architecture change, not an attempt to imitate a conversational surface behavior. Existing Room mechanisms for turn-taking, grounding, repair, topic development, and relationship state remain unchanged. Individual project skills may support those mechanisms, but routing does not prescribe canned social phrases.

## 6. Mechanism evidence

The supported mechanism is selective context exposure: keep generally necessary instructions resident, keep optional procedural knowledge outside the prompt, and inject only a small relevant subset near the inference where it is used. This reduces irrelevant instruction load while preserving access to specialized procedures.

## 7. Competing explanations and limitations

- Longer context is not inherently harmful; relevant context can improve performance. The problem is irrelevant or poorly placed context, so aggressive deletion can create false negatives.
- The 2026 @skills paper motivates a protocol and reports ecosystem measurements, but it does not establish that one trigger algorithm is universally optimal for this Room, local GGUF model, or four-entity longitudinal setting.
- Lexical routing can miss semantically relevant skills or fire on ambiguous terms. For that reason routing is capped, transparent, and additive rather than replacing the existing core.
- Automatic triggering in @skills is described as requiring resident frontmatter. The Room adaptation instead performs deterministic routing outside the model. This avoids spending model attention on trigger descriptions, but it is an implementation extension rather than a literal copy of the protocol.

## 8. Context transfer check

Evidence from QA, synthetic reasoning, and coding-agent skill ecosystems transfers only partially to an autonomous social conversation. The transferable claim is narrow: irrelevant context can impair model performance and optional procedures need not be permanently resident. There is not yet direct evidence that this exact router improves The Room's conversational quality.

## 9. Implementation mapping

- Preserve existing private perception, deliberation, and expression prompts as the resident core.
- Store optional project skills as standard `SKILL.md` directories under `skills/room/`.
- Route outside the model using only public recent conversation text and topic state plus skill frontmatter triggers.
- Load at most two selected skill bodies, capped at 1,200 added characters, for one prompted node invocation.
- If no skill clears the relevance threshold, leave `ROOM_NODE_PROMPT` unchanged.
- Never log prompt contents. Publish only selected skill names, matched public trigger labels, sizes, role/entity/node identifiers, and a one-way context fingerprint.
- Keep the existing Room engine unchanged; the wrapper execs it after constructing the temporary environment.

## 10. Pre-change baseline and validation criteria

Baseline: optional capabilities must be encoded in resident prompts or engine logic; there is no observable per-inference skill selection layer.

Success criteria after deployment:

1. All 12 prompted node roles can complete beats through the wrapper without changing the existing engine output contract.
2. Project skill bodies contribute zero resident project-skill characters when not selected.
3. No inference loads more than two project skills or more than 1,200 temporary skill characters.
4. Unmatched contexts leave the existing prompt unchanged.
5. Technical contexts route `technical-systems`; emotionally explicit contexts can route `emotional-attunement`; unrelated synthetic contexts can route zero skills.
6. Telemetry contains no private prompt text, credentials, hidden reasoning, or conversation transcript.
7. Room cadence and publication continue successfully after deployment.

Failure/revert criteria: repeated beat failures attributable to the wrapper, material cadence regression, systematic irrelevant skill firing, prompt/privacy leakage, or conversational degradation that disappears when routing is disabled.

## Post-change result

Pending live deployment observation. Static unit checks cover routing, zero-match fallback, and prompt-size caps; live cadence and behavioral effects must be judged from subsequent Room beats.
