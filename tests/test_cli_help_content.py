from __future__ import annotations

import pytest

from lifeos_cli.cli import build_parser
from lifeos_cli.cli_support.parser import build_cli_brand_banner, get_cli_brand_banner_width


def test_cli_top_level_help_describes_command_grammar(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])

    captured = capsys.readouterr()

    assert "██╗     ██╗███████╗███████╗ ██████╗ ███████╗" in captured.out
    assert "███████╗██║██║     ███████╗╚██████╔╝███████║" in captured.out
    assert "usage:" not in captured.out
    assert "Run LifeOS resource commands from the terminal." not in captured.out
    assert "repo: https://github.com/lifeos-plus/lifeos-cli" in captured.out
    assert "uv tool install --upgrade lifeos-cli" in captured.out
    assert "lifeos <resource> <action> [arguments] [options]" in captured.out
    assert "Resources model domains" not in captured.out
    assert "resources:" in captured.out
    assert "resources:\n  resource" not in captured.out
    assert "init" in captured.out
    assert "schedule" in captured.out
    assert "task" in captured.out
    assert "primary command reference" in captured.out
    assert "Run `lifeos init` to initialize LifeOS before getting started." in captured.out
    assert (
        "Welcome bug reports and suggestions through https://github.com/lifeos-plus/lifeos-cli."
        in captured.out
    )
    assert (
        "repo: https://github.com/lifeos-plus/lifeos-cli\nuv tool install --upgrade lifeos-cli"
        in captured.out
    )
    assert "\n  lifeos <resource> <action> [arguments] [options]" in captured.out
    assert 'lifeos note add "Capture an idea"' in captured.out


def test_cli_brand_banner_uses_ansi_shadow_font() -> None:
    banner = build_cli_brand_banner()
    banner_lines = banner.splitlines()

    assert "██╗     ██╗███████╗███████╗ ██████╗ ███████╗" in banner
    assert banner_lines[-2] == "╚══════╝╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚══════╝"
    assert get_cli_brand_banner_width() == 44


def test_cli_init_help_avoids_hard_wrapped_description_fragments(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["init", "--help"])

    captured = capsys.readouterr()

    assert (
        "Create or update the local LifeOS config file and verify that the database is reachable."
        in captured.out
    )
    assert "--database-url DATABASE_URL           " in captured.out
    assert "When no database URL is configured yet" in captured.out
    assert (
        "Create or update the local LifeOS config file and verify that the database\nis reachable."
        not in captured.out
    )


def test_cli_config_help_avoids_hard_wrapped_description_fragments(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["config", "--help"])

    captured = capsys.readouterr()

    assert (
        "Inspect the effective configuration resolved from the config file and "
        "environment variables." in captured.out
    )
    assert (
        "Inspect the effective configuration resolved from the config file and\n"
        "environment variables." not in captured.out
    )


def test_cli_note_add_help_avoids_hard_wrapped_description_fragments(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["note", "add", "--help"])

    captured = capsys.readouterr()

    assert (
        "Use this action to capture short thoughts, prompts, or raw text before linking them "
        "to tasks, people, or timelogs."
    ) in captured.out
    assert (
        "Use this action to capture short thoughts, prompts, or raw text before linking\nthem"
        not in captured.out
    )


def test_cli_task_help_describes_event_bridge_without_action_level_schedule_contract(
    capsys,
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["task", "--help"])

    captured = capsys.readouterr()

    assert "Use `lifeos event add --task-id <task-id>`" in captured.out
    assert "A task appears in `lifeos schedule show`" not in captured.out


def test_cli_task_add_help_describes_planning_cycle_semantics(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["task", "add", "--help"])

    captured = capsys.readouterr()
    normalized_output = " ".join(captured.out.split())

    assert "Planning cycle type: 7years, year, month, week, or day" in normalized_output
    assert "Start date of the enclosing planning cycle window" in captured.out
    assert "not a clock-time execution slot" in captured.out
    assert "--planning-cycle-type week --planning-cycle-days 7" in captured.out


