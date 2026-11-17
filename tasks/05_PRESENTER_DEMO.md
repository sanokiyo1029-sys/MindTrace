# Task: Presenter 2 (Live Demo Operator + Physical QA + Backup Speaker)

**Owner:** Saniya (`@ssaniyabi`) · **Branch:** `docs/demo` · **Folder:** `demo/`
You make sure the **live demo works in front of judges**. You run the phone and laptop during the pitch, own all physical materials, test the scanner with real paper, and can give the whole pitch if Presenter 1 can't.

Read first: `docs/PROBLEM_STATEMENT.md`, `docs/TEAM_PLAN.md`, and the scanner section of `tasks/01_BACKEND.md` (B4). **How your part plugs into the others: `docs/INTEGRATION.md`.**

## D1 · Materials (H00–H03)
- [ ] Confirm printer access (where, who, how to print from a laptop/phone). Test print anything
- [ ] Get: 20+ A4 sheets, 3–4 dark pens + pencils, an eraser, a phone stand or a stack of books, a desk lamp if the room is dim
- [ ] Phone with a good rear camera, charged, + power bank + hotspot
- [ ] Fill the materials checklist in `docs/TEAM_PLAN.md` and tick it off

## D2 · Scanner test pack (H05–H12) ← backend depends on you
Once backend prints sheets (milestone M1), make a **physical test pack** and keep it in a folder:
- [ ] 5 clean sheets, one per student, filled with **known answers**. Write the ground truth in `demo/test_pack.md`:
  ```
  MT-001 Aarav : Q1=A Q2=B Q3=B
  MT-002 ...
  ```
  Make sure the wrong answers create a clear pattern (e.g. 3 of 5 pick 2/6 on Q1) so the insight is interesting
- [ ] Edge cases (one sheet each): double-bubbled, half-erased, very faint pencil, blank question, ticked instead of filled, crumpled, photo at an angle, photo in dim light, same sheet scanned twice
- [ ] Sit with Backend and scan the pack again and again. Record in `demo/scan_log.md`: sheet, condition, expected, got, pass/fail. This is how backend tunes the thresholds
- [ ] Find the best scanning setup (distance, angle, lighting) and write it in `demo/scanning_tips.md`

## D3 · Demo runbook (H09–H15)
Write `demo/runbook.md`, the exact clicks for the live demo, so anyone could run it:
1. Laptop: app open on Teacher → New assessment, concepts text ready to paste
2. Generate → edit one option → Approve → open PDF (already printed copies in hand)
3. Hand a fresh sheet to a judge/teammate: "Please answer Q1, any option"
4. Phone: Scanner page → Start → Capture → show the result
5. Scan the other 4 pre-filled sheets quickly
6. Review → fix one flagged sheet (the double-bubble one) → Confirm
7. Insights → open the top misconception card → show evidence + activity + follow-up
8. (if time) Student login on the phone → own results only
- Include: URLs, logins/PINs (fictional), where each sheet is in the folder, what to say if something fails

## D4 · Backup plan (H15–H18) ← do not skip
- [ ] **Screen-record the full real flow** on laptop + phone (a genuine run, not a mockup). Save to `demo/` (or Drive if large, link in runbook)
- [ ] Screenshots of every screen for Presenter 1's deck
- [ ] Check the app works with `AI_MODE=fixtures` (no internet) and know how to switch to it
- [ ] Check the **Upload image** fallback works if live camera fails
- [ ] Spare printed sheets: blank + pre-filled test pack

## D5 · Rehearse + submit (H18–H24)
- [ ] 3 timed rehearsals with Presenter 1, live scan every time
- [ ] Learn the full pitch so you can present solo (backup speaker)
- [ ] Submission checklist with the organisers' requirements: repo link, video, deck, README, team details. Submit **before** the deadline, not at it
- [ ] Keep standups on time: ping everyone every 3 hours for Done / Next / Blocker

## Rules
- Use only fictional student names on paper and in the app.
- If something fails live, say so calmly and switch to the backup. Never fake a result.
