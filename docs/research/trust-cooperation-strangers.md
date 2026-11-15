# Emergent trust and cooperation: research note

Status: research only; no behavior change authorized by this note.

## Trigger

Paper supplied for study: Michael W. Macy and John Skvoretz, "The Evolution of Trust and Cooperation between Strangers: A Computational Model," American Sociological Review 63(5), 1998, 638-660. DOI: 10.2307/2657332.

## Research question

What mechanisms from research on trust, social distance, partner choice, embeddedness, reciprocity, and network evolution can improve longitudinal relationship development among Sarah, Mara, Owen, and Jules without copying a stylized game model into conversation?

## 1. Observed Room problem

Current Room behavior makes relationship differentiation difficult. Every observer's familiarity with a speaker increases after every observed message, not only after direct interaction, and the beat architecture requires all four entities to contribute. This tends to collapse social distance and can drive all pair relationships toward similar saturation. The current conversation generator also gives limited behavioral consequences to trust, selective engagement, vulnerability, or relationship history.

## 2. Foundational evidence

Macy and Skvoretz (1998) model the emergence of trust and cooperation between strangers. Their core result is structural rather than linguistic: cooperation can emerge under particular conditions involving an option not to interact and embedded local interaction. In their model, effective trust norms emerge locally among neighbors and may later diffuse through weak ties to outsiders. Their claim is not that agents should simply say more trusting things; interaction structure changes what strategies can survive.

## 3. Later empirical and theoretical evidence

Buchan, Croson, and Dawes (2002), "Swift Neighbors and Persistent Strangers," American Journal of Sociology 108(1):168-206, DOI 10.1086/344546, experimentally examined one-shot exchange among manipulated neighbors and strangers in four countries. Cooperation declined with social distance, and social identity changed trusting behavior even when exchange structure and incentives were otherwise identical. The paper also cautions that trust and reciprocity can be distinct rather than interchangeable behaviors.

Rand, Arbesman, and Christakis (2011), "Dynamic Social Networks Promote Cooperation in Experiments with Humans," PNAS 108(48):19193-19198, DOI 10.1073/pnas.1108243108, found that allowing people to make and break ties can stabilize cooperation. This supports treating partner selection and disengagement as behavior, rather than assuming a fixed uniform interaction network.

Shirado, Fu, Fowler, and Christakis (2013), "Quality versus Quantity of Social Ties in Experimental Cooperative Networks," Nature Communications 4:2814, DOI 10.1038/ncomms3814, found a Goldilocks effect: too little network change and too much network change both harmed cooperation; intermediate tie dynamics performed best. This argues against both permanently fixed relationships and constant partner switching.

Melamed and Simpson (2016), "Strong Ties Promote the Evolution of Cooperation in Dynamic Networks," Social Networks 45:32-44, DOI 10.1016/j.socnet.2015.11.001, combined an agent-based model with a laboratory experiment. Relationship duration, used as a measure of tie strength, mediated the effect of tie value on cooperation. This supports explicitly representing the strength and history of each pair rather than a single generic familiarity counter.

Melamed, Harrell, and Simpson (2018), "Cooperation, Clustering, and Assortative Mixing in Dynamic Networks," PNAS 115(5):951-956, DOI 10.1073/pnas.1715357115, experimentally separated reputation from network dynamics. Dynamic networks produced high cooperation even without reputation information; reputation influenced partner choice, but network dynamics themselves drove cooperation. They also found that allowing partner-specific cooperative choices can make static networks perform as well as dynamic networks. This is highly relevant to a four-person Room: differentiated behavior toward particular partners may matter more than globally changing partners.

Molina, Nee, and Holm (2022/2023), "Cooperation with Strangers: Spillover of Community Norms," Organization Science 34(6):2315-2331, DOI 10.1287/orsc.2021.1521, found that locally learned expectations about cooperation and norm enforcement were associated with cooperation toward strangers. This supports a possible group-level learned norm that emerges from repeated local interactions, but it should not erase pair-specific relationship differences.

## 4. Natural-behavior implication

Human-like trust should not be implemented as a phrase style. It should appear as differentiated choices: whom an entity addresses, whose uncertainty it tolerates, whose claim it accepts provisionally, how vulnerable it is willing to be, how much effort it invests in repair, whether it returns to an unfinished exchange, and whether it chooses to disengage or re-engage.

## 5. Mechanism candidates for Entity 4

These are hypotheses for testing, not implementation instructions.

