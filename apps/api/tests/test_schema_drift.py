"""Live database (built from Prisma's migrations) ↔ SQLAlchemy models.

Alembic is used as a library only (compare_metadata); it never runs a migration.
"""

import enum

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import Base


def _diff(sync_conn: Connection) -> list[object]:
    ctx = MigrationContext.configure(
        sync_conn,
        opts={
            "compare_type": True,
            "include_name": lambda name, type_, _: not (type_ == "table" and name == "_prisma_migrations"),
        },
    )
    return list(compare_metadata(ctx, Base.metadata))


async def test_models_match_prisma_migrations(migrated_engine: AsyncEngine) -> None:
    async with migrated_engine.connect() as conn:
        assert await conn.run_sync(_diff) == []


def _mapped_enums() -> dict[str, type[enum.Enum]]:
    found: dict[str, type[enum.Enum]] = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, ENUM) and column.type.enum_class is not None:
                found[column.type.name] = column.type.enum_class
    return found


@pytest.mark.parametrize("type_name", sorted(_mapped_enums()))
async def test_enum_values_match_pg_enum(migrated_engine: AsyncEngine, type_name: str) -> None:
    # compare_metadata doesn't compare enum *values*.
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = :name ORDER BY e.enumsortorder"
            ),
            {"name": type_name},
        )
        db_values = [r[0] for r in rows]
    assert db_values == [m.value for m in _mapped_enums()[type_name]]
