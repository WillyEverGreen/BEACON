"""add_lighthouse_enrichment_column

Adds the `lighthouse_enrichment` nullable JSON column to the `scans` table.
This holds the complete Lighthouse enrichment output block (status, scores,
findings, batch metrics) written atomically by the BackgroundTask enricher.

Revision ID: c9e1f3a27b84
Revises: 81e9864e53a7
Create Date: 2026-04-20 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9e1f3a27b84"
down_revision: Union[str, None] = "81e9864e53a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add lighthouse_enrichment JSON column to scans table."""
    op.add_column(
        "scans",
        sa.Column("lighthouse_enrichment", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Drop lighthouse_enrichment column from scans table."""
    op.drop_column("scans", "lighthouse_enrichment")
