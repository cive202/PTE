"""
Writing Evaluator Module
Implements deterministic, rubric-aligned scoring for:
- Summarize Written Text (SWT)
- Write Essay
- Write Email
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
    SWT_WRITING_REFERENCE_FILE,
    ESSAY_WRITING_REFERENCE_FILE,
    EMAIL_WRITING_REFERENCE_FILE,
)
from src.shared.services import GRAMMAR_SERVICE_URL


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

TRANSITION_WORDS = {
    "however",
    "therefore",
    "moreover",
    "furthermore",
    "in addition",
    "for example",
    "for instance",
    "on the other hand",
    "in contrast",
    "as a result",
    "consequently",
    "overall",
    "in conclusion",
}

SWT_WORD_MIN = 5
SWT_WORD_MAX = 75
ESSAY_BEST_MIN = 200
ESSAY_BEST_MAX = 300
ESSAY_ALLOWED_MIN = 120
ESSAY_ALLOWED_MAX = 380
EMAIL_BEST_MIN = 50
EMAIL_BEST_MAX = 120
EMAIL_ALLOWED_MIN = 30
EMAIL_ALLOWED_MAX = 150
DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "difficult": 2}


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
        # Compatibility with old combined writing file shape.
        combined_rows = data.get(expected_key)
        if isinstance(combined_rows, list):
            return [row for row in combined_rows if isinstance(row, dict)]

    return []


def _load_swt_rows() -> List[Dict]:
    return _read_rows_from_file(SWT_WRITING_REFERENCE_FILE, "summarize_written_text")


def _load_essay_rows() -> List[Dict]:
    return _read_rows_from_file(ESSAY_WRITING_REFERENCE_FILE, "write_essay")


def _load_email_rows() -> List[Dict]:
    return _read_rows_from_file(EMAIL_WRITING_REFERENCE_FILE, "write_email")


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


def _rows_for_task(task_type: str) -> List[Dict]:
    if task_type == "summarize_written_text":
        rows = _load_swt_rows()
    elif task_type == "write_essay":
        rows = _load_essay_rows()
    elif task_type == "write_email":
        rows = _load_email_rows()
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def _tokenize_words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text.lower())


def _split_sentences(text: str) -> List[str]:
    chunks = re.split(r"[.!?]+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _extract_keywords(text: str, max_items: int = 14) -> List[str]:
    tokens = _tokenize_words(text)
    filtered = [t for t in tokens if len(t) >= 4 and t not in STOPWORDS]
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


def _copy_ratio(source_text: str, response_text: str) -> float:
    source_tokens = _tokenize_words(source_text)
    response_tokens = _tokenize_words(response_text)
    if not source_tokens or not response_tokens:
        return 0.0

    source_set = set(source_tokens)
    copied = sum(1 for token in response_tokens if token in source_set)
    return copied / max(1, len(response_tokens))


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
        category_id = ""
        if isinstance(category, dict):
            category_id = str(category.get("id", ""))
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

    return {"grammar_errors": grammar_errors, "spelling_errors": spelling_errors}


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


def _score_grammar(grammar_errors: int, word_count: int) -> int:
    rate = (grammar_errors * 100) / max(1, word_count)
    if rate <= 4.0:
        return 2
    if rate <= 9.0:
        return 1
    return 0


def _score_spelling(spelling_errors: int, word_count: int) -> int:
    rate = (spelling_errors * 100) / max(1, word_count)
    if rate <= 1.5:
        return 2
    if rate <= 3.5:
        return 1
    return 0


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


def _score_vocabulary(vocab: Dict, word_count: int) -> int:
    ttr = float(vocab.get("type_token_ratio", 0.0))
    avg_len = float(vocab.get("avg_word_length", 0.0))

    if word_count < 20:
        if ttr >= 0.5 and avg_len >= 4.2:
            return 2
        if ttr >= 0.35:
            return 1
        return 0

    if ttr >= 0.5 and avg_len >= 4.5:
        return 2
    if ttr >= 0.36:
        return 1
    return 0


def get_writing_topics(task_type: str) -> List[str]:
    rows = _rows_for_task(task_type)
    topics = sorted({str(item.get("topic", "General")) for item in rows if isinstance(item, dict)})
    return topics


def get_writing_difficulties(task_type: str) -> List[str]:
    rows = _rows_for_task(task_type)
    values = {
        _normalize_difficulty(item.get("difficulty"))
        for item in rows
        if isinstance(item, dict)
    }
    return sorted(values, key=lambda value: (DIFFICULTY_ORDER.get(value, 99), value))


def get_writing_catalog(task_type: str) -> List[Dict]:
    rows = _rows_for_task(task_type)
    catalog = []
    for item in rows:
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


def get_swt_task(
    topic: Optional[str] = None,
    prompt_id: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> Optional[Dict]:
    rows = _load_swt_rows()
    if not isinstance(rows, list) or not rows:
        return None

    if prompt_id:
        for row in rows:
            if isinstance(row, dict) and str(row.get("id", "")) == str(prompt_id):
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


def get_essay_task(
    topic: Optional[str] = None,
    prompt_id: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> Optional[Dict]:
    rows = _load_essay_rows()
    if not isinstance(rows, list) or not rows:
        return None

    if prompt_id:
        for row in rows:
            if isinstance(row, dict) and str(row.get("id", "")) == str(prompt_id):
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


def get_email_task(
    topic: Optional[str] = None,
    prompt_id: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> Optional[Dict]:
    rows = _load_email_rows()
    if not isinstance(rows, list) or not rows:
        return None

    if prompt_id:
        for row in rows:
            if isinstance(row, dict) and str(row.get("id", "")) == str(prompt_id):
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


def evaluate_summarize_written_text(passage: str, response_text: str, prompt_id: Optional[str] = None) -> Dict:
    passage = _normalize_spaces(passage)
    response_text = _normalize_spaces(response_text)
    if not passage:
        return {"error": "Source passage is required."}
    if not response_text:
        return {"error": "Summary text is required."}

    response_tokens = _tokenize_words(response_text)
    word_count = len(response_tokens)
    sentence_count = len(_split_sentences(response_text))
    ends_with_terminal = bool(re.search(r"[.!?]$", response_text))

    form_issues = []
    if word_count < SWT_WORD_MIN or word_count > SWT_WORD_MAX:
        form_issues.append(f"Word count must be between {SWT_WORD_MIN} and {SWT_WORD_MAX}.")
    if sentence_count != 1:
        form_issues.append("Summary must be exactly one sentence.")
    if not ends_with_terminal:
        form_issues.append("Summary should end with proper sentence punctuation.")
    form_score = 1 if not form_issues else 0

    keywords = _extract_keywords(passage, max_items=14)
    coverage_ratio, matched_keywords, missing_keywords = _keyword_overlap(keywords, response_text)
    if coverage_ratio >= 0.66:
        content_score = 2
    elif coverage_ratio >= 0.40:
        content_score = 1
    else:
        content_score = 0

    grammar = _grammar_signals(response_text)
    grammar_score = _score_grammar(grammar["grammar_errors"], word_count)

    vocab = _vocabulary_signals(response_text)
    vocab_score = _score_vocabulary(vocab, word_count)

    copied_ratio = _copy_ratio(passage, response_text)
    if copied_ratio > 0.78 and word_count >= 15:
        vocab_score = max(0, vocab_score - 1)

    max_total = 7
    raw_total = form_score + content_score + grammar_score + vocab_score
    if form_score == 0:
        total_score = 0
    else:
        total_score = raw_total

    feedback = []
    if form_issues:
        feedback.extend(form_issues)
    if content_score == 0:
        feedback.append("Include more core ideas from the passage.")
    if grammar_score == 0:
        feedback.append("Fix grammar and punctuation to improve clarity.")
    if vocab_score == 0:
        feedback.append("Use clearer academic vocabulary and avoid repetition.")
    if copied_ratio > 0.78 and word_count >= 15:
        feedback.append("Paraphrase more instead of copying source wording.")
    if not feedback:
        feedback.append("Good one-sentence summary with balanced content and language quality.")

    return {
        "task": "summarize_written_text",
        "prompt_id": prompt_id,
        "scores": {
            "content": {"score": content_score, "max": 2},
            "form": {"score": form_score, "max": 1},
            "grammar": {"score": grammar_score, "max": 2},
            "vocabulary": {"score": vocab_score, "max": 2},
            "total": {
                "score": total_score,
                "max": max_total,
                "percent": round((total_score / max_total) * 100, 1),
            },
        },
        "analysis": {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "keyword_coverage_percent": round(coverage_ratio * 100, 1),
            "matched_keywords": matched_keywords,
            "missing_keywords": missing_keywords[:8],
            "copied_token_ratio_percent": round(copied_ratio * 100, 1),
            "grammar_errors": grammar["grammar_errors"],
            "grammar_service_available": grammar["service_available"],
        },
        "feedback": feedback,
    }


def evaluate_write_essay(prompt: str, response_text: str, prompt_id: Optional[str] = None) -> Dict:
    prompt = _normalize_spaces(prompt)
    response_text = _normalize_spaces(response_text)
    if not prompt:
        return {"error": "Essay prompt is required."}
    if not response_text:
        return {"error": "Essay text is required."}

    response_tokens = _tokenize_words(response_text)
    word_count = len(response_tokens)
    sentence_count = len(_split_sentences(response_text))
    paragraph_count = len([chunk for chunk in re.split(r"\n\s*\n", response_text) if chunk.strip()])
    if paragraph_count == 0:
        paragraph_count = 1

    if ESSAY_BEST_MIN <= word_count <= ESSAY_BEST_MAX:
        form_score = 2
    elif ESSAY_ALLOWED_MIN <= word_count <= ESSAY_ALLOWED_MAX:
        form_score = 1
    else:
        form_score = 0

    prompt_keywords = _extract_keywords(prompt, max_items=10)
    relevance_ratio, matched_keywords, missing_keywords = _keyword_overlap(prompt_keywords, response_text)

    if relevance_ratio >= 0.70:
        content_score = 6
    elif relevance_ratio >= 0.55:
        content_score = 5
    elif relevance_ratio >= 0.42:
        content_score = 4
    elif relevance_ratio >= 0.30:
        content_score = 3
    elif relevance_ratio >= 0.20:
        content_score = 2
    elif relevance_ratio >= 0.12:
        content_score = 1
    else:
        content_score = 0

    transition_hits = 0
    response_lower = response_text.lower()
    for transition in TRANSITION_WORDS:
        if transition in response_lower:
            transition_hits += 1

    paragraph_points = 2 if 2 <= paragraph_count <= 5 else (1 if paragraph_count >= 1 else 0)
    sentence_points = 2 if sentence_count >= 8 else (1 if sentence_count >= 5 else 0)
    transition_points = 2 if transition_hits >= 4 else (1 if transition_hits >= 2 else 0)
    coherence_score = paragraph_points + sentence_points + transition_points

    grammar = _grammar_signals(response_text)
    grammar_score = _score_grammar(grammar["grammar_errors"], word_count)
    spelling_score = _score_spelling(grammar["spelling_errors"], word_count)

    vocab = _vocabulary_signals(response_text)
    vocabulary_score = _score_vocabulary(vocab, word_count)

    off_topic = relevance_ratio < 0.10 and word_count >= 120
    max_total = 20
    total_score = (
        form_score
        + content_score
        + coherence_score
        + grammar_score
        + vocabulary_score
        + spelling_score
    )
    if off_topic:
        total_score = min(total_score, 6)

    feedback = []
    if form_score == 0:
        feedback.append(f"Target {ESSAY_BEST_MIN}-{ESSAY_BEST_MAX} words; avoid very short or very long essays.")
    if content_score <= 2:
        feedback.append("Address the prompt more directly with relevant arguments and examples.")
    if coherence_score <= 2:
        feedback.append("Improve structure with clearer paragraphs and transitions.")
    if grammar_score == 0:
        feedback.append("Reduce grammar errors to improve readability.")
    if spelling_score == 0:
        feedback.append("Correct spelling mistakes to protect your language score.")
    if vocabulary_score == 0:
        feedback.append("Use more precise and varied academic vocabulary.")
    if off_topic:
        feedback.append("Essay appears off-topic; align your response closely to the prompt.")
    if not feedback:
        feedback.append("Well-structured essay with relevant content and consistent language control.")

    return {
        "task": "write_essay",
        "prompt_id": prompt_id,
        "scores": {
            "content": {"score": content_score, "max": 6},
            "form": {"score": form_score, "max": 2},
            "development_structure_coherence": {"score": coherence_score, "max": 6},
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
            "sentence_count": sentence_count,
            "paragraph_count": paragraph_count,
            "transition_hits": transition_hits,
            "prompt_keyword_coverage_percent": round(relevance_ratio * 100, 1),
            "matched_prompt_keywords": matched_keywords,
            "missing_prompt_keywords": missing_keywords[:8],
            "grammar_errors": grammar["grammar_errors"],
            "spelling_errors": grammar["spelling_errors"],
            "grammar_service_available": grammar["service_available"],
            "off_topic_flag": off_topic,
        },
        "feedback": feedback,
    }


def _first_non_empty_line(text: str) -> str:
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _email_structure_signals(text: str) -> Dict:
    clean_text = _normalize_spaces(text)
    first_line = _first_non_empty_line(text) or clean_text
    lower_text = clean_text.lower()
    lower_first = first_line.lower()

    has_salutation = bool(
        re.match(r"^(dear|hello|hi|good morning|good afternoon|good evening)\b", lower_first)
    )

    has_closing = bool(
        re.search(
            r"\b(best regards|kind regards|regards|sincerely|yours sincerely|yours faithfully|thanks|thank you)\b",
            lower_text,
        )
    )

    has_purpose = any(
        marker in lower_text
        for marker in (
            "i am writing",
            "i'm writing",
            "i write to",
            "this email is to",
            "i would like to",
            "i would like to request",
            "i am contacting you",
            "i wanted to",
            "regarding",
        )
    )

    structure_elements = int(has_salutation) + int(has_purpose) + int(has_closing)
    return {
        "has_salutation": has_salutation,
        "has_purpose": has_purpose,
        "has_closing": has_closing,
        "structure_elements": structure_elements,
    }


def _marker_hits(text: str, markers: List[str]) -> int:
    lower_text = (text or "").lower()
    return sum(1 for marker in markers if marker in lower_text)


def evaluate_write_email(prompt: str, response_text: str, prompt_id: Optional[str] = None) -> Dict:
    prompt = _normalize_spaces(prompt)
    response_text = _normalize_spaces(response_text)
    if not prompt:
        return {"error": "Email prompt is required."}
    if not response_text:
        return {"error": "Email text is required."}

    response_tokens = _tokenize_words(response_text)
    word_count = len(response_tokens)
    sentence_count = len(_split_sentences(response_text))
    paragraph_count = len([chunk for chunk in re.split(r"\n\s*\n", response_text) if chunk.strip()])
    if paragraph_count == 0:
        paragraph_count = 1

    structure = _email_structure_signals(response_text)
    structure_elements = structure["structure_elements"]

    if EMAIL_BEST_MIN <= word_count <= EMAIL_BEST_MAX and structure_elements == 3:
        formal_requirements_score = 2
    elif EMAIL_ALLOWED_MIN <= word_count <= EMAIL_ALLOWED_MAX and structure_elements >= 2:
        formal_requirements_score = 1
    else:
        formal_requirements_score = 0

    prompt_keywords = _extract_keywords(prompt, max_items=10)
    relevance_ratio, matched_keywords, missing_keywords = _keyword_overlap(prompt_keywords, response_text)

    if word_count < EMAIL_ALLOWED_MIN:
        content_score = 0
    elif relevance_ratio >= 0.52:
        content_score = 3
    elif relevance_ratio >= 0.32:
        content_score = 2
    elif relevance_ratio >= 0.18:
        content_score = 1
    else:
        content_score = 0

    polite_hits = _marker_hits(
        response_text,
        ["please", "could you", "would you", "kindly", "thank you", "appreciate"],
    )
    informal_hits = _marker_hits(
        response_text,
        ["gonna", "wanna", "btw", "thx", "pls", "u ", "ur "],
    )

    if structure_elements >= 3 and polite_hits >= 1 and informal_hits == 0:
        email_conventions_score = 2
    elif structure_elements >= 2 and informal_hits <= 1:
        email_conventions_score = 1
    else:
        email_conventions_score = 0

    grammar = _grammar_signals(response_text)
    grammar_score = _score_grammar(grammar["grammar_errors"], word_count)
    spelling_score = _score_spelling(grammar["spelling_errors"], word_count)

    vocab = _vocabulary_signals(response_text)
    vocabulary_score = _score_vocabulary(vocab, word_count)

    gate_triggered = content_score == 0 or formal_requirements_score == 0
    if gate_triggered:
        grammar_score = 0
        vocabulary_score = 0
        spelling_score = 0

    max_total = 13
    total_score = (
        content_score
        + formal_requirements_score
        + grammar_score
        + vocabulary_score
        + spelling_score
        + email_conventions_score
    )

    feedback = []
    if formal_requirements_score == 0:
        feedback.append("Keep 50-120 words and include salutation, purpose, and closing.")
    elif formal_requirements_score == 1:
        feedback.append("Add the missing email structure element to reach full formal score.")
    if content_score <= 1:
        feedback.append("Address the task purpose more directly with key prompt details.")
    if email_conventions_score == 0:
        feedback.append("Use clearer email conventions and an appropriate tone for the recipient.")
    if gate_triggered:
        feedback.append("Grammar, vocabulary, and spelling are capped because content/formal requirements are too low.")
    else:
        if grammar_score == 0:
            feedback.append("Reduce grammar errors to improve readability.")
        if spelling_score == 0:
            feedback.append("Correct spelling mistakes to improve your language score.")
        if vocabulary_score == 0:
            feedback.append("Use more precise and varied vocabulary.")
    if not feedback:
        feedback.append("Clear and well-structured email with good language control.")

    return {
        "task": "write_email",
        "prompt_id": prompt_id,
        "scores": {
            "content": {"score": content_score, "max": 3},
            "formal_requirements": {"score": formal_requirements_score, "max": 2},
            "grammar": {"score": grammar_score, "max": 2},
            "vocabulary": {"score": vocabulary_score, "max": 2},
            "spelling": {"score": spelling_score, "max": 2},
            "email_conventions": {"score": email_conventions_score, "max": 2},
            "total": {
                "score": total_score,
                "max": max_total,
                "percent": round((total_score / max_total) * 100, 1),
            },
        },
        "analysis": {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "paragraph_count": paragraph_count,
            "prompt_keyword_coverage_percent": round(relevance_ratio * 100, 1),
            "matched_prompt_keywords": matched_keywords,
            "missing_prompt_keywords": missing_keywords[:8],
            "has_salutation": structure["has_salutation"],
            "has_purpose_statement": structure["has_purpose"],
            "has_closing": structure["has_closing"],
            "structure_element_count": structure_elements,
            "polite_marker_hits": polite_hits,
            "informal_marker_hits": informal_hits,
            "grammar_errors": grammar["grammar_errors"],
            "spelling_errors": grammar["spelling_errors"],
            "grammar_service_available": grammar["service_available"],
            "gate_triggered": gate_triggered,
        },
        "feedback": feedback,
    }
