# Benchmarks (submodules)

Each directory under `benchmarks/` should be a git submodule pointing at a rule benchmark repo:

- `benchmarks/<RULE>` -> `https://github.com/CursorCult/_benchmark_<RULE>.git`

Results are generated into:

- `rules/<RULE>/<language>/RESULTS.md`

