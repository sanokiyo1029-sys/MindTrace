# MindTrace: Team Plan (24 hours)

## Team & roles

Everyone: open your task file, then read `docs/INTEGRATION.md`.

| Role | Member | Task file | Branch |
|---|---|---|---|
| Backend + integration (leader) | Rohan `@sanokiyo1029-sys` | [tasks/01_BACKEND.md](../tasks/01_BACKEND.md) | `feat/backend` |
| Frontend | Risheeth `@risheeth26233` | [tasks/02_FRONTEND.md](../tasks/02_FRONTEND.md) | `feat/frontend` |
| Research & development (AI module + prompting) | Samrudh `@SamrudhNandakumar` | [tasks/03_RESEARCH_PROMPTING.md](../tasks/03_RESEARCH_PROMPTING.md) | `feat/ai` |
| Presenter 1: lead speaker + deck | Sree Athira `@sreeathira06` | [tasks/04_PRESENTER_LEAD.md](../tasks/04_PRESENTER_LEAD.md) | `docs/pitch` |
| Presenter 2: demo operator + QA + backup speaker | Saniya `@ssaniyabi` | [tasks/05_PRESENTER_DEMO.md](../tasks/05_PRESENTER_DEMO.md) | `docs/demo` |

**Leader + integration owner:** Rohan. **Demo speaker:** Sree Athira. **Demo operator + backup speaker:** Saniya.

## Who owns which folder (prevents merge fights)

| Folder | Owner |
|---|---|
| `backend/` (except `backend/app/ai/`) | Rohan |
| `backend/app/ai/`, `prompts/`, `tests/fixtures/`, `docs/misconceptions/` | Samrudh |
| `frontend/` | Risheeth |
| `pitch/` | Sree Athira |
| `demo/`, `docs/DISCLOSURES.md` | Saniya |
| `docs/CONTRACTS.md` | Everyone, **by PR only** |

## AI tools (3 builders have ChatGPT Plus + Claude Code)

- **Claude Code:** multi-file work, wiring, debugging, reviewing a PR. Start each session with: *"Read AGENTS.md and docs/CONTRACTS.md, then do X in <my folder> only."*
- **Codex (comes with ChatGPT Plus):** small bounded jobs: one endpoint, one component, unit tests, fixtures.
- **ChatGPT chat:** quick questions, wording, slide text for presenters.
- Usage limits reset on rolling windows. **Don't burn them on boilerplate or retries.** Give the agent the exact file and acceptance check.
- One agent per folder at a time. **Commit before** letting an agent loose, so you can `git restore`.
- These subscriptions **do not include API keys** for the app itself. See `tasks/03_RESEARCH_PROMPTING.md` → "LLM for the app".
- Never paste keys, `.env`, or real student data into any chat.

## Timeline (H00 = event start; shift to the real schedule)

| Time | Backend | Frontend | Research | Presenters | Checkpoint |
|---|---|---|---|---|---|
| H00–H02 | FastAPI skeleton, SQLite models, `/health` | Vite app, routes, mock data from fixtures | Misconception library + 3 sample questions in fixtures | Read all docs, problem research, deck outline | Contracts frozen, everyone runs the app |
| H02–H05 | Sheet layout + PDF + QR printing | Lesson input, question editor + approve | `generate_questions` + validator, fixtures mode | Deck v1; buy/arrange printer, paper, pens | **M1:** approved quiz → 5 printed sheets |
| H05–H09 | QR decode + page align + OMR | Scanner page (camera + upload), progress | Prompt tests on 10 lessons, fix bad outputs | Fill 5–10 sheets with varied marks; QA scans with backend | **M2:** 5 phone scans → correct IDs + options |
| H09–H12 | Review + confirm + insights aggregation | Review queue + insights dashboard | `teaching_suggestion` + student-friendly text | Script v1, demo runbook | **M3:** verified answers → misconception card |
| H12–H15 | Follow-up, student login, HTTPS tunnel/deploy | Follow-up screen + student view | `followup_questions` + quality pass | Screenshots, Q&A prep | **M4:** full loop + student screen |
| H15–H18 | Edge cases: duplicates, blur, AI down | Error states, mobile polish | Edge-case fixtures, honesty wording | Record backup video of real flow | Failure states handled honestly |
| H18–H21 | Bug fixes only | Polish | README sections, disclosures | 3 full rehearsals with live scan | 3-min demo rehearsed |
| H21–H24 | **Freeze** at H21, tag `v1.0-demo` | Freeze | Freeze | Submission, final run | Submitted + backup ready |

**Stop rule:** if M2 (real scan → correct answers) isn't working by **H09**, everyone helps on that path or we switch to *assisted capture* (photo + QR + teacher taps the answers). No stretch features while the camera → insight path is broken.

## Stand-up every 3 hours (2 minutes each, in group chat)

```
Done:     <what works, with a screenshot or link>
Next:     <next 3 hours>
Blocker:  <what you need and from whom>
```

## Git workflow

```bash
git clone https://github.com/sanokiyo1029-sys/MindTrace.git
cd MindTrace
git checkout -b feat/<your-area>
# ...work...
git add -A && git commit -m "feat: short description"
git pull --rebase origin main
git push -u origin feat/<your-area>
```
Open a PR into `main`. Backend (integration owner) runs a smoke test and merges. **Small PRs every 2–3 hours**, not one giant merge at 3 a.m. After every merge: `git pull origin main`.

## Materials checklist

- [ ] Printer access + A4 paper (20+ sheets), dark pens/pencils
- [ ] One phone with a good rear camera (+ optional stand), good lighting
- [ ] Laptop + chargers + power bank + hotspot
- [ ] 5 fictional students (names + codes + PINs) in `tests/fixtures/roster.json`
- [ ] Backup: saved sample quiz, pre-filled sheets, screenshots, a video of the real flow
