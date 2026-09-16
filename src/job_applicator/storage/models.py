import time

from sqlmodel import JSON, Column, Field, SQLModel

from job_applicator.enums import JobStatus


class User(SQLModel, table=True):
    __tablename__ = "users"
    telegram_chat_id: int = Field(primary_key=True)
    email: str | None = Field(default=None, unique=True, index=True)
    otp: str | None = None
    otp_expires: int | None = None
    verified: int = Field(default=0)
    desired_title: str | None = None
    # Users info from CV
    years_experience: int | None = None
    top_skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    key_achievements: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    preferred_location: str | None = None
    min_salary: str | None = None
    bio_summary: str | None = None
    # Min threshold
    min_match_score: int = Field(default=75)


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    id: int | None = Field(default=None, primary_key=True)
    user_chat_id: int = Field(foreign_key="users.telegram_chat_id")
    uri: str
    title: str | None = None
    company: str | None = None
    status: JobStatus = Field(default=JobStatus.NEW)
    match_pct: int | None = None
    company_summary: str | None = None
    red_flags: str | None = None
    cover_letter: str | None = None
    raw_text: str | None = None
    stack_match_pct: int | None = None
    seniority_match_pct: int | None = None
    location_match_pct: int | None = None
    created_at: int = Field(default_factory=lambda: int(time.time()))
