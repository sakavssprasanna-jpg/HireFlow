import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hireflow.db")

# SQLite connection args for concurrent access and thread safety
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def migrate_schema(bind_engine):
    """Ensure newly added columns exist in SQLite database without data loss."""
    if not str(bind_engine.url).startswith("sqlite"):
        return
    with bind_engine.connect() as conn:
        # Check interview_sessions
        session_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(interview_sessions)")).fetchall()}
        if session_cols:
            missing_session = [
                ("role_id", "TEXT"),
                ("experience_level", "VARCHAR(32) DEFAULT 'Mid Level'"),
                ("duration_seconds", "INTEGER DEFAULT 900"),
                ("remaining_seconds", "INTEGER DEFAULT 900"),
                ("current_question_index", "INTEGER DEFAULT 0"),
                ("summary_json", "TEXT"),
            ]
            for col_name, col_def in missing_session:
                if col_name not in session_cols:
                    conn.execute(text(f"ALTER TABLE interview_sessions ADD COLUMN {col_name} {col_def}"))
            conn.commit()

        # Check interview_questions
        q_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(interview_questions)")).fetchall()}
        if q_cols:
            missing_q = [
                ("question_type", "VARCHAR(32) DEFAULT 'GAP_INVESTIGATION'"),
                ("reason", "TEXT"),
                ("evidence_basis", "TEXT"),
                ("experience_level", "VARCHAR(32)"),
                ("priority", "VARCHAR(16) DEFAULT 'HIGH'"),
                ("estimated_duration_seconds", "INTEGER DEFAULT 180"),
                ("candidate_answer", "TEXT"),
                ("extracted_evidence", "TEXT"),
                ("evidence_status", "VARCHAR(32)"),
                ("is_skipped", "BOOLEAN DEFAULT 0"),
                ("is_answered", "BOOLEAN DEFAULT 0"),
                ("answered_at", "DATETIME"),
                ("order_index", "INTEGER DEFAULT 0"),
            ]
            for col_name, col_def in missing_q:
                if col_name not in q_cols:
                    conn.execute(text(f"ALTER TABLE interview_questions ADD COLUMN {col_name} {col_def}"))
            conn.commit()

def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

