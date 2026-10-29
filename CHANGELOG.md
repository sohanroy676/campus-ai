# Changelog

All notable changes to this project are documented here.
Format follows Keep a Changelog. Generated from Conventional Commits — regenerate via the `/commit` command, do not hand-edit.

## [Unreleased]

### Added
- Add time model and core schemas
- Add hard-rule checks and plan validator
- Add CP-SAT encodings for hard rules
- Add source-side equipment contention to R4
- Add lexicographic objective stages and scorer
- Add lexicographic solve and infeasibility explanation
- Add start-shift stage between K and T
- Add append-only event store and state projection
- Add scenario file loader and demo scenario
- Add greedy recovery baseline
- Run one scenario end to end with joint or greedy
- Derive recovery window and movable classes
- Derive window and movable ids when a scenario omits them

### Changed
- Share stage K move cost with greedy

### Documentation
- Record scaffold status and add changelog config
- Record scaffold merge and push
- Add model spec and ADR 0002
- Update progress, roadmap and changelog
- Extend R4 in the spec and refresh memory-bank
- Record solver status and open spec questions
- Correct memory-bank after solver-stages merge
- Record Gate 1 and refresh memory-bank and changelog
- Record the sim-and-greedy merge in memory-bank

### Maintenance
- Add project docs, agent rules and CI config
- Scaffold uv project, package layout and CLI stub
