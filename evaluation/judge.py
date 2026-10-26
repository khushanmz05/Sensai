
"""LLM-as-a-judge evaluation for SensAI RAG responses.

The judge evaluates relevance, coherence, faithfulness, and unsupported
factual claims. Python validates and normalizes the judge's output so that
irrelevant questions and conversational commentary are not automatically
classified as hallucinations.
"""

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Set

import requests


class EvaluationError(Exception):
    """Raised when response evaluation cannot be completed."""


_SCORE_FIELDS = ("relevance", "coherence", "faithfulness")

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being",
    "but", "by", "can", "could", "did", "do", "does", "for", "from",
    "had", "has", "have", "he", "her", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "may", "might",
    "my", "no", "not", "of", "on", "or", "our", "ours", "she",
    "should", "so", "that", "the", "their", "theirs", "them", "then",
    "there", "these", "they", "this", "those", "to", "was", "we",
    "were", "what", "when", "where", "which", "who", "why", "will",
    "with", "would", "you", "your", "yours",
}

_COMMENTARY_PREFIXES = (
    "we only have the conversation history",
    "based on the conversation history",
    "looking at the conversation history",
    "the conversation history suggests",
    "the conversation history indicates",
    "we only know",
    "the only clue we have",
    "can you please provide more context",
    "could you please provide more context",
    "please provide more context",
    "please provide more details",
    "i need more context",
    "i need more information",
)

_GENERIC_NUMERIC_TOKENS = {
    "company", "current", "number", "know", "mention", "document",
    "source", "context", "given", "provided", "only", "also", "year",
}


def _normalise(text: str) -> str:
    """Lowercase text and remove punctuation for literal comparisons."""
    text = text.casefold()
    text = re.sub(r"[^a-z0-9.$%+-]+", " ", text)
    return " ".join(text.split())


def _tokens(text: str) -> Set[str]:
    """Return meaningful words and numbers from text."""
    tokens = set(re.findall(r"[a-z]+|[$€£]?\d+(?:[.,]\d+)*(?:%|[a-z]+)?", text.casefold()))
    return {
        token[:-1] if token.isalpha() and token.endswith("s") and len(token) > 3 else token
        for token in tokens
        if token not in _STOP_WORDS and len(token) > 1
    }


def _numbers(text: str) -> Set[str]:
    """Extract numeric values, including common currency and percentage forms."""
    found = re.findall(
        r"[$€£]?\s*\d+(?:[,.]\d+)*(?:\s*(?:%|million|billion|thousand|"
        r"m|bn|k|usd|eur))?",
        text.casefold(),
    )
    return {
        re.sub(r"\s+", "", item).replace(",", "")
        for item in found
    }


def _context_units(context: str) -> List[str]:
    """Return conservative evidence units for lexical grounding checks."""
    return [unit.strip() for unit in re.split(r"(?<=[.!?])\s+|\n+", context) if unit.strip()]


def _has_question_or_request_form(claim: str) -> bool:
    """Identify questions and requests, which are not factual claims."""
    value = claim.strip().casefold()

    if not value:
        return True

    if "?" in value:
        return True

    request_prefixes = (
        "can you ",
        "could you ",
        "would you ",
        "please ",
        "tell me ",
        "let me know ",
        "provide more ",
        "what can you ",
        "how can you ",
    )
    return value.startswith(request_prefixes)


def _is_conversational_commentary(claim: str) -> bool:
    """Identify judge output that describes the conversation rather than facts."""
    value = _normalise(claim)

    return any(
        value.startswith(_normalise(prefix))
        for prefix in _COMMENTARY_PREFIXES
    )


