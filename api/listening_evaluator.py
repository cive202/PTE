"""
Listening Evaluator Module
Implements deterministic, rubric-inspired scoring for:
- Summarize Spoken Text
- Multiple Choice, Multiple Answers
- Fill in the Blanks (Type In)
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from src.shared.paths import (
    FIB_LISTENING_REFERENCE_FILE,
    MCM_LISTENING_REFERENCE_FILE,
    MCS_LISTENING_REFERENCE_FILE,
    SMW_LISTENING_REFERENCE_FILE,
    SST_LISTENING_REFERENCE_FILE,
)
from src.shared.services import GRAMMAR_SERVICE_URL

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "there",
    "this",
    "to",
    "was",
    "were",
    "which",
    "with",
    "will",
    "can",
    "also",
    "into",
    "than",
    "while",
    "during",
    "about",
    "across",
}

DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "difficult": 2}

TASK_CONFIG = {
    "summarize_spoken_text": {
        "file": SST_LISTENING_REFERENCE_FILE,
        "primary_key": "summarize_spoken_text",
    },
    "multiple_choice_multiple": {
        "file": MCM_LISTENING_REFERENCE_FILE,
        "primary_key": "multiple_choice_multiple",
    },
    "multiple_choice_single": {
        "file": MCS_LISTENING_REFERENCE_FILE,
        "primary_key": "multiple_choice_single",
    },
    "fill_in_the_blanks": {
        "file": FIB_LISTENING_REFERENCE_FILE,
        "primary_key": "fill_in_the_blanks",
    },
    "select_missing_word": {
        "file": SMW_LISTENING_REFERENCE_FILE,
        "primary_key": "select_missing_word",
    },
}

SST_FORM_FULL_MIN = 50
SST_FORM_FULL_MAX = 70
SST_FORM_PARTIAL_MIN = 40
SST_FORM_PARTIAL_MAX = 100


def _normalize_task_type(task_type: str) -> str:
    normalized = str(task_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in TASK_CONFIG:
        raise ValueError(f"Unsupported listening task: {task_type}")
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


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _tokenize_words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", str(text or "").lower())


def _extract_keywords(text: str, max_items: int = 14) -> List[str]:
    tokens = _tokenize_words(text)
    filtered = [token for token in tokens if len(token) >= 4 and token not in STOPWORDS]
    if not filtered:
        return []

    counts = Counter(filtered)
    first_index = {}
    for idx, token in enumerate(filtered):
        if token not in first_index:
            first_index[token] = idx

    ranked = sorted(counts.items(), key=lambda item: (-item[1], first_index[item[0]], item[0]))
    return [token for token, _freq in ranked[:max_items]]


def _keyword_overlap(reference_keywords: List[str], response_text: str) -> Tuple[float, List[str], List[str]]:
    if not reference_keywords:
        return 0.0, [], []

    response_tokens = set(_tokenize_words(response_text))
    matched = [kw for kw in reference_keywords if kw in response_tokens]
    missing = [kw for kw in reference_keywords if kw not in response_tokens]
    return len(matched) / len(reference_keywords), matched, missing


def _vocabulary_signals(text: str) -> Dict:
    tokens = _tokenize_words(text)
    if not tokens:
        return {"type_token_ratio": 0.0, "avg_word_length": 0.0}
    unique_count = len(set(tokens))
    avg_word_length = sum(len(token) for token in tokens) / len(tokens)
    return {
        "type_token_ratio": unique_count / len(tokens),
        "avg_word_length": avg_word_length,
    }


def _fetch_grammar_matches(text: str, timeout: float = 6.0) -> Dict:
    payload = {"available": False, "matches": []}
    clean_text = _normalize_spaces(text)
    if not clean_text:
        return payload

    try:
        response = requests.post(GRAMMAR_SERVICE_URL, json={"text": clean_text}, timeout=timeout)
        if response.status_code != 200:
            return payload
        data = response.json()
        matches = data.get("matches", []) if isinstance(data, dict) else []
        if not isinstance(matches, list):
            matches = []
        payload["available"] = True
        payload["matches"] = matches
        return payload
    except Exception:
        return payload


def _classify_grammar_matches(matches: List[Dict]) -> Dict:
    grammar_errors = 0
    spelling_errors = 0
    for match in matches:
        if not isinstance(match, dict):
            continue
        rule = match.get("rule", {})
        if not isinstance(rule, dict):
            rule = {}
        rule_id = str(rule.get("id", "") or match.get("ruleId", ""))
        category = rule.get("category", {})
        category_id = str(category.get("id", "")) if isinstance(category, dict) else ""
        message = str(match.get("message", "")).lower()

        lower_rule_id = rule_id.lower()
        lower_category = category_id.lower()
        looks_spelling = (
            "morfologik" in lower_rule_id
            or "spell" in lower_rule_id
            or "spell" in lower_category
            or "spelling" in message
        )
        if looks_spelling:
            spelling_errors += 1
        else:
            grammar_errors += 1

    return {
        "grammar_errors": grammar_errors,
        "spelling_errors": spelling_errors,
    }


def _heuristic_grammar_signal(text: str) -> Dict:
    clean = _normalize_spaces(text)
    if not clean:
        return {"grammar_errors": 2, "spelling_errors": 0}

    issues = 0
    if clean and not clean[0].isupper():
        issues += 1
    if not re.search(r"[.!?]$", clean):
        issues += 1
    if re.search(r"\s{2,}", text):
        issues += 1
    if re.search(r"[!?.,]{3,}", clean):
        issues += 1

    return {"grammar_errors": issues, "spelling_errors": 0}


def _grammar_signals(text: str) -> Dict:
    external = _fetch_grammar_matches(text)
    if external["available"]:
        classified = _classify_grammar_matches(external["matches"])
        classified["service_available"] = True
        return classified

    fallback = _heuristic_grammar_signal(text)
    fallback["service_available"] = False
    return fallback


def _sst_similarity(reference_text: str, response_text: str) -> float:
    reference_text = _normalize_spaces(reference_text)
    response_text = _normalize_spaces(response_text)
    if not reference_text or not response_text:
        return 0.0

    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf = vectorizer.fit_transform([reference_text, response_text])
            return float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
        except Exception:
            pass

    ref_tokens = set(_tokenize_words(reference_text))
    response_tokens = set(_tokenize_words(response_text))
    if not ref_tokens or not response_tokens:
        return 0.0
    return len(ref_tokens & response_tokens) / len(ref_tokens | response_tokens)


def _score_sst_content(keyword_coverage: float, semantic_similarity: float, off_topic: bool) -> int:
    if off_topic:
        return 0
    if keyword_coverage >= 0.70 and semantic_similarity >= 0.48:
        return 4
    if keyword_coverage >= 0.55 and semantic_similarity >= 0.35:
        return 3
    if keyword_coverage >= 0.36 and semantic_similarity >= 0.22:
        return 2
    if keyword_coverage >= 0.18:
        return 1
    return 0


def _score_sst_form(word_count: int) -> int:
    if SST_FORM_FULL_MIN <= word_count <= SST_FORM_FULL_MAX:
        return 2
    if SST_FORM_PARTIAL_MIN <= word_count <= SST_FORM_PARTIAL_MAX:
        return 1
    return 0


def _score_sst_grammar(grammar_errors: int, word_count: int) -> int:
    rate = (grammar_errors * 100) / max(1, word_count)
    if rate <= 3.5:
        return 2
    if rate <= 7.5:
        return 1
    return 0


def _score_sst_vocabulary(vocab: Dict) -> int:
    ttr = float(vocab.get("type_token_ratio", 0.0))
    avg_len = float(vocab.get("avg_word_length", 0.0))
    if ttr >= 0.48 and avg_len >= 4.3:
        return 2
    if ttr >= 0.36:
        return 1
    return 0


def _score_sst_spelling(spelling_errors: int) -> int:
    if spelling_errors <= 0:
        return 2
    if spelling_errors == 1:
        return 1
    return 0


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


def get_listening_topics(task_type: str) -> List[str]:
    rows = _rows_for_task(task_type)
    return sorted({str(item.get("topic", "General")) for item in rows if isinstance(item, dict)})


def get_listening_difficulties(task_type: str) -> List[str]:
    rows = _rows_for_task(task_type)
    values = {
        _normalize_difficulty(item.get("difficulty"))
        for item in rows
        if isinstance(item, dict)
    }
    return sorted(values, key=lambda value: (DIFFICULTY_ORDER.get(value, 99), value))


def get_listening_catalog(task_type: str) -> List[Dict]:
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


def get_listening_task(
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


def evaluate_summarize_spoken_text(
    transcript: str,
    response_text: str,
    *,
    prompt_id: Optional[str] = None,
    key_points: Optional[List[str]] = None,
) -> Dict:
    transcript = _normalize_spaces(transcript)
    response_text = _normalize_spaces(response_text)
    if not transcript:
        return {"error": "Source transcript is required."}
    if not response_text:
        return {"error": "Summary text is required."}

    response_tokens = _tokenize_words(response_text)
    word_count = len(response_tokens)

    reference_keywords = _extract_keywords(transcript, max_items=16)
    if isinstance(key_points, list):
        for point in key_points:
            for token in _extract_keywords(str(point), max_items=4):
                if token not in reference_keywords:
                    reference_keywords.append(token)
        reference_keywords = reference_keywords[:18]

    keyword_coverage, matched_keywords, missing_keywords = _keyword_overlap(reference_keywords, response_text)
    semantic_similarity = _sst_similarity(transcript, response_text)

    off_topic_flag = keyword_coverage < 0.15 and semantic_similarity < 0.10
    form_score = _score_sst_form(word_count)
    content_score = _score_sst_content(keyword_coverage, semantic_similarity, off_topic_flag)

    grammar = _grammar_signals(response_text)
    grammar_score = _score_sst_grammar(grammar["grammar_errors"], word_count)
    vocabulary = _vocabulary_signals(response_text)
    vocabulary_score = _score_sst_vocabulary(vocabulary)
    spelling_score = _score_sst_spelling(grammar["spelling_errors"])

    gate_reason = None
    if form_score == 0:
        gate_reason = "form_out_of_range"
    elif off_topic_flag:
        gate_reason = "off_topic"

    if gate_reason:
        content_score = 0
        form_score = 0
        grammar_score = 0
        vocabulary_score = 0
        spelling_score = 0

    max_total = 12
    total_score = content_score + form_score + grammar_score + vocabulary_score + spelling_score

    feedback = []
    if gate_reason == "form_out_of_range":
        feedback.append("Keep your summary between 40 and 100 words; best scoring range is 50 to 70 words.")
    elif gate_reason == "off_topic":
        feedback.append("Your summary appears off-topic. Focus on the lecture's central message and supporting points.")

    if not gate_reason:
        if content_score <= 1:
            feedback.append("Cover more key ideas from the recording and avoid unrelated details.")
        if form_score == 1:
            feedback.append("Aim for the optimal 50 to 70 word range to improve form score.")
        if grammar_score == 0:
            feedback.append("Simplify sentence structure and correct grammar to improve clarity.")
        if vocabulary_score == 0:
            feedback.append("Use more precise academic vocabulary and avoid repetitive wording.")
        if spelling_score == 0:
            feedback.append("Review spelling carefully before submission.")

    if not feedback:
        feedback.append("Strong summary with balanced content coverage and language control.")

    return {
        "task": "summarize_spoken_text",
        "prompt_id": prompt_id,
        "scores": {
            "content": {"score": content_score, "max": 4},
            "form": {"score": form_score, "max": 2},
            "grammar": {"score": grammar_score, "max": 2},
            "vocabulary": {"score": vocabulary_score, "max": 2},
            "spelling": {"score": spelling_score, "max": 2},
            "total": {
                "score": total_score,
                "max": max_total,
                "percent": round((total_score / max_total) * 100, 1),
            },
        },
        "analysis": {
            "word_count": word_count,
            "keyword_coverage_percent": round(keyword_coverage * 100, 1),
            "semantic_similarity_percent": round(semantic_similarity * 100, 1),
            "matched_keywords": matched_keywords,
            "missing_keywords": missing_keywords[:10],
            "grammar_errors": grammar["grammar_errors"],
            "spelling_errors": grammar["spelling_errors"],
            "grammar_service_available": grammar["service_available"],
            "off_topic_flag": off_topic_flag,
            "gate_reason": gate_reason,
        },
        "feedback": feedback,
    }


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


def _evaluate_single_choice_correct_incorrect(
    correct_option_id: str,
    selected_option_id: str,
    *,
    prompt_id: Optional[str],
    task_name: str,
    success_message: str,
    incorrect_message: str,
) -> Dict:
    expected = str(correct_option_id or "").strip().upper()
    selected = str(selected_option_id or "").strip().upper()

    if not expected:
        return {"error": "Correct option is not configured for this item."}

    is_correct = bool(selected) and selected == expected
    total_score = 1 if is_correct else 0

    if is_correct:
        feedback = [success_message]
    elif selected:
        feedback = [incorrect_message]
    else:
        feedback = ["No option selected. Select one answer to receive a score."]

    return {
        "task": task_name,
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


def evaluate_multiple_choice_single(
    correct_option_id: str,
    selected_option_id: str,
    *,
    prompt_id: Optional[str] = None,
) -> Dict:
    return _evaluate_single_choice_correct_incorrect(
        correct_option_id=correct_option_id,
        selected_option_id=selected_option_id,
        prompt_id=prompt_id,
        task_name="multiple_choice_single",
        success_message="Correct. You selected the best response.",
        incorrect_message="Incorrect response. Review the key idea and choose the single best answer.",
    )


def evaluate_select_missing_word(
    correct_option_id: str,
    selected_option_id: str,
    *,
    prompt_id: Optional[str] = None,
) -> Dict:
    return _evaluate_single_choice_correct_incorrect(
        correct_option_id=correct_option_id,
        selected_option_id=selected_option_id,
        prompt_id=prompt_id,
        task_name="select_missing_word",
        success_message="Correct. You selected the missing word accurately.",
        incorrect_message="Incorrect choice. Focus on the end of the recording and contextual meaning.",
    )


def evaluate_fill_in_the_blanks(
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
        user_value = str(responses.get(blank_id, "")).strip()
        is_correct = _value_matches_expected(user_value, expected)
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
                "response": user_value,
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
            feedback.append("Review spelling carefully. Only correctly spelled words receive credit.")

    return {
        "task": "fill_in_the_blanks",
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
            "scoring_rule": "1 point per correctly spelled blank, minimum 0",
        },
        "feedback": feedback,
    }
