from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from job_applicator.config import config

engine = create_engine(
    config.database_uri,
    pool_pre_ping=True,
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session():
    with Session(engine, expire_on_commit=False) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
