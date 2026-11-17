from fastapi import HTTPException


def api_error(status: int, code: str, message: str, **extra) -> HTTPException:
    """All errors look like {"error": code, "message": text} (docs/CONTRACTS.md)."""
    return HTTPException(status, detail={"error": code, "message": message, **extra})
