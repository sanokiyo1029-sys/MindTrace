"""Gemini path of ai_bridge with Gemini's HTTP replies faked (no key or network needed)."""
import json

import httpx
import pytest

from app import ai_bridge, config, gemini


def test_lens_only_client_disables_server_gemini(client, monkeypatch):
    monkeypatch.setattr(config, "AI_MODE", "live")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    assert client.get("/api/health").json()["gemini"] is True
    lens = client.get("/api/health", headers={"X-MindTrace-Mode": "lens-only"}).json()
    assert lens["gemini"] is False and lens["ai_provider"] == "samples"
    assert client.get("/api/health").json()["gemini"] is True

GOOD = [
    {"concept": "adding equal denominators", "stem": "What is 1/4 + 2/4?", "answer": "B", "difficulty": "easy",
     "options": {"A": "3/8", "B": "3/4", "C": "2/16", "D": "1/4"}, "explanation": "Keep the quarters: 1 + 2 = 3 quarters.",
     "distractors": [{"option": "A", "misconception_id": "M_ADD_DENOMS", "why": "Added the bottoms"},
                     {"option": "C", "misconception_id": "M_MULTIPLY_INSTEAD", "why": "Multiplied"},
                     {"option": "D", "misconception_id": "M_IGNORE_SECOND", "why": "Ignored 2/4"}]},
    {"concept": "adding equal denominators", "stem": "What is 2/7 + 3/7?", "answer": "C", "difficulty": "easy",
     "options": {"A": "5/14", "B": "6/49", "C": "5/7", "D": "2/7"}, "explanation": "Sevenths stay sevenths: 2 + 3 = 5.",
     "distractors": [{"option": "A", "misconception_id": "M_ADD_DENOMS", "why": "Added the bottoms"},
                     {"option": "B", "misconception_id": "M_MULTIPLY_INSTEAD", "why": "Multiplied"},
                     {"option": "D", "misconception_id": "M_IGNORE_SECOND", "why": "Ignored 3/7"}]},
]
BAD = {**GOOD[0], "stem": "What is 1/5 + 2/5?", "answer": "A",  # answer key is wrong on purpose
       "options": {"A": "3/10", "B": "3/5", "C": "2/25", "D": "1/5"}}
ACTIVITY = {"title": "Fold and count", "minutes": 5, "steps": ["Fold a strip into fifths.", "Shade 1/5 then 2/5.", "Count the shaded fifths."]}


def reply(obj=None, status=200):
    body = ({"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}, "finishReason": "STOP"}]}
            if status == 200 else {"error": {"code": status, "message": "slow down", "status": "RESOURCE_EXHAUSTED"}})
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://gemini.test"))


@pytest.fixture
def live(monkeypatch):
    """Turn Gemini on with a fake key; record calls; replies come from the list the test sets."""
    monkeypatch.setattr(config, "AI_MODE", "live")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(gemini, "_cooldown_until", 0.0)
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)
    monkeypatch.setattr(ai_bridge, "_cache", {})
    state = {"replies": [], "calls": []}

    def fake_post(url, body, timeout=None):
        state["calls"].append(body)
        r = state["replies"].pop(0) if len(state["replies"]) > 1 else state["replies"][0]
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(gemini, "_post", fake_post)
    return state


def test_generate_uses_gemini_and_passes_checks(live):
    live["replies"] = [reply({"questions": GOOD})]
    qs, note = ai_bridge.generate_questions("fractions", "adding fractions", 2, "7")
    assert note is None and [q["source"] for q in qs] == ["ai", "ai"]
    assert all(ai_bridge.validate_question(q) == [] for q in qs)
    assert qs[0]["distractors"]["A"]["misconception_id"] == "M_ADD_DENOMS"
    assert live["calls"][0]["generationConfig"]["responseMimeType"] == "application/json"


def test_bad_draft_is_repaired_then_topped_up_with_labelled_sample(live):
    live["replies"] = [reply({"questions": [GOOD[0], BAD]}), reply({"questions": [BAD]})]
    qs, note = ai_bridge.generate_questions("fractions", "adding fractions", 2, "7")
    assert len(live["calls"]) == 2 and "Answer key looks wrong" in json.dumps(live["calls"][1])
    assert [q["source"] for q in qs] == ["ai", "sample"]
    assert "Gemini drafted 1 of 2" in note


def test_rate_limit_falls_back_and_cools_down(live):
    live["replies"] = [reply(status=429)]
    qs, note = ai_bridge.generate_questions("fractions", "x", 2, "7")
    assert {q["source"] for q in qs} == {"sample"} and "busy" in note and "saved sample" in note
    assert len(live["calls"]) == gemini.MAX_ATTEMPTS
    ai_bridge.generate_questions("fractions", "x", 2, "7")  # during cooldown: no new calls
    assert len(live["calls"]) == gemini.MAX_ATTEMPTS


def test_timeout_and_bad_key_fall_back_with_a_reason(live):
    live["replies"] = [httpx.ReadTimeout("slow")]
    _, note = ai_bridge.generate_questions("fractions", "x", 1, "7")
    assert "too long" in note
    live["replies"] = [httpx.Response(400, json={"error": {"message": "API key not valid"}}, request=httpx.Request("POST", "https://g"))]
    _, note = ai_bridge.generate_questions("fractions", "x", 1, "7")
    assert "GEMINI_API_KEY" in note


def test_teaching_suggestion_is_cached_and_checked(live):
    live["replies"] = [reply(ACTIVITY)]
    ev = [{"question_id": "q1", "option": "A", "count": 3}]
    a = ai_bridge.teaching_suggestion("M_ADD_DENOMS", ev)
    b = ai_bridge.teaching_suggestion("M_ADD_DENOMS", ev)
    assert a == b and a["source"] == "ai" and len(live["calls"]) == 1
    live["replies"] = [reply({"title": "x", "minutes": 5, "steps": ["only one"]})]
    assert ai_bridge.teaching_suggestion("M_GAP_THINKING", ev)["source"] == "sample"


def test_off_by_default_uses_labelled_samples():
    assert not gemini.enabled() and ai_bridge.provider() == "samples"
    qs, note = ai_bridge.generate_questions("fractions", "x", 2, "7")
    assert {q["source"] for q in qs} == {"sample"} and "sample" in note


def test_generate_route_with_gemini(client, live):
    live["replies"] = [reply({"questions": GOOD})]
    tok = client.post("/api/auth/teacher/login", json={"email": "teacher@mindtrace.demo", "password": "demo1234"}).json()["token"]
    a = client.post("/api/assessments/generate", headers={"Authorization": f"Bearer {tok}"},
                    json={"class_id": "cl_7a", "topic": "fractions", "concepts_text": "adding", "num_questions": 2}).json()
    assert a["notes"] == [] and [q["source"] for q in a["questions"]] == ["ai", "ai"]
    assert all(q["validation_errors"] == [] for q in a["questions"])
    assert client.get("/api/health").json()["ai_provider"] == "gemini"
