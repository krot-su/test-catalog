"""create products

Revision ID: 0001
Revises:
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("image_key", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_products_created_at_id",
        "products",
        [sa.text("created_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_products_created_at_id", table_name="products")
    op.drop_table("products")
