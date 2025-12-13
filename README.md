# CursorCult Results (`_results`)

This repo stores **benchmark results** for CursorCult rules and rulesets.

Benchmarks live in repos named:

- `_benchmark_<RULE>` (benchmarks a specific rule pack)
- `_benchmark_<RULESET>` (benchmarks a named ruleset)

Benchmarks should publish their results here via PRs so results are:

- versioned and reviewable
- easy to browse
- easy to compare across rule versions (`v0`, `v1`, `v2`, …)

## Structure

### Rule results

```text
rules/<RULE>/<language>/RESULTS.md
```

Example:

`rules/TDD/python/RESULTS.md`

### Ruleset results

```text
rulesets/<RULESET>/<language>/RESULTS.md
```

## What goes in `RESULTS.md`

At minimum:

- the benchmark repo link (e.g. `CursorCult/_benchmark_TDD`)
- what was measured
- a table of results by rule version (`v0`, `v1`, `v2`, …)

## License

Unlicense / public domain. See `LICENSE`.

