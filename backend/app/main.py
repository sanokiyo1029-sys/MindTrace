"""MindTrace API. Run from backend/:  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import ai_bridge, config
from app.routes import assessments, auth, classes, insights_route, scans, student
from app.seed import seed

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed()  # creates tables + demo teacher/class/students if missing
    yield


app = FastAPI(title="MindTrace API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
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
    return {"ok": True, "ai_mode": config.AI_MODE, "ai_module_loaded": ai_bridge.ai_module_loaded()}


for r in (auth.router, classes.router, assessments.router, scans.router, insights_route.router, student.router):
    app.include_router(r)

app.mount("/api/media", StaticFiles(directory=config.MEDIA_DIR), name="media")
