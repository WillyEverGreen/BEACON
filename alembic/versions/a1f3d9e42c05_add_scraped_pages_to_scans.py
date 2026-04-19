"""add scraped_pages to scans

Revision ID: a1f3d9e42c05
Revises: 7b2e6e7d8c1a
Create Date: 2026-04-19

Adds the `scraped_pages` JSON column to the `scans` table.
This enables per-scan URL transparency — the dashboard can show which
pages were actually crawled rather than just a page count.

NOTE: Must use sa.JSON() not sa.Text() to match the SQLAlchemy model's
      Mapped[list] = mapped_column(JSON, default=list) declaration.
      Using Text() would cause a type mismatch on deserialization.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1f3d9e42c05"
down_revision = "7b2e6e7d8c1a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Must use sa.JSON() to match models.py: Mapped[list] = mapped_column(JSON, default=list)
    # sa.Text() would cause a type mismatch — SQLAlchemy's JSON dialect handles
    # serialization/deserialization correctly; plain Text() would not.
    op.add_column(
        "scans",
        sa.Column("scraped_pages", sa.JSON(), nullable=True, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("scans", "scraped_pages")
