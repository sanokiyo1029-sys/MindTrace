"""Fixture-backed implementation of the shared MindTrace AI interface."""

import json
from pathlib import Path

__all__ = [
    "generate_questions",
    "validate_question",
    "teaching_suggestion",
    "followup_questions",
]

_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def _read_fixture(name: str):
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def generate_questions(topic: str, concepts_text: str, n: int, grade: str) -> list[dict]:
    if n <= 0:
        return []
    questions = _read_fixture("questions_sample.json")
    if n > len(questions):
        questions.extend(_read_fixture("questions_extra_sample.json"))
    return [dict(question, status="draft") for question in questions[:n]]


def validate_question(q: dict) -> list[str]:
    """Report no additional errors for R1. The backend bridge runs validation."""
    return []


def teaching_suggestion(misconception_id: str, evidence: list[dict]) -> dict:
    for entry in _read_fixture("misconceptions_fractions.json"):
        if entry["id"] == misconception_id:
            return entry["teaching_activity"]
    return {
        "title": "Explain a worked example",
        "minutes": 5,
        "steps": [
            "Draw a model of a problem on the board.",
            "Ask students to explain how they would find the answer.",
            "Check their reasoning with a second example.",
        ],
    }


def followup_questions(misconception_ids: list[str], n: int) -> list[dict]:
    if n <= 0:
        return []
    questions = _read_fixture("followup_questions_sample.json")
    requested = set(misconception_ids)
    selected = [
        question for question in questions
        if any(tag["misconception_id"] in requested for tag in question["distractors"].values())
    ]
    return (selected or questions[:1])[:n]
