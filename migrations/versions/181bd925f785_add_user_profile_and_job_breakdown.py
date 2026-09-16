"""add user profile and job breakdown

Revision ID: 181bd925f785
Revises:
Create Date: 2026-09-16 12:56:33.691815

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "181bd925f785"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Note: stack_match_pct, seniority_match_pct, location_match_pct were already created on jobs table in initial pass.

    # 1. Dynamic candidate profile columns on users table
    op.add_column("users", sa.Column("years_experience", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("top_skills", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("key_achievements", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("preferred_location", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("users", sa.Column("min_salary", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("users", sa.Column("bio_summary", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("users", sa.Column("min_match_score", sa.Integer(), server_default="75", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "min_match_score")
    op.drop_column("users", "bio_summary")
    op.drop_column("users", "min_salary")
    op.drop_column("users", "preferred_location")
    op.drop_column("users", "key_achievements")
    op.drop_column("users", "top_skills")
    op.drop_column("users", "years_experience")
