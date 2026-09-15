---
name: todo-list
description: Manage a todo board inside a Codex browser panel, with one-line task entry, queued local artifact reviews, and persistent evidence and status. Use for task lists with review buttons or tracked verification.
---

# Todo List

## Open

Resolve the actual source project from the user's request and its AGENTS.md before launching. Do not treat an artifact store or symlink wrapper as the application repository. Run:

```sh
python3 <skill>/scripts/board.py serve --project <actual-project>
```

Keep the execution session alive. Open the printed loopback URL in the current Codex browser panel with `open_in_codex`, placement `right`. The board's project button also edits the source root. A project change clears tracked paths and invalidates previous verification. Existing tasks persist.

The runtime requires macOS/Linux, Python 3.11+, and an installed, authenticated Codex CLI. `doctor --project <project>` checks CLI availability and login. Normal Codex account usage applies. The board follows browser light/dark preference; it does not inherit custom Codex theme tokens.

## Tasks and reviews

A title alone is sufficient. Create tasks from the current request, with optional project-relative paths and concrete acceptance criteria:

```sh
python3 <skill>/scripts/board.py add --project <project> --title 'Check the login flow' --path 'src/auth' --criterion 'Errors return to the login screen'
```

Repeat `--path` and `--criterion` as needed. Omitted paths trigger a read-only discovery pass inside the configured project, followed by artifact review. Omitted criteria initially use the title. Never select unrelated recent files or copy production source into the board to bypass a wrong project root; configure the correct root instead.

Review requests do not mark work completed. Update work independently with `status --project <project> --id <id> --work todo|doing|done`. Requests queue FIFO with one active review. Already queued/running tasks cannot be edited or requested twice.

The reviewer inspects local code and artifacts in a read-only Codex sandbox, without configured MCP servers. It does not log into services or manipulate browsers/simulators. A code review is not a live OAuth or end-to-end test. Criteria that require unavailable live observations remain blocked. For Figma comparisons, use explicitly identified local exports and identify the export as a snapshot; remote changes are not tracked.

A complete verdict requires every criterion to pass with evidence, no outstanding findings, and unchanged tracked content. Changed or deleted artifacts invalidate prior verification. Errors, missing evidence and interrupted runs never count as complete. The user must request any fixes separately.

## Persistence

State defaults to `~/.local/share/todo-list/<project-hash>/`. `--state-dir <directory>` explicitly overrides it, including for migration from an older board. Use the same override for serve/add/status/list. Do not commit state, runtime tokens, reviewer logs or user artifacts. An interrupted review becomes an error on restart and can be requested again. Stop the server session before updating the installed skill.
