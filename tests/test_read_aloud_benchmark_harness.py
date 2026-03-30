import json
from pathlib import Path

from scripts.read_aloud_benchmark import (
    evaluate_result_against_spec,
    evaluate_results_dir,
    load_manifest,
    load_rating_spec,
)


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "read_aloud"


def test_benchmark_manifest_and_rating_specs_load():
    manifest = load_manifest(FIXTURE_ROOT / "benchmark_manifest.json")
    ids = [entry["id"] for entry in manifest]

    assert ids == [
        "exact_read",
        "hyphen_variant",
        "inserted_noise_token",
        "long_final_fricative_no_silence",
    ]

    spec = load_rating_spec(manifest[0], FIXTURE_ROOT / "benchmark_manifest.json")
    assert "dimension_bands" in spec


def test_benchmark_evaluator_accepts_payload_inside_expected_bands(tmp_path):
    result_payload = {
        "scores": {
            "pronunciation_accuracy": {"percent": 98.0},
            "completeness": {"percent": 100.0},
            "stress": {"percent": 76.0},
            "prosody": {"percent": 88.0},
            "fluency": {"percent": 90.0},
        },
        "summary": {
            "omitted_words": 0,
            "inserted_words": 0,
            "mispronounced_words": 0,
        },
    }
    spec_path = FIXTURE_ROOT / "ratings" / "exact_read.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    evaluation = evaluate_result_against_spec(result_payload, spec)

    assert evaluation["passed"] is True
    assert evaluation["failures"] == []


def test_benchmark_results_dir_flags_missing_or_out_of_band_cases(tmp_path):
    manifest_path = FIXTURE_ROOT / "benchmark_manifest.json"
    result_path = tmp_path / "exact_read.json"
    result_path.write_text(
        json.dumps(
            {
                "scores": {
                    "pronunciation_accuracy": {"percent": 70.0},
                    "completeness": {"percent": 80.0},
                    "stress": {"percent": 60.0},
                    "prosody": {"percent": 75.0},
                    "fluency": {"percent": 75.0},
                },
                "summary": {
                    "omitted_words": 1,
                    "inserted_words": 0,
                    "mispronounced_words": 2,
                },
            }
        ),
        encoding="utf-8",
    )

    evaluations = evaluate_results_dir(tmp_path, manifest_path)
    exact_read = next(item for item in evaluations if item["id"] == "exact_read")
    hyphen_variant = next(item for item in evaluations if item["id"] == "hyphen_variant")

    assert exact_read["passed"] is False
    assert any("pronunciation_accuracy" in failure for failure in exact_read["failures"])
    assert hyphen_variant["passed"] is False
    assert any("missing result file" in failure for failure in hyphen_variant["failures"])
