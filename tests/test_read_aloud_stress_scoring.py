import api.validator as validator_module
from pte_core.scoring.stress_policy import classify_stress_result


def test_stress_policy_marks_single_syllable_or_low_confidence_cases_as_unreliable():
    result = classify_stress_result(
        1.0,
        {
            "match_info": "Single syllable word; lexical stress not diagnostic",
            "confidence": 0.4,
        },
    )

    assert result["stress_reliable"] is False
    assert result["stress_error"] is False
    assert result["stress_level"] == "unknown"


def test_stress_policy_preserves_real_reliable_mismatch():
    result = classify_stress_result(
        0.5,
        {
            "match_info": "Stress mismatch (expected index 0, observed 1)",
            "confidence": 0.9,
        },
    )

    assert result["stress_reliable"] is True
    assert result["stress_error"] is True
    assert result["stress_level"] == "error"


def test_read_aloud_score_contract_uses_conservative_stress_weighting():
    scores = validator_module.build_read_aloud_scores(
        words=[
            {
                "word": "kitchen",
                "status": "correct",
                "content_support": "match",
                "content_status": "realized",
                "combined_score": 0.92,
                "stress_score": 0.55,
                "stress_reliable": True,
            }
        ],
        pause_evals=[],
        total_pause_penalty=0.0,
        speech_rate_scale=1.0,
        mfa_word_gaps=[],
    )

    assert scores["pronunciation_accuracy"]["weighting"] == {
        "phoneme_accuracy": 90,
        "stress": 10,
    }
