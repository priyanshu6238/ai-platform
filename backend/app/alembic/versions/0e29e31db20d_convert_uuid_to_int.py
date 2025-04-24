"""convert_uuid_to_int

Revision ID: 0e29e31db20d
Revises: 543f97951bd0
Create Date: 2025-04-24 21:52:37.856067

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects.postgresql import UUID
import uuid


# revision identifiers, used by Alembic.
revision = '0e29e31db20d'
down_revision = '543f97951bd0'
branch_labels = None
depends_on = None


def upgrade():
    # Drop foreign key constraints first
    op.drop_constraint('projectuser_user_id_fkey', 'projectuser', type_='foreignkey')
    op.drop_constraint('apikey_user_id_fkey', 'apikey', type_='foreignkey')
    op.drop_constraint('document_owner_id_fkey', 'document', type_='foreignkey')

    # Create temporary columns for data migration
    op.add_column('user', sa.Column('new_id', sa.Integer(), nullable=True))
    op.add_column('document', sa.Column('new_id', sa.Integer(), nullable=True))
    op.add_column('document', sa.Column('new_owner_id', sa.Integer(), nullable=True))
    op.add_column('projectuser', sa.Column('new_user_id', sa.Integer(), nullable=True))
    op.add_column('apikey', sa.Column('new_user_id', sa.Integer(), nullable=True))

    # Create sequences for new IDs
    op.execute('CREATE SEQUENCE IF NOT EXISTS user_id_seq')
    op.execute('CREATE SEQUENCE IF NOT EXISTS document_id_seq')

    # Update user table with new integer IDs
    op.execute("""
        UPDATE "user" 
        SET new_id = nextval('user_id_seq')
        WHERE new_id IS NULL
    """)

    # Update document table with new integer IDs
    op.execute("""
        UPDATE document d
        SET new_id = nextval('document_id_seq'),
            new_owner_id = u.new_id
        FROM "user" u
        WHERE d.owner_id = u.id
    """)

    # Update projectuser table with new integer IDs
    op.execute("""
        UPDATE projectuser pu
        SET new_user_id = u.new_id
        FROM "user" u
        WHERE pu.user_id = u.id
    """)

    # Update apikey table with new integer IDs
    op.execute("""
        UPDATE apikey ak
        SET new_user_id = u.new_id
        FROM "user" u
        WHERE ak.user_id = u.id
    """)

    # Drop old columns and rename new ones
    op.drop_column('user', 'id')
    op.alter_column('user', 'new_id', new_column_name='id')
    op.create_primary_key('user_pkey', 'user', ['id'])

    op.drop_column('document', 'id')
    op.alter_column('document', 'new_id', new_column_name='id')
    op.drop_column('document', 'owner_id')
    op.alter_column('document', 'new_owner_id', new_column_name='owner_id')
    op.create_primary_key('document_pkey', 'document', ['id'])

    op.drop_column('projectuser', 'user_id')
    op.alter_column('projectuser', 'new_user_id', new_column_name='user_id')

    op.drop_column('apikey', 'user_id')
    op.alter_column('apikey', 'new_user_id', new_column_name='user_id')

    # Recreate foreign key constraints
    op.create_foreign_key('projectuser_user_id_fkey', 'projectuser', 'user', ['user_id'], ['id'])
    op.create_foreign_key('apikey_user_id_fkey', 'apikey', 'user', ['user_id'], ['id'])
    op.create_foreign_key('document_owner_id_fkey', 'document', 'user', ['owner_id'], ['id'])

    # Drop sequences
    op.execute('DROP SEQUENCE IF EXISTS user_id_seq')
    op.execute('DROP SEQUENCE IF EXISTS document_id_seq')


def downgrade():
    # Drop foreign key constraints first
    op.drop_constraint('projectuser_user_id_fkey', 'projectuser', type_='foreignkey')
    op.drop_constraint('apikey_user_id_fkey', 'apikey', type_='foreignkey')
    op.drop_constraint('document_owner_id_fkey', 'document', type_='foreignkey')

    # Create temporary columns for data migration
    op.add_column('user', sa.Column('old_id', UUID(), nullable=True))
    op.add_column('document', sa.Column('old_id', UUID(), nullable=True))
    op.add_column('document', sa.Column('old_owner_id', UUID(), nullable=True))
    op.add_column('projectuser', sa.Column('old_user_id', UUID(), nullable=True))
    op.add_column('apikey', sa.Column('old_user_id', UUID(), nullable=True))

    # Generate new UUIDs for users
    op.execute("""
        UPDATE "user" 
        SET old_id = gen_random_uuid()
        WHERE old_id IS NULL
    """)

    # Update document table with UUIDs
    op.execute("""
        UPDATE document d
        SET old_id = gen_random_uuid(),
            old_owner_id = u.old_id
        FROM "user" u
        WHERE d.owner_id = u.id
    """)

    # Update projectuser table with UUIDs
    op.execute("""
        UPDATE projectuser pu
        SET old_user_id = u.old_id
        FROM "user" u
        WHERE pu.user_id = u.id
    """)

    # Update apikey table with UUIDs
    op.execute("""
        UPDATE apikey ak
        SET old_user_id = u.old_id
        FROM "user" u
        WHERE ak.user_id = u.id
    """)

    # Drop old columns and rename new ones
    op.drop_column('user', 'id')
    op.alter_column('user', 'old_id', new_column_name='id')
    op.create_primary_key('user_pkey', 'user', ['id'])

    op.drop_column('document', 'id')
    op.alter_column('document', 'old_id', new_column_name='id')
    op.drop_column('document', 'owner_id')
    op.alter_column('document', 'old_owner_id', new_column_name='owner_id')
    op.create_primary_key('document_pkey', 'document', ['id'])

    op.drop_column('projectuser', 'user_id')
    op.alter_column('projectuser', 'old_user_id', new_column_name='user_id')

    op.drop_column('apikey', 'user_id')
    op.alter_column('apikey', 'old_user_id', new_column_name='user_id')

    # Recreate foreign key constraints
    op.create_foreign_key('projectuser_user_id_fkey', 'projectuser', 'user', ['user_id'], ['id'])
    op.create_foreign_key('apikey_user_id_fkey', 'apikey', 'user', ['user_id'], ['id'])
    op.create_foreign_key('document_owner_id_fkey', 'document', 'user', ['owner_id'], ['id'])
