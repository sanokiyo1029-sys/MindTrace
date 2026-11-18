"""MindTrace API. Run from backend/:  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app import ai_bridge, config, gemini
from app.routes import accounts, assessments, auth, classes, exams, insights_route, media, scans, student, teaching
from app.seed import seed

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed()  # creates tables + demo teacher/class/students if missing
    yield


app = FastAPI(title="MindTrace API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def select_client_mode(request: Request, call_next):
    # The APK explicitly opts out of server-side Gemini for question drafts, handwriting and feedback too.
    mode = gemini.lens_only_client.set(request.headers.get("X-MindTrace-Mode") == "lens-only")
    try:
        return await call_next(request)
    finally:
        gemini.lens_only_client.reset(mode)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173",
                   "https://localhost", "capacitor://localhost"],  # Android app (Capacitor WebView)
    allow_origin_regex=r"https://.*\.trycloudflare\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    body = exc.detail if isinstance(exc.detail, dict) else {"error": "error", "message": str(exc.detail)}
    return JSONResponse(body, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    return JSONResponse({"error": "bad_request", "message": f"{where}: {first.get('msg', 'invalid input')}"}, status_code=422)


@app.get("/api/health")
def health():
    return {"ok": True, "ai_mode": config.AI_MODE, "ai_module_loaded": ai_bridge.ai_module_loaded(),
            "ai_provider": ai_bridge.provider(), "gemini": gemini.enabled(),
            "storage": "persistent" if config.PERSISTENT_STORAGE else "temporary"}  # app.ai | gemini | samples (the key itself never leaves the server)


for r in (auth.router, classes.router, classes.student_router, assessments.router, scans.router, insights_route.router,
          student.router, teaching.router, media.router, accounts.router, exams.router):
    app.include_router(r)



# The website (frontend/dist, from `npm run build`) is served here too, so one address, or one Cloudflare
# tunnel to :8000, is the whole app: open it, sign in, land on the dashboard. Registered last on purpose.
@app.get("/{path:path}", include_in_schema=False)
def website(path: str):
    if path == "api" or path.startswith("api/"):
        raise HTTPException(404, detail={"error": "not_found", "message": "No such API route."})
    dist = config.FRONTEND_DIST.resolve()
    file = (dist / path).resolve()
    if path and file.is_file() and dist in file.parents:
        return FileResponse(file)
    index = dist / "index.html"
    if index.is_file():  # app routes like /insights are handled by the React router
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    raise HTTPException(404, detail={"error": "website_not_built",
                                     "message": "The website isn't built yet. Run `npm run build` in frontend/."})
