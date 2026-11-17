"""Gemini client for MindTrace's AI features (used by ai_bridge when Samrudh's app/ai module isn't installed).

The API key stays on the server (LLM_API_KEY in the repo-root .env); the browser and the Android app only ever
talk to our /api. Calls use the REST generateContent endpoint with a JSON schema, so replies are plain dicts.
Every failure becomes a GeminiError with a short message the teacher can read; callers fall back to samples.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import time

import httpx

from app import config

log = logging.getLogger("mindtrace.gemini")

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = httpx.Timeout(25.0, connect=8.0)
RETRYABLE = {429, 500, 503, 504}
MAX_ATTEMPTS = 3          # first try + 2 retries for busy / rate-limited answers
MAX_WAIT = 4.0            # never hold a teacher's request longer than this between retries
COOLDOWN = 30.0           # after a rate limit, skip Gemini for a bit instead of hammering it
_cooldown_until = 0.0


class GeminiError(Exception):
    """kind: not_configured | timeout | rate_limited | blocked | bad_output | api_error"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def enabled() -> bool:
    return config.AI_MODE == "live" and config.LLM_PROVIDER == "gemini" and bool(config.LLM_API_KEY)


VISION_TIMEOUT = httpx.Timeout(45.0, connect=8.0)  # reading a page photo takes longer than text


def _post(url: str, body: dict, timeout: httpx.Timeout = TIMEOUT) -> httpx.Response:  # one seam for tests
    return httpx.post(url, json=body, timeout=timeout,
                      headers={"x-goog-api-key": config.LLM_API_KEY, "Content-Type": "application/json"})


def _retry_delay(resp: httpx.Response, attempt: int) -> float:
    """Server hint (Retry-After or google.rpc.RetryInfo "13s") if any, else 1s, 2s; capped at MAX_WAIT."""
    hint = resp.headers.get("retry-after")
    if not hint:
        m = re.search(r'"retryDelay"\s*:\s*"([\d.]+)s"', resp.text)
        hint = m.group(1) if m else None
    try:
        wait = float(hint) if hint else float(attempt + 1)
    except ValueError:
        wait = float(attempt + 1)
    return wait


def ask(system: str, prompt: str, schema: dict, temperature: float = 0.4, image_jpeg: bytes | None = None) -> dict:
    """Send one prompt (and optionally one JPEG photo), get back the JSON object Gemini produced for `schema`."""
    global _cooldown_until
    if not enabled():
        raise GeminiError("not_configured", "Gemini is not configured.")
    if time.monotonic() < _cooldown_until:
        raise GeminiError("rate_limited", "Gemini is busy right now (rate limit reached).")
    parts = [{"text": prompt}]
    config_ = {"temperature": temperature, "maxOutputTokens": 4096,
               "responseMimeType": "application/json", "responseJsonSchema": schema}
    if image_jpeg is not None:  # image first, then the instructions; high resolution for handwriting
        parts.insert(0, {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(image_jpeg).decode()}})
        config_["mediaResolution"] = "MEDIA_RESOLUTION_HIGH"
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}], "generationConfig": config_}
    model = config.LLM_VISION_MODEL if image_jpeg is not None else config.LLM_MODEL
    url = URL.format(model=model)
    timeout = VISION_TIMEOUT if image_jpeg is not None else TIMEOUT
    for attempt in range(MAX_ATTEMPTS):
        started = time.monotonic()
        try:
            resp = _post(url, body, timeout)
        except httpx.TimeoutException:
            raise GeminiError("timeout", "Gemini took too long to answer.") from None
        except httpx.HTTPError as exc:
            raise GeminiError("api_error", f"Could not reach Gemini ({type(exc).__name__}).") from None
        log.info("gemini %s -> %s in %.1fs", model, resp.status_code, time.monotonic() - started)  # never the content

        if resp.status_code in RETRYABLE and attempt < MAX_ATTEMPTS - 1:
            wait = _retry_delay(resp, attempt)
            daily_quota = resp.status_code == 429 and "quota" in resp.text.lower() and wait > MAX_WAIT
            if not daily_quota:
                time.sleep(min(wait, MAX_WAIT))
                continue
        if resp.status_code == 429:
            _cooldown_until = time.monotonic() + COOLDOWN
            raise GeminiError("rate_limited", "Gemini is busy right now (rate limit reached).")
        if resp.status_code in (500, 503, 504):
            raise GeminiError("api_error", "Gemini is temporarily unavailable.")
        if resp.status_code in (401, 403) or (resp.status_code == 400 and "API key" in resp.text):
            raise GeminiError("api_error", "Gemini rejected the API key (check LLM_API_KEY).")
        if resp.status_code == 404:
            raise GeminiError("api_error", f"Gemini model '{model}' was not found (check LLM_MODEL / LLM_VISION_MODEL).")
        if resp.status_code >= 400:
            log.warning("gemini error %s: %s", resp.status_code, resp.text[:300])
            raise GeminiError("api_error", f"Gemini returned an error ({resp.status_code}).")
        return _parse(resp)
    raise GeminiError("api_error", "Gemini is temporarily unavailable.")  # pragma: no cover


def _parse(resp: httpx.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        raise GeminiError("bad_output", "Gemini sent an unreadable reply.") from None
    if (data.get("promptFeedback") or {}).get("blockReason"):
        raise GeminiError("blocked", "Gemini declined this request.")
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
    if not text:
        reason = cand.get("finishReason", "")
        raise GeminiError("blocked" if reason not in ("", "STOP", "MAX_TOKENS") else "bad_output",
                          "Gemini returned an empty answer.")
    try:
        out = json.loads(text)
    except ValueError:
        raise GeminiError("bad_output", "Gemini's answer was cut off or not valid JSON.") from None
    if not isinstance(out, dict):
        raise GeminiError("bad_output", "Gemini's answer had the wrong shape.")
    return out