1. Replace one-dimensional familiarity with a pair-specific relationship state. Candidate dimensions: exposure, direct-interaction history, predictability, confidence/trust, reciprocity, warmth/affiliation, respect, unresolved tension, repair history, disclosure depth, and shared-reference count.
2. Passive observation should produce much smaller relationship change than direct exchange. A message addressed to Owen should not increase Mara's relationship with the speaker by the same amount as Owen's.
3. Give each entity selective engagement at the micro level. The Room can remain continuously active while an entity sometimes listens, declines, postpones, redirects, or chooses a different partner. Silence/non-entry can become meaningful without freezing the room.
4. Allow trust to begin with low-cost behavior and escalate only after matched responsiveness. Later experimental work on cooperation is consistent with gradual investment rather than immediate maximal commitment.
5. Make partner histories asymmetric. Sarah's trust in Owen need not equal Owen's trust in Sarah.
6. Separate trust from reciprocity. An entity may regard another as predictable or safe without liking them, and may reciprocate help without generalized trust.
7. Let local pair norms spill into group expectations only gradually. Group-level norms should be learned from repeated evidence, not preset as uniform cooperation.
8. Preserve weak ties. A less-close pair can introduce novelty and bridge conversational clusters, but weaker ties should not automatically transmit as much trust or shared understanding as stronger ties.
9. Give relational history behavioral consequences in topic selection: stronger or more trusting pairs can return to unfinished topics, use shared shorthand, challenge one another more safely, or disclose more specifically.
10. Do not maximize cooperation. Realistic social development requires boundary conditions, misreads, selective trust, occasional refusal, repair, and different relationship trajectories.

## 6. Competing explanations and limits

Macy and Skvoretz (1998) is a stylized evolutionary game simulation about one-shot social dilemmas, not a model of four people in long-running conversation. It should therefore inspire mechanisms, not be copied literally.

Later work shows that cooperation can arise through several mechanisms besides the exact Macy-Skvoretz pathway, including dynamic partner choice, conditional behavior, local norms, cultural/social learning, and differentiated partner-specific decisions. Weak ties also have limits: lower trust and lower shared context can reduce their capacity to transmit complex or novel information. Partner choice can also amplify inequality by concentrating interaction among already attractive or high-resource partners. These findings argue against a simple "strong ties good, weak ties bad" rule.

## 7. Context-transfer check

The Room is a repeated four-person environment, whereas the original Macy-Skvoretz problem is trust among strangers under one-shot conditions. The transferable mechanisms are social distance, selective interaction, embeddedness, heterogeneous tie strength, uncertainty, learning from outcomes, and norm spillover. The one-shot payoff matrix, genetic selection framing, and literal cooperate/defect choice do not directly transfer.

## 8. Current-engine mismatch

The current engine increments every observer's familiarity with every speaker after observed messages and requires four contributors on every beat. These rules reduce relational differentiation and remove a meaningful non-entry/partner-choice mechanism. This is a candidate architectural cause of socially flat long-run behavior and should be tested before modifying dialogue wording.

## 9. Proposed implementation mapping for later evaluation

Before any code change, design a relationship-state schema and event-based update rule. Relationship changes should depend on who addressed whom, whether the exchange was direct or overheard, whether the partner responded contingently, whether a prediction about the partner was confirmed or violated, whether a rupture was repaired, and whether vulnerability or cooperative effort was reciprocated. Topic-selection logic should be allowed to use pair history as one input, but personality and current conversational relevance should remain independent inputs.

The system should also distinguish room activity from individual participation: continuous cognition does not require all four entities to externalize one message on every beat.

## 10. Pre-change validation plan

Do not deploy until baseline measurements are captured. At minimum measure:

- pairwise relationship variance over time;
- proportion of direct versus merely observed interaction;
- how quickly familiarity currently saturates;
- distribution of who addresses whom;
- number of beats in which all four are forced to speak;
- topic persistence and topic return by pair;
- repeated/canned sentence rate;
- evidence of asymmetric pair histories;
- frequency and outcome of conversational repair;
- whether behavioral consequences follow from relationship state.

A successful later change should produce differentiated, stable-but-evolving pair relationships without reducing the Room to cliques, without stopping continuous room activity, and without merely replacing one set of canned phrases with another.

## Decision

Do not yet modify `room_engine.py` from this paper alone. The paper provides strong candidate mechanisms, especially social distance, selective interaction, differentiated pair histories, and local-to-general norm learning. These now need to be integrated with the broader conversation research gate before implementation.