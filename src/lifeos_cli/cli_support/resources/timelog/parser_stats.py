"""Builder helpers for timelog stats commands."""

from __future__ import annotations

import argparse
from datetime import date
from functools import partial

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.parser_common import (
    add_date_range_arguments,
    add_start_end_date_arguments,
)
from lifeos_cli.cli_support.resources.timelog.handlers import (
    handle_timelog_stats_day_async,
    handle_timelog_stats_period_async,
    handle_timelog_stats_range_async,
    handle_timelog_stats_rebuild_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def _month_value(value: str) -> date:
    """Parse a YYYY-MM month value."""
    return date.fromisoformat(f"{value}-01")


def build_timelog_stats_parser(
    timelog_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the timelog stats command tree."""
    stats_parser = add_documented_help_parser(
        timelog_subparsers,
        "stats",
        help_content=HelpContent(
            summary=_("resources.timelog.parser_stats.query_timelog_stats_grouped_by_area_summary"),
            description=_("resources.timelog.parser_stats.query_timelog_stats_grouped_by_area"),
            examples=(
                "lifeos timelog stats day --help",
                "lifeos timelog stats range --help",
                "lifeos timelog stats rebuild --help",
            ),
            notes=(
                _(
                    "resources.timelog.parser_stats.use_day_week_month_and_year_for_calendar_based_views"
                ),
                _(
                    "resources.timelog.parser_stats.use_range_for_arbitrary_windows_and_rebuild_to_refresh_persisted_stats"
                ),
                _(
                    "resources.timelog.parser_stats.mayan_day_out_of_time_excluded_from_week_and_month"
                ),
                _(
                    "resources.timelog.parser_stats.stats_are_grouped_only_by_area_task_effort_remains_separate_task_feature"
                ),
                _(
                    "resources.timelog.parser_stats.run_timelog_stats_rebuild_after_upgrading_older_datasets_or_importing_historical_timelogs"
                ),
            ),
        ),
    )
    stats_subparsers = stats_parser.add_subparsers(
        dest="timelog_stats_command",
        title=_("resources.timelog.parser_stats.stats_actions"),
        metavar=_("resources.timelog.parser_stats.stats_action"),
    )

    stats_day_parser = add_documented_parser(
        stats_subparsers,
        "day",
        help_content=HelpContent(
            summary=_(
                "resources.timelog.parser_stats.show_one_day_of_timelog_stats_grouped_by_area"
            ),
            description=_(
                "resources.timelog.parser_stats.show_one_local_operational_day_of_timelog_stats_grouped_by_area"
            ),
            examples=("lifeos timelog stats day --date 2026-04-10",),
        ),
    )
    stats_day_parser.add_argument(
        "--date",
        dest="target_date",
        required=True,
        type=date.fromisoformat,
        help=_("resources.timelog.parser_stats.local_operational_date_in_yyyy_mm_dd_format"),
    )
    stats_day_parser.set_defaults(handler=make_sync_handler(handle_timelog_stats_day_async))

    stats_range_parser = add_documented_parser(
        stats_subparsers,
        "range",
        help_content=HelpContent(
            summary=_(
                "resources.timelog.parser_stats.show_date_range_of_timelog_stats_grouped_by_area"
            ),
            description=_(
                "resources.timelog.parser_stats.show_one_local_date_range_of_timelog_stats_grouped_by_area"
            ),
            examples=("lifeos timelog stats range --start-date 2026-04-01 --end-date 2026-04-30",),
            notes=(_("common.messages.use_start_date_end_date_for_inclusive_local_date_range"),),
        ),
    )
    add_start_end_date_arguments(
        stats_range_parser,
        start_date_help=_("common.messages.inclusive_local_date_range_start_date"),
        end_date_help=_("common.messages.inclusive_local_date_range_end_date"),
    )
    stats_range_parser.set_defaults(handler=make_sync_handler(handle_timelog_stats_range_async))

    stats_week_parser = add_documented_parser(
        stats_subparsers,
        "week",
        help_content=HelpContent(
            summary=_(
                "resources.timelog.parser_stats.show_one_week_of_timelog_stats_grouped_by_area"
            ),
            description=_(
                "resources.timelog.parser_stats.show_one_configured_local_week_of_timelog_stats_grouped_by_area"
            ),
            examples=("lifeos timelog stats week --date 2026-04-10",),
            notes=(
                _(
                    "resources.timelog.parser_stats.the_week_boundary_follows_configured_week_starts_on_preference"
                ),
            ),
        ),
    )
    stats_week_parser.add_argument(
        "--date",
        dest="target_date",
        required=True,
        type=date.fromisoformat,
        help=_("resources.timelog.parser_stats.reference_local_date_in_yyyy_mm_dd_format"),
    )
    stats_week_parser.set_defaults(
        handler=make_sync_handler(partial(handle_timelog_stats_period_async, granularity="week"))
    )

    stats_month_parser = add_documented_parser(
        stats_subparsers,
        "month",
        help_content=HelpContent(
            summary=_(
                "resources.timelog.parser_stats.show_one_month_of_timelog_stats_grouped_by_area"
            ),
            description=_(
                "resources.timelog.parser_stats.show_one_calendar_month_of_timelog_stats_grouped_by_area"
            ),
            examples=("lifeos timelog stats month --month 2026-04",),
        ),
    )
    stats_month_parser.add_argument(
        "--month",
        required=True,
        type=_month_value,
        help=_("resources.timelog.parser_stats.calendar_month_in_yyyy_mm_format"),
    )
    stats_month_parser.set_defaults(
        handler=make_sync_handler(partial(handle_timelog_stats_period_async, granularity="month"))
    )

    stats_year_parser = add_documented_parser(
        stats_subparsers,
        "year",
        help_content=HelpContent(
            summary=_(
                "resources.timelog.parser_stats.show_one_year_of_timelog_stats_grouped_by_area"
            ),
            description=_(
                "resources.timelog.parser_stats.show_one_calendar_year_of_timelog_stats_grouped_by_area"
            ),
            examples=("lifeos timelog stats year --year 2026",),
        ),
    )
    stats_year_parser.add_argument(
        "--year",
        required=True,
        type=int,
        help=_("resources.timelog.parser_stats.calendar_year_for_example_2026"),
    )
    stats_year_parser.set_defaults(
        handler=make_sync_handler(partial(handle_timelog_stats_period_async, granularity="year"))
    )

    stats_rebuild_parser = add_documented_parser(
        stats_subparsers,
        "rebuild",
        help_content=HelpContent(
            summary=_(
                "resources.timelog.parser_stats.rebuild_persisted_timelog_stats_grouped_by_area"
            ),
            description=(
                _(
                    "resources.timelog.parser_stats.rebuild_persisted_day_week_month_and_year_timelog_stats_grouped_by_area"
                )
            ),
            examples=(
                "lifeos timelog stats rebuild --date 2026-04-10",
                "lifeos timelog stats rebuild --date 2026-01-01 --date 2026-03-31",
                "lifeos timelog stats rebuild --start-date 2026-01-01 --end-date 2026-03-31",
                "lifeos timelog stats rebuild --all",
            ),
            notes=(
                _(
                    "resources.timelog.parser_stats.use_rebuild_after_upgrading_older_datasets_or_importing_historical_timelogs"
                ),
                _(
                    "resources.timelog.parser_stats.rebuild_uses_configured_timezone_and_day_starts_at_preference"
                ),
                _("resources.timelog.parser_stats.repeat_date_for_rebuild_dates"),
                _("common.messages.use_start_date_end_date_for_inclusive_local_date_range"),
            ),
        ),
    )
    add_date_range_arguments(
        stats_rebuild_parser,
        date_help=_("resources.timelog.parser_stats.repeat_for_one_or_more_rebuild_dates"),
    )
    add_start_end_date_arguments(
        stats_rebuild_parser,
        start_date_help=_("common.messages.inclusive_local_date_range_start_date"),
        end_date_help=_("common.messages.inclusive_local_date_range_end_date"),
    )
    stats_rebuild_parser.add_argument(
        "--all",
        dest="rebuild_all",
        action="store_true",
        help=_(
            "resources.timelog.parser_stats.rebuild_every_local_date_touched_by_active_timelogs_with_linked_areas"
        ),
    )
    stats_rebuild_parser.set_defaults(handler=make_sync_handler(handle_timelog_stats_rebuild_async))
