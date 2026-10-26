from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7c4f91a82e16"
down_revision = "2be24ae39601"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_trip_assignments_active_trip",
        "trip_assignments",
        ["trip_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade():
    op.drop_index(
        "uq_trip_assignments_active_trip",
        table_name="trip_assignments",
    )