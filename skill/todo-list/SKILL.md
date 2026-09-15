---
name: todo-list
description: Manage a todo board inside a Codex browser panel, with one-line task entry, platform-specific UI reviews, and persistent evidence and status. Use for task lists with review buttons or tracked verification.
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

The UI requests live review by default. Each task selects one or more of Web, Android and iOS. The live worker enables only configured local computer-use MCP servers and uses their documented APIs to observe and interact with the actual app. A selected platform must have observed steps and screenshot evidence before passing. No code-only substitution is allowed. Mobile requires a connected test device or running test simulator/emulator and app; Web can specify its test URL. A missing environment or tool is reported as blocked. Do not claim that this skill installs or universally supplies the device tools.

Review requests do not authorize destructive real-account actions, credential entry, provider consent or payments. Respect computer-use confirmation rules and identify the exact user action needed when blocked. Never synthesize screenshots to satisfy the evidence requirement. The API's optional `mode=code` is for explicitly requested artifact-only diagnostics.

Ideas live in a separate tab without review buttons. Convert an idea to a task when the user is ready, preserving its text and choosing platforms.
A complete verdict requires every criterion to pass with evidence, no outstanding findings, and unchanged tracked content. Changed or deleted artifacts invalidate prior verification. Errors, missing evidence and interrupted runs never count as complete. The user must request any fixes separately.

## Persistence

State defaults to `~/.local/share/todo-list/<project-hash>/`. `--state-dir <directory>` explicitly overrides it, including for migration from an older board. Use the same override for serve/add/status/list. Do not commit state, runtime tokens, reviewer logs or user artifacts. An interrupted review becomes an error on restart and can be requested again. Stop the server session before updating the installed skill.

## Language

English and Korean are supported. The browser selects Korean for Korean locales and English otherwise; board settings override and save that preference. Review requests snapshot the selected language. Existing evidence and task text retain their original language. CLI task creation accepts `--language en|ko` (default English).

## Environment recovery

Blocked reviews offer a preparation dialog with read-only Android/iOS device inventory, platform editing, and user environment details passed to retry. Newly requested reviews that become blocked open the dialog while the page remains active. Device presence does not prove UI control permission. Do not infer missing devices from the desktop app list alone. Never claim the panel grants OS permissions or boots devices: the user prepares the environment and approves device prompts.
