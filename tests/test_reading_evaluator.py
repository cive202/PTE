import api.reading_evaluator as reading_module


def test_get_reading_task_filters_by_difficulty():
    task = reading_module.get_reading_task("multiple_choice_multiple", difficulty="easy")
    assert isinstance(task, dict)
    assert task.get("difficulty") == "easy"


def test_get_reading_catalog_returns_items():
    catalog = reading_module.get_reading_catalog("multiple_choice_single")
    assert isinstance(catalog, list)
    assert catalog
    assert "difficulty" in catalog[0]


def test_reading_multiple_choice_multiple_applies_deduction_and_floor():
    result = reading_module.evaluate_multiple_choice_multiple(
        ["A", "C", "D"],
        ["A", "B", "D"],
        prompt_id="rmcm_x",
    )

    assert result["task"] == "multiple_choice_multiple"
    assert result["scores"]["total"]["score"] == 1
    assert result["analysis"]["raw_score"] == 1

    floored = reading_module.evaluate_multiple_choice_multiple(
        ["A", "C"],
        ["B", "D"],
        prompt_id="rmcm_y",
    )
    assert floored["scores"]["total"]["score"] == 0
    assert floored["analysis"]["raw_score"] == -2
    assert floored["analysis"]["minimum_zero_applied"] is True


def test_reading_multiple_choice_single_correct_incorrect():
    correct = reading_module.evaluate_multiple_choice_single("B", "B", prompt_id="rmcs_x")
    assert correct["task"] == "multiple_choice_single"
    assert correct["scores"]["total"]["score"] == 1

    incorrect = reading_module.evaluate_multiple_choice_single("B", "A", prompt_id="rmcs_y")
    assert incorrect["scores"]["total"]["score"] == 0


def test_reading_fill_in_the_blanks_dropdown_scores_per_blank():
    blanks = [
        {"id": "1", "answer": "barriers"},
        {"id": "2", "answer": "marine"},
        {"id": "3", "answer": "participate"},
    ]
    responses = {"1": "barriers", "2": "domestic", "3": "participate"}

    result = reading_module.evaluate_fill_in_the_blanks_dropdown(blanks, responses, prompt_id="rfibd_x")
    assert result["task"] == "fill_in_the_blanks_dropdown"
    assert result["scores"]["total"]["score"] == 2
    assert result["scores"]["total"]["max"] == 3
