"""repair findings treatment-item foreign key

Revision ID: 4f2c9d7e1a10
Revises: 3b805a8b02ae
"""
from alembic import op
import sqlalchemy as sa
revision = "4f2c9d7e1a10"
down_revision = "3b805a8b02ae"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("findings", schema=None) as batch_op:
        batch_op.create_foreign_key("fk_findings_treatment_item_id", "treatment_items", ["treatment_item_id"], ["id"])

def downgrade() -> None:
    with op.batch_alter_table("findings", schema=None) as batch_op:
        batch_op.drop_constraint("fk_findings_treatment_item_id", type_="foreignkey")
