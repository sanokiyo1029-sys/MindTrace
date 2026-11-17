# MindTrace: Domain & Problem Statement

**Event:** STEM for Impact 2026, 24-hour hackathon
**Project:** MindTrace (formerly the "ClassPulse" working plan)
**Tagline:** *Trace the thinking behind every wrong answer.*

---

## Domain

**Education Technology (EdTech): AI for STEM classroom assessment**

- Sub-domain: formative assessment and learning analytics
- Users: school STEM teachers (primary), students (secondary)
- Demo subject: Mathematics, Class 7 **fractions**

> If the event gives a fixed list of tracks, pick the closest one (usually *Education*, *EdTech*, *AI for Social Good* or *STEM Education*) and keep this sub-domain line as the description.

---

## Problem statement (submission version)

> In STEM classrooms, teachers can mark a paper quiz right or wrong, but with a class of 30 or more students they rarely have time to find out **why** many students picked the same wrong answer. Paper is still the most accessible way to test students who don't have their own devices, yet the reasoning behind repeated mistakes is lost once the marks are added up. So the next lesson either re-teaches everything or moves on with the misconception still in place.
>
> Teachers need a fast, trustworthy way to turn a short paper quiz into **class-wide evidence of what students may have misunderstood** and a **concrete next teaching step**, without giving students devices and without taking decisions away from the teacher.

### One-line version (for slides and forms)

> Teachers see scores, not thinking. MindTrace turns a printed STEM quiz, scanned with one phone, into a map of what the class likely misunderstood and what to teach next.

---

## Proposed solution (short)

1. **Enter lesson.** The teacher types or pastes the concepts taught today.
2. **Generate.** MindTrace drafts 1–5 MCQs. Every wrong option is tagged with the misconception it usually signals. The teacher edits and approves.
3. **Print.** Each student gets an A4 sheet with a random QR sheet ID, answer bubbles and a "why did you choose this?" box.
4. **Answer on paper.** Students need no phone, no login and no internet.
5. **Scan.** The teacher scans the sheets with one phone. QR identifies the sheet, OMR reads the bubbles, and unclear marks go to a review queue.
6. **Insight.** The class report shows the most common *possible* misconceptions, the evidence behind each, a 5-minute corrective activity and a fresh follow-up question.
7. **Retest.** The follow-up quiz shows whether the class improved.

## Why it matters (impact)

- **Teacher time:** turns a pile of papers into a prioritised "what to re-teach" list.
- **Access:** students stay on paper, so it works in classrooms without student devices.
- **Better teaching:** links an observed mistake to a specific action, then checks whether that action worked.
- **Scales across STEM:** fractions today; the same flow works for science, physics and coding concepts.

## What makes it different from a quiz app

A quiz app tells you **who got it wrong**. MindTrace tells you **what the class probably misunderstood, why we think so, what to do next, and whether it worked**, and it does this from paper.

## Honesty rules (we say these out loud)

- A wrong option is **evidence**, not proof, of a misconception. Reports say *"possible"* and show the source answers.
- Handwriting analysis is optional. If OCR is off or unreadable, we say so.
- The teacher approves every question and confirms uncertain scans.
- Prior art exists (Plickers-style card scanning, GuruGraph-style reasoning diagnosis). Our contribution is the full **paper → evidence → teaching action → retest** loop for teachers.

## MVP scope (frozen)

| In | Not in the 24 hours |
|---|---|
| 1 topic (fractions), 3 questions, 5 fictional students | Multi-agent orchestration |
| Real printed sheets + real phone scans | Full handwriting maths solving |
| Teacher review of unclear marks | Admin / school portals |
| Class insight + teaching action + follow-up question | Production-quality regional languages |
| Student view (ID + PIN), own results only | Long-term knowledge graph |
