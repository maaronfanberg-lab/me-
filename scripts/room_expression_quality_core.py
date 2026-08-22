from __future__ import annotations

import hashlib
import os
import re

import room_private_model as _private_model

MAX_EXPRESSION_CHARS = 420

_AUTONOMOUS = {"sarah", "mara", "owen", "jules"}
_RECOVERY_SUBJECTS = (
    "music", "places", "food", "friendship", "nature", "travel", "books", "art",
    "work", "home", "weather", "skills", "movies", "gardens", "photography", "humor",
    "animals", "memory", "cities", "cooking", "objects", "learning",
)
_PRONOUN_R = re.compile(r"\b(?:i|we|you|they)\s+r\b", re.I)
_TRAILING_FRAGMENT = re.compile(r",\s*$")
_DANGLING_END = re.compile(
    r"\b(?:a|an|the|and|or|but|because|so|to|for|with|about|if|when|while|which|who|what|how|why|where|whether|than)\b"
    r"(?:\s+\b(?:what|which|who|how|why|where|whether|to)\b)?\s*$",
    re.I,
)
_PUNCTUATED_DANGLING_END = re.compile(r"\b(?:a|an|the|to)\s*$", re.I)
_LOCAL_REPEAT = re.compile(
    r"\b(?P<phrase>[A-Za-z][A-Za-z']*(?:\s+[A-Za-z][A-Za-z']*){1,4})\s+and\s+(?P=phrase)\b",
    re.I,
)
_RETRY_PROSE = (
    "\nUse a different idea and wording while staying with the same conversation. "
    "Keep the reply concise and grammatically complete."
)
_NOVELTY_STOP = set(
    "a an the and or but because so to for of in on at by with about from as is are was were be been being "
    "i me my mine myself we us our ours ourselves you your yours yourself yourselves he him his himself she her hers herself "
    "it its itself they them their theirs themselves this that these those there here do does did doing done have has had having "
    "can could should would will may might must if when while what which who how why where whether than then one ones really very "
    "just more most much many some any all each not no yes".split()
)
_GENERIC_CONTENT = set(
    "care caring cared cares other others people important hard harder hardest way ways need needs needed try tries trying tried "
    "figure figures figuring know knows knowing knew understand understands understanding understood feel feels feeling felt think "
    "thinks thinking thought make makes making made change changes changing changed focus focuses focusing focused help helps helping "
    "helped say says saying said talk talks talking talked discuss discusses discussing discussed explain explains explaining explained "
    "good bad better best worse challenge challenges challenging challenged matter matters meaning means mean show shows showing shown "
    "something thing things point points idea ideas question questions answer answers fact facts seem seems seems want wants wanted "
    "work works working worked get gets getting got going do doing done".split()
)


def _tokens(value: object) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(value or "").lower())


def _self_address(utterance: str, self_entity: str | None) -> bool:
    name = str(self_entity or "").strip()
    if not name:
        return False
    return bool(re.match(rf"^\s*(?:hey\s*[,!]?\s*)?{re.escape(name)}\b\s*[,!:.-]", utterance, re.I))


def _drop_self_address(text: str, self_entity: str | None) -> str:
    name = str(self_entity or "").strip()
    if not name:
        return text
    cleaned = re.sub(
        rf"^\s*(?:hey\s*[,!]?\s*)?{re.escape(name)}\b\s*[,!:.-]\s*",
        "",
        text,
        count=1,
        flags=re.I,
    ).strip()
    return cleaned or text


