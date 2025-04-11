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
    # Drop the primary key constraint with CASCADE
    op.execute('ALTER TABLE "user" DROP CONSTRAINT user_pkey CASCADE')

    # Create a new integer column for the user table
    op.add_column(
        "user",
        sa.Column(
            "new_id",
            sa.Integer,
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

    # Add new integer column to item table
    op.add_column(
        "item",
        sa.Column("new_owner_id", sa.Integer, nullable=True)
    )

    # Update the foreign key references
    op.execute(
        'UPDATE item SET new_owner_id = (SELECT new_id FROM "user" WHERE "user".id = item.owner_id)'
    )

    # Drop the old UUID columns and rename the new integer columns
    op.drop_column("user", "id")
    op.alter_column("user", "new_id", new_column_name="id")
    op.drop_column("item", "owner_id")
    op.alter_column("item", "new_owner_id", new_column_name="owner_id")

    # Create primary key constraint on the new integer column
    op.create_primary_key("user_pkey", "user", ["id"])

    # Recreate foreign key constraints
    op.create_foreign_key(
        "item_owner_id_fkey",
        "item",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE"
    )


def downgrade():
    # Drop foreign key constraints first
    op.drop_constraint("item_owner_id_fkey", "item", type_="foreignkey")

    # Add UUID columns back
    op.add_column(
        "user",
        sa.Column(
            "old_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
    )

    op.add_column(
        "item",
        sa.Column(
            "old_owner_id",
            postgresql.UUID(as_uuid=True),
            nullable=True
        ),
    )

    # Populate the UUID columns with new UUIDs
    op.execute('UPDATE "user" SET old_id = uuid_generate_v4()')
    op.execute(
        'UPDATE item SET old_owner_id = (SELECT old_id FROM "user" WHERE "user".id = item.owner_id)'
    )

    # Drop the integer columns and rename the UUID columns back
    op.drop_constraint("user_pkey", "user", type_="primary")
    op.drop_column("user", "id")
    op.alter_column("user", "old_id", new_column_name="id")
    op.drop_column("item", "owner_id")
    op.alter_column("item", "old_owner_id", new_column_name="owner_id")

    # Create primary key constraint on the UUID column
    op.create_primary_key("user_pkey", "user", ["id"])

    # Recreate foreign key constraints
    op.create_foreign_key(
        "item_owner_id_fkey",
        "item",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE"
    ) 