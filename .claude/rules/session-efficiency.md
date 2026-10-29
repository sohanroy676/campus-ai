# Session & Token Efficiency

- Do not re-read files already in context unless they've changed.
- Read only the files relevant to the current task, not the whole directory tree.
- Prefer targeted Grep/Glob over opening large files fully when just locating something.
- `memory-bank/projectBrief.md`, `activeContext.md` and `progress.md` are imported by CLAUDE.md at session start; read the other memory-bank files on demand.
- At the end of a work session (or after completing 1-2 features), update `memory-bank/progress.md` and `memory-bank/activeContext.md` with current state, then recommend `/clear` or a fresh session for the next feature.
- Background work (dev servers, evals, CI, long test runs): start it in the background and use Monitor (or `Bash` with `run_in_background` for a single completion event) instead of sleeping and re-checking. Filters must cover failure signatures, not just success.
