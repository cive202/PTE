import api.image_evaluator as image_evaluator


def test_describe_image_runtime_config_defaults(monkeypatch):
    monkeypatch.delenv("PTE_DI_PREP_SECONDS", raising=False)
    monkeypatch.delenv("PTE_DI_RESPONSE_SECONDS", raising=False)
    monkeypatch.delenv("PTE_DI_RECOMMENDED_MIN_SECONDS", raising=False)

    config = image_evaluator.get_describe_image_runtime_config()
    assert config["prep_seconds"] == 25
    assert config["response_seconds"] == 40
    assert config["recommended_response_min_seconds"] == 20
    assert config["recommended_response_max_seconds"] == 40


def test_describe_image_runtime_config_clamps_min_to_response(monkeypatch):
    monkeypatch.setenv("PTE_DI_RESPONSE_SECONDS", "30")
    monkeypatch.setenv("PTE_DI_RECOMMENDED_MIN_SECONDS", "45")

    config = image_evaluator.get_describe_image_runtime_config()
    assert config["response_seconds"] == 30
    assert config["recommended_response_min_seconds"] == 30


def test_calculate_score_gates_irrelevant_content():
    reference = "The bar chart shows quarterly sales from Q1 to Q4 rising from 45 to 92."
    keywords = ["bar chart", "quarterly", "sales", "Q1", "Q4", "rising"]
    student = "I enjoy traveling with friends and cooking new dishes every weekend."

    score, details = image_evaluator.calculate_score(reference, student, keywords, speech_duration_seconds=20)

    assert score == 0
    assert details["content_gate"]["active"] is True
    assert details["content_gate"]["code"] == "irrelevant"
    assert details["pronun_score"] == 0
    assert details["fluency_score"] == 0


def test_calculate_score_template_signal_does_not_gate_relevant_answer():
    reference = "The bar chart shows quarterly sales from Q1 to Q4 with an increasing trend."
    keywords = ["bar chart", "quarterly", "sales", "Q1", "Q2", "Q3", "Q4", "increasing trend"]
    student = (
        "At a fleeting glance, the given chart shows quarterly sales from Q1 to Q4. Overall it can be clearly seen that "
        "there is an increasing trend and Q4 is highest."
    )

    score, details = image_evaluator.calculate_score(reference, student, keywords, speech_duration_seconds=32)

    assert score > 0
    assert details["template_evidence"]["is_flagged"] is True
    assert details["content_gate"]["active"] is False


def test_calculate_score_duration_affects_fluency():
    reference = "The bar chart shows quarterly sales rising steadily from Q1 to Q4."
    keywords = ["bar chart", "quarterly", "sales", "Q1", "Q4", "rising"]
    student = "The bar chart shows quarterly sales from Q1 to Q4 and overall there is a rising trend."

    score_short, details_short = image_evaluator.calculate_score(
        reference, student, keywords, speech_duration_seconds=8
    )
    score_good, details_good = image_evaluator.calculate_score(
        reference, student, keywords, speech_duration_seconds=32
    )

    assert details_good["fluency_score"] > details_short["fluency_score"]
    assert score_good >= score_short
