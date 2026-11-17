# MindTrace frontend

React + Vite teacher workspace for the paper-first assessment flow.

## Run locally

```bash
npm ci
npm run dev
```

The development server runs at `http://localhost:5173`. It proxies `/api/*` to `http://localhost:8000/api/*`, preserving the shared contract's `/api` prefix.

## Modes and configuration

- `VITE_MOCK=true` (default) loads the clearly labelled fictional sample assessment and insight fixture in `src/fixtures/demo.json`. It does not fake sheet PDFs, scan results, or student authentication.
- `VITE_MOCK=false` enables the API integration. `VITE_API_URL` defaults to `/api`.
- Camera access requires localhost or HTTPS. Actual image processing requires the backend.

Set these in `frontend/.env.local` to connect a real backend:

```env
VITE_API_URL=/api
VITE_MOCK=false
```

## Screens

Overview, assessment setup, question review/approval, print preview, camera and image upload, scan review, class insights, teaching activity/follow-up, teacher login, and student results login.

## API contract

Requests follow `docs/CONTRACTS.md`: teacher login, assessment generation, question patch, approval, print PDF, scan upload/progress, scan review/confirmation, insights, follow-up, and student login/results. Teacher and student auth tokens stay in memory. QR generation, OMR results, and class insights come from the backend in live mode.

## Known integration limits

- The provided workspace contains no backend implementation or shared `tests/fixtures/`; demo data is local to this frontend and labelled.
- Live class selection currently uses the documented demo class `cl_7a`.
- Rejected scans show a rescan path; the contract has no scan-delete or replacement UI.
- The PDF preview is illustrative. Live mode opens the actual contract-generated PDF.

## Check

```bash
npm run build
```
