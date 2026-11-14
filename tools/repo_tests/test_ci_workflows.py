# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks on this fork's GitHub automation. No FreeCAD build needed.

Run from the repo root:
    pixi run python -m unittest discover -s tools/repo_tests -v

Why: upstream FreeCAD's workflows and Dependabot config ran on every push to this repo, testing
FreeCAD instead of our code. We replaced them with our own workflow (ADR 0005). An upstream
merge can bring them back; these tests catch that before the merge lands.
"""

import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
OUR_WORKFLOWS = {"studio-ci.yml"}
# owner/repo[/path]@<full 40-char commit SHA>: a tag can be moved to point at other code, a SHA can't.
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def load_workflow(name: str) -> dict:
    with open(WORKFLOWS / name, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # YAML 1.1 reads the bare key `on` as the boolean True.
    if True in data:
        data["on"] = data.pop(True)
    return data


def run_commands(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job.get("steps", []))


class WorkflowSetTest(unittest.TestCase):
    def test_only_our_workflows_exist(self):
        found = {p.name for p in WORKFLOWS.iterdir() if p.suffix in (".yml", ".yaml")}
        self.assertEqual(
            sorted(found - OUR_WORKFLOWS),
            [],
            "upstream workflows run on our pushes; delete them (see docs/CORE_PATCHES.md)",
        )
        self.assertEqual(sorted(OUR_WORKFLOWS - found), [], "our workflow file is missing")

    def test_no_upstream_dependabot_config(self):
        self.assertFalse(
            (REPO / ".github" / "dependabot.yml").exists(),
            "upstream's Dependabot config opens daily PRs against FreeCAD's dependencies on our repo",
        )


class StudioCITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wf = load_workflow("studio-ci.yml")
        cls.jobs = cls.wf["jobs"]

    def test_triggers(self):
        on = self.wf["on"]
        self.assertIn("main", on["push"]["branches"])
        for trigger in ("pull_request", "workflow_dispatch", "schedule"):
            self.assertIn(trigger, on)

    def test_token_is_read_only_by_default(self):
        self.assertEqual(self.wf["permissions"], {"contents": "read"})

    def test_every_job_has_a_timeout(self):
        # GitHub's default is 6 hours; a hung FreeCAD test would burn all of it.
        for name, job in self.jobs.items():
            with self.subTest(job=name):
                self.assertIn("timeout-minutes", job)

    def test_actions_are_pinned_to_commit_shas(self):
        for name, job in self.jobs.items():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if uses and not uses.startswith("./"):
                    with self.subTest(job=name, uses=uses):
                        self.assertRegex(uses, PINNED)

    def test_windows_build_runs_studio_checks(self):
        windows = [job for job in self.jobs.values() if str(job.get("runs-on", "")).startswith("windows")]
        self.assertEqual(len(windows), 1, "expected exactly one Windows build job")
        commands = run_commands(windows[0])
        # CI tests what we ship: the slim build (ADR 0006), not upstream's full module set.
        self.assertIn("pixi run configure-slim-release", commands)
        self.assertIn("pixi run build-slim-release", commands)
        for line in commands.splitlines():
            if "--build-dir" in line or "--exe" in line:
                with self.subTest(line=line):
                    self.assertIn("build/slim-release", line)
        self.assertRegex(commands, r"run_headless_suites\.py .*TestStudioApp")
        # Through the isolating runner: a bare `FreeCAD.exe -t` uses the real profile and can
        # stop at the first-run settings-migration dialog, hanging until the job times out.
        self.assertRegex(commands, r"run_gui_suites\.py .*TestStudioGui")
        self.assertNotRegex(commands, r"FreeCAD\.exe.* -t ")
        self.assertIn("startup_smoke.py", commands)

    def test_these_repo_checks_run_in_ci(self):
        commands = "\n".join(run_commands(job) for job in self.jobs.values())
        self.assertIn("tools/repo_tests", commands)


if __name__ == "__main__":
    unittest.main()
