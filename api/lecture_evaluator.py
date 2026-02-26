"""
Retell Lecture Evaluation Module

Production-oriented evaluator that scores:
- Content relevance and key-idea coverage
- Pronunciation from MFA word-level evidence
- Oral fluency from duration, pace, and discourse structure

The implementation is practice-oriented and transparent; Pearson's full
production algorithm is proprietary.
"""

import json
import os
import random
import re
from typing import Dict, List, Optional, Tuple

from src.shared.paths import LECTURE_REFERENCE_FILE

# Fallback lexical similarity.
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

# Reuse speaking-semantic model and MFA pronunciation aggregation.
from api.image_evaluator import get_semantic_model, compute_pronunciation_score

try:
    from sentence_transformers import util as st_util

    SENTENCE_UTIL_AVAILABLE = True
except Exception:
    SENTENCE_UTIL_AVAILABLE = False

REFERENCES_FILE = LECTURE_REFERENCE_FILE
DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "difficult": 2}

TEMPLATE_PATTERNS = [
    r"\bat a fleeting glance\b",
    r"\bthe lecture was very interesting\b",
    r"\bthis topic is very useful in our daily life\b",
    r"\bi am done\b",
    r"\bthank you\b",
]

HARD_TEMPLATE_PATTERNS = {
    r"\bat a fleeting glance\b",
    r"\bi am done\b",
}

FILLER_TOKENS = {
    "um",
    "uh",
    "erm",
    "ah",
    "hmm",
}

CONNECTOR_PATTERN = re.compile(
    r"\b(first|firstly|second|secondly|third|thirdly|then|next|also|additionally|"
    r"moreover|furthermore|however|finally|overall|in summary|in conclusion)\b"
)


