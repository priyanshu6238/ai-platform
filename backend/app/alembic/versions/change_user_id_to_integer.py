"""Change User model ID from UUID to integer

Revision ID: change_user_id_to_integer
Revises: d98dd8ec85a3
Create Date: 2024-04-11 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "change_user_id_to_integer"
down_revision = "d98dd8ec85a3"
branch_labels = None
depends_on = None


def upgrade():
    # Create a new integer column for the user table
    op.add_column(
        "user",
        sa.Column(
            "new_id",
            sa.Integer,
            sa.Identity(always=True),
            nullable=False,
        ),
    )

    # Create a sequence for the new integer IDs
    op.execute('CREATE SEQUENCE IF NOT EXISTS user_id_seq AS INTEGER')
    op.execute("SELECT setval('user_id_seq', COALESCE((SELECT MAX(CAST(id AS TEXT)::bigint) FROM \"user\"), 1), false)")

    # Populate the new integer column with sequential values
    op.execute(
        'UPDATE "user" SET new_id = nextval(\'user_id_seq\')'
    )

    # Drop the old UUID column and rename the new integer column
    op.drop_constraint("user_pkey", "user", type_="primary")
    op.drop_column("user", "id")
    op.alter_column("user", "new_id", new_column_name="id")

    # Create primary key constraint on the new integer column
    op.create_primary_key("user_pkey", "user", ["id"])

    # Update foreign key references in related tables
    # Note: You'll need to add similar changes for any tables that reference the user table
    # For example, if you have a documents table:
    # op.add_column("document", sa.Column("new_owner_id", sa.Integer, nullable=True))
    # op.execute('UPDATE document SET new_owner_id = (SELECT new_id FROM "user" WHERE "user".id = document.owner_id)')
    # op.drop_constraint("document_owner_id_fkey", "document", type_="foreignkey")
    # op.drop_column("document", "owner_id")
    # op.alter_column("document", "new_owner_id", new_column_name="owner_id")
    # op.create_foreign_key("document_owner_id_fkey", "document", "user", ["owner_id"], ["id"])


def downgrade():
    # Add UUID column back
    op.add_column(
        "user",
        sa.Column(
            "old_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
    )

    # Populate the UUID column with new UUIDs
    op.execute('UPDATE "user" SET old_id = uuid_generate_v4()')

    # Drop the integer column and rename the UUID column back
    op.drop_constraint("user_pkey", "user", type_="primary")
    op.drop_column("user", "id")
    op.alter_column("user", "old_id", new_column_name="id")

    # Create primary key constraint on the UUID column
    op.create_primary_key("user_pkey", "user", ["id"])

    # Update foreign key references in related tables back to UUID
    # Note: You'll need to add similar changes for any tables that reference the user table
    # For example, if you have a documents table:
    # op.add_column("document", sa.Column("old_owner_id", postgresql.UUID(as_uuid=True), nullable=True))
    # op.execute('UPDATE document SET old_owner_id = (SELECT old_id FROM "user" WHERE "user".id = document.owner_id)')
    # op.drop_constraint("document_owner_id_fkey", "document", type_="foreignkey")
    # op.drop_column("document", "owner_id")
    # op.alter_column("document", "old_owner_id", new_column_name="owner_id")
    # op.create_foreign_key("document_owner_id_fkey", "document", "user", ["owner_id"], ["id"]) 