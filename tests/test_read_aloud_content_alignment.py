import json
from pathlib import Path

from read_aloud.alignment.content_matcher import compare_text


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "read_aloud" / "content_cases.json"
)


def _load_cases():
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _get_case(case_id: str):
    for case in _load_cases():
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def _inserted_words(diff_rows):
    return [row["word"] for row in diff_rows if row["status"] == "inserted"]


def _omitted_words(diff_rows):
    return [row["word"] for row in diff_rows if row["status"] == "omitted"]


def _correct_words(diff_rows):
    return [row["word"] for row in diff_rows if row["status"] == "correct"]


def test_content_alignment_fixtures_load():
    cases = _load_cases()
    assert {case["id"] for case in cases} == {
        "exact_read",
        "transcript_punctuation_only",
        "hyphen_variant",
        "inserted_noise_token",
        "inserted_article",
    }


def test_exact_read_preserves_lexical_words_as_correct():
    case = _get_case("exact_read")
    diff_rows, normalized_transcript = compare_text(case["reference"], case["transcript"])

    assert normalized_transcript == (
        "you don't have to spend a lot of time in the kitchen on weekends "
        "say nutrition experts"
    )
    assert _inserted_words(diff_rows) == []
    assert _correct_words(diff_rows)[:5] == ["you", "don't", "have", "to", "spend"]


def test_transcript_punctuation_tokens_do_not_create_empty_insertions():
    case = _get_case("transcript_punctuation_only")
    diff_rows, _ = compare_text(case["reference"], case["transcript"])

    assert "" not in _inserted_words(diff_rows)
    assert _inserted_words(diff_rows) == []
    assert _omitted_words(diff_rows) == [",", "."]


def test_hyphen_variants_do_not_create_false_content_mismatches():
    case = _get_case("hyphen_variant")
    diff_rows, normalized_transcript = compare_text(case["reference"], case["transcript"])

    assert normalized_transcript == "the use of time saving appliances"
    assert _inserted_words(diff_rows) == []
    assert _omitted_words(diff_rows) == []
    assert _correct_words(diff_rows) == [
        "the",
        "use",
        "of",
        "time",
        "saving",
        "appliances",
    ]


def test_real_inserted_noise_token_is_still_preserved():
    case = _get_case("inserted_noise_token")
    diff_rows, _ = compare_text(case["reference"], case["transcript"])

    assert _inserted_words(diff_rows) == ["safs"]
    assert "who" in _correct_words(diff_rows)


def test_real_inserted_article_is_still_preserved():
    case = _get_case("inserted_article")
    diff_rows, _ = compare_text(case["reference"], case["transcript"])

    assert _inserted_words(diff_rows) == ["the"]
    assert _correct_words(diff_rows) == ["to", "reduce", "stress"]

def test_no_alignment_row_uses_an_empty_lexical_token():
    case = _get_case("transcript_punctuation_only")
    diff_rows, _ = compare_text(case["reference"], case["transcript"])
    assert all(row["word"] != "" for row in diff_rows)


def test_substitution_keeps_expected_word_for_acoustic_resolution():
    diff_rows, _ = compare_text("home chefs", "home cooks")

    chefs_row = next(row for row in diff_rows if row["word"] == "chefs" and row.get("ref_index") is not None)
    inserted_rows = [row for row in diff_rows if row["status"] == "inserted"]

    assert chefs_row["status"] == "correct"
    assert chefs_row["content_support"] == "contradicted"
    assert chefs_row["asr_word"] == "cooks"
    assert [row["word"] for row in inserted_rows] == ["cooks"]
