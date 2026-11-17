# tests/fixtures/

Owner: Research. Sample JSON for every shape in `docs/CONTRACTS.md`, plus `roster.json` (fictional students only).
Frontend mocks and `AI_MODE=fixtures` both read from here.

`questions_sample.json` is the frozen three-question quiz. The AI stub uses
`questions_extra_sample.json` for requests of four or five questions and
`followup_questions_sample.json` for the retest.

The assessment, class insights and student report show a confirmed assessment.
The scan sample is from the review step before confirmation. Its media URLs
have the API shape and serve as placeholders in mock mode.
