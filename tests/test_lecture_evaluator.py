import api.lecture_evaluator as lecture_module


def test_get_lecture_categories_returns_values():
    categories = lecture_module.get_lecture_categories()
    assert isinstance(categories, list)
    assert categories
    assert all(item in {"easy", "medium", "difficult"} for item in categories)


def test_get_random_lecture_filters_by_difficulty():
    lecture = lecture_module.get_random_lecture(difficulty="easy")
    assert isinstance(lecture, dict)
    assert lecture.get("difficulty") == "easy"


def test_get_lecture_catalog_returns_items():
    catalog = lecture_module.get_lecture_catalog()
    assert isinstance(catalog, list)
    assert catalog
    first = catalog[0]
    assert "difficulty" in first
    assert "prompt_seconds_estimate" in first
    assert "prompt_word_count" in first
    assert first["prompt_seconds_estimate"] > 0
    assert first["prompt_word_count"] > 0


def test_runtime_config_defaults_are_valid():
    config = lecture_module.get_retell_lecture_runtime_config()
    assert config["prep_seconds"] > 0
    assert config["response_seconds"] > 0
    assert config["prompt_min_seconds"] <= config["prompt_max_seconds"]
    assert config["recommended_response_min_seconds"] <= config["recommended_response_max_seconds"]


def test_resolve_prompt_transcript_prefers_explicit_prompt():
    lecture_data = {
        "prompt_transcript": "Short prompt version.",
        "transcript": "Long full transcript should not be used.",
    }
    assert lecture_module.resolve_prompt_transcript(lecture_data) == "Short prompt version."


def test_evaluate_lecture_returns_enriched_fields(monkeypatch):
    monkeypatch.setattr(lecture_module, "get_semantic_model", lambda: None)
    monkeypatch.setattr(lecture_module, "compute_pronunciation_score", lambda _words: (72.0, 0.8))

    lecture = lecture_module.get_random_lecture(difficulty="easy")
    lecture_id = lecture["id"]
    response = (
        "The lecture explains that Gutenberg's printing press enabled mass production of books, "
        "increased literacy, and spread ideas during the Renaissance and Reformation."
    )
    result = lecture_module.evaluate_lecture(
        lecture_id,
        response,
        mfa_words=[{"status": "correct", "start": 0.0, "end": 20.0}],
        speech_duration_seconds=24.0,
    )

    assert isinstance(result, dict)
    assert "score" in result
    assert "details" in result
    assert "reference" in result
    assert "full_transcript" in result
    assert "example_response" in result
    assert result["prompt_duration_estimate_seconds"] > 0
    assert result["details"]["duration_seconds"] is not None


def test_calculate_score_applies_short_content_gate(monkeypatch):
    monkeypatch.setattr(lecture_module, "get_semantic_model", lambda: None)
    score, details = lecture_module.calculate_score(
        "This lecture discusses renewable energy and policy effects.",
        "too short",
        keywords=["renewable", "policy"],
        key_points=["renewable energy policy impact"],
        mfa_words=[],
    )
    assert score == 0
    assert details["content_gate"]["active"] is True
    assert details["content_gate"]["code"] == "too_short"
