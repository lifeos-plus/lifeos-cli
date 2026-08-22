# lifeos-cli

English: [README.md](README.md)

```text
██╗     ██╗███████╗███████╗ ██████╗ ███████╗
██║     ██║██╔════╝██╔════╝██╔═══██╗██╔════╝
██║     ██║█████╗  █████╗  ██║   ██║███████╗
██║     ██║██╔══╝  ██╔══╝  ██║   ██║╚════██║
███████╗██║██║     ███████╗╚██████╔╝███████║
╚══════╝╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚══════╝
```

`lifeos-cli` 是一个 terminal-native、local-first 的 LifeOS，用于量化自我工作流。它用同一套结构化系统管理意图、计划、执行、人际关系、金钱、反思和被测量的现实。

当前产品面已经很完整：以 typed Python CLI 作为主接口，支持 SQLite 和 PostgreSQL 后端、Alembic 迁移、本地 FastAPI 服务，并提供一方 React Web UI（位于独立的 `lifeos-web` 仓库），让人类可以通过浏览器操作同一份已配置的 LifeOS 数据库。CLI 同时面向人类和 agent 设计，具备稳定命令语法、help-first 文档、identifier-driven 流程和可预测的文本输出。

## 为什么做它

大多数个人系统会把生活拆散到多个互不相通的工具里。任务在一个地方，日程在另一个地方，笔记在别处，实际投入的时间又散落在各种零碎记录里。这会让一些实际问题变得很难回答：

- 我原本打算做什么？
- 实际上发生了什么？
- 我的时间到底花在了哪里？
- 哪些习惯是真正活出来的，哪些只是停留在愿望里？
- 我真正服务的是哪些人、哪些项目、哪些优先级？
- 计划、时间、习惯、笔记、人际关系和财务之间到底如何连接？

`lifeos-cli` 把个人操作系统同时视为 planning graph 和 evidence ledger：

- intention：areas、visions、tasks、habits、planned events、finance structures
- reality：timelogs、habit actions、notes、relationship records、finance snapshots、aggregate stats

目标不只是存储数据，而是提供一套人类和 agent 都能使用的命令与 API 表面，用来记录正在发生的生活、事后审视它，并自动化可重复的自我管理流程。

## 当前能力地图

已实现系统覆盖了从计划到证据再到复盘的主要量化自我闭环。

| Area | Current support |
| --- | --- |
| Life structure | `area` 记录用于稳定生活领域，支持显示顺序、颜色/图标元数据、active 状态和软删除。 |
| Direction | `vision` 记录支持状态、area 归属、task tree、stats、experience points、task-effort 同步和 harvest 流程。 |
| Execution | 分层 `task` 记录支持父子结构、planning-cycle 字段、状态更新、subtree/hierarchy 视图、reorder/move 和聚合 stats。 |
| Calendar intent | 计划型 `event` 支持 appointment/timeblock/deadline 类型、all-day、recurrence rules、单实例范围的 recurring update/delete、task/area/person/tag 链接和有界展开。 |
| Daily schedule | `schedule` day/range 视图聚合 planned events、planning-cycle tasks 和 habit actions，并支持 overdue unfinished task / habit-action roll-forward。 |
| Routines | `habit` 支持 daily/weekly/monthly/yearly cadence、weekday/weekend 控制、task 链接、stats 和按需 `habit-action` 物化。 |
| Time reality | `timelog` 支持日期与日期时间录入、quick batch entry、list/search 过滤、关系链接、batch update/delete、templates 和按 area 分组的 stats。 |
| Notes and reflection | `note` 支持 inline/stdin/file capture、search、完整内容展示、批量内容替换、软删除，并可关联 tasks、visions、events、person、timelogs 和 tags。 |
| Relationships | `person` 支持关系元数据、生日/纪念日、tags、相关活动、anniversaries，以及来自 events、notes、timelogs 的链接。 |
| Taxonomy | `tag` 支持 category/entity-type 元数据，以及跨资源 association counts。 |
| Finance | 支持 assets、可复用 finance trees、nodes、instant/period snapshots、exchange-rate snapshots、default tree bootstrap，以及资产负债表/现金流风格的数据建模。 |
| Health data | `menstrual` 每日生理周期记录与自定义因素、`body-measurement` 体重/身体成分测量（统一 kg 存储、偏好单位展示），以及 `sleep` 睡眠分段与按需每日汇总。 |
| Data portability | 支持规范 JSON/JSONL export/import、完整 bundle backup/restore、dry-run validation、row-level errors、自然键 upsert import 和面向机器的 batch update/delete。 |
| Configuration | 持久化 database 与 preference 配置，包括 timezone、language、day boundary、week boundary、theme 和默认 vision experience rate。 |
| Local Web API | FastAPI routers 覆盖 health、tasks、visions、habits、notes、timelogs、timelog templates、person、areas、finance、planned events、stats、tags、preferences、menstrual days、menstrual factors、body measurements 和 sleep segments。 |
| Web UI | 位于 `lifeos-plus/lifeos-web` 的一方 Vite/React workspace，覆盖 visions、habits、planning、timelog、finance、insights/stats、schedule/calendar、notes、person 和 settings。 |

