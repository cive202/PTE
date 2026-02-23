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
    assert "difficulty" in catalog[0]