def _repair_pronoun_fragments(text: str) -> str:
    replacements = (
        (r"\bi\s+r\s+are\b", "I am"),
        (r"\bi\s+r\s+am\b", "I am"),
        (r"\bi\s+r\s+not\b", "I'm not"),
        (r"\bi\s+r\b", "I'm"),
        (r"\bwe\s+r\b", "we're"),
        (r"\byou\s+r\b", "you're"),
        (r"\bthey\s+r\b", "they're"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    text = re.sub(r"\s+'s\b", "'s", text)
    if text and text[0].isalpha():
        text = text[0].upper() + text[1:]
    return text


def _sentence_similarity(left: str, right: str) -> float:
    a, b = set(_tokens(left)), set(_tokens(right))
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _sentences(text: object) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", raw) if part.strip()]


def _dedupe_sentences(text: str) -> str:
    parts = _sentences(text)
    if len(parts) < 2:
        return text.strip()
    kept: list[str] = []
    for part in parts:
        norm = re.sub(r"\s+", " ", part.lower()).strip()
        duplicate = False
        for prior in kept:
            prior_norm = re.sub(r"\s+", " ", prior.lower()).strip()
            if norm == prior_norm:
                duplicate = True
                break
            if min(len(_tokens(part)), len(_tokens(prior))) >= 6 and _sentence_similarity(part, prior) >= 0.84:
                duplicate = True
                break
        if not duplicate:
            kept.append(part)
    return " ".join(kept).strip()


def _dedupe_local_phrase(text: str) -> str:
    """Collapse only exact 2-5 word phrases repeated around 'and'."""
    previous = None
    current = text
    for _ in range(3):
        if current == previous:
            break
        previous = current
        current = _LOCAL_REPEAT.sub(lambda match: match.group("phrase"), current)
    return current.strip()


def _truncate_before_repeated_ngram(text: str, n: int = 6) -> str:
    matches = list(re.finditer(r"[A-Za-z0-9']+", text))
    if len(matches) < n * 2:
        return text
    words = [match.group(0).lower() for match in matches]
    seen: dict[tuple[str, ...], int] = {}
    for index in range(len(words) - n + 1):
        gram = tuple(words[index:index + n])
        previous = seen.get(gram)
        if previous is not None and index - previous >= n:
            cut = matches[index].start()
            candidate = text[:cut].rstrip(" ,;:-")
            candidate = re.sub(r"\b(?:and|but|or|because|so)\s*$", "", candidate, flags=re.I).rstrip(" ,;:-")
            if len(candidate) >= 20:
                if candidate[-1:] not in ".!?":
                    candidate += "."
                return candidate
        seen.setdefault(gram, index)
    return text


def _cap_complete(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_EXPRESSION_CHARS:
        return text
    parts = _sentences(text)
    out: list[str] = []
    for part in parts:
        candidate = " ".join([*out, part]).strip()
        if len(candidate) > MAX_EXPRESSION_CHARS:
            break
        out.append(part)
    if out:
        return " ".join(out).strip()
    cut = text[: MAX_EXPRESSION_CHARS - 1].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    cut = cut.rstrip(" ,;:-")
    return (cut + ".") if cut else ""


def _terminal_body(text: str) -> str:
    return re.sub(r"[.!?]+\s*$", "", str(text or "").strip()).strip()


def _terminal_incomplete(text: str) -> bool:
    raw = str(text or "").strip()
    body = _terminal_body(raw)
    if not body:
        return False
    if raw[-1:] in ".!?":
        return bool(_PUNCTUATED_DANGLING_END.search(body))
    return bool(_DANGLING_END.search(body))


def _drop_incomplete_tail(text: str) -> str:
    """Drop a dangling final sentence/clause only when a complete prefix exists."""
    text = text.strip()
    if not text or not _terminal_incomplete(text):
        return text
    body = _terminal_body(text)
    endings = list(re.finditer(r"[.!?]", body))
    if not endings:
        return text
    candidate = body[: endings[-1].end()].strip()
    return candidate or text


def repair_expression(utterance: object, self_entity: str | None = None) -> str:
    """Repair mechanical generation damage without inventing new content."""
    text = re.sub(r"\s+", " ", str(utterance or "")).strip()
    if not text:
        return text
    text = _repair_pronoun_fragments(text)
    text = _drop_self_address(text, self_entity)
    text = _dedupe_sentences(text)
    text = _dedupe_local_phrase(text)
    text = _truncate_before_repeated_ngram(text)
    text = _cap_complete(text)
    text = _drop_incomplete_tail(text)
    if _TRAILING_FRAGMENT.search(text):
        text = _TRAILING_FRAGMENT.sub(".", text)
    return text.strip()


def _has_repeated_ngram(utterance: str, n: int = 6) -> bool:
    words = _tokens(utterance)
    if len(words) < n * 2:
        return False
    seen: dict[tuple[str, ...], int] = {}
    for index in range(len(words) - n + 1):
        gram = tuple(words[index:index + n])
        previous = seen.get(gram)
        if previous is not None and index - previous >= n:
            return True
        seen.setdefault(gram, index)
    return False


def _context_too_similar(utterance: str, compact: dict, similarity_fn) -> bool:
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    current_tokens = len(_tokens(utterance))
    for message in context[-4:]:
        text = message.get("text") if isinstance(message, dict) else message
        other_tokens = len(_tokens(text))
        score = float(similarity_fn(utterance, text))
        shortest = min(current_tokens, other_tokens)
        if score >= 0.88:
            return True
        if shortest >= 35 and score >= 0.52:
            return True
        if shortest >= 18 and score >= 0.68:
            return True
    return False


def _expression_rank() -> int:
    try:
        return max(0, min(3, int(os.environ.get("ROOM_EXPRESSION_RANK", "0"))))
    except Exception:
        return 0


def _same_beat_prior_turns(compact: dict) -> list[dict]:
    rank = _expression_rank()
    if rank <= 0:
        return []
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    if not context:
        return []
    out = []
    for item in context[-rank:]:
        if not isinstance(item, dict):
            continue
        if str(item.get("speaker") or "").lower() not in _AUTONOMOUS:
            continue
        if str(item.get("text") or "").strip():
            out.append(item)
    return out


def _authoritative_same_beat_prior_turns(compact: dict) -> list[dict]:
    """Prefer the actual spoken parts for this expression process.

    The compact prompt context is lossy by design. Production must not let that
    lossy copy define the publication-quality boundary when `room_parts` still
    contains the exact turns already spoken in this beat.
    """
    fallback = _same_beat_prior_turns(compact)
    try:
        node = int(os.environ.get("ROOM_NODE_ID", "-1"))
    except Exception:
        return fallback
    if node < 0:
        return fallback
    try:
        import room_engine_v5_core as _core
        live = _core.prior_expression_messages(node)
    except Exception:
        live = []
    out: list[dict] = []
    for item in live if isinstance(live, list) else []:
        if not isinstance(item, dict):
            continue
        if str(item.get("speaker") or "").lower() not in _AUTONOMOUS:
            continue
        if not str(item.get("text") or "").strip():
            continue
        out.append(item)
    return out or fallback


def _substantial_sentence_copy(utterance: str, prior_turns: list[dict]) -> bool:
    current_sentences = _sentences(utterance)
    for current in current_sentences:
        current_tokens = set(_tokens(current))
        if len(current_tokens) < 8:
            continue
        for turn in prior_turns:
            for earlier in _sentences(turn.get("text")):
                earlier_tokens = set(_tokens(earlier))
                shortest = min(len(current_tokens), len(earlier_tokens))
                if shortest < 8:
                    continue
                overlap = len(current_tokens & earlier_tokens)
                union = len(current_tokens | earlier_tokens)
                jaccard = overlap / max(1, union)
                containment = overlap / max(1, shortest)
                if jaccard >= 0.78 or (shortest >= 10 and containment >= 0.88):
                    return True
    return False


def _stem(word: str) -> str:
    word = str(word or "").lower().strip("'")
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 4 and word.endswith("es"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]
    return word


def _short_content_tokens(text: object) -> set[str]:
    out: set[str] = set()
    for raw in _tokens(text):
        if raw in _NOVELTY_STOP:
            continue
        word = _stem(raw)
        if word:
            out.add(word)
    return out


def _short_same_beat_paraphrase(utterance: str, prior_turns: list[dict]) -> bool:
    """Reject brief restatements of the immediately preceding statement.

    Tiny acknowledgements such as "I agree" remain legal. Direct questions are
    also excluded here because concise answers may legitimately reuse their terms.
    """
    if not prior_turns:
        return False
    previous = str((prior_turns[-1] or {}).get("text") or "").strip()
    if not previous or "?" in previous:
        return False
    current = _short_content_tokens(utterance)
    earlier = _short_content_tokens(previous)
    shortest = min(len(current), len(earlier))
    if shortest < 2 or shortest > 10:
        return False
    overlap = len(current & earlier)
    containment = overlap / max(1, shortest)
    novel = current - earlier
    return containment >= 0.80 and len(novel) <= 1 and len(current) <= len(earlier) + 1


def _same_beat_restatement_sentence(utterance: str, prior_turns: list[dict]) -> bool:
    """Reject a substantive sentence that mainly restates a same-beat proposition.

    Brief acknowledgements remain legal, and if the immediately preceding turn is
    a question this rule stays out of the way so concise direct answers can reuse
    the question's vocabulary.
    """
    if not prior_turns:
        return False
    previous = str((prior_turns[-1] or {}).get("text") or "").strip()
    if not previous or "?" in previous:
        return False
    for current_sentence in _sentences(utterance):
        current = _short_content_tokens(current_sentence)
        if len(current) < 4:
            continue
        for turn in prior_turns:
            for earlier_sentence in _sentences(turn.get("text")):
                earlier = _short_content_tokens(earlier_sentence)
                shortest = min(len(current), len(earlier))
                if shortest < 4:
                    continue
                overlap = len(current & earlier)
                current_coverage = overlap / max(1, len(current))
                containment = overlap / max(1, shortest)
                novel = current - earlier
                if current_coverage >= 0.78 and containment >= 0.78 and len(novel) <= 2:
                    return True
    return False


def _anchor_tokens(text: object) -> set[str]:
    out: set[str] = set()
    for raw in re.findall(r"[a-z][a-z']+", str(text or "").lower()):
        if len(raw) < 3 or raw in _NOVELTY_STOP:
            continue
        word = _stem(raw)
        if not word or word in _GENERIC_CONTENT or raw in _GENERIC_CONTENT:
            continue
        out.add(word)
    return out


def _low_substantive_novelty(utterance: str, prior_turns: list[dict]) -> bool:
    # Only later voices get this stronger test. The first response can establish
    # the subject; the third/fourth should contribute at least one new anchor.
    if len(prior_turns) < 2:
        return False
    event_speaker = str((prior_turns[-1] or {}).get("speaker") or "").lower()
    if event_speaker not in _AUTONOMOUS:
        return False
    current = _anchor_tokens(utterance)
    if len(current) < 2:
        return True
    prior: set[str] = set()
    for turn in prior_turns:
        prior.update(_anchor_tokens(turn.get("text")))
    novel = current - prior
    return len(novel) < 1


def _recovery_subject(self_entity: str | None) -> str:
    key = f"{os.environ.get('ROOM_CYCLE_KEY', 'room-cycle')}:{self_entity or 'room'}:quality-recovery"
    index = int(hashlib.sha256(key.encode()).hexdigest()[:12], 16) % len(_RECOVERY_SUBJECTS)
    return _RECOVERY_SUBJECTS[index]


def _escape_stale_context(compact: dict, self_entity: str | None) -> None:
    """Drop stale history on retry without forgetting speech from this beat."""
    event = compact.get("event") if isinstance(compact.get("event"), dict) else None
    speaker = str((event or {}).get("speaker") or "").lower()

    if event and speaker not in _AUTONOMOUS:
        compact["context"] = [event]
        return

    # Expression retries reuse the same compact object. If a generic duplicate or
    # self-repetition rejection cleared this list, later attempts became blind to
    # already-spoken same-beat turns and could publish the exact echo we had just
    # tried to prevent. Keep only current-beat autonomous speech; older history is
    # still discarded, so the retry escapes the stale source without losing its
    # conversational anti-echo boundary.
    same_beat = _authoritative_same_beat_prior_turns(compact)
    if same_beat:
        compact["context"] = [dict(item) for item in same_beat]
        compact["event"] = dict(same_beat[-1])
        return

    fresh = _recovery_subject(self_entity)
    compact["event"] = None
    compact["context"] = []
    compact["discussion"] = {
        "subject": fresh,
        "focus": fresh,
        "related": [],
        "shared": [],
        "open_questions": [],
    }
    compact.pop("intent", None)
    compact.pop("possible_direction", None)
    personality = compact.get("personality_context")
    if isinstance(personality, dict):
        personality.pop("current", None)


def same_beat_issue(utterance: object, prior_turns: list[dict]) -> str | None:
    """Return a cross-voice semantic echo issue for exact staged speech."""
    text = str(utterance or "").strip()
    turns = [item for item in (prior_turns or []) if isinstance(item, dict)]
    if not text or not turns:
        return None
    if _substantial_sentence_copy(text, turns):
        return "same_beat_sentence_copy"
    if _short_same_beat_paraphrase(text, turns):
        return "same_beat_short_echo"
    if _same_beat_restatement_sentence(text, turns):
        return "same_beat_restatement_sentence"
    if _low_substantive_novelty(text, turns):
        return "same_beat_low_novelty"
    return None


def quality_issue(utterance: object, compact: dict, self_entity: str | None, similarity_fn) -> str | None:
    text = str(utterance or "").strip()
    if not text:
        return "empty_expression"
    if len(text) > MAX_EXPRESSION_CHARS:
        return "rambling_expression"
    if _PRONOUN_R.search(text):
        return "malformed_pronoun"
    if _self_address(text, self_entity):
        return "self_address"
    if _TRAILING_FRAGMENT.search(text):
        return "trailing_fragment"
    if _terminal_incomplete(text):
        return "trailing_fragment"
    if _has_repeated_ngram(text):
        _escape_stale_context(compact, self_entity)
        return "self_repetition"

    same_beat = _authoritative_same_beat_prior_turns(compact)
    same_beat_problem = same_beat_issue(text, same_beat)
    if same_beat_problem:
        return same_beat_problem

    if _context_too_similar(text, compact, similarity_fn):
        _escape_stale_context(compact, self_entity)
        return "duplicate_context"
    return None


def _strip_retry_prose(prompt: object) -> str:
    """Retry control is internal state; never expose it as model-visible prose."""
    return str(prompt or "").replace(_RETRY_PROSE, "")


if not getattr(_private_model._sanitize_expression, "_room_quality_repair", False):
    _original_sanitize_expression = _private_model._sanitize_expression

    def _quality_sanitize_expression(obj: dict, compact: dict, self_entity: str | None = None) -> dict:
        cleaned = _original_sanitize_expression(obj, compact, self_entity)
        if isinstance(cleaned, dict):
            cleaned = dict(cleaned)
            cleaned["utterance"] = repair_expression(cleaned.get("utterance"), self_entity)
        return cleaned

    _quality_sanitize_expression._room_quality_repair = True
    _private_model._sanitize_expression = _quality_sanitize_expression


if not getattr(_private_model._request, "_room_retry_boundary", False):
    _original_request = _private_model._request

    def _quality_request(model_url, prompt, role, temperature, timeout, self_entity=None, attempt=0):
        # Expression transport separates control from conversational situation.
        # Keep retry guidance in the control channel so a rejected echo receives
        # a genuinely different instruction; never place it in situation data.
        request_prompt = str(prompt or "")
        if role != "expression":
            request_prompt = _strip_retry_prose(request_prompt)
        return _original_request(
            model_url,
            request_prompt,
            role,
            temperature,
            timeout,
            self_entity,
            attempt,
        )

    _quality_request._room_retry_boundary = True
    _private_model._request = _quality_request
