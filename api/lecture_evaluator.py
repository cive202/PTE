"""
Lecture Evaluation Module
Handles evaluation of student retell lecture responses against reference transcripts.
Uses TF-IDF similarity for content matching and keyword coverage.
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
LECTURES_DIR = DATA_DIR / "lectures"
REFERENCES_FILE = DATA_DIR / "lecture_references.json"


def load_lecture_data() -> Dict:
    """Load lecture reference data from JSON file."""
    if not REFERENCES_FILE.exists():
        return {"lectures": []}
    
    with open(REFERENCES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_random_lecture() -> Optional[Dict]:
    """Get a random lecture from the available set."""
    data = load_lecture_data()
    lectures = data.get("lectures", [])
    
    if not lectures:
        return None
    
    return random.choice(lectures)


def get_lecture_by_id(lecture_id: str) -> Optional[Dict]:
    """Get specific lecture by ID."""
    data = load_lecture_data()
    lectures = data.get("lectures", [])
    
    for lec in lectures:
        if lec.get("id") == lecture_id:
            return lec
    
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
    Calculate PTE-style score (0-90) for Retell Lecture.
    
    Returns:
        (score, details) where details contains breakdown
    """
    if not student_text or len(student_text.strip()) < 10:
        return 0, {
            "content_score": 0,
            "keyword_score": 0,
            "pronunciation_score": 0,
            "fluency_score": 0,
            "feedback": "Response too short or empty."
        }
    
    # 1. Content accuracy (0-40 points) - TF-IDF similarity
    content_similarity = tfidf_similarity(reference, student_text)
    content_score = content_similarity * 40
    
    # 2. Keyword coverage (0-30 points) - Higher weight for keywords in lecture
    keyword_coverage = calculate_keyword_coverage(keywords, student_text)
    keyword_score = keyword_coverage * 30
    
    # 3. Fluency/Pronunciation (0-20 points) - Placeholder / Word count proxy
    # Ideally should come from ASR confidence
    word_count = len(student_text.split())
    if word_count > 40:
        fluency_score = 20
    elif word_count > 20:
        fluency_score = 10
    else:
        fluency_score = 5
        
    # Total score (capped at 90)
    total_score = int(min(90, content_score + keyword_score + fluency_score))
    
    details = {
        "content_score": round(content_score, 1),
        "keyword_score": round(keyword_score, 1),
        "fluency_score": round(fluency_score, 1),
        "content_similarity": round(content_similarity * 100, 1),
        "keyword_coverage": round(keyword_coverage * 100, 1),
        "word_count": word_count
    }
    
    return total_score, details


def generate_feedback(score: int, details: Dict, keywords: List[str], student_text: str) -> str:
    """Generate human-readable feedback based on score and details."""
    feedback_parts = []
    
    # Overall performance
    if score >= 80:
        feedback_parts.append("Excellent summary! You captured the main points effectively.")
    elif score >= 65:
        feedback_parts.append("Good summary with most important details covered.")
    elif score >= 50:
        feedback_parts.append("Average summary. Try to include more key points.")
    else:
        feedback_parts.append("Your summary needs significant improvement.")
    
    # Content feedback
    if details.get("content_similarity", 0) < 40:
        feedback_parts.append("Focus on retelling the core message of the lecture.")
        
    # Keyword feedback
    missing_keywords = []
    student_lower = student_text.lower()
    for kw in keywords:
        if kw.lower() not in student_lower:
            missing_keywords.append(kw)
    
    if missing_keywords:
        feedback_parts.append(f"You missed some key terms: {', '.join(missing_keywords[:3])}.")
        
    return " ".join(feedback_parts)


def evaluate_lecture(lecture_id: str, student_text: str) -> Dict:
    """
    Main evaluation function for Retell Lecture.
    
    Args:
        lecture_id: ID of the lecture
        student_text: Student's transcribed summary
    
    Returns:
        Dictionary with score, feedback, and details
    """
    # Get lecture data
    lecture_data = get_lecture_by_id(lecture_id)
    if not lecture_data:
        return {
            "error": "Lecture not found",
            "score": 0
        }
    
    reference = lecture_data.get("transcript", "")
    keywords = lecture_data.get("keywords", [])
    
    # Calculate score
    score, details = calculate_score(reference, student_text, keywords)
    
    # Generate feedback
    feedback = generate_feedback(score, details, keywords, student_text)
    
    return {
        "score": score,
        "feedback": feedback,
        "details": details,
        "lecture_title": lecture_data.get("title", ""),
        "transcription": student_text,
        "reference": reference,
        "keywords": keywords
    }


if __name__ == "__main__":
    # Test the evaluator
    print("Testing Lecture Evaluator...")
    
    lec = get_random_lecture()
    if lec:
        print(f"\nLecture: {lec['title']}")
        print(f"Transcript: {lec['transcript'][:100]}...")
        
        # Test with a sample response
        sample_response = "The lecture talks about galaxies which are massive systems of stars held by gravity. The milky way is a spiral galaxy."
        result = evaluate_lecture(lec['id'], sample_response)
        
        print(f"\nScore: {result['score']}/90")
        print(f"Feedback: {result['feedback']}")
        print(f"Details: {result['details']}")
