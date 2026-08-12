"""Migrate entity-to-person links into associations and archive person_associations.

The historical ``person_associations`` table is renamed to an archive table
instead of being dropped, so no existing row can be lost during the upgrade.
Rows whose ``entity_type`` is not representable in ``associations`` stay in
the archive untouched; supported rows are copied (with deduplication) into
``associations`` as ``target_model='person'`` links with ``link_type='is_about'``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "20260812_1200"
down_revision = "20260704_1500"
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)

_SOURCE_MODEL_VALUES = (
    "'event', 'habit_action', 'note', 'person', 'tag', 'task', "
    "'timelog', 'timelog_template', 'vision'"
)
_LEGACY_SOURCE_MODEL_VALUES = (
    "'event', 'habit_action', 'note', 'person', 'task', 'timelog', 'vision'"
)
_PERSON_TARGET_MODEL = "person"
_PERSON_LINK_TYPE = "is_about"
_ARCHIVE_TABLE_NAME = "person_associations_legacy_20260812"
_INSERT_BATCH_SIZE = 500
#: Entity types accepted as association source models after this migration.
_MIGRATED_ENTITY_TYPES = frozenset(
    {
        "event",
        "habit_action",
        "note",
        "person",
        "tag",
        "task",
        "timelog",
        "timelog_template",
        "vision",
    }
)
#: Entity types that historically lived in ``person_associations`` and must be
#: pruned from ``associations`` again on downgrade. Notes and person-to-person
#: links always lived in ``associations`` and stay there.
_LEGACY_PERSON_ASSOCIATION_TYPES = frozenset(
    {"event", "tag", "task", "timelog", "timelog_template", "vision"}
)


def _schema_name() -> str | None:
    context = op.get_context()
    return context.version_table_schema


def _associations_table(schema_name: str | None) -> sa.TableClause:
    return sa.table(
        "associations",
        sa.column("id", sa.Uuid()),
        sa.column("source_model", sa.String()),
        sa.column("source_id", sa.Uuid()),
        sa.column("target_model", sa.String()),
        sa.column("target_id", sa.Uuid()),
        sa.column("link_type", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        schema=schema_name,
    )


def _person_associations_table(
    table_name: str,
    schema_name: str | None,
) -> sa.TableClause:
    return sa.table(
        table_name,
        sa.column("entity_type", sa.String()),
        sa.column("entity_id", sa.Uuid()),
        sa.column("person_id", sa.Uuid()),
        schema=schema_name,
    )


def _migrate_person_links(schema_name: str | None) -> None:
    connection = op.get_bind()
    person_associations = _person_associations_table("person_associations", schema_name)
    associations = _associations_table(schema_name)
    existing_rows = connection.execute(
        sa.select(
            associations.c.source_model,
            associations.c.source_id,
            associations.c.target_id,
        ).where(associations.c.target_model == _PERSON_TARGET_MODEL)
    ).all()
    existing = {
        (source_model, source_id, target_id) for source_model, source_id, target_id in existing_rows
    }

    rows = connection.execute(
        sa.select(
            person_associations.c.entity_type,
            person_associations.c.entity_id,
            person_associations.c.person_id,
        )
    ).all()
    now = datetime.now(UTC)
    copied = 0
    skipped = 0
    insert_rows: list[dict[str, object]] = []
    for entity_type, entity_id, person_id in rows:
        if entity_type not in _MIGRATED_ENTITY_TYPES:
            skipped += 1
            continue
        if (entity_type, entity_id, person_id) in existing:
            continue
        insert_rows.append(
            {
                "id": uuid4(),
                "source_model": entity_type,
                "source_id": entity_id,
                "target_model": _PERSON_TARGET_MODEL,
                "target_id": person_id,
                "link_type": _PERSON_LINK_TYPE,
                "created_at": now,
                "updated_at": now,
            }
        )
        copied += 1
        if len(insert_rows) >= _INSERT_BATCH_SIZE:
            connection.execute(associations.insert(), insert_rows)
            insert_rows = []
    if insert_rows:
        connection.execute(associations.insert(), insert_rows)
    if skipped:
        logger.warning(
            "Skipped %s person_associations rows with unsupported entity types; "
            "they remain preserved in %s",
            skipped,
            _ARCHIVE_TABLE_NAME,
        )
    logger.info("Migrated %s entity-to-person links into associations", copied)


def _prune_migrated_person_links(schema_name: str | None) -> None:
    """Remove from associations the rows that the upgrade copied from the archive."""
    connection = op.get_bind()
    person_associations = _person_associations_table("person_associations", schema_name)
    associations = _associations_table(schema_name)
    archive_match = sa.exists(
        sa.select(1).where(
            person_associations.c.entity_type == associations.c.source_model,
            person_associations.c.entity_id == associations.c.source_id,
            person_associations.c.person_id == associations.c.target_id,
        )
    )
    connection.execute(
        associations.delete().where(
            associations.c.target_model == _PERSON_TARGET_MODEL,
            associations.c.source_model.in_(sorted(_LEGACY_PERSON_ASSOCIATION_TYPES)),
            archive_match,
        )
    )


def upgrade() -> None:
    schema_name = _schema_name()

    with op.batch_alter_table("associations", schema=schema_name) as batch_op:
        batch_op.drop_constraint(
            "ck_associations_source_model_valid",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_associations_source_model_valid",
            f"source_model IN ({_SOURCE_MODEL_VALUES})",
        )

    _migrate_person_links(schema_name)

    op.rename_table(
        "person_associations",
        _ARCHIVE_TABLE_NAME,
        schema=schema_name,
    )


def downgrade() -> None:
    schema_name = _schema_name()

    op.rename_table(
        _ARCHIVE_TABLE_NAME,
        "person_associations",
        schema=schema_name,
    )

    _prune_migrated_person_links(schema_name)

    with op.batch_alter_table("associations", schema=schema_name) as batch_op:
        batch_op.drop_constraint(
            "ck_associations_source_model_valid",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_associations_source_model_valid",
            f"source_model IN ({_LEGACY_SOURCE_MODEL_VALUES})",
        )
