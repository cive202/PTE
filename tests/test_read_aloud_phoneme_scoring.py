from pte_core.phoneme.g2p import PhonemeReferenceBuilder
from pte_core.scoring.accent_scorer import AccentTolerantScorer


def test_word_to_pronunciation_variants_returns_all_cmu_variants():
    builder = object.__new__(PhonemeReferenceBuilder)
    builder.cmu = {
        "route": [
            ("R", "UW1", "T"),
            ("R", "AW1", "T"),
        ]
    }
    builder.g2p = lambda _word: []
    builder.cache = {}
    builder.variant_cache = {}

    variants = builder.word_to_pronunciation_variants("route")

    assert variants == [["r", "uw1", "t"], ["r", "aw1", "t"]]
    assert builder.word_to_phonemes("route") == ["r", "uw1", "t"]


def test_score_word_variants_chooses_the_best_valid_pronunciation():
    scorer = AccentTolerantScorer()

    result = scorer.score_word_variants(
        expected_variants=[["r", "uw1", "t"], ["r", "aw1", "t"]],
        spoken_phonemes=["r", "aw1", "t"],
        accent="Non-Native English",
    )

    assert result["accuracy"] == 100.0
    assert result["expected_variant"] == ["r", "aw1", "t"]
    assert result["expected_variants_count"] == 2
