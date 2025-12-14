#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / ".runs"


@dataclass(frozen=True)
class Toolchain:
    language: str
    runner: Path
    aggregator: Path


def run_cmd(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    # Merge env if provided
    final_env = os.environ.copy()
    if env:
        final_env.update(env)

    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=final_env, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )


def changed_gitlinks(base: str, head: str) -> set[str]:
    raw = subprocess.check_output(["git", "diff", "--raw", base, head], text=True)
    changed: set[str] = set()
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        meta, path = parts
        meta_parts = meta.split()
        if len(meta_parts) < 3:
            continue
        old_mode = meta_parts[0].lstrip(":")
        new_mode = meta_parts[1]
        if old_mode == "160000" and new_mode == "160000":
            changed.add(path.strip())
    return changed


def list_rule_benchmarks() -> list[Path]:
    bench_root = ROOT / "benchmarks"
    if not bench_root.is_dir():
        return []
    
    benchmarks: list[Path] = []
    for bench_dir in sorted(bench_root.iterdir()):
        if not bench_dir.is_dir():
            continue
        if (bench_dir / ".git").exists():
            benchmarks.append(bench_dir)
    return benchmarks


def find_toolchains(benchmark_dir: Path) -> list[Toolchain]:
    toolchains: list[Toolchain] = []
    for child in sorted(benchmark_dir.iterdir()):
        if not child.is_dir():
            continue
        language = child.name
        
        # Look for runner (run_all.sh)
        runner = child / "run_all.sh"
        if not runner.exists():
            runner = child / "run_all"
        
        # Look for aggregator (generate_results.py)
        aggregator = child / "generate_results.py"

        if runner.exists() and aggregator.exists():
            toolchains.append(Toolchain(language=language, runner=runner, aggregator=aggregator))
    return toolchains

def ensure_results_path(rule: str, language: str) -> Path:
    out_dir = ROOT / "rules" / rule / language
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "RESULTS.md"

def execute_runs(rule: str, language: str, runner: Path, num_runs: int, working_dir: Path) -> Path:
    """Executes the runner N times, collecting output in a temp directory."""
    runs_storage = RUNS_DIR / rule / language
    if runs_storage.exists():
        shutil.rmtree(runs_storage)
    runs_storage.mkdir(parents=True, exist_ok=True)

    print(f"Running {rule}/{language} x{num_runs}...")
    for i in range(1, num_runs + 1):
        run_id = f"run_{i}"
        run_output_dir = runs_storage / run_id
        run_output_dir.mkdir()
        
        print(f"  Iteration {i}/{num_runs}")
        
        cmd = ["bash", str(runner), str(run_output_dir)]
        run_cmd(cmd, cwd=working_dir)
    
    return runs_storage

def aggregate_results(aggregator: Path, input_dir: Path, out_path: Path, working_dir: Path) -> None:
    print(f"Aggregating {input_dir} -> {out_path.relative_to(ROOT)}")
    
    cmd = [
        "python3", str(aggregator),
        "--input-dir", str(input_dir),
        "--output", str(out_path)
    ]
    # We run aggregator in the language dir (working_dir) so it can find weights.json etc.
    run_cmd(cmd, cwd=working_dir)

def process_benchmarks(benchmarks_paths: Iterable[Path], num_runs: int) -> None:
    for bench_path in benchmarks_paths:
        rule = bench_path.name
        toolchains = find_toolchains(bench_path)
        
        if not toolchains:
            print(f"skip: {rule} (no run_all.sh + generate_results.py found)", file=sys.stderr)
            continue
            
        for tc in toolchains:
            # Execute Runs
            runs_dir = execute_runs(rule, tc.language, tc.runner, num_runs, working_dir=bench_path / tc.language)
            
            # Aggregate
            out_path = ensure_results_path(rule, tc.language)
            aggregate_results(tc.aggregator, runs_dir, out_path, working_dir=bench_path / tc.language)

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Regenerate benchmark results.")
    p.add_argument("--base", help="Base commit SHA (for PRs).")
    p.add_argument("--head", help="Head commit SHA (for PRs).")
    p.add_argument("--check", action="store_true", help="Fail if regeneration changes tracked files.")
    p.add_argument("--all", action="store_true", help="Regenerate all benchmarks.")
    p.add_argument("--bench", action="append", help="Regenerate specific benchmark (e.g. 'TDD').")
    p.add_argument("--runs", type=int, default=1, help="Number of iterations per benchmark.")
    args = p.parse_args(argv)

    benchmarks_to_process: list[Path] = [] 
    
    if args.all:
        benchmarks_to_process = list_rule_benchmarks()
    elif args.bench:
        all_benchs = {p.name: p for p in list_rule_benchmarks()}
        for name in args.bench:
            if name in all_benchs:
                benchmarks_to_process.append(all_benchs[name])
            else:
                print(f"Benchmark not found: {name}", file=sys.stderr)
    else:
        base = args.base or os.getenv("BASE_SHA")
        head = args.head or os.getenv("HEAD_SHA")

        if base and head:
            changed_submodules = changed_gitlinks(base, head)
            if "_metrics" in changed_submodules:
                benchmarks_to_process = list_rule_benchmarks()
            else:
                for path_str in sorted(changed_submodules):
                    if path_str.startswith("benchmarks/"):
                        benchmarks_to_process.append(ROOT / path_str)

    if not benchmarks_to_process:
        if not (args.all or args.bench):
            print("No benchmark submodule changes detected. Use --all or --bench to force run.")
    else:
        process_benchmarks(benchmarks_to_process, args.runs)

    if args.check:
        run_cmd(["git", "diff", "--exit-code"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