def test_cli_schedule_show_help_explains_task_inclusion_rule(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["schedule", "show", "--help"])

    captured = capsys.readouterr()

    assert (
        "Overdue unfinished tasks and habit actions also roll forward into non-future "
        "schedule days." in captured.out
    )
    assert "Task rows come from planning-cycle overlap" in captured.out
    assert (
        "Habit action rows use `action_date`; pending rows older than the three-day planning "
        "grace window are reconciled to missed before the schedule is shown." in captured.out
    )
    assert (
        "Task section columns: task_id, status, planning_cycle_type, planning_cycle_start_date, "
        "planning_cycle_end_date, content."
    ) in captured.out
    assert (
        "Habit action section columns: habit_action_id, status, action_date, habit_title."
        in captured.out
    )
    assert (
        "Event section columns: event_id, event_type, start_time, end_time, title."
    ) in captured.out
    assert (
        "When `--date` is omitted, `show` uses the current configured local date." in captured.out
    )
    assert "Event rows stay under the event section and include their `event_type`." in captured.out
    assert "--hide-overdue-unfinished" in captured.out
    assert (
        "Overdue unfinished planning tasks and habit actions are shown by default" in captured.out
    )


def test_cli_habit_task_associations_help_documents_header(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["habit", "task-associations", "--help"])

    captured = capsys.readouterr()

    assert "audit which active habits are still attached to tasks" in captured.out
    assert (
        "tab-separated columns: task_id, habit_id, habit_status, habit_start_date, habit_title."
        in captured.out
    )


def test_cli_vision_with_tasks_help_documents_task_header(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["vision", "with-tasks", "--help"])

    captured = capsys.readouterr()

    assert "tab-separated columns: task_id, status, parent_task_id, content." in captured.out


def test_cli_task_subtree_help_explains_tree_shape(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["task", "with-subtasks", "--help"])

    captured = capsys.readouterr()

    assert "active descendants indented by depth" in captured.out
    assert "completion_percentage" in captured.out
    assert "Use `hierarchy` when you need the full active tree" in captured.out


def test_cli_task_hierarchy_help_explains_scope_boundary(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["task", "hierarchy", "--help"])

    captured = capsys.readouterr()

    assert "The output starts with the vision identifier" in captured.out
    assert "Use `with-subtasks` when you want to inspect only one branch" in captured.out


def test_cli_task_stats_help_explains_aggregation_rules(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["task", "stats", "--help"])

    captured = capsys.readouterr()

    assert (
        "Totals aggregate the selected task together with all active descendants." in captured.out
    )
    assert "`completion_percentage` measures how many of those children are done." in captured.out


def test_cli_habit_stats_help_explains_derived_metrics(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["habit", "stats", "--help"])

    captured = capsys.readouterr()

    assert (
        "derived from cadence settings together with materialized `habit-action` records"
        in captured.out
    )
    assert "Use `show` when you also need the underlying habit fields" in captured.out


def test_cli_vision_stats_help_explains_scope_boundary(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["vision", "stats", "--help"])

    captured = capsys.readouterr()

    assert (
        "Counts and effort totals aggregate all active tasks linked to the vision." in captured.out
    )
    assert (
        "Use `with-tasks` when you need the row-level task list instead of totals." in captured.out
    )


def test_cli_vision_sync_experience_help_explains_when_to_use(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["vision", "sync-experience", "--help"])

    captured = capsys.readouterr()

    assert "Use this after task effort changes" in captured.out
    assert "otherwise from preferences" in captured.out


def test_cli_vision_harvest_help_explains_readiness_and_effect(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["vision", "harvest", "--help"])

    captured = capsys.readouterr()

    assert "only when the vision is active and already at final stage" in captured.out
    assert "changes the vision status from `active` to `fruit`" in captured.out


def test_cli_event_add_help_describes_extended_recurrence_frequencies(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["event", "add", "--help"])

    captured = capsys.readouterr()

    assert "monthly" in captured.out
    assert "yearly" in captured.out


def test_cli_habit_add_help_describes_extended_cadence_cycles(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["habit", "add", "--help"])

    captured = capsys.readouterr()

    assert "monthly" in captured.out
    assert "yearly" in captured.out


def test_cli_schedule_help_explains_show_list_boundary(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["schedule", "show", "--help"])

    captured = capsys.readouterr()

    assert (
        "Use `list` when you need the same schedule view across an inclusive date range."
        in captured.out
    )

    with pytest.raises(SystemExit):
        parser.parse_args(["schedule", "list", "--help"])

    captured = capsys.readouterr()

    expected = "Use `show` when you want the single-day entrypoint with the same sections."
    assert expected in captured.out
    assert "lifeos schedule list --start-date 2026-04-10 --end-date 2026-04-16" in captured.out
    assert "Use either repeated `--date` or `--start-date/--end-date`, not both." in captured.out


