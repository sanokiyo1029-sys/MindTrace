"""Plain-Python aggregation: verified answers -> possible misconceptions with evidence. No AI here
except the teaching suggestion + follow-up question text, which come through ai_bridge."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from app import ai_bridge

UNCERTAINTY = ("A wrong option is evidence of an incorrect answer, not proof of the reasoning. "
               "Some students may have guessed.")


def build(assessment: dict, questions: list[dict], scans: list[dict], printed: int, needs_review: int,
          with_ai: bool = True) -> dict:
    lib = ai_bridge.misconception_library()
    verified = [s for s in scans if s["status"] == "accepted"]
    total = len(verified)
    q_stats = []
    per_mis = defaultdict(lambda: {"students": set(), "evidence": []})
    for q in questions:
        if q.get("type") == "descriptive":  # written answers: teacher-reviewed feedback, not bubble counts
            continue
        dist = {"A": 0, "B": 0, "C": 0, "D": 0, "blank": 0}
        chosen_by = defaultdict(set)
        for s in verified:
            a = next((x for x in s["answers"] if x["question_id"] == q["id"]), None)
            final = (a or {}).get("final") or "blank"
            dist[final if final in dist else "blank"] += 1
            if final in ("A", "B", "C", "D"):
                chosen_by[final].add(s["sheet_id"])
        q_stats.append({"question_id": q["id"], "correct": dist.get(q["answer"], 0), "total": total, "distribution": dist})
        for opt, sheets in chosen_by.items():
            if opt == q["answer"]:
                continue
            mid = ((q.get("distractors") or {}).get(opt) or {}).get("misconception_id")
            if not mid:
                continue
            per_mis[mid]["students"] |= sheets
            per_mis[mid]["evidence"].append({"question_id": q["id"], "option": opt, "count": len(sheets),
                                             "option_text": q["options"][opt], "stem": q["stem"]})

    ranked = sorted(per_mis.items(), key=lambda kv: len(kv[1]["students"]), reverse=True)
    cards = []
    for rank, (mid, info) in enumerate(ranked):
        ev = sorted(info["evidence"], key=lambda e: e["count"], reverse=True)
        top = ev[0]
        label = lib.get(mid, {}).get("label", mid)
        card = {
            "misconception_id": mid,
            "label": label,
            "status": "possible",
            "students_affected": len(info["students"]),
            "evidence": [{"question_id": e["question_id"], "option": e["option"], "count": e["count"]} for e in ev],
            "why_we_think_so": (f"{top['count']} of {total} students chose {top['option_text']} for "
                                f"“{top['stem']}”, which matches: {label.lower()}."),
            "uncertainty": UNCERTAINTY,
            "teaching_action": None,
            "followup_question": None,
        }
        cards.append(card)
    if with_ai and cards:  # only the top few get (possibly slow) AI calls, asked in parallel
        with ThreadPoolExecutor(max_workers=6) as pool:
            jobs = [(c, pool.submit(ai_bridge.teaching_suggestion, c["misconception_id"], c["evidence"]),
                     pool.submit(ai_bridge.followup_questions, [c["misconception_id"]], 1)) for c in cards[:3]]
        for c, teach, follow in jobs:
            c["teaching_action"] = teach.result()
            fq = follow.result()
            c["followup_question"] = fq[0] if fq else None
    used_ai = ai_bridge.ai_module_loaded() or any(
        (c["teaching_action"] or {}).get("source") == "ai" or (c["followup_question"] or {}).get("source") == "ai"
        for c in cards)

    caveats = ["Handwritten reasoning and written answers aren't counted here; review them under Student feedback."]
    missing = max(printed - total, 0)
    if missing:
        caveats.append(f"{missing} printed paper(s) not scanned yet")
    if any(q.get("source") == "sample" for q in questions):
        caveats.append("Questions came from the saved sample set")
    return {
        "assessment_id": assessment["id"],
        "papers": {"printed": printed, "verified": total, "needs_review": needs_review, "missing": missing},
        "questions": q_stats,
        "misconceptions": cards,
        "caveats": caveats,
        "generated_by": "rules+ai" if used_ai else "rules+samples",
    }
