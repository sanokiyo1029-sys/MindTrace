# Deploying MindTrace (free)

## Why papers and scans disappear on Render's free plan
A free Render web service has a temporary disk. It is wiped when the service restarts: after a new deploy, and when
the free instance sleeps after about 15 idle minutes and wakes up again. With the default SQLite database
(`backend/mindtrace.db`) that wipe erases every account, class, assessment, scan and photo. Then:
- the review queue can't load the paper ("no longer on the server"),
- Choose Student / Confirm Paper fail because the scan or assessment is gone,
- scan photos (and Google Lens hand-off) 404.

The app now says so: the teacher workspace shows a red banner when `/api/health` reports `"storage": "temporary"`.

## Fix: connect a free Postgres database (nothing paid)
1. Create a free Postgres database, for example:
   - **Neon** (neon.tech, free tier, does not expire), or
   - **Supabase** (supabase.com, free tier), or
   - **Render Postgres** (free, but deleted after 30 days).
2. Copy its connection string (`postgres://user:password@host/dbname?sslmode=require`).
3. In Render → the `mindtrace-demo-api` service → **Environment**, add `DATABASE_URL` with that string. Never commit it.
4. **Manual Deploy → Deploy latest commit.** On start-up MindTrace creates the tables and the demo data.
5. Check `https://<your-service>.onrender.com/api/health` shows `"storage": "persistent"`.

`postgres://` URLs are accepted as-is (the app switches them to the `psycopg` driver). Scan photos, crops and
question pictures are stored in the database too (`media_blobs`), so they come back after a restart.

## Other settings (Render → Environment)
| Variable | Needed for |
|---|---|
| `DATABASE_URL` | Keeping data across restarts (above) |
| `FRONTEND_ORIGIN` | The site's own https address (CORS) |
| `GOOGLE_CLIENT_ID` | Continue with Google |
| `PUBLIC_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Password-reset emails (optional) |
| `GEMINI_API_KEY` | Optional server-side reading of handwriting; without it the bubble reader is used |

Build command: `pip install -r backend/requirements.txt && cd frontend && npm ci && npm run build`.
Render free services don't always auto-deploy on push: use **Manual Deploy**.
