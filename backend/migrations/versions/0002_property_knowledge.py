"""Add synthetic property inventory and document metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0002_property_knowledge"
down_revision = "0001_voice_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("properties", sa.Column("id", sa.String(64), primary_key=True),
                    sa.Column("name", sa.String(120), nullable=False), sa.Column("location", sa.String(120), nullable=False),
                    sa.Column("type", sa.String(30), nullable=False), sa.Column("status", sa.String(30), nullable=False),
                    sa.Column("possession", sa.String(80), nullable=False), sa.Column("amenities", sa.JSON(), nullable=False),
                    sa.Column("connectivity", sa.String(250), nullable=False), sa.Column("payment", sa.String(250), nullable=False))
    op.create_index("ix_properties_location", "properties", ["location"])
    op.create_table("property_units", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("property_id", sa.String(64), sa.ForeignKey("properties.id"), nullable=False),
                    sa.Column("configuration", sa.String(30), nullable=False), sa.Column("price_inr", sa.Integer(), nullable=False),
                    sa.Column("carpet_sqft", sa.Integer(), nullable=False), sa.Column("available", sa.Integer(), nullable=False),
                    sa.UniqueConstraint("property_id", "configuration"))
    op.create_index("ix_property_units_property_id", "property_units", ["property_id"])
    op.create_table("knowledge_documents", sa.Column("id", sa.String(160), primary_key=True),
                    sa.Column("source", sa.String(250), nullable=False), sa.Column("category", sa.String(40), nullable=False),
                    sa.Column("property_id", sa.String(64)), sa.Column("content_hash", sa.String(64), nullable=False),
                    sa.Column("chunk_count", sa.Integer(), nullable=False), sa.Column("status", sa.String(20), nullable=False))


def downgrade() -> None:
    op.drop_table("knowledge_documents")
    op.drop_index("ix_property_units_property_id", table_name="property_units")
    op.drop_table("property_units")
    op.drop_index("ix_properties_location", table_name="properties")
    op.drop_table("properties")
