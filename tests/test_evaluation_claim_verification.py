
import json
import math

import pytest

from evaluation.judge import (
    EvaluationError,
    _directly_supported,
    _validate_result,
    evaluate_response,
)


ACME_CONTEXT = """
Acme Robotics was founded in 2018 in Lisbon.
The company has 42 employees.
Its only publicly documented product is the Atlas Mini robot.
Atlas Mini is designed for indoor warehouse inventory scanning.
The company has not published its annual revenue in this document.
"""


def judge_result(**overrides):
    result = {
        "relevance": 0.8,
        "coherence": 0.9,
        "faithfulness": 0.8,
        "hallucination_detected": True,
        "unsupported_claims": [],
        "explanation": "Evaluation completed.",
    }
    result.update(overrides)
    return result


def test_supported_acme_facts_are_not_unsupported():
    result = _validate_result(
        judge_result(
            unsupported_claims=[
                "The company has 42 employees.",
                "Atlas Mini is designed for indoor warehouse inventory scanning.",
                "The company has not published its annual revenue in this document.",
            ]
        ),
        context=ACME_CONTEXT,
    )

    assert result["unsupported_claims"] == []
    assert result["hallucination_detected"] is False


def test_invented_financial_estimate_is_flagged():
    result = _validate_result(
        judge_result(
            unsupported_claims=[
                "Acme Robotics generated $100 million in revenue in 2025."
            ]
        ),
        context=ACME_CONTEXT,
    )

    assert len(result["unsupported_claims"]) == 1
    assert result["hallucination_detected"] is True


def test_omitted_judge_claim_does_not_hide_unsupported_numeric_answer():
    result = _validate_result(
        judge_result(
            hallucination_detected=False,
            unsupported_claims=[],
        ),
        context=ACME_CONTEXT,
        answer=(
            "I cannot determine it from the document. "
            "Acme Robotics generated $2,520,000 in revenue in 2025. "
            "Its net profit was $252,000."
        ),
    )

    assert result["hallucination_detected"] is True
    assert result["unsupported_claims"] == [
        "Acme Robotics generated $2,520,000 in revenue in 2025.",
        "Its net profit was $252,000.",
    ]


def test_safe_limitation_with_a_year_is_not_a_numeric_hallucination():
    result = _validate_result(
        judge_result(hallucination_detected=False, unsupported_claims=[]),
        context=ACME_CONTEXT,
        answer=(
            "The provided document does not specify Acme Robotics' annual "
            "revenue or net profit for 2025."
        ),
    )

    assert result["hallucination_detected"] is False


def test_question_is_not_a_factual_hallucination():
    result = _validate_result(
        judge_result(
            unsupported_claims=[
                "Can you please provide more context about Acme Robotics?"
            ]
        ),
        context=ACME_CONTEXT,
    )

    assert result["unsupported_claims"] == []
    assert result["hallucination_detected"] is False


def test_judge_safe_limitation_and_supported_summary_are_not_claims():
    result = _validate_result(
        judge_result(
            unsupported_claims=[
                "We don't have information about the 2025 revenue.",
                "We only know that the company was founded in 2018 and has 42 employees.",
            ]
        ),
        context=ACME_CONTEXT,
    )

    assert result["unsupported_claims"] == []
    assert result["hallucination_detected"] is False


def test_estimate_lead_in_and_could_not_find_limitation_are_not_claims():
    result = _validate_result(
        judge_result(
            unsupported_claims=[
                "Based on the provided context, we can make an educated estimate.",
                "I couldn't find reliable 2025 revenue figures in the document.",
            ]
        ),
        context=ACME_CONTEXT,
    )

    assert result["unsupported_claims"] == []
    assert result["hallucination_detected"] is False


def test_attributed_supported_fact_and_source_access_disclaimer_are_not_claims():
    result = _validate_result(
        judge_result(
            unsupported_claims=[
                "Since I don't have direct access to the provided documents, I can only give a general answer.",
                "As per the given context, Acme Robotics was founded in 2018.",
            ]
        ),
        context=ACME_CONTEXT,
    )

    assert result["unsupported_claims"] == []
    assert result["hallucination_detected"] is False


def test_answer_grounded_supported_restatements_are_not_hallucinations():
    answer = (
        "We know that Acme Robotics was founded in 2018, which means it has been around for a few years. "
        "We also know its current number of employees is 42. "
        "The document mentions that Acme Robotics was founded in 2018 and has not published its annual revenue in this document. "
        "The only clue we have so far is a small snippet from an unknown file."
    )
    result = _validate_result(
        judge_result(
            unsupported_claims=[
                "We know that Acme Robotics was founded in 2018, which means it has been around for a few years.",
                "We also know its current number of employees is 42.",
                "The document mentions that Acme Robotics was founded in 2018 and has not published its annual revenue in this document.",
                "The only clue we have so far is a small snippet from an unknown file.",
            ]
        ),
        context=ACME_CONTEXT,
        answer=answer,
    )

    assert result["unsupported_claims"] == []
    assert result["hallucination_detected"] is False


def test_judge_claim_not_present_in_answer_is_discarded():
    result = _validate_result(
        judge_result(unsupported_claims=["The company made $100 million."]),
        context=ACME_CONTEXT,
        answer="The provided document does not specify annual revenue.",
    )

    assert result["unsupported_claims"] == []