def test_cli_habit_action_help_explains_update_log_boundary(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["habit-action", "update", "--help"])

    captured = capsys.readouterr()

    assert "Use `log` when you know the habit and date" in captured.out

    with pytest.raises(SystemExit):
        parser.parse_args(["habit-action", "log", "--help"])

    captured = capsys.readouterr()

    expected = "Use `update` when you already have the materialized action identifier."
    assert expected in captured.out


def test_cli_data_help_explains_machine_workflow_boundaries(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["data", "import", "--help"])

    captured = capsys.readouterr()

    expected = "Use `--dry-run` before applying a large file or a full bundle restore."
    assert expected in captured.out

    with pytest.raises(SystemExit):
        parser.parse_args(["data", "batch-update", "--help"])

    captured = capsys.readouterr()

    assert (
        "Start from `data export` output when preparing machine-generated patch rows."
        in captured.out
    )

    with pytest.raises(SystemExit):
        parser.parse_args(["data", "batch-delete", "--help"])

    captured = capsys.readouterr()

    assert (
        "Use this command for file-driven or machine-generated cleanup across many rows."
        in captured.out
    )
    assert (
        "Use resource-specific delete commands when you want narrower human-guided changes."
        in captured.out
    )
    assert "use `lifeos <resource> delete` instead" in captured.out


def test_resource_batch_delete_help_points_to_data_batch_delete(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["area", "delete", "--help"])

    captured = capsys.readouterr()

    assert "lifeos data batch-delete" in captured.out


def test_cli_vision_experience_help_explains_manual_vs_synced_updates(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["vision", "add-experience", "--help"])

    captured = capsys.readouterr()

    assert "Use this for explicit manual credit" in captured.out
    assert (
        "Use `sync-experience` when experience should be recomputed from task effort."
        in captured.out
    )


def test_cli_task_move_and_reorder_help_explain_boundary(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["task", "move", "--help"])

    captured = capsys.readouterr()

    assert "Use `reorder` when only sibling display order changes" in captured.out
    assert "Use `--old-parent-task-id` as an optimistic guard" in captured.out

    with pytest.raises(SystemExit):
        parser.parse_args(["task", "reorder", "--help"])

    captured = capsys.readouterr()

    assert "This command changes only `display_order`" in captured.out
    assert "Use `move` when parentage or vision membership also needs to change." in captured.out


def test_cli_init_and_config_help_explain_bootstrap_boundary(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["init", "--help"])

    captured = capsys.readouterr()

    assert "Use `config set` for supported follow-up edits" in captured.out

    with pytest.raises(SystemExit):
        parser.parse_args(["config", "--help"])

    captured = capsys.readouterr()

    assert "Use `show` to inspect effective values" in captured.out
    expected = "Use `set` to persist supported keys without re-running the full init flow."
    assert expected in captured.out

    with pytest.raises(SystemExit):
        parser.parse_args(["config", "show", "--help"])

    captured = capsys.readouterr()

    expected = "Use `config set` to persist one supported key after reviewing the current values."
    assert expected in captured.out

    with pytest.raises(SystemExit):
        parser.parse_args(["config", "set", "--help"])

    captured = capsys.readouterr()

    assert "Use `lifeos init` for first-time bootstrap" in captured.out


