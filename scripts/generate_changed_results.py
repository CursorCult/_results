#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Generator:
    language: str
    path: Path


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )


def output(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def changed_gitlinks(base: str, head: str) -> set[str]:
    raw = subprocess.check_output(["git", "diff", "--raw", base, head], text=True)
    changed: set[str] = set()
    for line in raw.splitlines():
        # Example:
        # :160000 160000 <old> <new> M\t_metrics
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


def list_benchmark_dirs() -> list[Path]:
    benchmarks_root = ROOT / "benchmarks"
    if not benchmarks_root.is_dir():
        return []
    dirs: list[Path] = []
    for child in sorted(benchmarks_root.iterdir()):
        if not child.is_dir():
            continue
        # Submodules have a .git file inside the directory in a working tree.
        if (child / ".git").exists():
            dirs.append(child)
    return dirs


def find_generators(benchmark_dir: Path) -> list[Generator]:
    generators: list[Generator] = []
    for child in sorted(benchmark_dir.iterdir()):
        if not child.is_dir():
            continue
        language = child.name
        py = child / "generate_results.py"
        sh = child / "generate_results.sh"
        exe = child / "generate_results"
        if py.is_file():
            generators.append(Generator(language=language, path=py))
        elif sh.is_file():
            generators.append(Generator(language=language, path=sh))
        elif exe.is_file():
            generators.append(Generator(language=language, path=exe))
    return generators


def ensure_results_path(rule: str, language: str) -> Path:
    out_dir = ROOT / "rules" / rule / language
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "RESULTS.md"


def run_generator(*, benchmark_dir: Path, generator: Generator, metrics_dir: Path, out_path: Path) -> None:
    env = os.environ.copy()
    env["METRICS_DIR"] = str(metrics_dir)
    env["OUTPUT_PATH"] = str(out_path)
    env["RESULTS_ROOT"] = str(ROOT)

    cmd: list[str]
    if generator.path.suffix == ".py":
        cmd = [
            "python3",
            str(generator.path),
            "--metrics-dir",
            str(metrics_dir),
            "--output",
            str(out_path),
        ]
    elif generator.path.suffix == ".sh":
        cmd = ["bash", str(generator.path)]
    else:
        cmd = [str(generator.path)]

    proc = subprocess.run(cmd, cwd=str(benchmark_dir), env=env, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Generator failed: {generator.path}\n{proc.stderr.strip() or proc.stdout.strip()}"
        )

    if out_path.exists():
        return
    if proc.stdout.strip():
        out_path.write_text(proc.stdout, encoding="utf-8")
        return
    raise RuntimeError(
        f"Generator produced no output file and no stdout: {generator.path}"
    )


def generate_for_benchmarks(benchmarks: Iterable[Path]) -> None:
    metrics_dir = ROOT / "_metrics"
    if not metrics_dir.is_dir():
        raise RuntimeError("Missing _metrics submodule; run `git submodule update --init --recursive`.")

    for bench_dir in benchmarks:
        rule = bench_dir.name
        gens = find_generators(bench_dir)
        if not gens:
            print(f"skip: {rule} (no generate_results.* found)", file=sys.stderr)
            continue
        for gen in gens:
            out_path = ensure_results_path(rule, gen.language)
            print(f"run: {rule}/{gen.language} -> {out_path.relative_to(ROOT)}")
            run_generator(benchmark_dir=bench_dir, generator=gen, metrics_dir=metrics_dir, out_path=out_path)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Regenerate benchmark results.")
    p.add_argument("--base", help="Base commit SHA (for PRs).")
    p.add_argument("--head", help="Head commit SHA (for PRs).")
    p.add_argument("--check", action="store_true", help="Fail if regeneration changes tracked files.")
    p.add_argument("--all", action="store_true", help="Regenerate all benchmarks.")
    p.add_argument("--bench", action="append", help="Regenerate specific benchmark (e.g. 'TDD').")
    args = p.parse_args(argv)

    benchmarks: list[Path] = []
    
    if args.all:
        benchmarks = list_benchmark_dirs()
    elif args.bench:
        all_benchs = {b.name: b for b in list_benchmark_dirs()}
        for name in args.bench:
            if name in all_benchs:
                benchmarks.append(all_benchs[name])
            else:
                print(f"Benchmark not found: {name}", file=sys.stderr)
    else:
        base = args.base or os.getenv("BASE_SHA")
        head = args.head or os.getenv("HEAD_SHA")

        if base and head:
            changed = changed_gitlinks(base, head)
            if "_metrics" in changed:
                benchmarks = list_benchmark_dirs()
            else:
                benchmarks = [ROOT / path for path in sorted(changed) if path.startswith("benchmarks/")]
        else:
            changed = set()

    if not benchmarks:
        if not (args.all or args.bench):
            print("No benchmark submodule changes detected. Use --all or --bench to force run.")
    else:
        generate_for_benchmarks(benchmarks)

    if args.check:
        # Ensure results are committed.
        run(["git", "diff", "--exit-code"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

