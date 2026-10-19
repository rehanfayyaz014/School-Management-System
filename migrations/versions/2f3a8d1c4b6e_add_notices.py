"""add notices

Revision ID: 2f3a8d1c4b6e
Revises: 9b33426aed2b
"""
from alembic import op
import sqlalchemy as sa


revision = "2f3a8d1c4b6e"
down_revision = "9b33426aed2b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=20), nullable=False),
        sa.Column("notice_date", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "audience IN ('all', 'teacher', 'student')",
            name="ck_notice_audience"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("notices")