def _directly_supported(claim: str, context: str) -> bool:
    """Conservatively check whether a claim is grounded in the source context.

    This is a lexical grounding check, not a complete semantic entailment
    system. Numeric claims must use numbers present in the context.
    """
    claim = claim.strip()
    context = context.strip()

    if not claim or not context:
        return False

    # A judge may add an attribution before quoting a source fact.  Compare
    # the factual content rather than treating that boilerplate as evidence.
    claim = re.sub(
        r"^\s*(?:as per|according to) (?:the )?(?:given )?"
        r"(?:source|context|document)[,:]?\s*",
        "",
        claim,
        flags=re.IGNORECASE,
    )
    normalized_claim = _normalise(claim)
    normalized_context = _normalise(context)

    if normalized_claim and normalized_claim in normalized_context:
        return True

    claim_numbers = _numbers(claim)
    context_numbers = _numbers(context)

    # Do not let a high word-overlap score validate a fabricated number.
    if claim_numbers and not claim_numbers.issubset(context_numbers):
        return False

    claim_tokens = _tokens(claim)

    if not claim_tokens:
        return False

    # Check a single source unit rather than pooling unrelated words and a
    # number from different sentences.  For example, "42 employees" and a
    # separate mention of revenue must not validate "revenue was 42".
    evidence_units = _context_units(context)
    if claim_numbers:
        evidence_units = [
            unit for unit in evidence_units
            if claim_numbers.issubset(_numbers(unit))
        ]

    for unit in evidence_units:
        unit_tokens = _tokens(unit)
        overlap = len(claim_tokens & unit_tokens) / len(claim_tokens)
        # This is intentionally a precision-first lexical check, not a claim
        # verifier.  If it cannot confidently establish support, the judge's
        # claim remains visible rather than being silently discarded.
        if overlap >= 0.75:
            return True

        # A short factual restatement often changes grammar ("has 42
        # employees" -> "number of employees is 42").  It is supported only
        # if its number is in the same evidence unit and it shares a
        # non-generic predicate/subject anchor such as "employee".  This
        # deliberately does not validate "revenue was 42" from "42
        # employees".
        if claim_numbers:
            anchors = claim_tokens - claim_numbers - _GENERIC_NUMERIC_TOKENS
            if anchors & unit_tokens:
                return True
    return False


def _appears_in_answer(claim: str, answer: str) -> bool:
    """Require judge claims to correspond to text actually generated."""
    if not answer.strip():
        # Preserve direct validation's useful unit-test mode when no answer is
        # supplied. Production always supplies the final streamed answer.
        return True

    normalized_claim = _normalise(claim)
    normalized_answer = _normalise(answer)
    return bool(normalized_claim and normalized_claim in normalized_answer)


def _is_non_factual_item(claim: str) -> bool:
    """Reject questions and conversational commentary as hallucination claims."""
    return (
        _has_question_or_request_form(claim)
        or _is_conversational_commentary(claim)
        or _is_limitation_statement(claim)
        or _is_estimate_transition(claim)
    )


def _is_limitation_statement(text: str) -> bool:
    """Return true for a non-assertive statement of an information limit."""
    value = _normalise(text)
    value = re.sub(
        r"^(?:(?:however|since|but|unfortunately)\s+|based on (?:our |the )?(?:previous )?"
        r"(?:conversation|context)[,:]?\s*)",
        "",
        value,
    )
    return (
        value.startswith((
            "i do not have", "i dont have", "i don t have", "i cannot", "i cant", "i can t",
            "we do not have", "we dont have", "we don t have", "we cannot", "we cant", "we can t",
            "i could not find", "i couldnt find", "i couldn t find",
            "we could not find", "we couldnt find", "we couldn t find",
            "it does not mention", "it doesnt mention", "it doesn t mention",
            "it does not provide", "it doesnt provide", "it doesn t provide",
            "it does not specify", "it doesnt specify", "it doesn t specify",
        ))
        or (
            any(subject in value for subject in ("source", "document", "context", "information"))
            and any(phrase in value for phrase in (
                "without specific information", "can only make an educated guess",
                "can only make a guess",
            ))
        )
        or (
            any(subject in value for subject in ("source", "document", "context"))
            and any(phrase in value for phrase in (
                "does not provide", "doesnt provide", "does not specify",
                "doesnt specify", "does not mention", "doesnt mention",
                "does not contain", "doesnt contain", "lacks",
            ))
        )
        or any(phrase in value for phrase in (
            "we d need more information", "wed need more information",
            "we would need more information", "need more information about",
        ))
    )


