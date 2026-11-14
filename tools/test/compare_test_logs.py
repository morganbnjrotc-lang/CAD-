# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compare two run_headless_suites.py logs: which tests disappeared, which got worse.

Usage (from the repo root):
    pixi run python tools/test/compare_test_logs.py BEFORE.log AFTER.log [--allow-missing PREFIX ...]

Use it to show a change is "no worse than baseline": e.g. the slim build against the full build,
or a branch with an upstream merge against main. A test counts as missing if it ran in BEFORE but
not in AFTER; --allow-missing lists test-id prefixes that are expected to go away (tests of a
module the change removes). Exit code 0 only if nothing got worse and nothing unexpected is missing.
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

STARTED = re.compile(r"^\[watchdog\] (\S+)$", re.M)
BROKEN = re.compile(r"^(FAIL|ERROR): (\w+) \(([\w.]+)\)", re.M)
SUMMARY = re.compile(r"STUDIO_SUITE_SUMMARY (.*)")


def parse(path: Path) -> tuple[set[str], set[str], str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    started = set(STARTED.findall(text))
    broken = {test_id for _, _, test_id in BROKEN.findall(text)}
    summary = SUMMARY.findall(text)
    return started, broken, summary[-1] if summary else "NO SUMMARY (run crashed or hung?)"


def group(test_id: str) -> str:
    return test_id.split(".", 1)[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--allow-missing", nargs="*", default=[], metavar="PREFIX")
    args = parser.parse_args()

    before, before_broken, before_summary = parse(args.before)
    after, after_broken, after_summary = parse(args.after)
    print(f"before: {before_summary}\nafter:  {after_summary}\n")

    missing = before - after
    allowed = {t for t in missing if any(t.startswith(p) for p in args.allow_missing)}
    unexpected = sorted(missing - allowed)
    worse = sorted(after_broken - before_broken)
    new = after - before

    print(f"tests in both: {len(before & after)}")
    print(f"missing in after: {len(missing)} ({len(allowed)} expected)")
    for name, count in sorted(Counter(group(t) for t in missing).items()):
        print(f"    {name}: {count}")
    print(f"new in after: {len(new)}")
    print(f"failing/erroring in after but not before: {len(worse)}")
    for test_id in worse:
        print(f"    WORSE: {test_id}")
    for test_id in unexpected:
        print(f"    UNEXPECTEDLY MISSING: {test_id}")

    ok = not worse and not unexpected and "NO SUMMARY" not in after_summary
    print("\nPASS: no worse than before" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
