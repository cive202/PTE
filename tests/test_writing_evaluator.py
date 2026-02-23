import api.writing_evaluator as writing_module


def test_get_swt_task_returns_prompt():
    task = writing_module.get_swt_task()
    assert isinstance(task, dict)
    for key in ("id", "title", "topic", "difficulty", "passage"):
        assert key in task


def test_get_swt_task_filters_by_difficulty():
    task = writing_module.get_swt_task(difficulty="difficult")
    assert isinstance(task, dict)
    assert task.get("difficulty") == "difficult"


def test_get_essay_task_filters_by_difficulty():
    task = writing_module.get_essay_task(difficulty="difficult")
    assert isinstance(task, dict)
    assert task.get("difficulty") == "difficult"


def test_get_email_task_filters_by_difficulty():
    task = writing_module.get_email_task(difficulty="difficult")
    assert isinstance(task, dict)
    assert task.get("difficulty") == "difficult"


def test_get_writing_catalog_returns_items():
    swt_catalog = writing_module.get_writing_catalog("summarize_written_text")
    essay_catalog = writing_module.get_writing_catalog("write_essay")
    email_catalog = writing_module.get_writing_catalog("write_email")
    assert swt_catalog and essay_catalog and email_catalog
    assert "difficulty" in swt_catalog[0]


def test_swt_form_gate_forces_total_zero_when_invalid(monkeypatch):
    monkeypatch.setattr(
        writing_module,
        "_fetch_grammar_matches",
        lambda _text, timeout=6.0: {"available": False, "matches": []},
    )

    passage = "Urban heat islands raise city temperatures and increase energy demand during heat waves."
    response = "Too short"
    result = writing_module.evaluate_summarize_written_text(passage, response, prompt_id="swt_x")

    assert result["scores"]["form"]["score"] == 0
    assert result["scores"]["total"]["score"] == 0


def test_write_essay_scoring_contract(monkeypatch):
    monkeypatch.setattr(
        writing_module,
        "_fetch_grammar_matches",
        lambda _text, timeout=6.0: {"available": True, "matches": []},
    )

    prompt = (
        "Governments are increasingly adopting artificial intelligence in public services "
        "such as transport, healthcare, and administration."
    )
    response = (
        "Artificial intelligence can improve efficiency in transport scheduling, hospital triage, and "
        "administrative workflows. However, public systems must address bias, privacy, and accountability. "
        "Therefore, governments should require clear governance standards, human oversight, and regular audits. "
        "For example, agencies can publish model performance reports and allow independent review. "
        "In conclusion, AI in public services can deliver benefits when implementation is transparent and controlled."
    )

    result = writing_module.evaluate_write_essay(prompt, response, prompt_id="essay_x")
    assert result["scores"]["total"]["max"] == 20
    assert "development_structure_coherence" in result["scores"]
    assert isinstance(result["feedback"], list)


def test_write_essay_off_topic_flag_caps_total(monkeypatch):
    monkeypatch.setattr(
        writing_module,
        "_fetch_grammar_matches",
        lambda _text, timeout=6.0: {"available": False, "matches": []},
    )

    prompt = "Discuss benefits and risks of remote work policies."
    response = (
        "Mountain rivers carry minerals from highland regions into wider valleys where farms depend on seasonal "
        "water flow. Local communities often build small channels to guide water toward terraces. During dry periods, "
        "storage ponds help reduce crop losses and support livestock. Traditional methods are now mixed with modern "
        "monitoring tools to improve water use and reduce waste over time. "
        "Mountain rivers carry minerals from highland regions into wider valleys where farms depend on seasonal "
        "water flow. Local communities often build small channels to guide water toward terraces. During dry periods, "
        "storage ponds help reduce crop losses and support livestock. Traditional methods are now mixed with modern "
        "monitoring tools to improve water use and reduce waste over time. "
        "Mountain rivers carry minerals from highland regions into wider valleys where farms depend on seasonal "
        "water flow. Local communities often build small channels to guide water toward terraces. During dry periods, "
        "storage ponds help reduce crop losses and support livestock. Traditional methods are now mixed with modern "
        "monitoring tools to improve water use and reduce waste over time."
    )

    result = writing_module.evaluate_write_essay(prompt, response, prompt_id="essay_y")
    assert result["analysis"]["off_topic_flag"] is True
    assert result["scores"]["total"]["score"] <= 6


def test_write_email_scoring_contract(monkeypatch):
    monkeypatch.setattr(
        writing_module,
        "_fetch_grammar_matches",
        lambda _text, timeout=6.0: {"available": True, "matches": []},
    )

    prompt = (
        "You missed a scheduled appointment at the student services office. "
        "Write an email to apologize, explain briefly, and request a new time."
    )
    response = (
        "Dear Student Services Team,\n"
        "I am writing to apologize for missing my appointment today due to a delayed train service. "
        "Could you please offer a new slot on Wednesday afternoon or Thursday morning? "
        "Thank you for your understanding.\n"
        "Kind regards,\n"
        "Alex"
    )

    result = writing_module.evaluate_write_email(prompt, response, prompt_id="email_x")
    assert result["scores"]["total"]["max"] == 13
    assert "formal_requirements" in result["scores"]
    assert "email_conventions" in result["scores"]
    assert isinstance(result["feedback"], list)


def test_write_email_gate_zeros_language_scores(monkeypatch):
    monkeypatch.setattr(
        writing_module,
        "_fetch_grammar_matches",
        lambda _text, timeout=6.0: {"available": True, "matches": []},
    )

    prompt = "Write an email to request annual leave for next Monday and Tuesday."
    response = "Need leave."
    result = writing_module.evaluate_write_email(prompt, response, prompt_id="email_y")

    assert result["analysis"]["gate_triggered"] is True
    assert result["scores"]["grammar"]["score"] == 0
    assert result["scores"]["vocabulary"]["score"] == 0
    assert result["scores"]["spelling"]["score"] == 0
