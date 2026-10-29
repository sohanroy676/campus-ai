# Prompt for the next session

Continue work on campus-ai (D:\Programming\campus-ai; the earlier brief named C:\Users\Student\..., which does not exist on this machine). CLAUDE.md and the memory-bank are loaded.

## State
- The seeded synthetic generator is built (`generator/synth.py`, CLI `smartcampus generate`, spec section 8) and merged to `main` through its PR. Check `git log` and `gh pr list` to confirm what actually landed and that CI was green (`checks` and `secrets`). 451 tests.
- `scenarios/frozen/` is still empty. Never edit files there once written.
- Merged feature branches still exist; do not delete them.

## Environment (Windows)
- `export PATH="$HOME/.local/bin:$PATH"` for uv. gh is at "C:\Program Files\GitHub CLI\gh.exe" (sohanroy676).
- git-cliff: `uvx git-cliff --config cliff.toml -o CHANGELOG.md` (not yet run for the generator).
- Write files as UTF-8 without BOM and LF; use the Write tool for long files.
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Do not push or merge without approval. After a push, watch CI with Monitor (`gh pr checks`), report every terminal state including `secrets`, and do not report green unless seen.

## Open items, in order
1. Frozen set. Proposal awaiting the user's yes or changes: {small, medium} x load {50, 75} x severity {room, building, hold} x seeds {1, 2} = 24 scenarios, written with `smartcampus generate`. Medium at load 90 is out: joint finds no plan in its 10 s first stage. Verify all 24 with both `joint` and `greedy` offline (slow; run in the background and use Monitor), then add a golden test that regenerating them reproduces the files byte for byte. Record the generator version in each file (provenance does this already).
2. Spec assumptions 1-24 in `docs/model-spec.md` section 7 still need the user's confirmation (3 and 19 are resolved). Go through them with the user.
3. Housekeeping: update ROADMAP.md (generator moved out of Now/Next) and regenerate CHANGELOG.md; fix stale text (CLAUDE.md Status says there is no `src/`; progress.md used to say 12 assumptions; projectBrief says about 400 scenarios, ROADMAP says 100+ for Gate 2).
4. Then: ITC 2019 loader (waits for the user's data files), sequential and re-solve baselines, eval harness and stats (Gate 2), repair-overrun loop and approval triggers, contract-net.

## Known facts that matter
- Generated scenarios are big: about 250 classes (small, load 75) and 650 (medium); joint takes 15-35 s, greedy up to 75 s on small/90/building. Use `SolverSettings(stage_seconds=(5, 5, 3, 3, 2, 2))` in tests; `num_workers=1`, `random_seed=42`.
- Severity `overrun` was dropped: a repair overrun is an event (`RepairOverrun`), not scenario data.
- Changing the output for a given seed means bumping `GENERATOR_VERSION`.
