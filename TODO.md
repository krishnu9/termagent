# Post-v1 backlog

This is the remaining work after the first TermAgent v1 loop. Architecture, tools, sandbox, and TUI behavior are documented in [README.md](README.md) — start there before implementing anything here.

Items **1–4** from README “Possible improvements” are merged on master (do not re-implement):

- [x] Create `--workspace` if missing
- [x] Permission prompts for `write_file` / `run_shell` plus `--yes`
- [x] Stream model tokens in the TUI
- [x] Context hygiene (`list` ignore, `read_file` cap, search tool)

---

## Remaining improvements

- [ ] **Git tools (`git_status`, `git_diff`)**
  Add tools so the model can see repository state (status, diffs) the same way it uses `list` / `read_file`. Keep them on the existing tool dispatcher and subject to the same sandbox as other tools. Do **not** surface git as a TUI panel or dedicated UI — the model should call tools; the transcript stays the interface.

- [ ] **Session persistence**
  Save and load PydanticAI message history to disk so a session can resume after exit. `/reset` must still clear in-memory (and persisted) history so a fresh conversation is explicit, not accidental reuse of an old file.

- [ ] **Shell confinement**
  The file-path sandbox is **not** a jail: `run_shell` already has a timeout, but commands like `cd /` and `cat /etc/passwd` are not blocked. Either document this limitation loudly (README / help) or actually confine `run_shell` (e.g. reject dangerous cwd changes, or run in a subprocess with tighter limits). Do not imply the current sandbox is sufficient for untrusted prompts.

- [ ] **Cancel in-flight run (Escape)**
  Escape should abort the Textual worker. Today a long model call or a blocking shell like `sleep` owns the UI until it finishes. Wire cancel through so the user can interrupt without killing the process.

- [ ] **MCP / web / GitHub tools**
  Extra tools on the same dispatcher (MCP, web search, GitHub) after the core loop, hygiene, and permission prompts are solid. Do not expand tool surface until 1–4 (and ideally git/session/shell/cancel as needed) are merged.

- [ ] **Subagents (lowest priority)**
  Multi-agent coordination last. Subagents add orchestration, not a better understanding of the single-agent loop. Implement only after the rest of this backlog.
