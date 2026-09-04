# app/database/models.py

from sqlalchemy import Column, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id          = Column(Text, primary_key=True)   # UUID
    url         = Column(Text)
    title       = Column(Text)
    company     = Column(Text)
    raw_text    = Column(Text, nullable=False)
    track       = Column(Text)                      # set after taxonomy classification
    focus       = Column(Text)
    status      = Column(Text, default="ingested")  # ingested | generating | done | error
    app_status            = Column(Text, default=None)     # applied | interviewing | offer | rejected | pass | archived
    notes                 = Column(Text, default=None)
    figurative_assessment = Column(Text, default=None)
    text_fingerprint = Column(Text, default=None)    # sha256[:16] of first 2000 chars — fallback dedup
    ingested_at      = Column(Text, nullable=False)  # ISO8601
    role_match       = Column(Float, default=None)   # cosine sim against job_targets.json (0–1)
    week_label       = Column(Text, default=None)    # Monday of ingestion week YYYY-MM-DD (for tracker grouping)
    job_category     = Column(Text, default="Main")  # Main | PT | Bridge | Other

    @property
    def is_general_purpose(self) -> bool:
        """
        True for any job not tied to a specific posting — the seeded default
        CV, a general-purpose PT CV, or any future one made the same way.
        Not an ID allowlist: matches on the same signal the tracker UI already
        uses (no company set), so it stays correct for any user's data without
        hardcoding a specific job_id.
        """
        return not self.company or self.company == "—"


class Variant(Base):
    __tablename__ = "variants"

    id          = Column(Text, primary_key=True)    # e.g. soc_security_v1
    job_id      = Column(Text, ForeignKey("jobs.id"))
    track       = Column(Text)
    focus       = Column(Text)
    version     = Column(Integer)
    output_path = Column(Text)                      # path to outputs/resumes/{id}/
    reused      = Column(Integer, default=0)        # 0 = False, 1 = True
    created_at  = Column(Text, nullable=False)       # ISO8601
