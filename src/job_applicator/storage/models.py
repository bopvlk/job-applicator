import time
from sqlmodel import SQLModel, Field
from typing import Optional

class User(SQLModel, table=True):
    __tablename__ = "users"
    email: str = Field(primary_key=True)
    otp: Optional[str] = None
    otp_expires: Optional[int] = None
    verified: int = Field(default=0)
    desired_title: Optional[str] = None


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_email: str = Field(foreign_key="users.email")
    uri: str
    title: Optional[str] = None
    company: Optional[str] = None
    status: str = Field(default="New")
    match_pct: Optional[int] = None
    company_summary: Optional[str] = None
    red_flags: Optional[str] = None
    cover_letter: Optional[str] = None
    raw_text: Optional[str] = None
    created_at: int =  Field(default_factory=lambda: int(time.time())),
