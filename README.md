# Todo List

A compact todo and review panel for Codex. Add a task in one line, request a review, and inspect the evidence without losing your task list.

**v0.2.0 — platform-aware UI review and ideas.**

## Features

- Editable board name and actual source project root
- Tasks and Ideas; convert an idea to a task without losing its notes
- Per-task Web / Android / iOS checkboxes and optional web test URL
- One-line tasks; optional file scopes and acceptance criteria
- Actual UI inspection on selected platforms; artifact discovery for code-only diagnostics
- FIFO review queue with independent work and review states
- Evidence for each criterion, previous results, and change detection
- English and Korean UI with browser-language detection and a saved language selector
- New reviews and discovery explanations follow the requested language
- Compact accordion rows, semantic status colors, light/dark appearance
- Loopback-only server, same-origin requests, no frontend dependencies

## Requirements

macOS or Linux, Python 3.11+, and an authenticated Codex CLI on `PATH`.

Install/sign in to Codex using the [official CLI instructions](https://developers.openai.com/codex/cli/). Review requests use your normal Codex account usage. No separate API key is required.

## Install

```sh
git clone https://github.com/delochy/todo-list.git
cd todo-list
python3 install.py
```

Invoke `$todo-list` in Codex and ask it to open a board for your source project. If the skill is not yet listed, start a new Codex task.

Manual launch:

```sh
python3 ~/.codex/skills/todo-list/scripts/board.py doctor --project /path/to/project
python3 ~/.codex/skills/todo-list/scripts/board.py serve --project /path/to/project
```

Open the printed localhost address in the Codex browser panel. Keep the server running while using the board. Click the project name to choose the **real source directory**, not a folder of links or copied outputs.

## What a review means

`할 일 / 작업 중 / 작업 완료` are work states. Requesting a review does not change them.

| Review state | Meaning |
| --- | --- |
| 미검수 | No review yet |
| 검수 대기 | Queued; starts automatically in request order |
| 검수 중 | Codex is discovering or inspecting artifacts |
| 검수 완료 | Every criterion passed with evidence |
| 수정 필요 | A failed criterion or outstanding finding |
| 확인 불가 | Required artifacts or observations are unavailable |
| 실행 오류 | CLI failure, interruption, or invalid output |
| 재검수 필요 | Tracked files or the configured project changed |

The default review uses configured computer-use MCP tools to inspect the actual UI on the task's selected platforms. It discovers an available browser or running test device, performs the requested navigation, and records observed steps and PNG screenshots. Each selected platform is reported separately. A pass requires evidence on every selected platform; reading code alone cannot pass a live review.

**Setup is required:** the host must have an enabled local stdio computer-use MCP server (`cua_repl`, `computer-use`, `XcodeBuildMCP`, `xcodebuildmcp`, or `mobile-mcp`) whose tools support the chosen platform. Mobile reviews need a running simulator/emulator and the test app. Web reviews may specify a local/test URL. Availability depends on your Codex host; installing this skill does not install or provision device-control tools. If a tool, target or screenshot export is unavailable, the result is blocked with a next step.

The live worker enables only those UI MCP servers, uses a workspace-write sandbox for screenshot artifacts, and instructs the agent not to change application source or bypass tool permissions. It does not grant authorization for deleting real accounts, submitting credentials, payments, or provider permissions. Such steps must be handled through an appropriately authorized test environment. Screenshot and step validation prevents empty evidence from passing, but it is not a guarantee against every incorrect agent observation.

An internal `mode=code` API option retains the previous read-only artifact review for diagnostics. The UI requests live review by default.
Automatic discovery can miss files. Expand the task and edit its scope if necessary. Only tracked files are fingerprinted; changes to undiscovered dependencies or remote documents do not invalidate a result. Explicit image attachments are limited to five.

## Data and privacy

Task state and logs stay outside the repository, under `~/.local/share/todo-list/<project-hash>/`. The CLI sends the artifacts it reads to the configured Codex service as part of normal review. Do not use a project containing data you are not authorized to submit. The worker is scoped by prompt, configured UI tools, and local path validation, not a custom OS-level read allowlist. Screenshots may contain private app data and are stored with the other local review artifacts.

The server binds only to `127.0.0.1`; authenticated requests require a per-run token. Do not expose it with a public tunnel. Tokens/logs are runtime data, never repository content. The directory is private to the local user.

## Update and rollback

Stop the board, pull the new version, and rerun `python3 install.py`. The installer only copies release files and backs up the old skill under `~/.codex/skills/.todo-list-backups/`. State is unchanged. To roll back, stop the board and restore that backup directory as `~/.codex/skills/todo-list`.

For an older board, pass `--state-dir /path/to/old/state` to reuse its `board.json`. Back it up first. If the process was interrupted, request the review again. Do not run two servers against one state directory.

## Development

No Python runtime packages or frontend build step are required.

```sh
PYTHONPATH=skill/todo-list/scripts python3 -m unittest discover -s tests -v
node --check skill/todo-list/assets/board.js
```

Tests use a fixture CLI for deterministic output and check evidence requirements, platform scope and idea conversion; they do not claim to test every mobile host, live model quality or third-party login. GitHub Actions runs the same suite on macOS and Linux.

## Project layout

- `skill/todo-list/scripts/core.py`: persistence, path validation, queue, review runner
- `skill/todo-list/scripts/live_review.py`: platform contracts, UI MCP configuration and screenshot validation
- `skill/todo-list/scripts/webserver.py`: local HTTP routes and headers
- `skill/todo-list/scripts/board.py`: CLI entry point
- `skill/todo-list/assets/`: HTML, CSS, JavaScript (one maintained source for each)
- `tests/`: deterministic regression tests
- `install.py`: dependency-free installer with rollback

Custom Codex themes are not automatically inherited. The panel responds to its browser's light/dark preference and uses its own documented palette.

## License

MIT. This is an independent project, not an official OpenAI product.

## Languages

The panel automatically uses Korean for Korean browser locales and English otherwise. Choose Automatic, English or 한국어 in board settings. The preference is saved in the browser for this board address. New reviews use the selected language; previous reports and user-authored task text are preserved. UI and runtime messages live in `skill/todo-list/assets/locales.json`. Add matching locale keys there when contributing translations. Currently supported: English and Korean, not every language. CLI task creation accepts `--language en|ko`.

### Live review verification status

The local Web smoke check opened the running app and inspected its language menu using the configured UI tool. In that host, the worker could not export a Chrome screenshot, so the result correctly remained blocked. Android/iOS execution and screenshot export are host-dependent and have not been end-to-end certified across supported hosts. Do not treat the deterministic CI suite as device certification.

### Android screen access

Mobile reviews require a device-control MCP, not just a connected USB device. Configure [Mobile MCP](https://github.com/mobile-next/mobile-mcp) with `codex mcp add mobile-mcp -- npx -y @mobilenext/mobile-mcp@1.0.4`, with your Android SDK and Node executable available in its environment. The preparation dialog disables retry when no supported mobile MCP is configured. Configuration presence is not a live health check; the reviewer still validates screen access and screenshot capture.
