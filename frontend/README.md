# MindTrace frontend

React + Vite frontend for the paper-first assessment flow. The same build runs as the website and, wrapped with Capacitor, as the Android app.

## Run locally

```bash
npm ci
npm run dev
```

The development server runs at `http://localhost:5173`. It proxies `/api/*` to `http://localhost:8000/api/*`, preserving the shared contract's `/api` prefix. Start the backend first (`start-backend.bat` at the repo root).

**The backend also serves the built website** at `http://localhost:8000` (run `npm run build` after frontend changes; `start-backend.bat` builds it once if missing). So one address, or one tunnel (`cloudflared tunnel --url http://localhost:8000`), is the whole app: open it, sign in, land on the dashboard.

## Modes and configuration

Vite reads the **repo-root `.env`** (`envDir: '..'`, see `docs/INTEGRATION.md`).

- Standard teacher and student sign-in uses the backend.
- The teacher sign-in page offers **Explore sample workspace**, which uses the labelled fictional fixture in `src/fixtures/demo.json`. Set `VITE_MOCK=false` to hide the sample entry or `VITE_MOCK=true` to open the sample by default. Sample mode leaves PDF generation and scan processing to the backend.
- `VITE_API_URL` defaults to `/api`.
- **Server address** (Android app only): where the backend lives, saved on the device, e.g. `https://xxxx.trycloudflare.com`. The website always uses the server it was loaded from.
- **Gemini** runs on the server (see the root `.env`: `AI_MODE=live`, `LLM_API_KEY`). The New assessment screen says whether Gemini or the labelled saved samples are in use; questions and activities are tagged "AI draft" or "Saved sample", and fallback notes show as a banner.
- **Continue with Google** appears on the sign-in screen when the server has `GOOGLE_CLIENT_ID` (not inside the Android app).
- The teacher token, the open assessment and the server address are kept in `localStorage`, so a refresh keeps you signed in. A `401` signs you out.
- Camera access needs localhost or HTTPS. Image processing happens in the backend.

## Android app (Capacitor)

Needs Android Studio (for its Java) and the Android SDK.

```bash
npm run android:sync            # vite build + npx cap sync android
```

Then, in PowerShell:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
cd android; .\gradlew.bat assembleDebug
```

The APK is `android/app/build/outputs/apk/debug/app-debug.apk`. Install it with `adb install -r` (in the SDK's `platform-tools`) or copy it to the phone.

On the phone: start a tunnel on the PC (`cloudflared tunnel --url http://localhost:8000`), paste the `https://…trycloudflare.com` address into **Server address**, and sign in. The app runs on `https://localhost`, which the backend allows in CORS. The camera permission is asked the first time you press **Start camera** or **Upload image**. **Print** opens the PDF in the phone's browser.

`android/` is committed; its build output, copied web assets and `local.properties` are git-ignored.

## Screens

- `/` shows the public landing page and interactive fractions story.
- `/login` lets teachers and students choose their sign-in method.
- `/workspace` opens the teacher dashboard and its assessment, scan and insights tools.
- `/student` shows the signed-in student’s own results and feedback.

To exercise both roles and the sample workspace against the demo backend, open the preview in Playwright CLI and run `playwright-cli run-code --filename=tests/smoke.js` from this directory.

## API contract

Requests follow `docs/CONTRACTS.md`, including `GET /assessments`, `GET /assessments/{id}` and `GET /assessments/{id}/results`.

## Known limits

- Live class selection uses the documented demo class `cl_7a`.
- Rejected scans show a rescan path; the contract has no scan-delete or replacement UI.
- The on-screen sheet preview is illustrative. Print opens the real PDF from the backend.

## Check

```bash
npm run build
```
