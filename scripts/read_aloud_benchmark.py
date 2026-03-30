"""Read Aloud benchmark manifest loader and result evaluator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "read_aloud" / "benchmark_manifest.json"


def load_manifest(manifest_path: Path | None = None) -> List[Dict[str, Any]]:
    target = Path(manifest_path or DEFAULT_MANIFEST)
    with target.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, list):
        raise ValueError("Benchmark manifest must be a list.")
    return manifest


def load_rating_spec(entry: Dict[str, Any], manifest_path: Path | None = None) -> Dict[str, Any]:
    target_manifest = Path(manifest_path or DEFAULT_MANIFEST)
    ratings_path = (target_manifest.parent / str(entry["rating_file"])).resolve()
    with ratings_path.open("r", encoding="utf-8") as handle:
        spec = json.load(handle)
    if not isinstance(spec, dict):
        raise ValueError(f"Rating spec must be an object: {ratings_path}")
    return spec


def evaluate_result_against_spec(result_payload: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
    scores = result_payload.get("scores", {}) if isinstance(result_payload, dict) else {}
    summary = result_payload.get("summary", {}) if isinstance(result_payload, dict) else {}
    dimension_bands = spec.get("dimension_bands", {})
    expected_counts = spec.get("expected_counts", {})

    failures: List[str] = []

    for dimension, band in dimension_bands.items():
        if not isinstance(band, list) or len(band) != 2:
            failures.append(f"{dimension}: invalid expected band")
            continue
        actual = scores.get(dimension, {}).get("percent")
        if actual is None:
            failures.append(f"{dimension}: missing score")
            continue
        actual_value = float(actual)
        low, high = float(band[0]), float(band[1])
        if actual_value < low or actual_value > high:
            failures.append(f"{dimension}: {actual_value:.1f} outside {low:.1f}-{high:.1f}")

    count_aliases = {
        "omitted_words": summary.get("omitted_words", summary.get("omitted", 0)),
        "inserted_words": summary.get("inserted_words", summary.get("inserted", 0)),
        "mispronounced_words": summary.get("mispronounced_words", summary.get("mispronounced", 0)),
    }
    for count_name, actual in count_aliases.items():
        min_key = f"{count_name}_min"
        max_key = f"{count_name}_max"
        if min_key in expected_counts and int(actual) < int(expected_counts[min_key]):
            failures.append(f"{count_name}: {actual} below minimum {expected_counts[min_key]}")
        if max_key in expected_counts and int(actual) > int(expected_counts[max_key]):
            failures.append(f"{count_name}: {actual} above maximum {expected_counts[max_key]}")

    return {
        "id": spec.get("id"),
        "passed": not failures,
        "failures": failures,
    }


def evaluate_results_dir(results_dir: Path, manifest_path: Path | None = None) -> List[Dict[str, Any]]:
    evaluations = []
    for entry in load_manifest(manifest_path):
        result_path = Path(results_dir) / f"{entry['id']}.json"
        if not result_path.exists():
            evaluations.append(
                {
                    "id": entry["id"],
                    "passed": False,
                    "failures": [f"missing result file: {result_path.name}"],
                }
            )
            continue
        with result_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        spec = load_rating_spec(entry, manifest_path)
        evaluations.append(evaluate_result_against_spec(payload, spec))
    return evaluations


def _print_evaluations(evaluations: List[Dict[str, Any]]) -> int:
    overall_success = True
    for item in evaluations:
        status = "PASS" if item.get("passed") else "FAIL"
        print(f"[{status}] {item.get('id')}")
        for failure in item.get("failures", []):
            print(f"  - {failure}")
        overall_success = overall_success and bool(item.get("passed"))
    return 0 if overall_success else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Read Aloud result payloads against benchmark score bands.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Path to benchmark manifest JSON.")
    parser.add_argument("--results-dir", type=Path, help="Directory containing one JSON result payload per benchmark case.")
    parser.add_argument("--list", action="store_true", help="List benchmark case ids from the manifest.")
    args = parser.parse_args()

    if args.list:
        for entry in load_manifest(args.manifest):
            print(entry.get("id"))
        return 0

    if not args.results_dir:
        parser.error("--results-dir is required unless --list is used")

    evaluations = evaluate_results_dir(args.results_dir, args.manifest)
    return _print_evaluations(evaluations)


if __name__ == "__main__":
    raise SystemExit(main())
