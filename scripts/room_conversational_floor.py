#!/usr/bin/env python3
"""Choose one conversational *opportunity* before generating public speech.

An addressed recipient takes precedence over unsolicited contributions.
Otherwise we use each character's already-computed private intention,
personal traits and relationship context. This is a bounded text-only
engineering approximation to turn selection, not a rule against repeated
words, not a topic-rotation quota, and not a license to fabricate agreement.

Phase-1 integration always returns an awake speaker. Genuine voluntary
silence requires a separate heartbeat/recovery protocol before deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

ORDER = ("sarah", "mara", "owen", "jules")
ACTIONS = {"answer", "deepen", "disclose", "compare", "disagree", "repair",
           "support", "callback", "bridge", "close"}
NODE = {"sarah": 2, "mara": 5, "owen": 8, "jules": 11}


def _norm(value):
    return str(value or "").strip().lower()


def _target(event):
    if not isinstance(event, dict):
        return ""
    cognition = event.get("cognition")
    cognition = cognition if isinstance(cognition, dict) else {}
    return _norm(cognition.get("target") or event.get("target"))


def is_directed(event, recipient):
    """Require an *audible* vocative, not the generator's hidden target alone."""
    speaker = _norm((event or {}).get("speaker"))
    target = _norm(recipient)
    if not isinstance(event, dict) or target not in ORDER or speaker == target:
        return False
    # An audible vocative overrides private target metadata. The model's
    # guessed partner is not evidence of whom the public speaker addressed.
    spoken = str(event.get("text") or "")
    # Actual vocatives, including Allen messages that have no hidden target.
    # Quoted name mentions without a conversational invitation are not enough.
    name = re.escape(target)
    # Distinguish a *vocative* from a third-person mention. In
    # "Mara, why did you disagree with Sarah?" only Mara is addressed;
    # "Sarah?" in the question is NOT a second addressed speaker.
    return bool(
        re.search(r"^\s*(?:hey|hi|hello|listen|okay|ok)\s+" + name + r"\b\s*[,?!:]", spoken, re.I)
        or re.search(r"^\s*" + name + r"\b\s*[,?!:]", spoken, re.I)
        or re.search(r"^\s*@" + name + r"\b", spoken, re.I)
        or re.search(r"^\s*" + name + r"\s+(?:can|could|would|will|what|why|how|are|do|did|is|have|tell|please)\b", spoken, re.I)
        # Natural mid-utterance question vocative: "I'm curious, Mara, did you ...?"
        # Require a following interrogative to distinguish direct selection
        # from ordinary third-person mentions and appositives.
        or re.search(r",\s*" + name + r"\s*,\s*(?:can|could|would|will|do|did|are|is|have|has|what|why|where|when|how|tell|please)\b", spoken, re.I)
        or re.search(r",\s*" + name + r"\s*[?!\.]?\s*$", spoken, re.I)
    )



def audible_addressee(speaker, spoken, eligible=ORDER):
    """Return only a uniquely audible, eligible addressee.

    When an expression's internal target differs from its public vocative,
    public speech determines the recorded recipient. No inferred targets
    are produced for an unaddressed statement.
    """
    event = {"speaker": speaker, "text": spoken}
    named = [name for name in eligible if is_directed(event, name)]
    return named[0] if len(named) == 1 else None


def public_participant_turns(history):
    """One source-of-truth for the public turns each awake mind may observe.

    The Room's system status and private cognition are never conversational
    utterances. An accepted Allen turn is, regardless of its runtime tag.
    Source ID and spoken text must be available for all consuming stages.
    """
    return [
        item for item in history
        if isinstance(item, dict)
        and _norm(item.get("speaker")) in (*ORDER, "allen")
        and str(item.get("id") or "").strip()
        and str(item.get("text") or "").strip()
    ]


def last_participant_turn(history):
    """Match the same evidence projection in selection and publication."""
    public = public_participant_turns(history)
    return public[-1] if public else None


def last_participant_source_id(history):
    return (last_participant_turn(history) or {}).get("id")


def _score(entity, last, thought, profile, relationships):
    """Importance to this character, not novelty or speaker rotation."""
    delib = thought if isinstance(thought, dict) else {}
    traits = profile.get("traits") if isinstance(profile, dict) else {}
    traits = traits if isinstance(traits, dict) else {}
    speaker = _norm((last or {}).get("speaker"))
    partner = _norm(delib.get("preferred_partner"))
    action = _norm(delib.get("action"))
    # Personality colors a meaningful bid; it must not create a bid by itself.
    score = (0.065 * float(traits.get("curiosity", .5))
             + 0.045 * float(traits.get("extraversion", .5))
             - 0.035 * float(traits.get("inhibition", .5)))
    if speaker and speaker != entity and partner == speaker:
        score += .48
    if speaker == entity:
        if _norm(delib.get("unresolved_thread")):
            score += .08  # an unfinished contribution can continue
        else:
            score -= .24  # completed turns make others' responses relevant
    if action in {"answer", "repair"} and partner == speaker and speaker != entity:
        score += .19
    if action in {"disagree", "disclose", "repair", "callback"}:
        score += .17
    elif action in {"compare", "answer"}:
        score += .08
    if _norm(delib.get("unresolved_thread")):
        score += .13
    relation = ((relationships or {}).get(entity) or {}).get(speaker) or {}
    score += .08 * float(relation.get("reciprocity") or 0)
    return score


