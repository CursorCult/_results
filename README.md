# CursorCult Results (`_results`)

This repo stores **benchmark results** for CursorCult rules and rulesets.

Benchmarks live in repos named:

- `_benchmark_<RULE>` (benchmarks a specific rule pack)

Benchmarks should publish their results here via PRs so results are:

- versioned and reviewable
- easy to browse
- easy to compare across rule versions (`v0`, `v1`, `v2`, …)

## Submodules (pinning versions)

This repo pins the exact versions used to generate results via git submodules:

- `_metrics/` -> `CursorCult/_metrics` (standard metrics)
- `benchmarks/<RULE>/` -> `CursorCult/_benchmark_<RULE>` (rule benchmark implementation)

Updating a submodule pointer is what triggers “regenerate results”.

## Workflow (PR-driven regeneration)

1. Open a PR against `CursorCult/_results`.
2. Update one or more submodules (e.g. bump `_metrics`, or bump `benchmarks/TDD`).
3. Regenerate results for what changed:

```sh
git submodule update --init --recursive
python3 scripts/generate_changed_results.py --bench TDD
```

4. Commit the updated `rules/**/RESULTS.md` files and push.

CI checks that submodule pointer bumps are accompanied by corresponding `RESULTS.md` updates (it does not re-run LLM benchmarks).

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

Ruleset result files should summarize/aggregate results from the relevant per-rule benchmarks.

## What goes in `RESULTS.md`

At minimum:

- the benchmark repo link (e.g. `CursorCult/_benchmark_TDD`)
- what was measured
- a table of results by rule version (`v0`, `v1`, `v2`, …)

## License

Unlicense / public domain. See `LICENSE`.
