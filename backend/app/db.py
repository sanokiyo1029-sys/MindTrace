from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401  (register tables)

    Base.metadata.create_all(engine)
    migrate()


# Columns added for the roll-number + Gemini scanning workflow. create_all() makes them in NEW databases;
# migrate() adds them to databases created before (idempotent, runs at every start).
_NEW_COLUMNS = {
    "students": {"roll_no": "VARCHAR"},
    "scans": {"roll_number": "VARCHAR", "extracted_by": "VARCHAR", "identity": "JSON", "warnings": "JSON"},
}


def migrate():
    from collections import defaultdict

    from sqlalchemy import inspect, text

    from app.rolls import from_student_code

    insp = inspect(engine)
    with engine.begin() as con:
        for table, cols in _NEW_COLUMNS.items():
            have = {c["name"] for c in insp.get_columns(table)}
            for name, sqltype in cols.items():
                if name not in have:
                    con.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}"))
        # Backfill roll numbers from the login code ("7A-01" -> "01"); keep the full code if that would clash.
        rows = con.execute(text("SELECT id, class_id, student_code, roll_no FROM students")).all()
        taken = defaultdict(set)
        for _, cls, _, roll in rows:
            if roll:
                taken[cls].add(roll)
        for sid, cls, code, roll in rows:
            if roll:
                continue
            new = from_student_code(code)
            if new in taken[cls]:
                new = code
            taken[cls].add(new)
            con.execute(text("UPDATE students SET roll_no = :r WHERE id = :i"), {"r": new, "i": sid})
        con.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_students_class_roll ON students (class_id, roll_no)"))
        # Scans made before this change were identified by the old QR code.
        con.execute(text("UPDATE scans SET extracted_by = 'qr_legacy' WHERE extracted_by IS NULL"))
        # At most one live scan per student's paper. Also stops two simultaneous uploads both becoming live.
        con.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_scans_current ON scans (sheet_id) "
                         "WHERE is_current AND sheet_id IS NOT NULL"))
