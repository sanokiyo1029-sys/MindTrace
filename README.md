# MindTrace

**Trace the thinking behind every wrong answer.**
STEM for Impact 2026 · 24-hour hackathon · Domain: **EdTech: AI for STEM classroom assessment**

> Teachers see scores, not thinking. MindTrace turns a printed STEM quiz, scanned with one phone, into a map of what the class likely misunderstood and what to teach next.

**Status:** being built at the event. This README lists only what actually works. See [What works](#what-works).

---

## Problem

In STEM classrooms, teachers can mark a paper quiz right or wrong, but with 30+ students they rarely have time to find out **why** many students picked the same wrong answer. Paper is still the most accessible format for students without devices, yet the reasoning behind repeated mistakes is lost once marks are added up. → Full statement: [docs/PROBLEM_STATEMENT.md](docs/PROBLEM_STATEMENT.md)

## How it works

```
Teacher types concepts → AI drafts MCQs (each wrong option = a known misconception) → teacher approves
→ identical A4 papers, roll number written at the top → students answer on paper → teacher scans with one phone
→ Gemini reads the roll number and marks → teacher confirms each paper → class report: possible misconceptions,
  evidence, a 5-minute teaching activity → follow-up quiz to check improvement
```

| Part | Tech |
|---|---|
| Web app (teacher + student, mobile scanner) | React + Vite |
| API | Python · FastAPI · SQLite |
| Printable papers | ReportLab (roll-number boxes, no QR) |
| Scanning | Gemini (roll number + marks, JSON schema) + OpenCV bubble reader as cross-check / fallback |
| AI | LLM for question drafting, teaching suggestions, follow-ups (with an offline fixtures mode) |

## Team

| Role | Member | Task file |
|---|---|---|
| Backend + integration (leader) | Rohan ([@sanokiyo1029-sys](https://github.com/sanokiyo1029-sys)) | [tasks/01_BACKEND.md](tasks/01_BACKEND.md) |
| Frontend | Risheeth ([@risheeth26233](https://github.com/risheeth26233)) | [tasks/02_FRONTEND.md](tasks/02_FRONTEND.md) |
| Research & development (AI + prompting) | Samrudh ([@SamrudhNandakumar](https://github.com/SamrudhNandakumar)) | [tasks/03_RESEARCH_PROMPTING.md](tasks/03_RESEARCH_PROMPTING.md) |
| Presenter: lead speaker + deck | Sree Athira ([@sreeathira06](https://github.com/sreeathira06)) | [tasks/04_PRESENTER_LEAD.md](tasks/04_PRESENTER_LEAD.md) |
| Presenter: live demo + QA + backup speaker | Saniya ([@ssaniyabi](https://github.com/ssaniyabi)) | [tasks/05_PRESENTER_DEMO.md](tasks/05_PRESENTER_DEMO.md) |

Plan, timeline and git workflow: [docs/TEAM_PLAN.md](docs/TEAM_PLAN.md) · How the parts combine: [docs/INTEGRATION.md](docs/INTEGRATION.md) · Shared JSON/API contracts: [docs/CONTRACTS.md](docs/CONTRACTS.md)

## Repo layout

```
backend/     FastAPI, DB, PDF, scanner, insights   (backend/app/ai/ = AI module)
frontend/    React app: teacher screens, phone scanner, student view
prompts/     LLM prompts + prompt test results
tests/       fixtures (sample JSON, roster), API tests, sample scans
docs/        problem statement, contracts, team plan, disclosures
tasks/       one task file per team member
pitch/       deck, script, Q&A, sources
demo/        runbook, test pack ground truth, scan log, backup video link
```

## Run it locally

```bash
cp .env.example .env

# backend (http://localhost:8000/docs)
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# demo login: teacher@mindtrace.demo / demo1234

# frontend
cd frontend && npm install && npm run dev
```

## What works

_Update honestly before submission._

- [ ] Teacher creates and approves a quiz
- [ ] Printable roll-number papers
- [ ] Live phone scan → correct sheet + answers
- [ ] Review of unclear marks
- [ ] Class misconception report + teaching activity
- [ ] Follow-up quiz
- [ ] Student view (own results only)

## Known limitations

- A wrong option is evidence, not proof, of a misconception. Reports say "possible".
- Handwriting analysis is optional/off unless stated.
- Needs a printer and a teacher phone. Camera needs HTTPS.
- Demo uses fictional students only.

## Disclosures & prior art

AI-assisted development and reused ideas are listed in [docs/DISCLOSURES.md](docs/DISCLOSURES.md).
Related work: [Plickers](https://help.plickers.com/hc/en-us/articles/360009395854-What-is-Plickers) (card scanning), [GuruGraph](https://github.com/samarthputhraya/gurugraph) (reasoning-first diagnosis). MindTrace joins paper scanning, misconception diagnosis, a teaching action and a retest into one teacher workflow.
