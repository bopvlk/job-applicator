from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlmodel import SQLModel

# 1. Беремо URI бази з нашого єдиного конфігураційного об'єкта
from job_applicator.config import config
# 2. Імпортуємо моделі, щоб Alembic «побачив» класи User та Job
from job_applicator.storage.models import Job, User  # noqa: F401

alembic_config = context.config

if alembic_config.config_file_name is not None:
  fileConfig(alembic_config.config_file_name)

# Метадані SQLModel для автопорівняння схеми
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
  """Run generation SQL-script"""
  context.configure(
      url=config.database_uri,
      target_metadata=target_metadata,
      literal_binds=True,
      dialect_opts={"paramstyle": "named"},
  )
  with context.begin_transaction():
    context.run_migrations()


def run_migrations_online() -> None:
  """Start of migration on live CockroachDB."""
  connectable = create_engine(config.database_uri)

  with connectable.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
      context.run_migrations()


if context.is_offline_mode():
  run_migrations_offline()
else:
  run_migrations_online()