## Interfaces

terminal-native CLI 是主要产品接口，也是命令参考的来源：

```bash
lifeos --help
lifeos <resource> --help
lifeos <resource> <action> --help
```

命令形状刻意保持稳定：

```text
lifeos <resource> <action> [arguments] [options]
```

这种形状刻意对人类和 agent 都友好。人类可以使用显式、可发现的命令；agent 可以依赖确定性的 help、稳定标识符、紧凑的 tabular list 输出和带标签的 detail 输出。

本地 Web UI 是面向人类的浏览器界面，用来操作同一份 LifeOS 数据。它是一方、本地化的产品面：UI 位于独立的 `lifeos-web` 仓库，通过生成的 OpenAPI 契约与 Web API 通信。

## 快速开始

`lifeos-cli` 需要 Python 3.11 或更高版本；CI 覆盖 Python 3.11 至 3.14。

从 PyPI 安装或升级：

```bash
uv tool install --upgrade lifeos-cli
```

只有在需要 PostgreSQL 支持时，再安装对应可选依赖：

```bash
uv tool install --upgrade "lifeos-cli[postgres]"
```

如果需要浏览器访问或 HTTP 访问，可以安装可选的本地 Web API 运行时依赖。它会使用同一份 LifeOS 数据库配置：

```bash
uv tool install --upgrade "lifeos-cli[web]"
```

`lifeos-cli` 支持 SQLite 和 PostgreSQL。

- SQLite 适合本地、单用户、低门槛使用场景。
- PostgreSQL 仍然是支持 schema 的部署型后端。

初始化本地环境：

```bash
lifeos init
```

对于本地优先的单机使用，`lifeos init` 可以直接引导 SQLite，无需额外启动数据库服务。后端默认值和示例以 `lifeos init --help` 为准。

查看并调整运行时偏好：

```bash
lifeos config show
lifeos config set preferences.timezone America/Toronto
lifeos config set preferences.language zh-Hans
lifeos config set preferences.day_starts_at 04:00
lifeos config set preferences.week_starts_on monday
```

## 常见 CLI 工作流

```bash
lifeos area add "Health" --color "#16A34A" --icon heart
lifeos vision add "Build a stronger health baseline" --area-id <area-id>
lifeos task add "Train three times this week" --vision-id <vision-id> --planning-cycle-type week --planning-cycle-days 7 --planning-cycle-start-date 2026-04-13
lifeos event add "Strength training" --start-time 2026-04-13T18:00:00 --end-time 2026-04-13T19:00:00 --task-id <task-id>
lifeos schedule show --date 2026-04-13
lifeos timelog add "Workout" --start-time 2026-04-13T18:00:00 --end-time 2026-04-13T19:00:00 --task-id <task-id>
lifeos habit add "Morning mobility" --start-date 2026-04-01 --duration-days 100 --cadence-frequency daily
lifeos habit-action log --habit-id <habit-id> --date 2026-04-13 --status done
lifeos note add "Energy was higher after sleeping earlier." --task-id <task-id>
lifeos finance tree-ensure-default
lifeos data export all --output lifeos-bundle.zip
```

