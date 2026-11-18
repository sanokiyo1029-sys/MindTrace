"""Google Cloud OCR and optional translation for the teacher's scan preview."""
import base64

import httpx

from app import config
from app.errors import api_error

VISION_URL = "https://vision.googleapis.com/v1/images:annotate"
TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"


def _post(url: str, body: dict) -> dict:
    response = httpx.post(url, json=body, headers={"x-goog-api-key": config.GOOGLE_SCAN_API_KEY}, timeout=20)
    response.raise_for_status()
    return response.json()


def read_photo(image: bytes, target: str | None) -> dict:
    try:
        page = _post(VISION_URL, {"requests": [{
            "image": {"content": base64.b64encode(image).decode("ascii")},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }]})["responses"][0]
        if page.get("error"):
            raise ValueError("Cloud Vision declined the image")
        text = (page.get("fullTextAnnotation") or {}).get("text", "").strip()
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise api_error(502, "scan_ocr_failed", "Google Cloud Vision couldn't read this photo. Try again or use the original photo.") from None

    result = {"text": text, "translation": None, "translation_error": None}
    if target and text:
        try:
            reply = _post(TRANSLATE_URL, {"q": text, "target": target, "format": "text"})
            translated = reply["data"]["translations"][0]["translatedText"]
            if not isinstance(translated, str) or not translated.strip():
                raise ValueError("Cloud Translation returned empty text")
            result["translation"] = translated
        except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError):
            result["translation_error"] = "Google Cloud Translation couldn't translate this text. The recognized text is still available."
    return result
