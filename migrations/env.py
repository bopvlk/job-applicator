from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlmodel import SQLModel

# 1. Database URI from application config
from job_applicator.config import config
# 2. Import all models so Alembic reflects User and Job schemas
from job_applicator.storage.models import Job, User  # noqa: F401

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# Target SQLModel metadata for auto-generating migrations
target_metadata = SQLModel.metadata


def include_object(object, name, type_, reflected, compare_to):
    """Filter out internal CockroachDB tables and objects."""
    if type_ == "table" and name and name.startswith("_"):
        return False
    return True


def run_migrations_offline() -> None:
    """Generate SQL migration scripts offline."""
    context.configure(
        url=config.database_uri,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Execute migrations directly on live CockroachDB."""
    connectable = create_engine(config.database_uri)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()