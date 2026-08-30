from contextlib import contextmanager

from sqlmodel import SQLModel, Session
from sqlalchemy import create_engine

import job_applicator.storage.models
from job_applicator.config import config


engine = create_engine(
    config.database_uri,
    pool_pre_ping=True,
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session():
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
