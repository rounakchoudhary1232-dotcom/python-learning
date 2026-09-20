"""Small, append-only schema bootstrap for the MVP.

It only creates missing tables and records the current schema version; it never
drops, truncates, or recreates existing user data. Add numbered upgrade steps
here before changing persistent models in future phases.
"""
from sqlalchemy import Column, Integer, MetaData, Table, select, text
from .database import Base, engine

SCHEMA_VERSION = 4
metadata = MetaData()
versions = Table("schema_migrations", metadata, Column("version", Integer, primary_key=True))


def upgrade_database() -> None:
    metadata.create_all(engine, tables=[versions], checkfirst=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    with engine.begin() as connection:
        # Existing SQLite databases predate the model constraint; add the
        # equivalent index without rebuilding or deleting any user data.
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_market_data_candle ON market_data (instrument_id, timeframe, timestamp)"))
        applied = {row[0] for row in connection.execute(select(versions.c.version))}
        if SCHEMA_VERSION not in applied:
            connection.execute(versions.insert().values(version=SCHEMA_VERSION))
