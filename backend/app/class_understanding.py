"""Teacher dashboard evidence from reviewed multiple-choice answers."""
from app import marking


def add_assessment(concepts, results, assessment, questions, scans, students_by_sheet, library):
    if assessment.status == "draft":
        return

    scored = {}
    seen = set()
    for qid, question in questions.items():
        name = question.get("concept") or assessment.topic
        concept = concepts.setdefault(name, {"name": name, "topic": assessment.topic, "assessment_ids": [], "mistakes": {}})
        if name not in seen:
            concept["assessment_ids"].append(assessment.id)
            seen.add(name)
        if not marking.written(question) and question.get("answer") in ("A", "B", "C", "D"):
            scored[qid] = (name, question)

    distributions = {qid: {} for qid in scored}
    for scan in scans:
        student_id = students_by_sheet.get(scan.sheet_id)
        if student_id is None:
            continue
        by_concept = {}
        for qid, final in {answer["question_id"]: answer.get("final") for answer in scan.answers}.items():
            if qid not in scored or final not in ("A", "B", "C", "D", "blank"):
                continue
            name, question = scored[qid]
            record = by_concept.setdefault(name, {"assessment_id": assessment.id, "student_id": student_id,
                                                  "concept": name, "correct": 0, "answered": 0})
            record["correct"] += final == question["answer"]
            record["answered"] += 1
            counts = distributions[qid]
            counts[final] = counts.get(final, 0) + 1
        results.extend(by_concept.values())

    for qid, (name, question) in scored.items():
        options = question.get("options") or {}
        counts = distributions[qid]
        answered = sum(counts.values())
        if not answered:
            continue
        for choice in (*options, "blank"):
            if choice == question["answer"]:
                continue
            distractor = (question.get("distractors") or {}).get(choice) or {}
            label = library.get(distractor.get("misconception_id"), {}).get("label")
            chosen = options.get(choice, "Left blank" if choice == "blank" else choice)
            expected = options.get(question["answer"], question["answer"])
            stem = question.get("stem", "")
            mistake = concepts[name]["mistakes"].setdefault((stem, chosen, expected, label), {
                "question_id": qid, "stem": stem, "choice": chosen, "expected": expected,
                "count": 0, "answered": 0, "possible_misconception": label,
            })
            mistake["count"] += counts.get(choice, 0)
            mistake["answered"] += answered
