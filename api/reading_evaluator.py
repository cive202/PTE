"""
Reading Evaluator Module
Implements deterministic, rubric-inspired scoring for:
- Reading and Writing: Fill in the Blanks (Dropdown)
- Multiple Choice, Multiple Answers
- Multiple Choice, Single Answer
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Dict, List, Optional

from src.shared.paths import (
    FIB_DROPDOWN_READING_REFERENCE_FILE,
    MCM_READING_REFERENCE_FILE,
    MCS_READING_REFERENCE_FILE,
)

DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "difficult": 2}

TASK_CONFIG = {
    "fill_in_the_blanks_dropdown": {
        "file": FIB_DROPDOWN_READING_REFERENCE_FILE,
        "primary_key": "fill_in_the_blanks_dropdown",
    },
    "multiple_choice_multiple": {
        "file": MCM_READING_REFERENCE_FILE,
        "primary_key": "multiple_choice_multiple",
    },
    "multiple_choice_single": {
        "file": MCS_READING_REFERENCE_FILE,
        "primary_key": "multiple_choice_single",
    },
}


def _normalize_task_type(task_type: str) -> str:
    normalized = str(task_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in TASK_CONFIG:
        raise ValueError(f"Unsupported reading task: {task_type}")
    return normalized


def _read_rows_from_file(reference_file: Path, expected_key: str) -> List[Dict]:
    if not reference_file.exists():
        return []

    try:
        with open(reference_file, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
    except Exception:
        return []

    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]

    if isinstance(data, dict):
        for key in (expected_key, "items"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]

    return []


def _rows_for_task(task_type: str) -> List[Dict]:
    normalized = _normalize_task_type(task_type)
    config = TASK_CONFIG[normalized]
    return _read_rows_from_file(config["file"], config["primary_key"])


def _normalize_difficulty(value: Optional[str], fallback: str = "medium") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in DIFFICULTY_ORDER:
        return normalized
    if normalized in {"normal", "moderate"}:
        return "medium"
    if normalized in {"hard", "advanced", "high"}:
        return "difficult"
    if normalized in {"basic", "low"}:
        return "easy"
    return fallback


def _normalize_answer_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9'-]+", " ", str(value or "").lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _value_matches_expected(user_value: str, expected_value) -> bool:
    candidate = _normalize_answer_token(user_value)
    if isinstance(expected_value, list):
        options = [_normalize_answer_token(item) for item in expected_value]
    else:
        options = [_normalize_answer_token(expected_value)]
    return candidate in {opt for opt in options if opt}


def get_reading_difficulties(task_type: str) -> List[str]:
    rows = _rows_for_task(task_type)
    values = {
        _normalize_difficulty(item.get("difficulty"))
        for item in rows
        if isinstance(item, dict)
    }
    return sorted(values, key=lambda value: (DIFFICULTY_ORDER.get(value, 99), value))


def get_reading_catalog(task_type: str) -> List[Dict]:
    rows = _rows_for_task(task_type)
    catalog = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        record_id = str(item.get("id", "")).strip()
        if not record_id:
            continue
        catalog.append(
            {
                "id": record_id,
                "title": str(item.get("title", "Untitled")),
                "topic": str(item.get("topic", "General")),
                "difficulty": _normalize_difficulty(item.get("difficulty")),
            }
        )

    return sorted(
        catalog,
        key=lambda entry: (
            DIFFICULTY_ORDER.get(str(entry.get("difficulty", "")).lower(), 99),
            str(entry.get("topic", "")).lower(),
            str(entry.get("title", "")).lower(),
        ),
    )


def get_reading_task(
    task_type: str,
    topic: Optional[str] = None,
    task_id: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> Optional[Dict]:
    rows = _rows_for_task(task_type)
    if not rows:
        return None

    if task_id:
        wanted_id = str(task_id).strip()
        for row in rows:
            if isinstance(row, dict) and str(row.get("id", "")).strip() == wanted_id:
                return row

    filtered = [row for row in rows if isinstance(row, dict)]

    if difficulty:
        wanted = _normalize_difficulty(difficulty, fallback="")
        if not wanted:
            return None
        by_difficulty = [
            row
            for row in filtered
            if _normalize_difficulty(row.get("difficulty"), fallback="medium") == wanted
        ]
        if not by_difficulty:
            return None
        filtered = by_difficulty

    if topic:
        topic_lc = str(topic).strip().lower()
        by_topic = [row for row in filtered if str(row.get("topic", "")).strip().lower() == topic_lc]
        if not by_topic:
            return None
        filtered = by_topic

    return random.choice(filtered or rows)


def evaluate_multiple_choice_multiple(
    correct_option_ids: List[str],
    selected_option_ids: List[str],
    *,
    prompt_id: Optional[str] = None,
) -> Dict:
    normalized_correct = {str(item).strip().upper() for item in (correct_option_ids or []) if str(item).strip()}
    normalized_selected = {str(item).strip().upper() for item in (selected_option_ids or []) if str(item).strip()}

    if not normalized_correct:
        return {"error": "Correct options are not configured for this item."}

    correct_selected = sorted(normalized_selected & normalized_correct)
    incorrect_selected = sorted(normalized_selected - normalized_correct)
    missed_correct = sorted(normalized_correct - normalized_selected)

    raw_score = len(correct_selected) - len(incorrect_selected)
    total_score = max(0, raw_score)
    max_total = len(normalized_correct)

    feedback = []
    if normalized_selected == normalized_correct:
        feedback.append("Perfect response. You selected all correct options without penalties.")
    else:
        if incorrect_selected:
            feedback.append(
                f"You selected {len(incorrect_selected)} incorrect option(s), which reduced your score."
            )
        if missed_correct:
            feedback.append(f"You missed {len(missed_correct)} correct option(s).")
        if not feedback:
            feedback.append("Partially correct response.")

    return {
        "task": "multiple_choice_multiple",
        "prompt_id": prompt_id,
        "scores": {
            "content": {"score": total_score, "max": max_total},
            "total": {
                "score": total_score,
                "max": max_total,
                "percent": round((total_score / max_total) * 100, 1) if max_total else 0.0,
            },
        },
        "analysis": {
            "selected_options": sorted(normalized_selected),
            "correct_options": sorted(normalized_correct),
            "correct_selected": correct_selected,
            "incorrect_selected": incorrect_selected,
            "missed_correct": missed_correct,
            "raw_score": raw_score,
            "minimum_zero_applied": raw_score < 0,
            "scoring_rule": "+1 each correct selected, -1 each incorrect selected, minimum 0",
        },
        "feedback": feedback,
    }


def evaluate_multiple_choice_single(
    correct_option_id: str,
    selected_option_id: str,
    *,
    prompt_id: Optional[str] = None,
) -> Dict:
    expected = str(correct_option_id or "").strip().upper()
    selected = str(selected_option_id or "").strip().upper()

    if not expected:
        return {"error": "Correct option is not configured for this item."}

    is_correct = bool(selected) and selected == expected
    total_score = 1 if is_correct else 0

    if is_correct:
        feedback = ["Correct. You selected the best response."]
    elif selected:
        feedback = ["Incorrect response. Review the main idea and choose the single best answer."]
    else:
        feedback = ["No option selected. Select one answer to receive a score."]

    return {
        "task": "multiple_choice_single",
        "prompt_id": prompt_id,
        "scores": {
            "content": {"score": total_score, "max": 1},
            "total": {
                "score": total_score,
                "max": 1,
                "percent": round(total_score * 100.0, 1),
            },
        },
        "analysis": {
            "selected_option": selected,
            "correct_option": expected,
            "is_correct": is_correct,
            "scoring_rule": "Correct/incorrect (1 for correct, 0 for incorrect or unanswered)",
        },
        "feedback": feedback,
    }


def evaluate_fill_in_the_blanks_dropdown(
    blanks: List[Dict],
    responses: Dict[str, str],
    *,
    prompt_id: Optional[str] = None,
) -> Dict:
    if not isinstance(blanks, list) or not blanks:
        return {"error": "No blanks are configured for this item."}

    if not isinstance(responses, dict):
        responses = {}

    rows = []
    total_score = 0
    for blank in blanks:
        blank_id = str(blank.get("id", "")).strip()
        expected = blank.get("answer", "")
        selected_value = str(responses.get(blank_id, "")).strip()
        is_correct = _value_matches_expected(selected_value, expected)
        if is_correct:
            total_score += 1

        if isinstance(expected, list):
            expected_label = " / ".join(str(item) for item in expected)
        else:
            expected_label = str(expected)

        rows.append(
            {
                "id": blank_id,
                "expected": expected_label,
                "selected": selected_value,
                "is_correct": is_correct,
            }
        )

    max_total = len(blanks)
    missed = [row for row in rows if not row["is_correct"]]

    feedback = []
    if total_score == max_total:
        feedback.append("Excellent. All blanks are correct.")
    else:
        feedback.append(f"You answered {total_score} of {max_total} blanks correctly.")
        if missed:
            feedback.append("Review context around each blank and choose the best-fitting option.")

    return {
        "task": "fill_in_the_blanks_dropdown",
        "prompt_id": prompt_id,
        "scores": {
            "content": {"score": total_score, "max": max_total},
            "total": {
                "score": total_score,
                "max": max_total,
                "percent": round((total_score / max_total) * 100, 1) if max_total else 0.0,
            },
        },
        "analysis": {
            "items": rows,
            "missed_count": len(missed),
            "scoring_rule": "1 point per correct blank, minimum 0",
        },
        "feedback": feedback,
    }
