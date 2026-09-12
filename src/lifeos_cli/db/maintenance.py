"""Database maintenance helpers for setup and diagnostics."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from importlib.resources import as_file, files

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from lifeos_cli.config import (
    ensure_database_driver_available,
    ensure_database_url_storage_ready,
    get_database_settings,
)
from lifeos_cli.db.services.derived_audit import audit_derived_data, audit_soft_deleted_references
from lifeos_cli.db.services.hierarchy import (
    HierarchyValidationError,
    validate_persisted_hierarchies,
)
from lifeos_cli.db.services.integrity_audit import audit_referential_integrity
from lifeos_cli.db.services.task_effort import rebuild_task_efforts
from lifeos_cli.db.services.write_locks import lock_planning_writes
from lifeos_cli.db.session import get_async_engine, get_async_session_factory


@dataclass(frozen=True)
class DatabaseCheckReport:
    """Operational database checks suitable for CLI reporting."""

    dialect: str
    current_revision: str | None
    head_revision: str
    storage_issues: tuple[str, ...]
    association_issues: tuple[str, ...]
    association_warnings: tuple[str, ...]
    repaired_count: int
    hierarchy_issues: tuple[str, ...] = ()
    derived_issues: tuple[str, ...] = ()
    data_warnings: tuple[str, ...] = ()
    rebuilt_task_count: int = 0

    @property
    def ok(self) -> bool:
        """Return whether schema, storage, and weak references are healthy."""
        return (
            self.current_revision == self.head_revision
            and not self.storage_issues
            and not self.association_issues
            and not self.hierarchy_issues
            and not self.derived_issues
        )


async def ping_database() -> None:
    """Validate that the configured database is reachable."""
    engine = get_async_engine()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def check_database(
    *, repair: bool = False, rebuild_effort: bool = False
) -> DatabaseCheckReport:
    """Check migration state, backend integrity, and polymorphic references."""
    settings = get_database_settings()
    database_url = settings.require_database_url()
    with ExitStack() as stack:
        alembic_config = build_alembic_config(sqlalchemy_url=database_url, stack=stack)
        head_revision = ScriptDirectory.from_config(alembic_config).get_current_head()
        if head_revision is None:
            raise RuntimeError("Packaged Alembic migrations do not define a head revision.")

    engine = get_async_engine()
    storage_issues: list[str] = []
    async with engine.connect() as connection:
        dialect = connection.dialect.name

        def current_revision(sync_connection) -> str | None:
            context = MigrationContext.configure(
                sync_connection,
                opts={"version_table_schema": settings.database_schema},
            )
            return context.get_current_revision()

        revision = await connection.run_sync(current_revision)
        if dialect == "sqlite":
            quick_check = (await connection.execute(text("PRAGMA quick_check"))).scalars().all()
            storage_issues.extend(str(value) for value in quick_check if str(value).lower() != "ok")
            foreign_key_rows = (await connection.execute(text("PRAGMA foreign_key_check"))).all()
            storage_issues.extend(
                "Foreign-key violation: " + ", ".join(str(value) for value in row)
                for row in foreign_key_rows
            )

    association_issues: tuple[str, ...] = ()
    association_warnings: tuple[str, ...] = ()
    repaired_count = 0
    hierarchy_issues: list[str] = []
    derived_issues: tuple[str, ...] = ()
    data_warnings: tuple[str, ...] = ()
    rebuilt_task_count = 0
    if revision == head_revision:
        session = get_async_session_factory()()
        try:
            await lock_planning_writes(session)
            for task_hierarchy in (True, False):
                try:
                    await validate_persisted_hierarchies(
                        session, tasks=task_hierarchy, finance=not task_hierarchy
                    )
                except HierarchyValidationError as exc:
                    hierarchy_issues.append(str(exc))
            audit = await audit_referential_integrity(
                session,
                repair=repair and not storage_issues,
            )
            data_warnings = await audit_soft_deleted_references(session)
            try:
                if rebuild_effort and not storage_issues:
                    rebuilt_task_count = await rebuild_task_efforts(session)
                derived_issues, experience_warnings = await audit_derived_data(session)
                data_warnings += experience_warnings
            except HierarchyValidationError as exc:
                derived_issues = (f"Effort audit/rebuild blocked: {exc}",)
            if (repair or rebuild_effort) and not storage_issues:
                repaired_count = audit.repaired_count
                audit = await audit_referential_integrity(session, repair=False)
                await session.commit()
            else:
                await session.rollback()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        association_issues = tuple(
            issue.message for issue in audit.issues if not issue.kind.startswith("soft_deleted_")
        )
        association_warnings = tuple(
            issue.message for issue in audit.issues if issue.kind.startswith("soft_deleted_")
        )
    return DatabaseCheckReport(
        dialect=dialect,
        current_revision=revision,
        head_revision=head_revision,
        storage_issues=tuple(storage_issues),
        association_issues=association_issues,
        association_warnings=association_warnings,
        repaired_count=repaired_count,
        hierarchy_issues=tuple(hierarchy_issues),
        derived_issues=derived_issues,
        data_warnings=data_warnings,
        rebuilt_task_count=rebuilt_task_count,
    )


def build_alembic_config(*, sqlalchemy_url: str, stack: ExitStack) -> Config:
    """Build an Alembic config backed by packaged migration resources."""
    script_location = stack.enter_context(as_file(files("lifeos_cli.alembic")))
    alembic_config = Config()
    alembic_config.set_main_option("script_location", str(script_location))
    alembic_config.set_main_option("sqlalchemy.url", sqlalchemy_url)
    return alembic_config


def upgrade_database(revision: str = "head") -> None:
    """Apply Alembic migrations to the configured database."""
    settings = get_database_settings()
    database_url = settings.require_database_url()
    ensure_database_driver_available(database_url)
    ensure_database_url_storage_ready(database_url)
    with ExitStack() as stack:
        alembic_config = build_alembic_config(
            sqlalchemy_url=database_url,
            stack=stack,
        )
        command.upgrade(alembic_config, revision)
