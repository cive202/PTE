import api.listening_evaluator as listening_module


def test_get_listening_task_filters_by_difficulty():
    task = listening_module.get_listening_task("summarize_spoken_text", difficulty="easy")
    assert isinstance(task, dict)
    assert task.get("difficulty") == "easy"


def test_get_listening_catalog_returns_items():
    catalog = listening_module.get_listening_catalog("multiple_choice_multiple")
    assert isinstance(catalog, list)
    assert catalog
    assert "difficulty" in catalog[0]


def test_multiple_choice_multiple_applies_deduction_and_floor():
    result = listening_module.evaluate_multiple_choice_multiple(
        ["A", "C", "D"],
        ["A", "B", "D"],
        prompt_id="mcm_x",
    )

    assert result["task"] == "multiple_choice_multiple"
    assert result["scores"]["total"]["score"] == 1
    assert result["analysis"]["raw_score"] == 1

    floored = listening_module.evaluate_multiple_choice_multiple(
        ["A", "C"],
        ["B", "D"],
        prompt_id="mcm_y",
    )
    assert floored["scores"]["total"]["score"] == 0
    assert floored["analysis"]["raw_score"] == -2
    assert floored["analysis"]["minimum_zero_applied"] is True


def test_multiple_choice_single_uses_correct_incorrect_scoring():
    correct = listening_module.evaluate_multiple_choice_single(
        "B",
        "b",
        prompt_id="mcs_x",
    )
    assert correct["task"] == "multiple_choice_single"
    assert correct["scores"]["total"]["score"] == 1
    assert correct["analysis"]["is_correct"] is True

    incorrect = listening_module.evaluate_multiple_choice_single(
        "B",
        "A",
        prompt_id="mcs_y",
    )
    assert incorrect["scores"]["total"]["score"] == 0
    assert incorrect["analysis"]["is_correct"] is False


def test_select_missing_word_uses_correct_incorrect_scoring():
    result = listening_module.evaluate_select_missing_word(
        "D",
        "C",
        prompt_id="smw_x",
    )
    assert result["task"] == "select_missing_word"
    assert result["scores"]["total"]["score"] == 0
    assert result["analysis"]["correct_option"] == "D"
    assert result["analysis"]["selected_option"] == "C"


def test_fill_in_the_blanks_scores_per_blank():
    blanks = [
        {"id": "1", "answer": "ecosystems"},
        {"id": "2", "answer": "water"},
        {"id": "3", "answer": "biodiversity"},
    ]
    responses = {"1": "ecosystems", "2": "waters", "3": "biodiversity"}

    result = listening_module.evaluate_fill_in_the_blanks(blanks, responses, prompt_id="fib_x")
    assert result["task"] == "fill_in_the_blanks"
    assert result["scores"]["total"]["score"] == 2
    assert result["scores"]["total"]["max"] == 3


def test_sst_form_gate_zeros_scores(monkeypatch):
    monkeypatch.setattr(
        listening_module,
        "_fetch_grammar_matches",
        lambda _text, timeout=6.0: {"available": False, "matches": []},
    )

    transcript = (
        "The lecture explains how sustainable farming protects soil and water, "
        "supports biodiversity, and improves long-term food security."
    )
    response = "Too short."

    result = listening_module.evaluate_summarize_spoken_text(
        transcript,
        response,
        prompt_id="sst_x",
        key_points=["soil protection", "water conservation", "food security"],
    )

    assert result["task"] == "summarize_spoken_text"
    assert result["analysis"]["gate_reason"] == "form_out_of_range"
    assert result["scores"]["total"]["score"] == 0