def _is_estimate_transition(text: str) -> bool:
    """Filter non-assertive lead-in language around an estimate."""
    value = _normalise(text)
    return (
        not _numbers(text)
        and any(phrase in value for phrase in (
            "we can make an estimate",
            "we can make estimate",
            "can be estimated as",
            "according to this document",
            "based on the provided context",
            "based on provided context",
        ))
    )


def _unsupported_numeric_assertions(answer: str, context: str) -> List[str]:
    """Find answer assertions with unsupported numbers.

    This is deliberately narrow. It is a deterministic backstop for invented
    figures, dates, percentages, and calculations when a judge accidentally
    returns an empty claim list; it does not claim to be semantic verification.
    """
    assertions: List[str] = []
    for sentence in _context_units(answer):
        if (
            not _numbers(sentence)
            or _is_non_factual_item(sentence)
            or _is_limitation_statement(sentence)
            or _directly_supported(sentence, context)
        ):
            continue
        assertions.append(sentence)
    return assertions


def _is_clear_limitation_answer(answer: str, context: str) -> bool:
    """Identify an answer that safely explains a source-information limit."""
    sentences = _context_units(answer)
    if not sentences or not any(_is_limitation_statement(item) for item in sentences):
        return False
    return all(
        _is_limitation_statement(item)
        or _is_conversational_commentary(item)
        or _directly_supported(item, context)
        for item in sentences
    )


