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


def calculate_score(
    reference: str,
    student_text: str,
    keywords: List[str],
    mfa_words: Optional[List[Dict]] = None,
) -> Tuple[int, Dict]:
    """
    Calculate PTE-style score (0-90) for image description — Hybrid engine.

    Sub-scores (matching APEuni's Content / Pronun / Fluency breakdown):
    - Content  (Semantic Match + Keyword Coverage): 0-90
    - Pronun   (MFA word-level accuracy):           0-90
    - Fluency  (length ratio + structure):          0-90
    - Total    (weighted average of the three):     0-90

    Weights for total:
        Content  40%  (semantic 26.7% + keyword 13.3%)
        Pronun   30%
        Fluency  30%  (structure 15% + length 15%)
    """
    if not student_text or len(student_text.strip()) < 10:
        return 0, {
            "content_score": 0,
            "pronun_score": 0,
            "fluency_score": 0,
            "keyword_score": 0,
            "structure_score": 0,
            "feedback": "Description too short or empty.",
            "word_count": 0,
        }

    # ── 1. Content: Semantic Match (26.7% of total → 24 pts) ──────────────
    semantic_sim = max(0.0, calculate_semantic_similarity(reference, student_text))
    semantic_pts = semantic_sim * 24  # out of 24

    # ── 2. Content: Keyword Coverage (13.3% of total → 12 pts) ───────────
    keyword_cov = calculate_keyword_coverage(keywords, student_text)
    keyword_pts = keyword_cov * 12   # out of 12

    content_raw = semantic_pts + keyword_pts  # 0-36 pts
    # Scale to 0-90 for display
    content_score_90 = round(content_raw / 36 * 90, 1)

    # ── 3. Pronunciation (30% of total → 27 pts) ─────────────────────────
    pronun_score_90, pronun_raw = compute_pronunciation_score(mfa_words or [])
    pronun_pts = pronun_raw * 27     # 0-27 pts for total

    # ── 4. Fluency: Structure (15% of total → 13.5 pts) ──────────────────
    structure = check_structure(student_text)
    structure_pts = 0.0
    if structure['has_intro']:      structure_pts += 4.5
    if structure['has_conclusion']: structure_pts += 4.5
    if structure['has_trends']:     structure_pts += 4.5

    # ── 5. Fluency: Length ratio (15% of total → 13.5 pts) ───────────────
    ref_len = len(reference.split())
    stu_len = len(student_text.split())
    if ref_len > 0:
        ratio = stu_len / ref_len
        if 0.6 <= ratio <= 1.5:
            length_pts = 13.5
        elif ratio < 0.6:
            length_pts = ratio / 0.6 * 13.5
        else:
            length_pts = max(6.0, 1.5 / ratio * 13.5)
    else:
        length_pts = 0.0

    fluency_pts = structure_pts + length_pts  # 0-27 pts
    fluency_score_90 = round(fluency_pts / 27 * 90, 1)

    # ── Total ─────────────────────────────────────────────────────────────
    raw_total = content_raw + pronun_pts + fluency_pts  # 0-90
    total_score = int(min(90, raw_total))

    details = {
        # APEuni-style 0-90 sub-scores
        "content_score": content_score_90,
        "pronun_score": pronun_score_90,
        "fluency_score": fluency_score_90,
        # Legacy breakdown (kept for backward compat)
        "keyword_score": round(keyword_pts, 1),
        "structure_score": round(structure_pts, 1),
        # Raw metrics
        "semantic_similarity": round(semantic_sim * 100, 1),
        "keyword_coverage": round(keyword_cov * 100, 1),
        "structure_metrics": structure,
        "word_count": stu_len,
    }

    return total_score, details


def generate_feedback(score: int, details: Dict, keywords: List[str], student_text: str) -> str:
    """Generate human-readable feedback based on score and details."""
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

    if not feedback_parts:
        feedback_parts.append("Excellent description! You covered content, structure, and keywords well.")
    
    return " ".join(feedback_parts)


def evaluate_description(
    image_id: str,
    student_text: str,
    mfa_words: Optional[List[Dict]] = None,
) -> Dict:
    """
    Main evaluation function.

    Args:
        image_id:     ID of the image being described.
        student_text: ASR transcription of the student's speech.
        mfa_words:    Optional list of MFA word dicts (from align_and_validate).
                      When provided, pronunciation score is computed from them.
    """
    image_data = get_image_by_id(image_id)
    if not image_data:
        return {"error": "Image not found", "score": 0}

    reference = image_data.get("reference", "")
    keywords  = image_data.get("keywords", [])

    # Calculate score (passes MFA words for pronunciation scoring)
    score, details = calculate_score(reference, student_text, keywords, mfa_words=mfa_words)

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
