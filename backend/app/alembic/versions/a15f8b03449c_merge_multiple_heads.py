"""merge multiple heads

Revision ID: a15f8b03449c
Revises: 8d7a05fd0ad4, change_user_id_to_integer
Create Date: 2025-04-11 22:55:38.092406

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a15f8b03449c'
down_revision = ('8d7a05fd0ad4', 'change_user_id_to_integer')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
