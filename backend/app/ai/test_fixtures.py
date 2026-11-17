import json
from pathlib import Path

from app import ai_bridge
from app.ai import (
    followup_questions,
    generate_questions,
    teaching_suggestion,
    validate_question,
)


def test_fixture_entry_points():
    questions = generate_questions("fractions", "Add and compare fractions", 5, "7")
    assert len(questions) == 5
    assert all(q["status"] == "draft" and q["source"] == "sample" for q in questions)
    assert all(validate_question(q) == [] for q in questions)

    misconception = "M_ADD_DENOMS"
    activity = teaching_suggestion(misconception, [])
    assert activity["minutes"] == 5
    assert 3 <= len(activity["steps"]) <= 5

    (followup,) = followup_questions([misconception], 1)
    assert followup["status"] == "draft"
    assert followup["stem"] not in {q["stem"] for q in questions}
    assert misconception in {tag["misconception_id"] for tag in followup["distractors"].values()}


def test_mock_responses_reference_the_frozen_quiz():
    fixtures = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
    samples = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in fixtures.glob("*.json")
    }
    quiz = samples["questions_sample"]
    assessment = samples["assessment_sample"]
    scan = samples["scan_result_sample"]
    insights = samples["insights_sample"]
    results = samples["student_results_sample"]["assessments"][0]
    question_ids = [q["id"] for q in quiz]

    assert len(quiz) == 3 and all(q["status"] == "approved" for q in quiz)
    assert assessment["questions"] == quiz
    assert assessment["id"] == insights["assessment_id"] == results["assessment_id"]
    assert all(q["assessment_id"] == assessment["id"] for q in quiz)
    for rows in (scan["answers"], insights["questions"], results["answers"]):
        assert [row["question_id"] for row in rows] == question_ids

    for name in ("questions_sample", "questions_extra_sample", "followup_questions_sample"):
        for question in samples[name]:
            assert ai_bridge.validate_question(question) == [], question["stem"]
