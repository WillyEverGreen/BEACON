"""add scan coverage metrics

Revision ID: 7b2e6e7d8c1a
Revises: cdc14274a3f6
Create Date: 2026-04-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7b2e6e7d8c1a"
down_revision = "cdc14274a3f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("issue_types_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("scans", sa.Column("failing_elements_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("scans", sa.Column("pages_scanned", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("scans", sa.Column("pages_discovered", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("scans", "pages_discovered")
    op.drop_column("scans", "pages_scanned")
    op.drop_column("scans", "failing_elements_count")
    op.drop_column("scans", "issue_types_count")