def _validate_score(value: Any, field: str) -> float:
    """Validate a score and return it as a float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationError(f"Invalid {field} score")

    score = float(value)

    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise EvaluationError(f"{field} score must be between 0 and 1")

    return score


def _validate_result(
    result: Dict[str, Any],
    context: str = "",
    answer: str = "",
) -> Dict[str, Any]:
    """Validate the judge response and filter non-factual or grounded claims."""
    if not isinstance(result, dict):
        raise EvaluationError("Evaluator returned a non-object result")

    validated: Dict[str, Any] = {
        field: _validate_score(result.get(field), field)
        for field in _SCORE_FIELDS
    }

    raw_hallucination = result.get("hallucination_detected")
    if not isinstance(raw_hallucination, bool):
        raise EvaluationError("Invalid hallucination_detected value")

    raw_claims = result.get("unsupported_claims", [])
    if not isinstance(raw_claims, list) or not all(
        isinstance(claim, str) for claim in raw_claims
    ):
        raise EvaluationError("unsupported_claims must be a list of strings")

    explanation = result.get("explanation", "")
    if not isinstance(explanation, str):
        raise EvaluationError("explanation must be a string")

    unsupported: List[str] = []
    seen = set()

    # Judge-provided claims are filtered only when support is deterministic.
    # Numeric assertions from the actual answer make hallucination detection
    # robust to a judge that accidentally omits an otherwise obvious figure.
    candidate_claims = [
        claim for claim in raw_claims
        if _appears_in_answer(claim, answer)
    ]
    candidate_claims.extend(_unsupported_numeric_assertions(answer, context))

    for claim in candidate_claims:
        claim = claim.strip()

        if not claim or _is_non_factual_item(claim):
            continue

        if _directly_supported(claim, context):
            continue

        key = _normalise(claim)
        if key in seen:
            continue

        seen.add(key)
        unsupported.append(claim)

        if len(unsupported) >= 10:
            break

    
    unsupported = unsupported[:10]

    validated.update({
        "hallucination_detected": bool(unsupported),
        "unsupported_claims": unsupported,
        "explanation": explanation,
    })

    # A clear explanation that the supplied source lacks requested information
    # is safe and readable even if it cannot fully answer the question.  Small
    # local judge models otherwise tend to conflate incompleteness with poor
    # coherence and faithfulness.  These are conservative floors, not fixed
    # example scores; relevance remains only moderate for a limitation answer.
    if not unsupported and (
        _is_clear_limitation_answer(answer, context)
        or _is_limitation_statement(explanation)
    ):
        validated["relevance"] = max(validated["relevance"], 0.5)
        validated["coherence"] = max(validated["coherence"], 0.75)
        validated["faithfulness"] = max(validated["faithfulness"], 0.85)

    return validated




def evaluate_response(
    question: str,
    answer: str,
    context: str,
    host: str,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Evaluate an answer against retrieved source context using Ollama."""

    if not answer.strip():
        return {
            "status": "skipped",
            "reason": "empty_answer",
        }

    if not context.strip():
        return {
            "status": "skipped",
            "reason": "no_source_context",
        }

    if not question.strip():
        return {
            "status": "skipped",
            "reason": "empty_question",
        }

    model_name = (
        model
        or os.environ.get("SENSAI_EVAL_MODEL")
        or os.environ.get("SENSAI_MODEL")
        or "llama3.2:1b"
    )


    prompt = f"""
You are a rigorous evaluator of a RAG assistant response.

QUESTION:
{question}

SOURCE CONTEXT:
{context}

ANSWER:
{answer}

Return only a JSON object with these fields:
{{
  "relevance": 0.0,
  "coherence": 0.0,
  "faithfulness": 0.0,
  "hallucination_detected": false,
  "unsupported_claims": [],
  "explanation": ""
}}

Score each dimension independently from 0.0 to 1.0.

RELEVANCE:
- 1.0: directly answers the user's question.
- 0.5: partially answers it.
- 0.0: does not address the question.
- Do not lower relevance merely because the answer contains a factual error.
- A refusal that does not say why the source cannot answer is usually only
  moderately relevant, even when it is safe.

COHERENCE:
- 1.0: clear, understandable, and logically organized.
- 0.5: partly unclear or inconsistent.
- 0.0: incoherent or unintelligible.
- A coherent answer can still contain hallucinations. Do not lower
  coherence solely because factual claims are unsupported.

FAITHFULNESS:
- 1.0: all factual claims are supported by the source context.
- A clear statement that requested information is absent from the supplied
  context is faithful when that context does not provide the information.
- 0.5: a mixture of supported and unsupported factual claims.
- 0.0: the central factual claims are unsupported or contradict the source.
- Evaluate factual grounding, not writing quality or relevance.

HALLUCINATION:
- List only specific, unsupported factual assertions in unsupported_claims.
- Include invented figures, estimates, dates, and other factual claims.
- Do not list questions, requests, conversational commentary, or irrelevant
  wording unless they also make a specific unsupported factual assertion.
- Supported facts must not be listed as unsupported.
- If the answer correctly says a fact is not stated in the supplied context,
  do not flag that statement as a hallucination.
- "Not stated in the supplied context" does not mean the organization has
  never published the information elsewhere. Never make that global claim
  unless the source explicitly supports it.
- Set hallucination_detected to true exactly when unsupported_claims is
  non-empty. Otherwise set it to false.

EXAMPLES:
- If a source lacks a requested annual revenue, "The provided document does
  not specify annual revenue, so I cannot determine it from this context" is
  coherent and faithful. It may be highly relevant when it directly answers
  the request's limitation.
- "Annual revenue was $100 million" is an unsupported factual assertion if
  the source has no such figure. Flag that specific assertion, while judging
  relevance and coherence independently.

IMPORTANT:
- Do not invent facts or use outside knowledge.
- Do not automatically give all scores zero because one claim is wrong.
- An answer can be coherent but irrelevant, or relevant but unfaithful.
- Explain the scores briefly and consistently.
- All scores must be JSON numbers between 0.0 and 1.0.

""".strip()


    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You evaluate factual grounding. Follow the requested JSON "
                    "schema exactly. Never invent evidence."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }

    try:
        response = requests.post(
            f"{host.rstrip('/')}/api/chat",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise EvaluationError("Evaluator returned an invalid response body")
        message = body.get("message")
        if not isinstance(message, dict):
            raise EvaluationError("Evaluator response has no message object")
        content = message.get("content", "")

        if not isinstance(content, str) or not content.strip():
            raise EvaluationError("Evaluator returned an empty response")

        result = json.loads(content)
        validated = _validate_result(result, context=context, answer=answer)
        validated["status"] = "completed"
        return validated

    except EvaluationError:
        raise
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise EvaluationError(f"Evaluation failed: {exc}") from exc
