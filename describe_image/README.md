# Describe Image Evaluator

This module implements the evaluation pipeline for the PTE "Describe Image" task.

## Features

1.  **ASR**: Uses `openai-whisper` (Medium model) to transcribe student speech.
2.  **Grammar**: Uses `language-tool-python` to detect grammar errors.
3.  **Fluency & Pronunciation**: Uses **MFA** (Montreal Forced Aligner) to align the transcript with the audio, providing precise timing metrics (pauses, speech rate) and acoustic pronunciation scores.
4.  **Content**: Generates a detailed prompt for an LLM (e.g., GPT-4) to evaluate the content against a provided image schema.

## Dependencies

Ensure you have installed the requirements:

```bash
pip install -r requirements.txt
```

And have MFA installed (if using local MFA) or Docker running (if using Dockerized MFA).

## Usage

```python
from describe_image.evaluator import DescribeImageEvaluator

evaluator = DescribeImageEvaluator()

# Define the image schema (what the student should describe)
image_schema = {
    "image_type": "bar_chart",
    "description": "The bar chart shows sales trends...",
    "key_points": [
        "Highest sales in 2020",
        "Steady increase",
        "Comparison between categories"
    ]
}

# Run evaluation
result = evaluator.evaluate("path/to/audio.wav", image_schema)

# Access results
print("Transcript:", result["transcript"])
print("Grammar Issues:", result["grammar_issues"])
print("Algorithmic Scores:", result["algorithmic_scores"])
print("LLM Evaluation:", result["llm_evaluation"])
```

## Configuration

- **ASR Model**: Defaults to "medium". Can be changed in `evaluator.py` or `asr.py`.
- **LLM**: The `call_llm` method in `evaluator.py` is currently a mock. You need to integrate your preferred LLM API (OpenAI, Gemini, etc.) there.
