# Project Instructions

- Read docs/research.md and docs/architecture.md before changing core architecture.
- Prefer maintained upstream packages with explicit licenses. Public source visibility is not permission to redistribute it.
- Do not write a replacement Power.log parser; use hslog. Add narrowly scoped adapters around its exported entities.
- Unknown game state stays null. Do not convert card mana costs into Battlegrounds purchase prices.
- Keep demo/import/live provenance visible and stored. Do not produce advice from combat, unknown identity, unknown gold, failed parsing, or stale live logs.
- Record data build/hash, dependency changes, mechanism coverage, and validation in docs/progress.md.
- Run npm run build and Python tests when state contracts or advice behavior change. Inspect UI with a real browser for user-facing changes.
- Keep raw client logs, local settings, history databases, output artifacts, and card caches under ignored data/ or output/ directories.
- Use focused commits and preserve user changes. Do not treat a new simulator as current-patch compatible until its license and mechanism coverage are verified.
