import time
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"
    telegram_chat_id: int = Field(primary_key=True)
    email: str | None = Field(default=None, unique=True, index=True)
    otp: str | None = None
    otp_expires: int | None = None
    verified: int = Field(default=0)
    desired_title: str | None = None


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    id: int | None = Field(default=None, primary_key=True)
    user_chat_id: int = Field(foreign_key="users.telegram_chat_id")
    uri: str
    title: str | None = None
    company: str | None = None
    status: str = Field(default="New")
    match_pct: int | None = None
    company_summary: str | None = None
    red_flags: str | None = None
    cover_letter: str | None = None
    raw_text: str | None = None
    created_at: int = Field(default_factory=lambda: int(time.time()))