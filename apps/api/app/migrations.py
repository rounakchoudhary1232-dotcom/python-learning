"""Small, append-only schema bootstrap for the MVP.

It only creates missing tables and records the current schema version; it never
drops, truncates, or recreates existing user data. Add numbered upgrade steps
here before changing persistent models in future phases.
"""
from sqlalchemy import Column, Integer, MetaData, Table, select
from .database import Base, engine

SCHEMA_VERSION = 2
metadata = MetaData()
versions = Table("schema_migrations", metadata, Column("version", Integer, primary_key=True))


def upgrade_database() -> None:
    metadata.create_all(engine, tables=[versions], checkfirst=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    with engine.begin() as connection:
        applied = {row[0] for row in connection.execute(select(versions.c.version))}
        if SCHEMA_VERSION not in applied:
            connection.execute(versions.insert().values(version=SCHEMA_VERSION))
