import json
from pathlib import Path

import pytest

from pte_core.pause.boundary import estimate_boundary_realization
from pte_core.pause.pause_evaluator import evaluate_pause


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "read_aloud" / "boundary_cases.json"
)


def _load_cases():
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _get_case(case_id: str):
    for case in _load_cases():
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def test_boundary_fixtures_load():
    cases = _load_cases()
    assert {case["id"] for case in cases} == {
        "clean_comma_pause",
        "long_final_fricative_no_silence",
    }


def test_clean_comma_pause_stays_in_ideal_range():
    case = _get_case("clean_comma_pause")
    pause_eval = evaluate_pause(
        punct=case["punctuation"],
        pause_duration=case["pause_duration"],
        prev_end=0.5,
        next_start=0.82,
        speech_rate_scale=case["speech_rate_scale"],
        prev_word="weekends",
    )

    assert pause_eval["status"] == "correct_pause"
    assert pause_eval["penalty"] == 0.0


def test_long_final_fricative_without_silence_is_not_a_plain_missed_pause():
    case = _get_case("long_final_fricative_no_silence")
    boundary = estimate_boundary_realization(
        prev_word_phones=[
            {"label": "W", "start": 0.00, "end": 0.05},
            {"label": "IY", "start": 0.05, "end": 0.14},
            {"label": "K", "start": 0.14, "end": 0.19},
            {"label": "EH", "start": 0.19, "end": 0.28},
            {"label": "N", "start": 0.28, "end": 0.34},
            {"label": "D", "start": 0.34, "end": 0.39},
            {"label": "Z", "start": 0.39, "end": 0.62},
        ],
        all_phones=[
            {"label": "HH", "start": 0.00, "end": 0.05},
            {"label": "AH", "start": 0.05, "end": 0.11},
            {"label": "L", "start": 0.11, "end": 0.17},
            {"label": "OW", "start": 0.17, "end": 0.25},
            {"label": "W", "start": 0.25, "end": 0.30},
            {"label": "ER", "start": 0.30, "end": 0.37},
            {"label": "L", "start": 0.37, "end": 0.43},
            {"label": "D", "start": 0.43, "end": 0.49},
            {"label": "W", "start": 0.49, "end": 0.54},
            {"label": "IY", "start": 0.54, "end": 0.63},
            {"label": "K", "start": 0.63, "end": 0.68},
            {"label": "EH", "start": 0.68, "end": 0.77},
            {"label": "N", "start": 0.77, "end": 0.83},
            {"label": "D", "start": 0.83, "end": 0.88},
            {"label": "Z", "start": 0.88, "end": 1.11},
        ],
    )
    pause_eval = evaluate_pause(
        punct=case["punctuation"],
        pause_duration=case["pause_duration"],
        prev_end=0.5,
        next_start=0.5,
        speech_rate_scale=case["speech_rate_scale"],
        prev_word="weekends",
        boundary_realization_score=boundary["score"],
    )

    assert boundary["score"] >= 0.6
    assert pause_eval["status"] == "weak_pause_but_good_boundary"