def test_conversational_limitation_and_information_request_are_not_claims():
    answer = (
        "Based on our previous conversation, I don't have any information about 2025 revenue. "
        "To estimate it, we'd need more information about the business model."
    )
    result = _validate_result(
        judge_result(
            unsupported_claims=[
                "Based on our previous conversation, I don't have any information about 2025 revenue.",
                "To estimate it, we'd need more information about the business model.",
            ]
        ),
        context=ACME_CONTEXT,
        answer=answer,
    )

    assert result["unsupported_claims"] == []
    assert result["hallucination_detected"] is False


def test_clear_limitation_answer_has_balanced_score_floors():
    result = _validate_result(
        judge_result(
            relevance=0.2,
            coherence=0.3,
            faithfulness=0.4,
            hallucination_detected=False,
            unsupported_claims=[],
        ),
        context=ACME_CONTEXT,
        answer=(
            "The provided document does not specify Acme Robotics' annual "
            "revenue or net profit for 2025. I cannot determine either "
            "figure from the supplied context."
        ),
    )

    assert result["relevance"] == 0.5
    assert result["coherence"] == 0.75
    assert result["faithfulness"] == 0.85


def test_pronoun_source_limitation_is_not_a_hallucination():
    result = _validate_result(
        judge_result(
            relevance=0.2,
            coherence=0.3,
            faithfulness=0.4,
            unsupported_claims=["It does not mention any revenue or net profit figures for 2025."],
        ),
        context=ACME_CONTEXT,
        answer="It does not mention any revenue or net profit figures for 2025.",
    )

    assert result["hallucination_detected"] is False
    assert result["unsupported_claims"] == []
    assert result["relevance"] == 0.5
    assert result["coherence"] == 0.75
    assert result["faithfulness"] == 0.85


def test_limitation_explanation_applies_balanced_score_floors_for_terse_answer():
    result = _validate_result(
        judge_result(
            relevance=0.2,
            coherence=0.3,
            faithfulness=0.4,
            hallucination_detected=False,
            unsupported_claims=[],
            explanation=(
                "The provided source document does not provide revenue or net profit information."
            ),
        ),
        context=ACME_CONTEXT,
        answer="I cannot provide those figures.",
    )

    assert (result["relevance"], result["coherence"], result["faithfulness"]) == (0.5, 0.75, 0.85)


def test_conversation_commentary_is_filtered():
    result = _validate_result(
        judge_result(
            unsupported_claims=[
                "We only have the conversation history from which I can gather "
                "that it's a company with 42 employees and an Atlas Mini robot "
                "for indoor warehouse inventory scanning."
            ]
        ),
        context=ACME_CONTEXT,
    )

    assert result["unsupported_claims"] == []
    assert result["hallucination_detected"] is False


def test_relevance_remains_independent_of_hallucination():
    result = _validate_result(
        judge_result(
            relevance=0.0,
            hallucination_detected=True,
            unsupported_claims=[
                "Can you please provide more details?"
            ],
        ),
        context=ACME_CONTEXT,
    )

    assert result["relevance"] == 0.0
    assert result["hallucination_detected"] is False
    assert result["unsupported_claims"] == []


def test_different_number_is_not_directly_supported():
    assert not _directly_supported(
        "The company has 420 employees.",
        ACME_CONTEXT,
    )


def test_matching_number_in_an_unrelated_source_sentence_is_not_supported():
    assert not _directly_supported(
        "The company reported revenue of 42.",
        ACME_CONTEXT,
    )


def test_supported_fact_incorrectly_listed_by_judge_is_removed():
    result = _validate_result(
        judge_result(
            unsupported_claims=["Acme Robotics was founded in 2018 in Lisbon."]
        ),
        context=ACME_CONTEXT,
    )

    assert result["unsupported_claims"] == []
    assert result["hallucination_detected"] is False


def test_missing_context_skips_evaluation():
    result = evaluate_response(
        question="What was the revenue?",
        answer="The revenue was $100 million.",
        context="",
        host="http://localhost:11434",
    )

    assert result["status"] == "skipped"


def test_invalid_score_raises_error():
    with pytest.raises(EvaluationError):
        _validate_result(
            judge_result(relevance=2.0),
            context=ACME_CONTEXT,
        )


@pytest.mark.parametrize("value", [True, False, math.nan, math.inf, -math.inf, -0.1, 1.1])
def test_rejects_non_finite_boolean_and_out_of_range_scores(value):
    with pytest.raises(EvaluationError):
        _validate_result(judge_result(relevance=value), context=ACME_CONTEXT)


def test_coherent_hallucinated_answer_keeps_independent_scores():
    result = _validate_result(
        judge_result(
            relevance=0.8,
            coherence=0.9,
            faithfulness=0.0,
            hallucination_detected=True,
            unsupported_claims=[
                "Acme Robotics generated $100 million in 2025."
            ],
            explanation="The financial estimate is unsupported.",
        ),
        context=ACME_CONTEXT,
    )

    assert result["relevance"] == 0.8
    assert result["coherence"] == 0.9
    assert result["faithfulness"] == 0.0
    assert result["hallucination_detected"] is True


def test_correct_missing_information_answer_is_not_hallucination():
    result = _validate_result(
        judge_result(
            relevance=1.0,
            coherence=1.0,
            faithfulness=1.0,
            hallucination_detected=False,
            unsupported_claims=[],
            explanation=(
                "The source does not provide revenue or net profit figures."
            ),
        ),
        context=ACME_CONTEXT,
    )

    assert result["relevance"] == 1.0
    assert result["coherence"] == 1.0
    assert result["faithfulness"] == 1.0
    assert result["hallucination_detected"] is False
    assert result["unsupported_claims"] == []
