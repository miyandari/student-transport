"""merge assignment migration heads

Revision ID: 1881a4d6b546
Revises: 6315d7341ecb, 7c4f91a82e16
Create Date: 2026-10-27 03:19:41.206725

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1881a4d6b546'
down_revision: Union[str, Sequence[str], None] = ('6315d7341ecb', '7c4f91a82e16')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
