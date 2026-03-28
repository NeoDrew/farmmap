"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-28
"""
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

logger = logging.getLogger(__name__)

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_postgis(conn) -> bool:
    """Check if PostGIS extension is available."""
    try:
        result = conn.execute(
            sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'postgis'")
        ).fetchone()
        return result is not None
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()
    postgis_available = _has_postgis(conn)

    if postgis_available:
        try:
            op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            logger.info("PostGIS extension enabled")
        except Exception as e:
            logger.warning("Could not enable PostGIS: %s — continuing without it", e)
            postgis_available = False
    else:
        logger.info("PostGIS not available on this database, using lat/lng only")

    op.create_table(
        "companies",
        sa.Column("company_number", sa.String(8), primary_key=True),
        sa.Column("company_name", sa.Text, nullable=False),
        sa.Column("status", sa.String(50)),
        sa.Column("sic_codes", postgresql.ARRAY(sa.String(10))),
        sa.Column("postcode", sa.String(10)),
        sa.Column("registered_address", postgresql.JSONB),
        sa.Column("lat", sa.Float),
        sa.Column("lng", sa.Float),
        sa.Column("geocode_quality", sa.String(20)),
        sa.Column("last_accounts_date", sa.Date),
        sa.Column("next_accounts_due", sa.Date),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    if postgis_available:
        try:
            op.execute("SELECT AddGeometryColumn('companies', 'geom', 4326, 'POINT', 2)")
            op.execute("CREATE INDEX idx_companies_geom ON companies USING GIST (geom)")
        except Exception as e:
            logger.warning("Could not add PostGIS geometry column: %s", e)

    op.execute("CREATE INDEX idx_companies_postcode ON companies (postcode)")
    op.execute("CREATE INDEX idx_companies_lat_lng ON companies (lat, lng)")

    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("company_number", sa.String(8), nullable=False, index=True),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("parse_source", sa.String(10)),
        sa.Column("parse_status", sa.String(20)),
        sa.Column("turnover", sa.Numeric(18, 2)),
        sa.Column("total_assets", sa.Numeric(18, 2)),
        sa.Column("net_assets", sa.Numeric(18, 2)),
        sa.Column("total_liabilities", sa.Numeric(18, 2)),
        sa.Column("employees", sa.Integer),
        sa.Column("raw_filing_url", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["company_number"], ["companies.company_number"]),
        sa.UniqueConstraint("company_number", "period_end", name="uq_accounts_company_period"),
    )
    op.create_index("idx_accounts_company_period", "accounts", ["company_number", "period_end"])

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("flow_name", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("companies_processed", sa.Integer),
        sa.Column("accounts_parsed", sa.Integer),
        sa.Column("parse_ok", sa.Integer),
        sa.Column("parse_partial", sa.Integer),
        sa.Column("parse_failed", sa.Integer),
        sa.Column("error_message", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("pipeline_runs")
    op.drop_table("accounts")
    try:
        op.execute("SELECT DropGeometryColumn('companies', 'geom')")
    except Exception:
        pass
    op.drop_table("companies")
