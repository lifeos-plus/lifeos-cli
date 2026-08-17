# LifeOS CLI command tree (complete)
# shape: lifeos <resource> <action> [arguments] [options]
# regenerate: LIFEOS_LANGUAGE=en uv run python scripts/audit_cli_help.py --format tree --output docs/cli-tree.md

├── area  —  Manage life areas
│   ├── add  —  Create an area
│   │       args: name [required]; --description; --color; --icon; --inactive; --display-order
│   ├── delete  —  Delete an area
│   │       args: area_ids [required]
│   ├── list  —  List areas
│   │       args: --include-inactive; --limit; --offset; --json
│   ├── show  —  Show an area
│   │       args: area_id [required]; --json
│   └── update  —  Update an area
│           args: area_id [required]; --name; --description; --clear-description; --color; --icon; --clear-icon; --active; --display-order
├── config  —  Inspect runtime configuration
│   ├── show  —  Show effective configuration
│   │       args: --show-secrets; --json
│   └── update  —  Persist one config value
│           args: key [required]; value [required]; --show-secrets
├── data  —  Run unified data import/export and batch commands
│   ├── batch-delete  —  Batch-delete one resource by identifiers
│   │       args: target [required]; --id; --ids-file; --file; --stdin; --format; --dry-run; --error-file
│   ├── batch-update  —  Batch-update one resource from canonical patch rows
│   │       args: target [required]; --file; --stdin; --format; --dry-run; --continue-on-error; --error-file
│   ├── export  —  Export one resource or a full bundle
│   │       args: target [required]; --format; --output
│   └── import  —  Import one resource or a full bundle
│           args: target [required]; --file; --stdin; --format; --dry-run; --continue-on-error; --replace-existing; --mode; --key; --error-file
├── db  —  Run database maintenance commands
│   ├── ping  —  Check database connectivity
│   └── upgrade  —  Apply migrations
├── event  —  Manage planned schedule events
│   ├── add  —  Create an event
│   │       args: title [required]; --description; --start-time; --end-time; --priority; --status; --type; --all-day; --area-id; --task-id; --recurrence-frequency; --recurrence-interval; --recurrence-count; --recurrence-until; --recurrence-weekdays; --recurrence-month-days; --recurrence-months; --recurrence-weekday-ordinal; --tag-id; --person-id
│   ├── delete  —  Delete an event
│   │       args: event_ids [required]; --scope; --instance-start
│   ├── list  —  List events
│   │       args: --title-contains; --status; --type; --area-id; --task-id; --person-id; --tag-id; --date; --start-date; --end-date; --start-time; --end-time; --limit; --offset; --json
│   ├── show  —  Show an event
│   │       args: event_id [required]; --json
│   └── update  —  Update an event
│           args: event_id [required]; --title; --description; --clear-description; --start-time; --end-time; --clear-end-time; --priority; --status; --type; --all-day; --area-id; --clear-area; --task-id; --clear-task; --recurrence-frequency; --recurrence-interval; --recurrence-count; --recurrence-until; --recurrence-weekdays; --recurrence-month-days; --recurrence-months; --recurrence-weekday-ordinal; --clear-advanced-recurrence; --clear-recurrence; --scope; --instance-start; --tag-id; --clear-tags; --person-id; --clear-person
├── finance  —  Manage unified finance trees and snapshots
│   ├── asset  —  Manage finance assets
│   │   ├── add  —  Create a finance asset
│   │   │       args: code [required]; --name; --decimal-places; --display-order
│   │   ├── delete  —  Delete a finance asset
│   │   │       args: asset_id [required]
│   │   ├── list  —  List finance assets
│   │   │       args: --limit; --offset; --json
│   │   ├── show  —  Show a finance asset
│   │   │       args: asset_id [required]; --json
│   │   └── update  —  Update a finance asset
│   │           args: asset_id [required]; --code; --name; --decimal-places; --display-order
│   ├── node  —  Manage finance tree nodes
│   │   ├── add  —  Add a finance tree node
│   │   │       args: tree_id [required]; name [required]; --parent-id; --currency-code; --display-order
│   │   ├── delete  —  Delete a finance node
│   │   │       args: node_id [required]
│   │   ├── list  —  List finance tree nodes
│   │   │       args: --tree-id; --json
│   │   ├── show  —  Show a finance tree node
│   │   │       args: node_id [required]; --json
│   │   └── update  —  Update a finance node
│   │           args: node_id [required]; --name; --currency-code; --display-order
│   ├── rate-snapshot  —  Manage finance exchange-rate snapshots
│   │   ├── add  —  Create a finance exchange-rate snapshot
│   │   │       args: --captured-at; --source; --note; --rate
│   │   ├── delete  —  Delete a finance exchange-rate snapshot
│   │   │       args: rate_snapshot_id [required]
│   │   ├── list  —  List finance exchange-rate snapshots
│   │   │       args: --limit; --offset; --json
│   │   ├── show  —  Show a finance exchange-rate snapshot
│   │   │       args: rate_snapshot_id [required]; --json
│   │   └── update  —  Update a finance exchange-rate snapshot
│   │           args: rate_snapshot_id [required]; --captured-at; --source; --note; --rate
│   ├── snapshot  —  Manage finance snapshots
│   │   ├── add  —  Create a finance snapshot
│   │   │       args: tree_id [required]; --title; --snapshot-ts; --period-start; --period-end; --primary-currency; --rate-snapshot-id; --note; --entry
│   │   ├── delete  —  Delete a finance snapshot
│   │   │       args: snapshot_id [required]
│   │   ├── list  —  List finance snapshots
│   │   │       args: --tree-id; --limit; --offset; --json
│   │   ├── show  —  Show a finance snapshot
│   │   │       args: snapshot_id [required]; --json
│   │   └── update  —  Update a finance snapshot
│   │           args: snapshot_id [required]; --title; --snapshot-ts; --period-start; --period-end; --primary-currency; --rate-snapshot-id; --note; --entry
│   └── tree  —  Manage finance trees
│       ├── add  —  Create a finance tree
│       │       args: name [required]; --primary-currency; --display-order; --default
│       ├── delete  —  Delete a finance tree
│       │       args: tree_id [required]
│       ├── ensure-default  —  Ensure a default finance tree exists
│       │       args: --primary-currency
│       ├── list  —  List finance trees
│       │       args: --limit; --offset; --json
│       ├── show  —  Show a finance tree
│       │       args: tree_id [required]; --json
│       └── update  —  Update a finance tree
│               args: tree_id [required]; --name; --primary-currency; --display-order; --default
├── habit  —  Manage recurring habits
│   ├── add  —  Create a habit
│   │       args: title [required]; --description; --start-date; --duration-days; --cadence-frequency; --weekdays; --weekends-only; --monthdays; --target-per-cycle; --target-per-week; --task-id
│   ├── delete  —  Delete a habit
│   │       args: habit_ids [required]
│   ├── list  —  List habits
│   │       args: --status; --title; --active-window-only; --with-stats; --count; --limit; --offset; --json
│   ├── show  —  Show a habit
│   │       args: habit_id [required]; --json
│   ├── stats  —  Show habit statistics
│   │       args: habit_id [required]
│   ├── task-associations  —  List task-to-habit associations
│   └── update  —  Update a habit
│           args: habit_id [required]; --title; --description; --clear-description; --start-date; --duration-days; --cadence-frequency; --weekdays; --weekends-only; --clear-weekdays; --monthdays; --clear-monthdays; --target-per-cycle; --target-per-week; --status; --task-id; --clear-task
├── habit-action  —  Manage dated habit actions
│   ├── delete  —  Delete a habit action
│   │       args: action_ids [required]
│   ├── list  —  List habit actions
│   │       args: --habit-id; --status; --date; --start-date; --end-date; --count; --limit; --offset; --json
│   ├── log  —  Update a habit action by date
│   │       args: --habit-id; --date; --status; --notes; --clear-notes
│   ├── show  —  Show a habit action
│   │       args: action_id [required]; --json
│   └── update  —  Update a habit action
│           args: action_id [required]; --status; --notes; --clear-notes
├── init  —  Initialize local configuration
│       args: --database-url; --schema; --echo; --timezone; --language; --day-starts-at; --week-starts-on; --vision-experience-rate-per-hour; --non-interactive; --skip-ping; --skip-migrate
├── note  —  Capture and manage notes
│   ├── add  —  Create a note
│   │       args: content [nargs=?]; --stdin; --file; --tag-id; --person-id; --task-id; --vision-id; --event-id; --timelog-id; --habit-action-id
│   ├── batch  —  Run batch note operations
│   │   └── update-content  —  Find and replace note content in bulk
│   │           args: --ids; --find-text; --replace-text; --case-sensitive
│   ├── delete  —  Delete a note
│   │       args: note_ids [required]
│   ├── list  —  List notes
│   │       args: --tag-id; --event-id; --person-id; --task-id; --timelog-id; --vision-id; --habit-action-id; --with-counts; --limit; --offset; --json
│   ├── search  —  Search notes
│   │       args: query [required]; --tag-id; --event-id; --person-id; --task-id; --timelog-id; --vision-id; --habit-action-id; --with-counts; --limit; --offset; --json
│   ├── show  —  Show full note content
│   │       args: note_id [required]; --json
│   └── update  —  Update a note
│           args: note_id [required]; content [nargs=?]; --tag-id; --clear-tags; --person-id; --clear-person; --task-id; --clear-tasks; --vision-id; --clear-visions; --event-id; --clear-events; --timelog-id; --clear-timelogs; --habit-action-id; --clear-habit-actions
├── person  —  Manage person and relationships
│   ├── add  —  Create a person
│   │       args: name [required]; --description; --nickname; --birth-date; --location; --tag-id
│   ├── delete  —  Delete a person
│   │       args: person_ids [required]
│   ├── list  —  List people
│   │       args: --search; --tag-id; --limit; --offset; --json
│   ├── show  —  Show a person
│   │       args: person_id [required]; --json
│   └── update  —  Update a person
│           args: person_id [required]; --name; --description; --clear-description; --nickname; --clear-nicknames; --birth-date; --clear-birth-date; --location; --clear-location; --tag-id; --clear-tags
├── planning  —  Show planning-cycle task trees
│   └── show  —  Show a planning view
│           args: --cycle-type; --at; --start; --depth; --status; --vision; --limit; --offset; --json
├── schedule  —  Inspect aggregated schedule views
│   ├── list  —  List a schedule range
│   │       args: --date; --start-date; --end-date; --hide-overdue-unfinished; --json
│   └── show  —  Show one schedule day
│           args: --date; --hide-overdue-unfinished; --json
├── tag  —  Manage tags
│   ├── add  —  Create a tag
│   │       args: name [required]; --entity-type; --category; --description; --color; --person-id
│   ├── delete  —  Delete a tag
│   │       args: tag_ids [required]
│   ├── list  —  List tags
│   │       args: --entity-type; --category; --person-id; --limit; --offset; --json
│   ├── show  —  Show a tag
│   │       args: tag_id [required]; --json
│   └── update  —  Update a tag
│           args: tag_id [required]; --name; --entity-type; --category; --description; --clear-description; --color; --clear-color; --person-id; --clear-person
├── task  —  Manage hierarchical tasks
│   ├── add  —  Create a task
│   │       args: content [required]; --vision-id; --description; --parent-task-id; --status; --priority; --display-order; --person-id; --estimated-effort; --planning-cycle-type; --planning-cycle-days; --planning-cycle-start-date
│   ├── delete  —  Delete a task
│   │       args: task_ids [required]
│   ├── hierarchy  —  Show a vision task hierarchy
│   │       args: vision_id [required]
│   ├── list  —  List tasks
│   │       args: --vision-id; --vision-in; --parent-task-id; --person-id; --status; --status-in; --exclude-status; --planning-cycle-type; --planning-cycle-start-date; --content; --limit; --offset; --json
│   ├── move  —  Move a task
│   │       args: task_id [required]; --old-parent-task-id; --new-parent-task-id; --clear-parent; --new-vision-id; --new-display-order
│   ├── reorder  —  Reorder tasks
│   │       args: --order
│   ├── show  —  Show a task
│   │       args: task_id [required]; --json
│   ├── stats  —  Show task statistics
│   │       args: task_id [required]
│   ├── update  —  Update a task
│   │       args: task_id [required]; --content; --description; --clear-description; --parent-task-id; --clear-parent; --status; --apply-to-subtasks; --priority; --display-order; --person-id; --clear-person; --estimated-effort; --clear-estimated-effort; --planning-cycle-type; --planning-cycle-days; --planning-cycle-start-date; --clear-planning-cycle
│   └── with-subtasks  —  Show a task subtree
│           args: task_id [required]
├── timelog  —  Manage actual time records
│   ├── add  —  Create a timelog
│   │       args: title [nargs=?]; --start-time; --end-time; --entry; --stdin; --file; --first-start-time; --yes; --tracking-method; --location; --energy-level; --notes; --area-id; --task-id; --tag-id; --person-id
│   ├── batch  —  Run batch timelog operations
│   │   └── update  —  Update multiple timelogs
│   │           args: --ids; --title; --find-title-text; --replace-title-text; --area-id; --clear-area; --task-id; --clear-task; --tag-id; --clear-tags; --person-id; --clear-person
│   ├── delete  —  Delete a timelog
│   │       args: timelog_ids [required]
│   ├── list  —  List timelogs
│   │       args: --title-contains; --notes-contains; --query; --tracking-method; --area-id; --area-name; --without-area; --task-id; --without-task; --person-id; --tag-id; --with-counts; --date; --start-date; --end-date; --start-time; --end-time; --count; --limit; --offset; --json
│   ├── search  —  Search timelogs
│   │       args: --title-contains; --notes-contains; --query; --tracking-method; --area-id; --area-name; --without-area; --task-id; --without-task; --person-id; --tag-id; --with-counts; --date; --start-date; --end-date; --start-time; --end-time; --count; --limit; --offset; --json
│   ├── show  —  Show a timelog
│   │       args: timelog_id [required]; --json
│   ├── stats  —  Query timelog stats grouped by area
│   │   ├── day  —  Show one day of timelog stats grouped by area
│   │   │       args: --date
│   │   ├── month  —  Show one month of timelog stats grouped by area
│   │   │       args: --month
│   │   ├── range  —  Show a date range of timelog stats grouped by area
│   │   │       args: --start-date; --end-date
│   │   ├── rebuild  —  Rebuild persisted timelog stats grouped by area
│   │   │       args: --date; --start-date; --end-date; --all
│   │   ├── week  —  Show one week of timelog stats grouped by area
│   │   │       args: --date
│   │   └── year  —  Show one year of timelog stats grouped by area
│   │           args: --year
│   └── update  —  Update a timelog
│           args: timelog_id [required]; --title; --start-time; --end-time; --tracking-method; --location; --clear-location; --energy-level; --clear-energy-level; --notes; --clear-notes; --area-id; --clear-area; --task-id; --clear-task; --tag-id; --clear-tags; --person-id; --clear-person
├── vision  —  Manage visions
│   ├── add  —  Create a vision
│   │       args: name [required]; --description; --status; --area-id; --person-id; --experience-rate-per-hour
│   ├── add-experience  —  Add vision experience
│   │       args: vision_id [required]; --points
│   ├── delete  —  Delete a vision
│   │       args: vision_ids [required]
│   ├── harvest  —  Harvest a vision
│   │       args: vision_id [required]
│   ├── list  —  List visions
│   │       args: --status; --area-id; --person-id; --limit; --offset; --json
│   ├── show  —  Show a vision
│   │       args: vision_id [required]; --json
│   ├── stats  —  Show vision stats
│   │       args: vision_id [required]
│   ├── sync-experience  —  Sync vision experience
│   │       args: vision_id [required]
│   ├── update  —  Update a vision
│   │       args: vision_id [required]; --name; --description; --clear-description; --status; --area-id; --clear-area; --person-id; --clear-person; --experience-rate-per-hour; --clear-experience-rate
│   └── with-tasks  —  Show a vision task tree
│           args: vision_id [required]
└── web  —  Run the optional local Web API
    └── serve  —  Serve the local Web API, optionally with built frontend assets
            args: --host; --port; --reload; --static-dir
