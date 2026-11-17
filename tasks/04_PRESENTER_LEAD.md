# Task: Presenter 1 (Lead Speaker + Pitch Deck)

**Owner:** `@________` · **Branch:** `docs/pitch` · **Folder:** `pitch/`
You are the **voice of MindTrace**. You present the problem, the story and the impact, and you handle judges' questions. Presenter 2 runs the live demo next to you and is your backup speaker.

Read first: `docs/PROBLEM_STATEMENT.md` (memorise the one-liner), `docs/TEAM_PLAN.md`. Skim `docs/CONTRACTS.md` §8 so you understand the insight report.

## P1 · Understand it (H00–H02)
- [ ] Read the problem statement until you can explain MindTrace in **20 seconds** without notes
- [ ] Ask each builder: "What will definitely work? What might not?" Write the answers in `pitch/notes.md`
- [ ] Confirm the event rules with the organisers: presentation length, slide format, submission deadline, repo public/private, video needed? Post the answers in the group chat

## P2 · Problem research (H01–H04)
- [ ] Find 2–3 **real, cited** facts that support the problem (class sizes, time teachers spend on assessment, common fraction misconceptions, device access in schools). Use reliable sources (government reports, UDISE+, ASER, NCERT, research papers). **Write the link next to every number** in `pitch/sources.md`. No made-up stats; judges check.
- [ ] Talk to 1–2 real teachers if you can (even a 5-minute call). One real quote beats any stat.

## P3 · Deck (H03–H09), 8–10 slides max
Use Canva / Google Slides / PowerPoint, whatever you're fastest in. Save the export to `pitch/MindTrace_deck.pdf`.

| # | Slide | Content |
|---|---|---|
| 1 | Title | MindTrace: *Trace the thinking behind every wrong answer* · team names · STEM for Impact 2026 |
| 2 | Problem | "The class scored 50%. **Which misconception caused it?**" + 1 cited fact |
| 3 | Who it hurts | Teacher with 30+ papers, no time; students without devices |
| 4 | Solution | 7-step loop: Lesson → Generate → Print → Answer on paper → Scan → Insight → Retest |
| 5 | **Live demo** | (switch to Presenter 2's screen) |
| 6 | How it works | Simple architecture: phone → FastAPI → QR + OMR → AI misconception tags → report |
| 7 | Why trust it | Teacher approves questions, uncertain scans go to review, "possible" not "proven", evidence shown |
| 8 | Impact | Teacher time saved, paper-friendly access, re-teach the right thing, works for any STEM topic |
| 9 | What's next | Handwriting analysis, Kannada/regional languages, offline mode, classroom pilot |
| 10 | Thank you | Repo link, team |

Design: big text, one idea per slide, real screenshots from the app (get them from Presenter 2 after H12).

## P4 · Script (H09–H15)
Write `pitch/script.md`, timed for **3 minutes** (adjust to the real slot):

| Time | Who | What |
|---|---|---|
| 0:00–0:25 | You | Problem hook: "A teacher knows the class scored 50%, but not *why*." |
| 0:25–0:50 | You + P2 | Teacher pastes today's concepts → 3 questions appear → edit one → approve → PDF |
| 0:50–1:35 | P2 | Hand a fresh sheet to a judge/teammate to fill → scan it live on the phone → student code + answers appear |
| 1:35–2:15 | You | Insight: most common possible misconception, evidence ("3 of 5 chose 2/6"), why we think so |
| 2:15–2:45 | You | Action: 5-minute fraction-strip activity + new follow-up question |
| 2:45–3:00 | You | Impact line: "Students stay on paper. Teachers get evidence to plan the next lesson." |

## P5 · Q&A prep (H12–H18)
Write `pitch/qna.md` with short, honest answers. Practise them out loud:
- **Why paper?** No student devices needed; quick classroom checks. Trade-off: needs a printer and the teacher's phone.
- **Isn't this just a quiz app?** A quiz app says *who* was wrong. We say *what the class probably misunderstood, why, what to teach next, and whether it worked.*
- **What if the AI is wrong?** Teacher approves every question; maths is checked in code; reports say "possible" and show the evidence.
- **What if the scan is wrong?** QR identifies the sheet (no name-reading); unclear marks go to the teacher's review; we never force a guess.
- **How is this different from Plickers / GuruGraph?** Plickers counts card answers; GuruGraph-style tools diagnose reasoning. We join paper scanning + misconception diagnosis + teaching action + retest in one teacher loop.
- **Privacy?** QR has no personal data; fictional names in the demo; students see only their own results.
- **What would you build next / how does it scale?** See slide 9. Any STEM topic just needs a misconception library.
- **What did AI help you build?** Be honest; see `docs/DISCLOSURES.md`.

## P6 · Rehearse (H18–H21)
- [ ] 3 full run-throughs with Presenter 2 and a **live scan** every time, timed
- [ ] One run where you pretend Wi-Fi died → switch to backup video/screenshots smoothly
- [ ] Final deck PDF in `pitch/`, link in README

## Rules
- Never claim something works if it doesn't. "This part is a prototype" is fine. Getting caught faking isn't.
- Never say "weak student". Say "students who may have this misconception".
- Use ChatGPT for wording and slide text, but every fact needs a real source you opened.