def test_cli_db_help_explains_ping_upgrade_boundary(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["db", "--help"])

    captured = capsys.readouterr()

    assert "Use `ping` to validate the current connection settings" in captured.out
    expected = "Use `upgrade` when the configured database schema needs to catch up with the code."
    assert expected in captured.out

    with pytest.raises(SystemExit):
        parser.parse_args(["db", "ping", "--help"])

    captured = capsys.readouterr()

    assert "Use this before `db upgrade`" in captured.out

    with pytest.raises(SystemExit):
        parser.parse_args(["db", "upgrade", "--help"])

    captured = capsys.readouterr()

    assert "it does not rewrite local config" in captured.out
    assert "Use `db ping` first" in captured.out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["task", "list", "--help"],
            "tab-separated columns: task_id, status, vision_id, parent_task_id, content.",
        ),
        (
            ["event", "list", "--help"],
            "tab-separated columns: event_id, status, event_type, start_time, end_time, "
            "task_id, title.",
        ),
        (
            ["habit", "list", "--help"],
            "Default list output prints a header row followed by tab-separated columns: "
            "habit_id, status, start_date, duration_days, cadence, task_id, title.",
        ),
        (
            ["note", "list", "--help"],
            "prints a header row followed by tab-separated columns: note_id, status, created_at, "
            "content.",
        ),
    ],
)
def test_cli_summary_list_help_documents_output_columns(
    argv: list[str],
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert expected in captured.out


def test_cli_note_help_avoids_duplicated_action_heading_and_reference_boilerplate(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["note", "--help"])

    captured = capsys.readouterr()

    assert "usage: lifeos note [-h] action ..." in captured.out
    assert "操作:\n  操作" not in captured.out
    assert "The note resource is the reference command family for LifeOS." not in captured.out
    assert "Future resources should follow the same command grammar:" not in captured.out


def test_cli_schedule_list_help_documents_section_headers(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["schedule", "list", "--help"])

    captured = capsys.readouterr()

    assert (
        "Non-empty schedule sections print a tab-separated header row before their entries."
        in captured.out
    )
    assert (
        "Task section columns: task_id, status, planning_cycle_type, planning_cycle_start_date, "
        "planning_cycle_end_date, content."
    ) in captured.out
    assert (
        "Habit action section columns: habit_action_id, status, action_date, habit_title."
        in captured.out
    )
    assert (
        "Event section columns: event_id, event_type, start_time, end_time, title."
    ) in captured.out
    assert "--hide-overdue-unfinished" in captured.out


def test_cli_planning_show_help_documents_window_semantics(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["planning", "show", "--help"])

    captured = capsys.readouterr()

    assert "Show tasks in one calendar-aware planning window" in captured.out
    assert "lifeos planning show --cycle-type 7years" in captured.out
    assert "lifeos planning show --cycle-type year --start 2026-07-26" in captured.out
    assert "planning_cycle_window" in captured.out
    assert "--at" in captured.out and "--start" in captured.out


def test_cli_person_help_describes_human_and_agent_subject_modeling(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["person", "--help"])

    captured = capsys.readouterr()

    assert "human partner and, when useful, a named automation identity" in captured.out
    assert "separate records when both can own work" in captured.out


@pytest.mark.parametrize(
    ("argv", "expected_text"),
    (
        (
            ["task", "add", "--help"],
            "mark whether the task belongs to the human, the agent, or both",
        ),
        (
            ["event", "add", "--help"],
            "keep human-only, agent-only, and shared time blocks distinct",
        ),
        (
            ["timelog", "add", "--help"],
            "state whether the effort belongs to the human, the agent, or both",
        ),
    ),
)
def test_cli_action_help_describes_subject_disambiguation(
    argv: list[str],
    expected_text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert expected_text in captured.out


def test_cli_event_delete_help_describes_recurring_scope_requirements(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["event", "delete", "--help"])

    captured = capsys.readouterr()

    assert "Use `--scope single|all_future|all` for recurring series deletes." in captured.out
    assert "`--scope single` and `--scope all_future` require `--instance-start`." in captured.out
    assert "--scope all_future --instance-start 2026-04-10T09:00:00" in captured.out
    assert "configured timezone is used before the value is converted to UTC" in captured.out


def test_cli_vision_update_help_lists_valid_statuses(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["vision", "update", "--help"])

    captured = capsys.readouterr()

    assert "active`, `archived`, and `fruit`" in captured.out
    assert "--status paused" not in captured.out


def test_cli_note_list_help_explains_output_shape(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["note", "list", "--help"])

    captured = capsys.readouterr()

    assert "prints a header row followed by tab-separated columns" in captured.out
    assert "Use --limit and --offset together for pagination." in captured.out


def test_cli_note_add_help_keeps_init_guidance_out_of_examples(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["note", "add", "--help"])

    captured = capsys.readouterr()

    assert "Run `lifeos init`" not in captured.out
    assert "\n  lifeos init\n" not in captured.out


def test_cli_note_add_help_shows_repeated_relation_flag_usage(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["note", "add", "--help"])

    captured = capsys.readouterr()

    assert (
        'lifeos note add "Review shared feedback" --tag-id <tag-id-1> --tag-id <tag-id-2>'
        in captured.out
    )
    assert "Repeat the same relation flag to link multiple records of that type" in captured.out


def test_cli_timelog_add_help_describes_quick_batch_mode(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["timelog", "add", "--help"])

    captured = capsys.readouterr()

    assert '--entry "0700 Breakfast" --entry "0830 Deep work"' in captured.out
    assert "lifeos timelog add --stdin" in captured.out
    assert "`HHMM Title` means `HHMM` is the segment end time, not the start time" in captured.out
    assert "uses the same parsing rules for `--entry`, `--stdin`, and `--file`" in captured.out
    assert "Rows are previewed before writing by default" in captured.out
    assert "the prompt is skipped for `--stdin` or `--yes`" in captured.out
    assert "latest active timelog end time" in captured.out
    assert "configured timezone is used before the value is converted to UTC" in captured.out


@pytest.mark.parametrize(
    "argv",
    (
        ["event", "add", "--help"],
        ["event", "update", "--help"],
        ["event", "delete", "--help"],
        ["timelog", "add", "--help"],
        ["timelog", "update", "--help"],
    ),
)
def test_cli_event_timelog_help_shows_shared_timezone_note(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert "configured timezone is used before the value is converted to UTC" in captured.out


@pytest.mark.parametrize("argv", (["event", "add", "--help"], ["timelog", "add", "--help"]))
def test_cli_event_timelog_add_help_shows_shared_relation_note(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert (
        "Repeat the same `--tag-id` or `--person-id` flag to attach multiple tags "
        "or people in one command."
    ) in captured.out


@pytest.mark.parametrize("argv", (["event", "list", "--help"], ["timelog", "list", "--help"]))
def test_cli_event_timelog_list_help_shows_shared_date_range_text(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()
    normalized_output = " ".join(captured.out.split())

    assert (
        "Repeat `--date` for one or more discrete local dates. Use "
        "`--start-date/--end-date` for one inclusive local-date range."
    ) in captured.out
    assert "one or more discrete" in normalized_output
    assert "--start-date START_DATE" in normalized_output
    assert "--end-date END_DATE" in normalized_output
    assert "define an overlap window, not exact" in captured.out
    assert "use `--start-date/--end-date` for local-date ranges" in captured.out


def test_cli_timelog_search_help_documents_keyword_advanced_query_entrypoint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["timelog", "search", "--help"])

    captured = capsys.readouterr()

    assert "Search timelogs with optional keyword, time-window, relation, and method filters." in (
        captured.out
    )
    assert (
        'lifeos timelog search --query "洗" --start-time 2026-06-16T16:00:00.000Z '
        "--end-time 2026-06-17T15:59:59.999Z --limit 500 --count"
    ) in captured.out
    assert "This command reuses `timelog list` filters and tab-separated summary output." in (
        captured.out
    )
    assert "`--query` does not search task or area names." in captured.out
    assert "--limit LIMIT" in captured.out
    assert "--count" in captured.out


@pytest.mark.parametrize("argv", (["event", "update", "--help"], ["timelog", "update", "--help"]))
def test_cli_event_timelog_update_help_shows_shared_clear_notes(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert "Use `--clear-*` flags to explicitly remove optional values." in captured.out
    assert (
        "Do not mix a value flag with the matching clear flag in the same command." in captured.out
    )


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["note", "update", "--help"],
            "--tag-id <tag-id-1> --tag-id <tag-id-2>",
        ),
        (
            ["task", "add", "--help"],
            "--person-id 33333333-3333-3333-3333-333333333333 "
            "--person-id 44444444-4444-4444-4444-444444444444",
        ),
        (
            ["task", "update", "--help"],
            "--person-id 33333333-3333-3333-3333-333333333333 "
            "--person-id 44444444-4444-4444-4444-444444444444",
        ),
        (
            ["vision", "add", "--help"],
            "--person-id 11111111-1111-1111-1111-111111111111 "
            "--person-id 22222222-2222-2222-2222-222222222222",
        ),
        (
            ["vision", "update", "--help"],
            "--person-id 11111111-1111-1111-1111-111111111111 "
            "--person-id 22222222-2222-2222-2222-222222222222",
        ),
        (
            ["tag", "add", "--help"],
            "--person-id 11111111-1111-1111-1111-111111111111 "
            "--person-id 22222222-2222-2222-2222-222222222222",
        ),
        (
            ["tag", "update", "--help"],
            "--person-id 11111111-1111-1111-1111-111111111111 "
            "--person-id 22222222-2222-2222-2222-222222222222",
        ),
        (
            ["event", "add", "--help"],
            "--person-id <person-id-1> --person-id <person-id-2> "
            "--tag-id <tag-id-1> --tag-id <tag-id-2>",
        ),
        (
            ["event", "update", "--help"],
            "--person-id <person-id-1> --person-id <person-id-2> "
            "--tag-id <tag-id-1> --tag-id <tag-id-2>",
        ),
        (
            ["timelog", "add", "--help"],
            "--person-id <person-id-1> --person-id <person-id-2> "
            "--tag-id <tag-id-1> --tag-id <tag-id-2>",
        ),
        (
            ["timelog", "update", "--help"],
            "--person-id <person-id-1> --person-id <person-id-2> "
            "--tag-id <tag-id-1> --tag-id <tag-id-2>",
        ),
        (
            ["timelog", "batch", "update", "--help"],
            "--person-id <person-id-1> --person-id <person-id-2> "
            "--tag-id <tag-id-1> --tag-id <tag-id-2>",
        ),
    ],
)
def test_cli_help_shows_repeated_relation_flag_examples(
    argv: list[str],
    expected: str,
    capsys,
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert expected in captured.out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["area", "update", "--help"],
            "lifeos area update 11111111-1111-1111-1111-111111111111 --clear-description",
        ),
        (
            ["person", "update", "--help"],
            "--clear-nicknames --clear-tags",
        ),
        (
            ["habit", "update", "--help"],
            "lifeos habit update 11111111-1111-1111-1111-111111111111 --clear-weekdays",
        ),
        (
            ["habit-action", "update", "--help"],
            "lifeos habit-action update 11111111-1111-1111-1111-111111111111 --clear-notes",
        ),
        (
            ["event", "update", "--help"],
            "--scope single --instance-start 2026-04-10T09:00:00 --clear-end-time",
        ),
    ],
)
def test_cli_help_shows_clear_and_scope_examples(
    argv: list[str],
    expected: str,
    capsys,
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert expected in captured.out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["vision", "update", "--help"],
            "--clear-description --clear-experience-rate",
        ),
        (
            ["tag", "update", "--help"],
            "--clear-description --clear-person",
        ),
        (
            ["task", "update", "--help"],
            "--clear-description --clear-estimated-effort",
        ),
        (
            ["note", "update", "--help"],
            "--clear-tags --clear-events",
        ),
    ],
)
def test_cli_help_shows_update_clear_examples(
    argv: list[str],
    expected: str,
    capsys,
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert expected in captured.out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["area", "delete", "--help"],
            "lifeos area delete <area-id-1> <area-id-2>",
        ),
        (
            ["person", "delete", "--help"],
            "lifeos person delete <person-id-1> <person-id-2>",
        ),
        (
            ["event", "delete", "--help"],
            "lifeos event delete <event-id-1> <event-id-2>",
        ),
        (
            ["task", "delete", "--help"],
            "lifeos task delete <task-id-1> <task-id-2>",
        ),
        (
            ["tag", "delete", "--help"],
            "lifeos tag delete <tag-id-1> <tag-id-2>",
        ),
        (
            ["vision", "delete", "--help"],
            "lifeos vision delete <vision-id-1> <vision-id-2>",
        ),
        (
            ["timelog", "batch", "delete", "--help"],
            "lifeos timelog batch delete --ids <timelog-id-1> <timelog-id-2>",
        ),
    ],
)
def test_cli_batch_action_help_shows_concrete_examples(
    argv: list[str],
    expected: str,
    capsys,
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert expected in captured.out


@pytest.mark.parametrize(
    ("argv", "expected", "unexpected"),
    [
        (
            ["timelog", "batch", "update", "--help"],
            "Timelog identifiers to update",
            "Timelog identifiers to delete",
        ),
    ],
)
def test_cli_batch_action_ids_help_matches_action_semantics(
    argv: list[str],
    expected: str,
    unexpected: str,
    capsys,
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert expected in captured.out
    assert unexpected not in captured.out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["task", "move", "--help"],
            "--old-parent-task-id 00000000-0000-0000-0000-000000000000 "
            "--new-parent-task-id 22222222-2222-2222-2222-222222222222 "
            "--new-display-order 10",
        ),
        (
            ["config", "show", "--help"],
            "lifeos config show --show-secrets",
        ),
        (
            ["config", "set", "--help"],
            "lifeos config set database.url "
            "sqlite+aiosqlite:///$HOME/.lifeos/work.db "
            "--show-secrets",
        ),
        (
            ["data", "batch-update", "--help"],
            "lifeos data batch-update event --file event-patch.jsonl --format jsonl "
            "--dry-run --error-file event-errors.jsonl",
        ),
    ],
)
def test_cli_help_shows_branching_operation_examples(
    argv: list[str],
    expected: str,
    capsys,
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert expected in captured.out