_SCENE_STOP = set(
    "about after again also along another before been being could would should "
    "their there these those where which while with from into behind among "
    "noticed notice check checked checking told said someone anyone happen happened "
    "seems seemed thing things yours mine ours them they that this who what when "
    "know really just more than some over under down have your been saw seen "
    "else were been will have right already".split()
)


def _fact_terms(text):
    return {token for token in re.findall(r"[a-z]{4,}", str(text or "").lower())
            if token not in _SCENE_STOP}


def _fact_opportunity(entity, latest, history, cycle):
    """A specific unresolved question can make a knowledgeable person relevant.

    The referee may compare an individual's private observation to the public
    question, but does not disclose private information to the other agents.
    Never selects speakers based on counts, rotation or personality stereotypes.
    """
    if not isinstance(latest, dict):
        return 0.0
    if _norm(latest.get("speaker")) == entity:
        return 0.0
    question = str(latest.get("text") or "").strip()
    if not question.endswith("?"):
        return 0.0
    # The newer planetarium trial uses a different source-bound world ledger.
    # A person who privately saw the cardboard is especially relevant to an
    # open question about the grille, without granting them a mandatory turn
    # or disclosing their private observation to the other characters.
    from room_causal_world import active as causal_active, PRIVATE, replay
    if (os.environ.get("ROOM_CAUSAL_WORLD_EXPERIMENT") == "1"
            and causal_active(cycle)):
        if entity in {item["speaker"] for item in replay(cycle, history)["disclosures"]}:
            return 0.0
        specific = (_fact_terms(question) & _fact_terms(PRIVATE.get(entity, ""))) - {
            "projector", "dimming", "planetarium", "visitor", "observed",
            "observation", "action", "something", "unusual",
        }
        return 0.72 if specific else 0.12
    from room_hidden_world import active_scene_window, private_observation
    if cycle < 35232 or not active_scene_window(cycle):
        return 0.0
    fact = private_observation(entity, cycle)
    relevant = _fact_terms(question) & _fact_terms(fact)
    # Once this agent has actually voiced the fact, it is no longer unshared.
    # This is an information opportunity, not an across-beat speaker quota.
    for previous in history[-12:]:
        if not isinstance(previous, dict) or _norm(previous.get("speaker")) != entity:
            continue
        voiced = _fact_terms(previous.get("text")) & _fact_terms(fact)
        if len(voiced) >= 2:
            return 0.0
    # A specific question about my observation is strongest. An unaddressed
    # open question about the shared *ongoing* problem can also invite a
    # participant who has a new eyewitness fact to volunteer it. The next
    # generation still chooses its words; no utterance is mandated.
    return 0.6 if relevant else (0.36 if cycle >= 35244 else 0.0)


