"""add the circular use-alter fks the v2 schema missed

Revision ID: a91d5304045c
Revises: 0170b87e7d08
Create Date: 2026-06-05 07:47:30.782436

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a91d5304045c'
down_revision: str | Sequence[str] | None = '0170b87e7d08'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # the two circular fks the v2 schema migration left out: a branch's fork point and a
    # project's primary branch. both are use_alter (the tables reference each other) and
    # set null on delete, matching orm_v2.
    op.create_foreign_key(
        "fk_branches_fork_beat", "branches", "beats",
        ["created_from_beat_id"], ["id"], ondelete="SET NULL", use_alter=True,
    )
    op.create_foreign_key(
        "fk_projects_primary_branch", "projects", "branches",
        ["primary_branch_id"], ["id"], ondelete="SET NULL", use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_primary_branch", "projects", type_="foreignkey")
    op.drop_constraint("fk_branches_fork_beat", "branches", type_="foreignkey")
