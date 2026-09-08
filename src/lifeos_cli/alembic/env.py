"""Alembic environment configuration for lifeos_cli."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

configured_url = config.get_main_option("sqlalchemy.url")

import lifeos_cli.db.models  # noqa: F401, E402
from lifeos_cli.config import get_database_settings, normalize_database_schema  # noqa: E402
from lifeos_cli.db.base import Base  # noqa: E402
from lifeos_cli.db.session import configure_async_engine  # noqa: E402

settings = get_database_settings()
if not configured_url:
    configured_url = settings.require_database_url()
    config.set_main_option("sqlalchemy.url", configured_url)
database_schema = normalize_database_schema(
    database_url=configured_url,
    configured_schema=settings.database_schema,
    explicit=False,
)
target_metadata = Base.metadata


def _include_application_object(
    _object: object,
    name: str | None,
    type_: str,
    _reflected: bool,
    _compare_to: object | None,
) -> bool:
    """Exclude Alembic's own revision table from application schema comparison."""
    return type_ != "table" or name != "alembic_version"


def _configure_migration_context(connection: Connection) -> None:
    if database_schema is not None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=_include_application_object,
            version_table_schema=database_schema,
        )
        return
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=_include_application_object,
    )


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    if database_schema is not None:
        context.configure(
            url=configured_url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=True,
            compare_server_default=True,
            include_object=_include_application_object,
            version_table_schema=database_schema,
        )
    else:
        context.configure(
            url=configured_url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=True,
            compare_server_default=True,
            include_object=_include_application_object,
        )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations using one established sync connection."""
    if database_schema is not None:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{database_schema}"'))
        connection.commit()
        if connection.dialect.name == "postgresql":
            quoted_schema = connection.dialect.identifier_preparer.quote_schema(database_schema)
            connection.exec_driver_sql(f"SET search_path TO {quoted_schema}")
            connection.commit()
            # Alembic autogenerate compares schema identity before applying SQLAlchemy's
            # schema translation. Treat the isolated LifeOS schema as PostgreSQL's
            # default so model tables declared without a schema match reflected tables.
            connection.dialect.default_schema_name = database_schema
            if connection.dialect.default_schema_name != database_schema:
                raise RuntimeError("Could not configure PostgreSQL schema reflection.")
    _configure_migration_context(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create one async engine and run migrations through a sync bridge."""
    connectable = configure_async_engine(
        async_engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
