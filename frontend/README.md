# MindTrace frontend

React + Vite teacher workspace for the paper-first assessment flow. The same build runs as the website and, wrapped with Capacitor, as the Android app.

## Run locally

```bash
npm ci
npm run dev
```

The development server runs at `http://localhost:5173`. It proxies `/api/*` to `http://localhost:8000/api/*`, preserving the shared contract's `/api` prefix. Start the backend first (`start-backend.bat` at the repo root).

## Modes and configuration

Vite reads the **repo-root `.env`** (`envDir: '..'`, see `docs/INTEGRATION.md`).

- **Live mode is the default.** Every screen calls the backend.
- `VITE_MOCK=true` turns on mock mode: the labelled fictional fixture in `src/fixtures/demo.json`. A "Mock mode · sample data, not live" tag shows on every screen. It does not fake sheet PDFs, scan results or student sign-in.
- `VITE_API_URL` defaults to `/api`.
- **Server address** (on the sign-in screens): where the backend lives, saved on the device. Leave it empty on the website. In the Android app, paste the backend's https tunnel address, e.g. `https://xxxx.trycloudflare.com`.
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

Overview (past assessments + per-student sheets), assessment setup, question review/approval, print preview, camera and image upload, scan review, class insights, teaching activity/follow-up, teacher login, and student results login (reachable without a teacher session).

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