def _safe_int_env(name: str, default: int, minimum: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        parsed = int(raw_value)
    except ValueError:
        parsed = default
    return max(minimum, parsed)


def _safe_float_env(name: str, default: float, minimum: float) -> float:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        parsed = float(raw_value)
    except ValueError:
        parsed = default
    return max(minimum, parsed)


def get_retell_lecture_runtime_config() -> Dict[str, float]:
    """Runtime config aligned to public PTE retell-lecture timings."""
    prep_seconds = _safe_int_env("PTE_RL_PREP_SECONDS", 10, 3)
    response_seconds = _safe_int_env("PTE_RL_RESPONSE_SECONDS", 40, 10)
    prompt_min_seconds = _safe_int_env("PTE_RL_PROMPT_MIN_SECONDS", 60, 20)
    prompt_max_seconds = _safe_int_env("PTE_RL_PROMPT_MAX_SECONDS", 90, prompt_min_seconds)
    recommended_response_min = _safe_int_env("PTE_RL_RECOMMENDED_MIN_RESPONSE_SECONDS", 22, 8)
    if recommended_response_min > response_seconds:
        recommended_response_min = response_seconds

    target_wps_min = _safe_float_env("PTE_RL_TARGET_WPS_MIN", 1.6, 0.5)
    target_wps_max = _safe_float_env("PTE_RL_TARGET_WPS_MAX", 3.2, target_wps_min)

    return {
        "prompt_min_seconds": prompt_min_seconds,
        "prompt_max_seconds": prompt_max_seconds,
        "prep_seconds": prep_seconds,
        "response_seconds": response_seconds,
        "recommended_response_min_seconds": recommended_response_min,
        "recommended_response_max_seconds": response_seconds,
        "target_wps_min": target_wps_min,
        "target_wps_max": target_wps_max,
    }


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


def load_lecture_data() -> Dict:
    """Load retell-lecture references."""
    if not REFERENCES_FILE.exists():
        return {"lectures": []}

    with open(REFERENCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def preprocess_text(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text


def _tokenize_words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", str(text or "").lower())


def _split_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _parse_speed_multiplier(speed: str) -> float:
    normalized = str(speed or "x1.0").strip().lower()
    if not normalized.startswith("x"):
        return 1.0
    try:
        value = float(normalized[1:])
    except ValueError:
        return 1.0
    return max(0.5, min(2.0, value))


def estimate_prompt_seconds(text: str, speed: str = "x1.0") -> int:
    """Estimate prompt duration from token count and selected speed."""
    word_count = len(_tokenize_words(text))
    if word_count <= 0:
        return 0

    # Approx spoken academic lecture pace for TTS content.
    base_seconds = word_count / 2.4
    speed_multiplier = _parse_speed_multiplier(speed)
    adjusted = base_seconds / speed_multiplier
    return int(round(max(5.0, adjusted)))


def resolve_prompt_transcript(lecture_data: Dict) -> str:
    """Return the transcript actually used for prompt playback and scoring."""
    prompt_transcript = str(lecture_data.get("prompt_transcript", "")).strip()
    if prompt_transcript:
        return prompt_transcript

    transcript = str(lecture_data.get("transcript", "")).strip()
    if not transcript:
        return ""

    cfg = get_retell_lecture_runtime_config()
    prompt_max_seconds = int(cfg["prompt_max_seconds"])
    current_estimate = estimate_prompt_seconds(transcript)
    if current_estimate <= prompt_max_seconds:
        return transcript

    sentences = _split_sentences(transcript)
    if not sentences:
        return transcript

    reduced: List[str] = []
    for sentence in sentences:
        candidate = " ".join(reduced + [sentence]).strip()
        if reduced and estimate_prompt_seconds(candidate) > prompt_max_seconds:
            break
        reduced.append(sentence)

    trimmed = " ".join(reduced).strip()
    return trimmed or transcript


def _build_example_response(lecture_data: Dict) -> str:
    explicit = str(lecture_data.get("example_response", "")).strip()
    if explicit:
        return explicit

    key_points = lecture_data.get("key_points", [])
    if isinstance(key_points, list):
        cleaned = [str(item).strip() for item in key_points if str(item).strip()]
        if cleaned:
            return " ".join(cleaned[:3])

    transcript = resolve_prompt_transcript(lecture_data)
    sentences = _split_sentences(transcript)
    return " ".join(sentences[:2])


def get_lecture_categories() -> List[str]:
    data = load_lecture_data()
    lectures = data.get("lectures", [])
    values = {
        _normalize_difficulty(item.get("difficulty"))
        for item in lectures
        if isinstance(item, dict)
    }
    return sorted(values, key=lambda value: (DIFFICULTY_ORDER.get(value, 99), value))


def get_lecture_catalog() -> List[Dict]:
    data = load_lecture_data()
    lectures = data.get("lectures", [])
    catalog = []
    for item in lectures:
        if not isinstance(item, dict):
            continue
        lecture_id = str(item.get("id", "")).strip()
        if not lecture_id:
            continue
        prompt_text = resolve_prompt_transcript(item)
        catalog.append(
            {
                "id": lecture_id,
                "title": str(item.get("title", "Untitled")),
                "difficulty": _normalize_difficulty(item.get("difficulty")),
                "prompt_seconds_estimate": estimate_prompt_seconds(prompt_text),
                "prompt_word_count": len(_tokenize_words(prompt_text)),
            }
        )

    return sorted(
        catalog,
        key=lambda entry: (
            DIFFICULTY_ORDER.get(str(entry.get("difficulty", "")).lower(), 99),
            str(entry.get("title", "")).lower(),
        ),
    )


def get_random_lecture(difficulty: Optional[str] = None) -> Optional[Dict]:
    data = load_lecture_data()
    lectures = data.get("lectures", [])
    if not lectures:
        return None

    filtered = [item for item in lectures if isinstance(item, dict)]
    if difficulty:
        wanted = _normalize_difficulty(difficulty, fallback="")
        if not wanted:
            return None
        filtered = [
            item
            for item in filtered
            if _normalize_difficulty(item.get("difficulty"), fallback="medium") == wanted
        ]
        if not filtered:
            return None

    return random.choice(filtered or lectures)


def get_lecture_by_id(lecture_id: str) -> Optional[Dict]:
    data = load_lecture_data()
    lectures = data.get("lectures", [])
    needle = str(lecture_id or "").strip()
    for lecture in lectures:
        if str(lecture.get("id", "")).strip() == needle:
            return lecture
    return None


def calculate_keyword_coverage(keywords: List[str], student_text: str) -> float:
    if not keywords:
        return 1.0
    text_lower = str(student_text or "").lower()
    matched = sum(1 for kw in keywords if str(kw).lower() in text_lower)
    return matched / len(keywords)


def _token_overlap_ratio(reference: str, student_text: str) -> float:
    reference_tokens = set(preprocess_text(reference).split())
    student_tokens = set(preprocess_text(student_text).split())
    if not reference_tokens or not student_tokens:
        return 0.0
    return len(reference_tokens & student_tokens) / len(reference_tokens)


def tfidf_similarity(reference: str, student_text: str) -> float:
    if not SKLEARN_AVAILABLE:
        return _token_overlap_ratio(reference, student_text)

    vectorizer = TfidfVectorizer()
    try:
        matrix = vectorizer.fit_transform([reference, student_text])
        similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
        return float(similarity)
    except Exception:
        return _token_overlap_ratio(reference, student_text)


def semantic_similarity(reference: str, student_text: str) -> float:
    model = get_semantic_model()
    if model is None or not SENTENCE_UTIL_AVAILABLE:
        return tfidf_similarity(reference, student_text)

    try:
        embeddings = model.encode([reference, student_text], convert_to_tensor=True)
        score = st_util.pytorch_cos_sim(embeddings[0], embeddings[1])
        return float(score.item())
    except Exception:
        return tfidf_similarity(reference, student_text)


def _keyword_overlap_for_point(point: str, student_text: str) -> float:
    point_tokens = set(_tokenize_words(point))
    if not point_tokens:
        return 0.0
    student_tokens = set(_tokenize_words(student_text))
    if not student_tokens:
        return 0.0
    return len(point_tokens & student_tokens) / len(point_tokens)


def calculate_key_point_coverage(
    key_points: List[str],
    student_text: str,
) -> Tuple[float, List[str], List[str], float]:
    cleaned_points = [str(item).strip() for item in key_points if str(item).strip()]
    if not cleaned_points:
        return 1.0, [], [], 1.0

    model = get_semantic_model()
    similarities: List[float] = []

    if model is not None and SENTENCE_UTIL_AVAILABLE:
        try:
            embeddings = model.encode(cleaned_points + [student_text], convert_to_tensor=True)
            student_embedding = embeddings[-1]
            for idx in range(len(cleaned_points)):
                sim = st_util.pytorch_cos_sim(embeddings[idx], student_embedding)
                similarities.append(float(sim.item()))
        except Exception:
            similarities = [_keyword_overlap_for_point(point, student_text) for point in cleaned_points]
    else:
        similarities = [_keyword_overlap_for_point(point, student_text) for point in cleaned_points]

    matched_points: List[str] = []
    missing_points: List[str] = []
    for point, sim in zip(cleaned_points, similarities):
        if sim >= 0.38:
            matched_points.append(point)
        else:
            missing_points.append(point)

    coverage = len(matched_points) / len(cleaned_points)
    avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
    return coverage, matched_points, missing_points, avg_similarity


def detect_memorized_template(student_text: str) -> Dict[str, object]:
    text_lower = str(student_text or "").lower()
    matched: List[str] = []
    hard_hit = False

    for pattern in TEMPLATE_PATTERNS:
        if re.search(pattern, text_lower):
            matched.append(pattern)
            if pattern in HARD_TEMPLATE_PATTERNS:
                hard_hit = True

    return {
        "is_flagged": hard_hit or len(matched) >= 2,
        "matched_count": len(matched),
        "matched_patterns": matched[:4],
    }


def infer_speaking_duration(
    mfa_words: Optional[List[Dict]] = None,
    fallback_seconds: Optional[float] = None,
) -> Optional[float]:
    starts: List[float] = []
    ends: List[float] = []

    for word in mfa_words or []:
        if not isinstance(word, dict):
            continue
        if word.get("status") == "deleted":
            continue
        start = word.get("start")
        end = word.get("end")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
            starts.append(float(start))
            ends.append(float(end))

    if starts and ends:
        return round(max(0.0, max(ends) - min(starts)), 2)

    if isinstance(fallback_seconds, (int, float)) and fallback_seconds > 0:
        return round(float(fallback_seconds), 2)

    return None


def _structure_metrics(student_text: str) -> Dict[str, object]:
    text_lower = str(student_text or "").lower()
    has_context = bool(re.search(r"\b(lecture|talk|speaker|presentation)\b", text_lower))
    connectors = CONNECTOR_PATTERN.findall(text_lower)
    has_summary = bool(re.search(r"\b(overall|in summary|in conclusion|to conclude)\b", text_lower))

    return {
        "has_context": has_context,
        "connector_count": len(connectors),
        "has_summary": has_summary,
    }


def _filler_ratio(student_text: str) -> float:
    words = _tokenize_words(student_text)
    if not words:
        return 0.0
    filler_count = sum(1 for token in words if token in FILLER_TOKENS)
    return filler_count / len(words)


def calculate_score(
    reference: str,
    student_text: str,
    keywords: List[str],
    key_points: List[str],
    mfa_words: Optional[List[Dict]] = None,
    speech_duration_seconds: Optional[float] = None,
) -> Tuple[int, Dict]:
    """
    Calculate retell-lecture score on 0-90.

    Weighting:
    - Content: 42 points
    - Pronunciation: 24 points
    - Fluency: 24 points
    """
    runtime = get_retell_lecture_runtime_config()
    text = str(student_text or "").strip()
    word_count = len(_tokenize_words(text))

    if not text or word_count < 5:
        return 0, {
            "content_score": 0,
            "pronun_score": 0,
            "fluency_score": 0,
            "word_count": word_count,
            "content_gate": {
                "active": True,
                "code": "too_short",
                "reason": "Response is too short to evaluate.",
            },
        }

    semantic_sim = max(0.0, semantic_similarity(reference, text))
    keyword_cov = calculate_keyword_coverage(keywords, text)
    key_point_cov, matched_points, missing_points, key_point_sim_avg = calculate_key_point_coverage(key_points, text)
    template = detect_memorized_template(text)
    duration_seconds = infer_speaking_duration(mfa_words, speech_duration_seconds)

    content_gate = {"active": False, "code": None, "reason": ""}
    if word_count < 12:
        content_gate = {
            "active": True,
            "code": "too_short",
            "reason": "Response is too short to cover lecture meaning.",
        }
    elif semantic_sim < 0.18 and keyword_cov < 0.15 and key_point_cov < 0.15:
        content_gate = {
            "active": True,
            "code": "irrelevant",
            "reason": "Response does not match lecture meaning.",
        }
    elif template["is_flagged"] and semantic_sim < 0.38 and keyword_cov < 0.30:
        content_gate = {
            "active": True,
            "code": "template_heavy",
            "reason": "Response appears templated and weakly tied to this lecture.",
        }

    if content_gate["active"]:
        return 0, {
            "content_score": 0,
            "pronun_score": 0,
            "fluency_score": 0,
            "semantic_similarity": round(semantic_sim * 100, 1),
            "keyword_coverage": round(keyword_cov * 100, 1),
            "key_point_coverage": round(key_point_cov * 100, 1),
            "key_point_similarity": round(key_point_sim_avg * 100, 1),
            "missing_key_points": missing_points[:3],
            "matched_key_points": matched_points,
            "word_count": word_count,
            "duration_seconds": duration_seconds,
            "content_gate": content_gate,
            "template_evidence": template,
        }

    # Content: 42 points.
    semantic_pts = semantic_sim * 22
    keyword_pts = keyword_cov * 8
    key_point_pts = key_point_cov * 12
    content_pts = semantic_pts + keyword_pts + key_point_pts
    content_score_90 = round(content_pts / 42 * 90, 1)

    # Pronunciation: 24 points.
    pronun_score_90, pronun_raw = compute_pronunciation_score(mfa_words or [])
    pronun_pts = pronun_raw * 24

    # Fluency: 24 points.
    structure = _structure_metrics(text)
    structure_pts = 0.0
    if structure["has_context"]:
        structure_pts += 2.5
    connector_count = int(structure["connector_count"])
    if connector_count >= 2:
        structure_pts += 2.5
    elif connector_count == 1:
        structure_pts += 1.2
    if structure["has_summary"]:
        structure_pts += 3.0

    duration_min = float(runtime["recommended_response_min_seconds"])
    duration_max = float(runtime["recommended_response_max_seconds"])
    if duration_seconds is None:
        duration_pts = 5.0
    elif duration_min <= duration_seconds <= duration_max:
        duration_pts = 8.0
    elif duration_seconds < duration_min:
        duration_pts = max(1.0, (duration_seconds / duration_min) * 8.0)
    else:
        duration_pts = max(1.5, (duration_max / duration_seconds) * 8.0)

    wps = 0.0
    target_wps_min = float(runtime["target_wps_min"])
    target_wps_max = float(runtime["target_wps_max"])
    if duration_seconds and duration_seconds > 0:
        wps = word_count / duration_seconds
        if target_wps_min <= wps <= target_wps_max:
            pace_pts = 8.0
        elif wps < target_wps_min:
            pace_pts = max(1.0, (wps / target_wps_min) * 8.0)
        else:
            pace_pts = max(1.0, (target_wps_max / wps) * 8.0)
    else:
        # Fallback when duration cannot be inferred.
        if 55 <= word_count <= 120:
            pace_pts = 6.0
        elif word_count < 55:
            pace_pts = max(1.0, (word_count / 55.0) * 6.0)
        else:
            pace_pts = max(1.0, (120.0 / word_count) * 6.0)

    filler_ratio = _filler_ratio(text)
    filler_penalty = 0.0
    if filler_ratio > 0.06:
        filler_penalty = 2.0
    elif filler_ratio > 0.03:
        filler_penalty = 1.0

    fluency_pts = max(0.0, min(24.0, structure_pts + duration_pts + pace_pts - filler_penalty))
    fluency_score_90 = round(fluency_pts / 24 * 90, 1)

    raw_total = content_pts + pronun_pts + fluency_pts
    total_score = int(min(90, raw_total))

    details = {
        "content_score": content_score_90,
        "pronun_score": pronun_score_90,
        "fluency_score": fluency_score_90,
        "semantic_similarity": round(semantic_sim * 100, 1),
        "keyword_coverage": round(keyword_cov * 100, 1),
        "key_point_coverage": round(key_point_cov * 100, 1),
        "key_point_similarity": round(key_point_sim_avg * 100, 1),
        "keyword_score": round(keyword_pts, 1),
        "key_point_score": round(key_point_pts, 1),
        "structure_score": round(structure_pts, 1),
        "duration_score": round(duration_pts, 1),
        "pace_score": round(pace_pts, 1),
        "filler_penalty": round(filler_penalty, 1),
        "missing_key_points": missing_points[:3],
        "matched_key_points": matched_points,
        "word_count": word_count,
        "duration_seconds": duration_seconds,
        "words_per_second": round(wps, 2) if wps else 0.0,
        "target_wps_min": target_wps_min,
        "target_wps_max": target_wps_max,
        "duration_target_min_seconds": duration_min,
        "duration_target_max_seconds": duration_max,
        "structure_metrics": structure,
        "content_gate": content_gate,
        "template_evidence": template,
    }
    return total_score, details


def generate_feedback(details: Dict) -> str:
    content_gate = details.get("content_gate", {})
    if content_gate.get("active"):
        code = content_gate.get("code", "")
        if code == "template_heavy":
            return (
                "Your response sounds memorized and not lecture-specific. "
                "Retell the speaker's actual key ideas using your own wording."
            )
        if code == "irrelevant":
            return (
                "Your response is off-topic. Focus on the lecture's main message "
                "and supporting points."
            )
        return "Your response is too short. Include key ideas from the lecture."

    feedback: List[str] = []

    if details.get("semantic_similarity", 0) < 55:
        feedback.append("Cover the lecture's main argument more clearly.")

    if details.get("key_point_coverage", 100) < 50:
        missing = details.get("missing_key_points", [])
        if missing:
            feedback.append(f"You missed key ideas such as: {missing[0]}")
        else:
            feedback.append("Include more key ideas from the lecture.")

    duration_seconds = details.get("duration_seconds")
    min_seconds = details.get("duration_target_min_seconds")
    max_seconds = details.get("duration_target_max_seconds")
    if isinstance(duration_seconds, (int, float)) and isinstance(min_seconds, (int, float)):
        if duration_seconds < min_seconds:
            feedback.append(f"Speak longer: target at least {int(min_seconds)} seconds.")
        elif isinstance(max_seconds, (int, float)) and duration_seconds > max_seconds:
            feedback.append(f"Keep your retell within {int(max_seconds)} seconds.")

    if details.get("pronun_score", 0) < 50:
        feedback.append("Improve pronunciation clarity on key content words.")

    if not feedback:
        feedback.append("Strong retell. You covered key ideas with clear fluency and pronunciation.")

    return " ".join(feedback)


def evaluate_lecture(
    lecture_id: str,
    student_text: str,
    mfa_words: Optional[List[Dict]] = None,
    speech_duration_seconds: Optional[float] = None,
) -> Dict:
    lecture_data = get_lecture_by_id(lecture_id)
    if not lecture_data:
        return {"error": "Lecture not found", "score": 0}

    prompt_transcript = resolve_prompt_transcript(lecture_data)
    keywords = lecture_data.get("keywords", [])
    key_points = lecture_data.get("key_points", [])

    score, details = calculate_score(
        prompt_transcript,
        student_text,
        keywords,
        key_points,
        mfa_words=mfa_words,
        speech_duration_seconds=speech_duration_seconds,
    )

    return {
        "score": score,
        "feedback": generate_feedback(details),
        "details": details,
        "lecture_title": lecture_data.get("title", ""),
        "transcription": student_text,
        "reference": prompt_transcript,
        "full_transcript": lecture_data.get("transcript", ""),
        "keywords": keywords,
        "key_points": key_points,
        "example_response": _build_example_response(lecture_data),
        "prompt_duration_estimate_seconds": estimate_prompt_seconds(prompt_transcript),
    }


if __name__ == "__main__":
    sample = get_random_lecture()
    if sample:
        result = evaluate_lecture(
            str(sample.get("id", "")),
            "The lecture explains main ideas and supporting details in a clear sequence.",
        )
        print(json.dumps(result, indent=2))