def choose_next(history, bus, config, minds, *, rank=0, cycle=None):
    """Return the rank-th *independently plausible* speaker opportunity.

    Rank 1 is a liveness fallback only after rank 0 had a technical failure.
    It is not a novelty quota or a demand that a reluctant person speak.
    """
    if not isinstance(history, list) or not isinstance(bus, dict):
        raise ValueError("conversation and recurrent bus must be readable")
    sleeping = {_norm(e) for e in config.get("sleeping_entities", ())}
    awake = [e for e in ORDER if e not in sleeping]
    if not awake:
        raise RuntimeError("no awake character, cannot select a speaker")
    if type(rank) is not int or not 0 <= rank < len(awake):
        raise ValueError("requested candidate is outside the awake group")
    last = last_participant_turn(history)
    author = _norm((last or {}).get("speaker"))
    # A person's spoken vocative is evidence even when Allen's turn lacks
    # internal target metadata. Multiple audible addressees leave the floor
    # open rather than inventing one exclusive recipient.
    audible = [e for e in awake if author != e and is_directed(last, e)]
    addressed = audible[0] if len(audible) == 1 else None
    profile = config.get("p") if isinstance(config.get("p"), dict) else {}
    state = minds.get("entities") if isinstance(minds.get("entities"), dict) else {}
    recurrent = bus.get("recurrent") if isinstance(bus.get("recurrent"), dict) else {}
    relationships = {e: (state.get(e) or {}).get("people") for e in awake}
    # The current Room autonomy engine is deliberately SINGLE PASS:
    # comprehension/thought nodes return None, and the transformer plans
    # inside its one speech generation. Requiring a separate thought action
    # here made every undirected live beat fail and switched the runner back
    # to the repetitive four-voice engine. Do not invent a private thought.
    has_deliberated_bid = any(
        isinstance((((recurrent.get(e) or {}).get("thought") or {}).get("private") or {}).get("deliberation"), dict)
        and _norm(((((recurrent.get(e) or {}).get("thought") or {}).get("private") or {}).get("deliberation") or {}).get("action"))
        for e in awake
    )
    if addressed is None and not has_deliberated_bid and last is None:
        raise RuntimeError("no observed utterance or deliberated social bid for the floor")
    # An actual public utterance creates a possible response/third-position
    # opportunity even when no independent model deliberation was scheduled.
    # This is not evidence of willingness, agreement, or comprehension.
    public_uptake = addressed is None and not has_deliberated_bid
    scene_relevant = bool(
        os.environ.get('ROOM_SCENE_RELEVANCE_FLOOR') == '1'
        and cycle is not None and int(cycle) >= 35232
        and addressed is None and public_uptake and last is not None
        and author != "allen"  # a real visitor's turn supersedes the trial
    )
    ranked = []
    for entity in awake:
        thought = (((recurrent.get(entity) or {}).get("thought") or {}).get("private") or {}).get("deliberation") or {}
        if public_uptake:
            # No separate intention was formed in this single-pass beat.
            # Fixed personality traits or historical affection are NOT an
            # observable claim to the current conversational floor. Instead
            # preserve only local, public relevance below and break otherwise
            # unclaimed opportunities by this immutable source's hash.
            # A same-speaker continuation remains possible if no one else is
            # awake, or when an actual deliberated bid is available.
            score = -.24 if author == entity else 0.0
        else:
            score = _score(entity, last, thought, profile.get(entity) or {}, relationships)
        if public_uptake and last:
            # A mentioned interlocutor or the originator of an earlier
            # unanswered/answered question has genuine local relevance.
            # Mentions are NOT compulsory direct addresses.
            latest_text = str(last.get("text") or "")
            if re.search(r"\b" + re.escape(entity) + r"\b", latest_text, re.I):
                score += .16
            prior = public_participant_turns(history)[-4:-1]
            if any(_norm(p.get("speaker")) == entity
                   and str(p.get("text") or "").rstrip().endswith("?")
                   for p in prior):
                score += .20
        if scene_relevant:
            score += _fact_opportunity(entity, last, history, int(cycle))
        seed = f"{(last or {}).get('id', '')}|{entity}|{_norm(thought.get('action'))}"
        tie = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) / (16 ** 8)
        ranked.append((score, tie, entity))
    ordered = [item[2] for item in sorted(ranked, reverse=True)]
    if addressed:
        ordered.remove(addressed)
        ordered.insert(0, addressed)
    chosen = ordered[rank]
    reason = ("addressed_recipient" if rank == 0 and addressed == chosen
              else "technical_fallback_opportunity" if rank > 0
              else "open_floor_uptake" if public_uptake
              else "open_floor_relevance")
    return {"speaker": chosen, "node": NODE[chosen], "reason": reason,
            "candidate_rank": rank, "candidate_speakers": ordered,
            "source_id": (last or {}).get("id"), "source_speaker": author}


def checked_floor(selection, *, awake, required=False):
    if not isinstance(selection, dict):
        raise ValueError("missing floor decision")
    speaker = _norm(selection.get("speaker"))
    allowed = {e for e in awake if e in ORDER}
    if speaker not in allowed or selection.get("node") != NODE[speaker]:
        raise ValueError("invalid or sleeping selected character")
    if required and selection.get("reason") not in {"addressed_recipient", "open_floor_relevance", "open_floor_uptake", "technical_fallback_opportunity"}:
        raise ValueError("unrecognized floor choice")
    return speaker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bus", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--rank", type=int, default=0)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "room/config.json").read_text(encoding="utf-8"))
    history = json.loads((root / "room/conversation.json").read_text(encoding="utf-8"))
    minds = json.loads((root / "room/cognitive_state.json").read_text(encoding="utf-8"))
    bus = json.loads(Path(args.bus).read_text(encoding="utf-8"))
    current = json.loads((root / 'room/state.json').read_text(encoding='utf-8'))
    decision = choose_next(history, bus, config, minds, rank=args.rank, cycle=current.get('cycle'))
    decision["cycle_key"] = str(bus.get("key") or "")
    decision["bus_sha256"] = hashlib.sha256(Path(args.bus).read_bytes()).hexdigest()
    checked_floor(decision, awake=[e for e in ORDER if e not in config.get("sleeping_entities", [])], required=True)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(decision, separators=(",", ":")) + "\n", encoding="utf-8")
    print("Room next conversational opportunity:", decision["speaker"],
          "because", decision["reason"])


if __name__ == "__main__":
    main()
