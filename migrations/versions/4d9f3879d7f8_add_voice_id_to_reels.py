"""add voice_id column to reels

Revision ID: 4d9f3879d7f8
Revises: 676cbd769452
Create Date: 2025-12-12 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d9f3879d7f8'
down_revision = '676cbd769452'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('voice_id', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('reels', schema=None) as batch_op:
        batch_op.drop_column('voice_id')
