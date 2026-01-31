"""
Image Description Evaluator Module
Handles evaluation of student image descriptions against reference descriptions.
Uses TF-IDF similarity for content matching.
"""

import json
import os
import random
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Try to import sklearn, fallback to simple matching if not available
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: sklearn not available, using simple keyword matching")

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
REFERENCES_FILE = DATA_DIR / "image_references.json"


def load_image_data() -> Dict:
    """Load image reference data from JSON file."""
    if not REFERENCES_FILE.exists():
        return {"images": []}
    
    with open(REFERENCES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_random_image() -> Optional[Dict]:
    """Get a random image from the available set."""
    data = load_image_data()
    images = data.get("images", [])
    
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


def calculate_length_score(reference: str, student_text: str) -> float:
    """
    Score based on length appropriateness.
    Penalize if too short or excessively long.
    """
    ref_words = len(reference.split())
    student_words = len(student_text.split())
    
    if student_words == 0:
        return 0.0
    
    ratio = student_words / ref_words
    
    # Ideal range: 0.7 to 1.5 of reference length
    if 0.7 <= ratio <= 1.5:
        return 1.0
    elif ratio < 0.7:
        # Too short - proportional penalty
        return ratio / 0.7
    else:
        # Too long - gentle penalty
        return max(0.5, 1.5 / ratio)


def tfidf_similarity(reference: str, student_text: str) -> float:
    """Calculate TF-IDF cosine similarity between texts."""
    if not SKLEARN_AVAILABLE:
        # Fallback to simple word overlap
        ref_words = set(preprocess_text(reference).split())
        student_words = set(preprocess_text(student_text).split())
        
        if not ref_words or not student_words:
            return 0.0
        
        overlap = len(ref_words & student_words)
        return overlap / len(ref_words)
    
    # Use TF-IDF
    vectorizer = TfidfVectorizer()
    try:
        tfidf_matrix = vectorizer.fit_transform([reference, student_text])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(similarity)
    except:
        return 0.0


def calculate_score(reference: str, student_text: str, keywords: List[str]) -> Tuple[int, Dict]:
    """
    Calculate PTE-style score (0-90) for image description.
    
    Returns:
        (score, details) where details contains breakdown
    """
    if not student_text or len(student_text.strip()) < 10:
        return 0, {
            "content_score": 0,
            "keyword_score": 0,
            "length_score": 0,
            "fluency_score": 0,
            "feedback": "Description too short or empty."
        }
    
    # 1. Content accuracy (0-50 points) - TF-IDF similarity
    content_similarity = tfidf_similarity(reference, student_text)
    content_score = content_similarity * 50
    
    # 2. Keyword coverage (0-20 points)
    keyword_coverage = calculate_keyword_coverage(keywords, student_text)
    keyword_score = keyword_coverage * 20
    
    # 3. Length appropriateness (0-10 points)
    length_ratio = calculate_length_score(reference, student_text)
    length_score = length_ratio * 10
    
    # 4. Fluency (0-10 points) - placeholder for now
    # Could use ASR confidence or grammar check in future
    fluency_score = 10
    
    # Total score (capped at 90)
    total_score = int(min(90, content_score + keyword_score + length_score + fluency_score))
    
    details = {
        "content_score": round(content_score, 1),
        "keyword_score": round(keyword_score, 1),
        "length_score": round(length_score, 1),
        "fluency_score": round(fluency_score, 1),
        "content_similarity": round(content_similarity * 100, 1),
        "keyword_coverage": round(keyword_coverage * 100, 1),
        "word_count": len(student_text.split())
    }
    
    return total_score, details


def generate_feedback(score: int, details: Dict, keywords: List[str], student_text: str) -> str:
    """Generate human-readable feedback based on score and details."""
    feedback_parts = []
    
    # Overall performance
    if score >= 80:
        feedback_parts.append("Excellent description! You captured the key information effectively.")
    elif score >= 65:
        feedback_parts.append("Good description with most important details covered.")
    elif score >= 50:
        feedback_parts.append("Adequate description, but some key details are missing.")
    else:
        feedback_parts.append("Your description needs significant improvement.")
    
    # Content similarity feedback
    content_sim = details.get("content_similarity", 0)
    if content_sim < 50:
        feedback_parts.append("Try to include more specific details from the image.")
    
    # Keyword coverage feedback
    keyword_cov = details.get("keyword_coverage", 0)
    if keyword_cov < 60:
        missing_keywords = []
        student_lower = student_text.lower()
        for kw in keywords[:5]:  # Check first 5 keywords
            if kw.lower() not in student_lower:
                missing_keywords.append(kw)
        
        if missing_keywords:
            feedback_parts.append(f"Consider mentioning: {', '.join(missing_keywords[:3])}.")
    
    # Length feedback
    word_count = details.get("word_count", 0)
    if word_count < 30:
        feedback_parts.append("Your description is too brief. Add more details.")
    elif word_count > 150:
        feedback_parts.append("Try to be more concise while keeping key information.")
    
    return " ".join(feedback_parts)


def evaluate_description(image_id: str, student_text: str) -> Dict:
    """
    Main evaluation function.
    
    Args:
        image_id: ID of the image being described
        student_text: Student's transcribed description
    
    Returns:
        Dictionary with score, feedback, and details
    """
    # Get image data
    image_data = get_image_by_id(image_id)
    if not image_data:
        return {
            "error": "Image not found",
            "score": 0
        }
    
    reference = image_data.get("reference", "")
    keywords = image_data.get("keywords", [])
    
    # Calculate score
    score, details = calculate_score(reference, student_text, keywords)
    
    # Generate feedback
    feedback = generate_feedback(score, details, keywords, student_text)
    
    return {
        "score": score,
        "feedback": feedback,
        "details": details,
        "image_title": image_data.get("title", ""),
        "transcription": student_text,
        "reference": reference,
        "keywords": keywords
    }


if __name__ == "__main__":
    # Test the evaluator
    print("Testing Image Evaluator...")
    
    # Load a sample image
    img = get_random_image()
    if img:
        print(f"\nImage: {img['title']}")
        print(f"Reference: {img['reference'][:100]}...")
        
        # Test with a sample student response
        sample_response = "The bar chart shows sales data for four quarters with an increasing trend."
        result = evaluate_description(img['id'], sample_response)
        
        print(f"\nScore: {result['score']}/90")
        print(f"Feedback: {result['feedback']}")
        print(f"Details: {result['details']}")
