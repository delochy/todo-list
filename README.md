# Todo List

A compact todo and review panel for Codex. Add a task in one line, request a review, and inspect the evidence without losing your task list.

**v0.1.0 — local artifact review, not live application testing.**

## Features

- Editable board name and actual source project root
- One-line tasks; optional file scopes and acceptance criteria
- Automatic relevant-file discovery inside the selected project
- FIFO review queue with independent work and review states
- Evidence for each criterion, previous results, and change detection
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

The worker uses `codex exec` with a read-only sandbox and no user-configured MCP servers. It inspects local source, tests and image exports. It **does not** execute live login flows, operate a simulator, or prove that a running app works. A request needing those observations may remain `확인 불가`; this is not a passing test. AI review is fallible: inspect the evidence before relying on it.

Automatic discovery can miss files. Expand the task and edit its scope if necessary. Only tracked files are fingerprinted; changes to undiscovered dependencies or remote documents do not invalidate a result. Explicit image attachments are limited to five.

## Data and privacy

Task state and logs stay outside the repository, under `~/.local/share/todo-list/<project-hash>/`. The CLI sends the artifacts it reads to the configured Codex service as part of normal review. Do not use a project containing data you are not authorized to submit. The worker is scoped by prompt and local path validation, not a custom OS-level read allowlist.

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

Tests use a fixture CLI for deterministic discovery/review output; they do not claim to test live model quality or third-party login. GitHub Actions runs the same suite on macOS and Linux.

## Project layout

- `skill/todo-list/scripts/core.py`: persistence, path validation, queue, review runner
- `skill/todo-list/scripts/webserver.py`: local HTTP routes and headers
- `skill/todo-list/scripts/board.py`: CLI entry point
- `skill/todo-list/assets/`: HTML, CSS, JavaScript (one maintained source for each)
- `tests/`: deterministic regression tests
- `install.py`: dependency-free installer with rollback

Custom Codex themes are not automatically inherited. The panel responds to its browser's light/dark preference and uses its own documented palette.

## License

MIT. This is an independent project, not an official OpenAI product.
