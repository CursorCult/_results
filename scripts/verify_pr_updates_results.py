#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class GitlinkChange:
    path: str


def output(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def changed_gitlinks(base: str, head: str) -> list[GitlinkChange]:
    raw = subprocess.check_output(["git", "diff", "--raw", base, head], text=True)
    changes: list[GitlinkChange] = []
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
            changes.append(GitlinkChange(path=path.strip()))
    return changes


def changed_paths(base: str, head: str) -> set[str]:
    raw = subprocess.check_output(["git", "diff", "--name-only", base, head], text=True)
    return {p.strip() for p in raw.splitlines() if p.strip()}


def main() -> int:
    base = (os.getenv("BASE_SHA") or "").strip()
    head = (os.getenv("HEAD_SHA") or "").strip()
    if not base or not head:
        print("Missing BASE_SHA/HEAD_SHA", file=sys.stderr)
        return 2

    gitlinks = changed_gitlinks(base, head)
    if not gitlinks:
        print("No submodule pointer changes detected.")
        return 0

    changed = changed_paths(base, head)

    failures: list[str] = []

    for gl in gitlinks:
        if gl.path == "_metrics":
            if not any(p.startswith("rules/") and p.endswith("/RESULTS.md") for p in changed):
                failures.append("Changed _metrics submodule but did not update any rules/**/RESULTS.md")
            continue

        if gl.path.startswith("benchmarks/"):
            rule = gl.path.split("/", 1)[1]
            expected_prefix = f"rules/{rule}/"
            if not any(p.startswith(expected_prefix) and p.endswith("/RESULTS.md") for p in changed):
                failures.append(f"Changed {gl.path} submodule but did not update any {expected_prefix}*/RESULTS.md")
            continue

    if failures:
        print("PR must update results when submodule pointers change:", file=sys.stderr)
        for f in failures:
            print(f"- {f}", file=sys.stderr)
        return 1

    print("OK: submodule changes accompanied by RESULTS.md updates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

