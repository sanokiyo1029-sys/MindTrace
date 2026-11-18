"""Scan photos, crops and question pictures: kept on disk for speed AND in the database, because free hosts (Render)
wipe the disk on every restart or deploy. A missing file is restored from the database the first time it's needed.
With a hosted Postgres (DATABASE_URL), papers and photos survive restarts; with SQLite on such a host neither does."""
from pathlib import Path

from app.config import MEDIA_DIR
from app.db import SessionLocal
from app.models import MediaBlob


def _key(path: Path) -> str:
    return path.resolve().relative_to(MEDIA_DIR.resolve()).as_posix()  # e.g. "scans/sc_ab12.jpg"


def save(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    with SessionLocal() as db:
        db.merge(MediaBlob(name=_key(path), data=data))
        db.commit()


def ensure(path: Path) -> bool:
    """True when the file is on disk (restored from the database if the disk was wiped)."""
    if path.is_file():
        return True
    with SessionLocal() as db:
        row = db.get(MediaBlob, _key(path))
    if row is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(row.data)
    return True


def delete(path: Path) -> None:
    path.unlink(missing_ok=True)
    with SessionLocal() as db:
        if row := db.get(MediaBlob, _key(path)):
            db.delete(row)
            db.commit()
