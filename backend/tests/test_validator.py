from app import ai_bridge, demo_data


def test_sample_questions_are_valid():
    for q in demo_data.QUESTIONS + list(demo_data.FOLLOWUPS.values()):
        assert ai_bridge.validate_question(q) == [], q["stem"]


def test_wrong_key_and_duplicate_correct_option():
    q = dict(demo_data.QUESTIONS[0], answer="A")
    assert any("Answer key looks wrong" in e for e in ai_bridge.validate_question(q))
    q = dict(demo_data.QUESTIONS[0], options={"A": "2/3", "B": "2/3", "C": "1/9", "D": "4/6"})
    errs = ai_bridge.validate_question(q)
    assert any("same" in e for e in errs) or any("also correct" in e for e in errs)