完整的 CLI 用法、工作流和输出约定，请参考 [docs/cli.md](docs/cli.md)。命令级事实应以 CLI help 为准，而不是放在仓库级文档中维护第二份来源。面向维护者的架构说明请参考 [docs/architecture.md](docs/architecture.md)。

## Local Web UI

一方 React Web UI 位于独立的 [`lifeos-web`](https://github.com/lifeos-plus/lifeos-web) 仓库，通过生成的 OpenAPI 契约与本项目的 Web API 通信。本仓库保留 Web API 和 `web serve` 命令。

启动本地 Web API 服务以支持浏览器或 HTTP 访问：

```bash
lifeos web serve
```

`lifeos web serve` 不会从 PyPI 安装、构建或内置前端。先从 `lifeos-web` 构建前端，再显式传入输出目录：

```bash
lifeos web serve --static-dir <path-to>/lifeos-web/dist
```

如果当前配置的数据库 URL 使用 PostgreSQL，需要同时安装或运行 `web` 和 `postgres` 两个可选依赖：

```bash
uv tool install --upgrade "lifeos-cli[web,postgres]"
uv run --extra web --extra postgres lifeos web serve
```

Web API 没有认证，默认绑定 `127.0.0.1`。使用非 loopback 的 `--host`（例如 `0.0.0.0`）启动会把个人数据暴露到网络中；此时 `lifeos web serve` 会打印警告。请保持 loopback 默认值，或通过网络层限制访问。默认还启用以下请求级边界：只接受 loopback `Host`（可用 `LIFEOS_WEB_ALLOWED_HOSTS` 扩展）、拒绝跨源请求、限制请求体与 API 速率、Swagger UI 默认关闭（需 `--docs` 显式开启）。完整边界清单以及 SQLite 文件权限、数据库凭据指引见 [SECURITY.md](SECURITY.md)。

前端开发时，可以在 `lifeos-web` 中启动 Vite app，并把 API 请求代理到本地 Web API：

```bash
git clone https://github.com/lifeos-plus/lifeos-web
cd lifeos-web
npm ci
npm run dev
```

前端 workspace 与跨仓契约策略详情见 [`lifeos-web` README](https://github.com/lifeos-plus/lifeos-web)。

## Agent 使用

任意能够执行终端命令并读取命令输出的 agent runtime 都可以操作同一套 CLI。这包括但不限于 Codex、OpenCode、Swival、Claude Code、Cursor、Gemini CLI、OpenClaw，以及你自己的自定义 agent runtime。

- 稳定的命令语法：`lifeos <resource> <action> [arguments] [options]`
- 以 `--help` 作为主命令参考的 help-first 模型
- 围绕 `list` 和 `show` 构建的 identifier-driven 发现流程
- 面向列表的紧凑摘要输出，以及面向详情的标注字段输出
- 在 `list`、`search`、`show` 读命令上可选的 `--json` 输出，便于稳定的机器解析；默认紧凑文本输出保持不变
- 使用 `task_id`、`vision_id`、`event_id` 等实体化主键列表头
- 持久化语言偏好，便于 agent 匹配面向人类 payload 的语言
- 数据 import/export 命令支持机器生成的清理、迁移和备份流程

## 开发验证

仓库改动应运行主验证入口：

```bash
bash ./scripts/doctor.sh
```

CLI 文档审查可以运行 help audit 脚本。它会遍历 parser tree，执行发现到的全部 `--help` 命令，并生成 Markdown 报告：

```bash
uv run python scripts/audit_cli_help.py
```

## Dependency Maintenance

Routine backend dependency version updates are checked weekly. Only semver minor version updates are included in routine automation; patch updates are intentionally excluded and major migrations remain explicit maintenance tasks. Security updates are handled independently. Pull request validation audits every locked Python extra and rejects known vulnerabilities. Frontend dependency maintenance moved to the `lifeos-web` repository.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the dependency maintenance commands and workflow boundaries.

## 项目策略

- 贡献流程：[CONTRIBUTING.md](CONTRIBUTING.md)
- 安全披露：[SECURITY.md](SECURITY.md)
- 社区行为规范：[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## 许可证

本项目使用 Apache License 2.0。详见 [LICENSE](LICENSE)。
