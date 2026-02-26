"""
Image Description Evaluator Module
Handles evaluation of student image descriptions against reference descriptions.
Uses Sentence Transformers for semantic matching and Regex for structure analysis.
"""

import json
import random
import re
import os
import threading
from typing import Dict, List, Tuple, Optional

# Try to import sentence_transformers for semantic matching
try:
    from sentence_transformers import SentenceTransformer, util
    TRANSFORMER_AVAILABLE = True
except ImportError:
    TRANSFORMER_AVAILABLE = False
    print("Warning: sentence-transformers not available, semantic scoring will be disabled")

from src.shared.paths import IMAGE_REFERENCE_FILE

# Global model cache
SEMANTIC_MODEL = None
MODEL_NAME = 'all-MiniLM-L6-v2'

def _eager_load_model():
    """Pre-load model into process memory."""
    global SEMANTIC_MODEL
    if TRANSFORMER_AVAILABLE and SEMANTIC_MODEL is None:
        try:
            print(f"[image_evaluator] Pre-loading SentenceTransformer: {MODEL_NAME}...")
            SEMANTIC_MODEL = SentenceTransformer(MODEL_NAME)
            print(f"[image_evaluator] Model ready.")
        except Exception as e:
            print(f"[image_evaluator] Failed to pre-load model: {e}")
            
# Optional warmup. Keep disabled by default so Flask startup is not blocked.
if os.getenv("IMAGE_EVALUATOR_PRELOAD", "0").lower() in {"1", "true", "yes"}:
    threading.Thread(target=_eager_load_model, daemon=True).start()

REFERENCES_FILE = IMAGE_REFERENCE_FILE

CHART_TYPE_LABELS = {
    "bargraph": "Bar Graph",
    "piechart": "Pie Chart",
    "other": "Other",
}

MEMORIZED_TEMPLATE_PATTERNS = [
    r"\bat a fleeting glance\b",
    r"\boverall it can be clearly seen\b",
    r"\bit is clear from the (?:chart|graph|picture|image)\b",
    r"\bthe given (?:chart|graph|picture|image)\b",
    r"\bthis is all about\b",
    r"\bi am done\b",
    r"\bthank you\b",
]

HARD_TEMPLATE_PATTERNS = {
    r"\bat a fleeting glance\b",
    r"\bthis is all about\b",
    r"\bi am done\b",
}


def _safe_int_env(name: str, default: int, minimum: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        parsed = int(raw_value)
    except ValueError:
        parsed = default
    return max(minimum, parsed)


def get_describe_image_runtime_config() -> Dict[str, int]:
    """Runtime timings aligned with public PTE describe-image guidance."""
    prep_seconds = _safe_int_env("PTE_DI_PREP_SECONDS", 25, 5)
    response_seconds = _safe_int_env("PTE_DI_RESPONSE_SECONDS", 40, 10)
    recommended_min_seconds = _safe_int_env("PTE_DI_RECOMMENDED_MIN_SECONDS", 20, 8)
    if recommended_min_seconds > response_seconds:
        recommended_min_seconds = response_seconds
    return {
        "prep_seconds": prep_seconds,
        "response_seconds": response_seconds,
        "recommended_response_min_seconds": recommended_min_seconds,
        "recommended_response_max_seconds": response_seconds,
    }


def load_image_data() -> Dict:
    """Load image reference data from JSON file."""
    if not REFERENCES_FILE.exists():
        return {"images": []}
    
    with open(REFERENCES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_image_topics() -> List[str]:
    """Get unique image topics derived from image difficulty levels."""
    data = load_image_data()
    images = data.get("images", [])
    topics = sorted({img.get("difficulty", "General").title() for img in images if isinstance(img, dict)})
    return topics


def _normalize_chart_type(chart_type: Optional[str]) -> str:
    if not chart_type:
        return "other"
    normalized = str(chart_type).strip().lower().replace(" ", "")
    if normalized in {"bar", "barchart", "bargraph", "bar_graph"}:
        return "bargraph"
    if normalized in {"pie", "piechart", "pie_graph"}:
        return "piechart"
    return "other"


def infer_chart_type(image: Dict) -> str:
    """Infer chart type from filename/title/reference/keywords."""
    if not isinstance(image, dict):
        return "other"

    signals = []
    for key in ("filename", "title", "reference"):
        value = image.get(key)
        if value:
            signals.append(str(value).lower())

    keywords = image.get("keywords", [])
    if isinstance(keywords, list):
        signals.extend(str(k).lower() for k in keywords)

    merged = " ".join(signals)
    if ("bar chart" in merged) or ("bar_graph" in merged) or ("bar-chart" in merged):
        return "bargraph"
    if ("pie chart" in merged) or ("pie_graph" in merged) or ("pie-chart" in merged):
        return "piechart"
    return "other"


def get_image_catalog() -> List[Dict]:
    """Return normalized metadata for all describe-image entries."""
    data = load_image_data()
    images = data.get("images", [])
    catalog = []
    for img in images:
        if not isinstance(img, dict):
            continue
        difficulty = str(img.get("difficulty", "general")).strip().lower() or "general"
        chart_type = infer_chart_type(img)
        catalog.append({
            "id": img.get("id", ""),
            "title": img.get("title", "Untitled"),
            "filename": img.get("filename", ""),
            "difficulty": difficulty,
            "difficulty_label": difficulty.title(),
            "chart_type": chart_type,
            "chart_type_label": CHART_TYPE_LABELS.get(chart_type, "Other"),
        })
    return catalog


def get_random_image(
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    chart_type: Optional[str] = None,
    image_id: Optional[str] = None,
    exclude_id: Optional[str] = None,
) -> Optional[Dict]:
    """Get a random image, optionally filtered by difficulty/type or direct image_id."""
    data = load_image_data()
    images = data.get("images", [])

    if not images:
        return None

    if image_id:
        filtered = [
            img for img in images
            if str(img.get("id", "")).strip() == str(image_id).strip()
        ]
        if filtered:
            return filtered[0]

    difficulty_filter = difficulty or topic
    if difficulty_filter:
        difficulty_normalized = str(difficulty_filter).strip().lower()
        images = [
            img for img in images
            if str(img.get("difficulty", "General")).strip().lower() == difficulty_normalized
        ]

    if chart_type:
        chart_type_normalized = _normalize_chart_type(chart_type)
        images = [img for img in images if infer_chart_type(img) == chart_type_normalized]

    if exclude_id:
        images = [img for img in images if str(img.get("id", "")).strip() != str(exclude_id).strip()]

    if not images:
        return None

    return random.choice(images)


def get_image_by_id(image_id: str) -> Optional[Dict]:
    """Get specific image by ID."""
    data = load_image_data()
    images = data.get("images", [])
    
    for img in images:
        if img.get("id") == image_id:
            return img
    
    return None


def get_semantic_model():
    """Return the pre-loaded model (or load it if somehow not ready)."""
    global SEMANTIC_MODEL
    if SEMANTIC_MODEL is None and TRANSFORMER_AVAILABLE:
        _eager_load_model()
    return SEMANTIC_MODEL


def preprocess_text(text: str) -> str:
    """Clean and normalize text for comparison."""
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove punctuation (keep alphanumeric and spaces)
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    return text


def calculate_keyword_coverage(keywords: List[str], student_text: str) -> float:
    """Calculate what percentage of keywords appear in student text."""
    if not keywords:
        return 1.0
    
    student_text_lower = student_text.lower()
    matched = sum(1 for kw in keywords if kw.lower() in student_text_lower)
    
    return matched / len(keywords)


def calculate_semantic_similarity(reference: str, student_text: str) -> float:
    """
    Calculate semantic similarity using Sentence Transformers.
    Returns a score between 0.0 and 1.0.
    """
    model = get_semantic_model()
    if model is None:
        return 0.0
    
    try:
        # Encode sentences to get their embeddings
        embedding_1 = model.encode(reference, convert_to_tensor=True)
        embedding_2 = model.encode(student_text, convert_to_tensor=True)
        
        # Compute cosine similarity
        score = util.pytorch_cos_sim(embedding_1, embedding_2)
        return float(score.item())
    except Exception as e:
        print(f"Semantic calculation error: {e}")
        return 0.0


def check_structure(text: str) -> Dict[str, bool]:
    """
    Check for structural elements using Regex.
    Returns dict: {'has_intro': bool, 'has_conclusion': bool, 'has_trends': bool}
    """
    text_lower = text.lower().strip()
    if not text_lower:
        return {'has_intro': False, 'has_conclusion': False, 'has_trends': False}

    # 1. Intro Check (Usually at the start)
    # Pattern: "The [chart/graph...] shows/displays..."
    intro_pattern = r"(the|this)\s+(image|chart|graph|map|table|diagram|bar|line|pie)\s+(shows|displays|illustrates|depicts|presents|gives|represented)"
    has_intro = bool(re.search(intro_pattern, text_lower))

    # 2. Conclusion Check
    # Pattern: "Overall", "In conclusion", "To summarize"
    conclusion_pattern = r"(overall|in conclusion|to conclude|to summarize|in summary|generally speaking)"
    has_conclusion = bool(re.search(conclusion_pattern, text_lower))

    # 3. Trend/Logic Check
    # Pattern: "increase", "decrease", "stable", "fluctuate", "highest", "lowest"
    trend_pattern = r"(increase|decrease|rise|fall|drop|climb|fluctuate|stable|steady|constant|trend|highest|lowest|maximum|minimum|peak)"
    has_trends = bool(re.search(trend_pattern, text_lower))

    return {
        'has_intro': has_intro,
        'has_conclusion': has_conclusion,
        'has_trends': has_trends
    }


def compute_pronunciation_score(mfa_words: List[Dict]) -> Tuple[float, float]:
    """
    Derive a pronunciation score (0-90) from MFA word-level data.

    Uses `accuracy_score` per word (0-100) if available, otherwise falls back
    to binary correct/mispronounced status.

    Returns:
        (pronun_score_0_to_90, raw_accuracy_0_to_1)
    """
    if not mfa_words:
        return 0.0, 0.0

    scored_words = []
    for w in mfa_words:
        status = w.get('status', 'unknown')
        if status == 'inserted':  # extra word — penalise
            scored_words.append(0.0)
            continue
        acc = w.get('accuracy_score')
        if acc is not None:
            scored_words.append(float(acc) / 100.0)
        elif status == 'correct':
            scored_words.append(1.0)
        elif status == 'mispronounced':
            scored_words.append(0.0)
        # deleted / unknown words are skipped (not penalised twice)

    if not scored_words:
        return 0.0, 0.0

    raw = sum(scored_words) / len(scored_words)  # 0.0 – 1.0
    pronun_score = round(raw * 90, 1)
    return pronun_score, raw


def detect_memorized_template(student_text: str) -> Dict[str, object]:
    """
    Detect high-risk template-heavy language.

    We only use this as a gating signal when content relevance is also weak.
    """
    text_lower = str(student_text or "").lower()
    matched_patterns = []
    hard_hit = False

    for pattern in MEMORIZED_TEMPLATE_PATTERNS:
        if re.search(pattern, text_lower):
            matched_patterns.append(pattern)
            if pattern in HARD_TEMPLATE_PATTERNS:
                hard_hit = True

    return {
        "is_flagged": hard_hit or len(matched_patterns) >= 3,
        "matched_count": len(matched_patterns),
        "matched_patterns": matched_patterns[:5],
    }


def calculate_number_coverage(reference: str, student_text: str) -> float:
    """
    Reward number/data mention when the prompt itself includes numbers.
    """
    reference_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", reference or ""))
    if not reference_numbers:
        return 1.0

    student_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", student_text or ""))
    if not student_numbers:
        return 0.0

    matched = reference_numbers.intersection(student_numbers)
    return len(matched) / len(reference_numbers)


def infer_speaking_duration(
    mfa_words: Optional[List[Dict]] = None,
    fallback_seconds: Optional[float] = None,
) -> Optional[float]:
    """Estimate speech duration from MFA words, with client-side fallback."""
    starts = []
    ends = []
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


def calculate_score(
    reference: str,
    student_text: str,
    keywords: List[str],
    mfa_words: Optional[List[Dict]] = None,
    speech_duration_seconds: Optional[float] = None,
) -> Tuple[int, Dict]:
    """
    Calculate PTE-style score (0-90) for image description — Hybrid engine.

    Sub-scores:
    - Content  (semantic + keyword + data points): 0-90
    - Pronun   (MFA word-level accuracy):          0-90
    - Fluency  (structure + length + timing):      0-90
    - Total: weighted 40/30/30 on a 0-90 scale.

    Public PTE guidance includes this gating behavior:
    when content quality is effectively zero, fluency and pronunciation should
    not contribute to the score. We implement a conservative gate for that.
    """
    timing_cfg = get_describe_image_runtime_config()
    text = (student_text or "").strip()
    word_count = len(text.split())

    if not text or len(text) < 10:
        return 0, {
            "content_score": 0,
            "pronun_score": 0,
            "fluency_score": 0,
            "keyword_score": 0,
            "structure_score": 0,
            "feedback": "Description too short or empty.",
            "word_count": 0,
            "content_gate": {"active": True, "code": "too_short", "reason": "Description too short or empty."},
            "duration_seconds": None,
        }

    semantic_sim = max(0.0, calculate_semantic_similarity(reference, text))
    keyword_cov = calculate_keyword_coverage(keywords, text)
    number_cov = calculate_number_coverage(reference, text)
    template_evidence = detect_memorized_template(text)
    duration_seconds = infer_speaking_duration(mfa_words, speech_duration_seconds)

    content_gate = {"active": False, "code": None, "reason": ""}
    if word_count < 8:
        content_gate = {
            "active": True,
            "code": "too_short",
            "reason": "Response is too short to cover the image meaning.",
        }
    elif semantic_sim < 0.22 and keyword_cov < 0.2:
        content_gate = {
            "active": True,
            "code": "irrelevant",
            "reason": "Response does not meaningfully match the image content.",
        }
    elif template_evidence["is_flagged"] and semantic_sim < 0.45 and keyword_cov < 0.35:
        content_gate = {
            "active": True,
            "code": "template_heavy",
            "reason": "Response appears template-heavy and weakly tied to this image.",
        }

    if content_gate["active"]:
        details = {
            "content_score": 0,
            "pronun_score": 0,
            "fluency_score": 0,
            "keyword_score": 0,
            "structure_score": 0,
            "semantic_similarity": round(semantic_sim * 100, 1),
            "keyword_coverage": round(keyword_cov * 100, 1),
            "number_coverage": round(number_cov * 100, 1),
            "structure_metrics": check_structure(text),
            "word_count": word_count,
            "content_gate": content_gate,
            "template_evidence": template_evidence,
            "duration_seconds": duration_seconds,
            "duration_target_min_seconds": timing_cfg["recommended_response_min_seconds"],
            "duration_target_max_seconds": timing_cfg["recommended_response_max_seconds"],
            "length_ratio": 0.0,
            "semantic_model_available": bool(TRANSFORMER_AVAILABLE and SEMANTIC_MODEL is not None),
        }
        return 0, details

    # Content points: 22 + 10 + 4 = 36
    semantic_pts = semantic_sim * 22
    keyword_pts = keyword_cov * 10
    number_pts = number_cov * 4
    content_raw = semantic_pts + keyword_pts + number_pts
    content_score_90 = round(content_raw / 36 * 90, 1)

    pronun_score_90, pronun_raw = compute_pronunciation_score(mfa_words or [])
    pronun_pts = pronun_raw * 27

    structure = check_structure(text)
    structure_pts = 0.0
    if structure['has_intro']:
        structure_pts += 3.0
    if structure['has_conclusion']:
        structure_pts += 3.0
    if structure['has_trends']:
        structure_pts += 3.0

    # Length fit: max 9 points.
    ref_len = len(reference.split())
    ratio = 0.0
    if ref_len > 0:
        ratio = word_count / ref_len
        if 0.6 <= ratio <= 1.5:
            length_pts = 9.0
        elif ratio < 0.6:
            length_pts = max(0.0, ratio / 0.6 * 9.0)
        else:
            length_pts = max(2.0, 1.5 / ratio * 9.0)
    else:
        length_pts = 4.5

    # Time fit (public task behavior: short prep + capped response window): max 9.
    duration_min = timing_cfg["recommended_response_min_seconds"]
    duration_max = timing_cfg["recommended_response_max_seconds"]
    if duration_seconds is None:
        duration_pts = 6.0  # neutral fallback if no reliable timing exists
    elif duration_min <= duration_seconds <= duration_max:
        duration_pts = 9.0
    elif duration_seconds < duration_min:
        duration_pts = max(1.5, duration_seconds / duration_min * 9.0)
    else:
        duration_pts = max(2.0, duration_max / duration_seconds * 9.0)

    fluency_pts = structure_pts + length_pts + duration_pts  # 0-27 pts
    fluency_score_90 = round(fluency_pts / 27 * 90, 1)

    raw_total = content_raw + pronun_pts + fluency_pts
    total_score = int(min(90, raw_total))

    details = {
        "content_score": content_score_90,
        "pronun_score": pronun_score_90,
        "fluency_score": fluency_score_90,
        "keyword_score": round(keyword_pts, 1),
        "structure_score": round(structure_pts, 1),
        "number_score": round(number_pts, 1),
        "semantic_similarity": round(semantic_sim * 100, 1),
        "keyword_coverage": round(keyword_cov * 100, 1),
        "number_coverage": round(number_cov * 100, 1),
        "structure_metrics": structure,
        "word_count": word_count,
        "duration_seconds": duration_seconds,
        "duration_target_min_seconds": duration_min,
        "duration_target_max_seconds": duration_max,
        "length_ratio": round(ratio, 3),
        "content_gate": content_gate,
        "template_evidence": template_evidence,
        "semantic_model_available": bool(TRANSFORMER_AVAILABLE and SEMANTIC_MODEL is not None),
    }

    return total_score, details


def generate_feedback(score: int, details: Dict, keywords: List[str], student_text: str) -> str:
    """Generate human-readable feedback based on score and details."""
    content_gate = details.get("content_gate", {})
    if content_gate.get("active"):
        gate_code = content_gate.get("code", "")
        if gate_code == "template_heavy":
            return (
                "Your response sounds over-templated and does not stay specific to this image. "
                "Use direct data points and image-specific comparisons."
            )
        if gate_code == "irrelevant":
            return (
                "Your response does not match the image meaning. Focus on key values, comparisons, "
                "and the overall trend shown in the chart."
            )
        return "Your response is too short. Give a full image-specific description."

    feedback_parts = []
    
    # Structure Feedback
    struct = details.get("structure_metrics", {})
    if not struct.get("has_intro"):
        feedback_parts.append("Start with an introduction like 'The chart shows...'.")
    if not struct.get("has_conclusion"):
        feedback_parts.append("Add a conclusion starting with 'Overall' or 'In conclusion'.")
    if not struct.get("has_trends"):
        feedback_parts.append("Mention trends using words like 'increase', 'decrease', or 'highest'.")

    # Semantic Feedback
    content_sim = details.get("semantic_similarity", 0)
    if content_sim < 60:
        feedback_parts.append("Your description doesn't fully capture the meaning of the image. Try to be more specific.")
    
    # Keyword Feedback
    keyword_cov = details.get("keyword_coverage", 0)
    if keyword_cov < 50:
        missing = [k for k in keywords if k.lower() not in student_text.lower()][:3]
        if missing:
            feedback_parts.append(f"Try to use key words: {', '.join(missing)}.")

    number_cov = details.get("number_coverage", 100)
    if number_cov < 50:
        feedback_parts.append("Include more data points (numbers or percentages) from the image.")

    duration_seconds = details.get("duration_seconds")
    min_seconds = details.get("duration_target_min_seconds")
    max_seconds = details.get("duration_target_max_seconds")
    if isinstance(duration_seconds, (int, float)) and isinstance(min_seconds, (int, float)):
        if duration_seconds < min_seconds:
            feedback_parts.append(f"Speak longer: target at least {int(min_seconds)} seconds for full coverage.")
        elif isinstance(max_seconds, (int, float)) and duration_seconds > max_seconds:
            feedback_parts.append(f"Keep your response within {int(max_seconds)} seconds.")

    if not feedback_parts:
        feedback_parts.append("Excellent description! You covered content, structure, and keywords well.")
    
    return " ".join(feedback_parts)


def evaluate_description(
    image_id: str,
    student_text: str,
    mfa_words: Optional[List[Dict]] = None,
    speech_duration_seconds: Optional[float] = None,
) -> Dict:
    """
    Main evaluation function.

    Args:
        image_id:     ID of the image being described.
        student_text: ASR transcription of the student's speech.
        mfa_words:    Optional list of MFA word dicts (from align_and_validate).
                      When provided, pronunciation score is computed from them.
        speech_duration_seconds: Optional client-side measured recording length.
    """
    image_data = get_image_by_id(image_id)
    if not image_data:
        return {"error": "Image not found", "score": 0}

    reference = image_data.get("reference", "")
    keywords  = image_data.get("keywords", [])

    # Calculate score (passes MFA words for pronunciation scoring)
    score, details = calculate_score(
        reference,
        student_text,
        keywords,
        mfa_words=mfa_words,
        speech_duration_seconds=speech_duration_seconds,
    )

    # Generate feedback
    feedback = generate_feedback(score, details, keywords, student_text)

    return {
        "score": score,
        "feedback": feedback,
        "details": details,
        "image_title": image_data.get("title", ""),
        "transcription": student_text,
        "reference": reference,
        "keywords": keywords,
    }


if __name__ == "__main__":
    # Test the evaluator
    print("Testing Image Evaluator (Hybrid AI)...")
    
    # Load a sample image
    img = get_random_image()
    if img:
        print(f"\nImage: {img['title']}")
        print(f"Reference: {img['reference'][:100]}...")
        
        # Test with a sample student response
        # 1. Good response
        good_response = "The bar chart shows sales data for four quarters. Overall, there is an increasing trend in revenue."
        print(f"\n--- Good Response: {good_response} ---")
        result = evaluate_description(img['id'], good_response)
        print(f"Score: {result['score']}/90")
        print(f"Details: {result['details']}")
        print(f"Feedback: {result['feedback']}")

        # 2. Bad response
        bad_response = "I see a picture with some blue bars and numbers."
        print(f"\n--- Bad Response: {bad_response} ---")
        result = evaluate_description(img['id'], bad_response)
        print(f"Score: {result['score']}/90")
        print(f"Details: {result['details']}")
        print(f"Feedback: {result['feedback']}")
